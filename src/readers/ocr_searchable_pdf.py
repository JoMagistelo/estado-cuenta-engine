from __future__ import annotations

import math
import os
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from readers.pdf_word_reader import PDFWordReader


OCR_LAYER_TAG = "EstadoCuentaEngineOCR"
OCR_FONT_BASENAME = "ECFOCRGlyphless"
OCR_FONT_RESOURCE_PREFIX = "ECFOCR"
OCR_COORDINATE_TOLERANCE = 0.15

# PDFMiner/pdfplumber calcula la caja vertical de este CIDFont con estos
# coeficientes. Hacer que Ascent - Descent == 1000 permite utilizar directamente
# la altura OCR como tamaño de fuente y reconstruir top/bottom sin aproximación.
_OCR_FONT_ASCENT = 793
_OCR_FONT_DESCENT = -207


class OCRSearchablePDFError(RuntimeError):
    """No fue posible construir o verificar el PDF con capa OCR."""


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OCRSearchablePDFError("La geometría OCR contiene un valor no numérico.") from exc
    if not math.isfinite(number):
        raise OCRSearchablePDFError("La geometría OCR contiene un valor no finito.")
    return number


def _projectable_words(spatial_words: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza únicamente el contrato mínimo necesario para la proyección.

    No corrige coordenadas ni reconstruye texto. Si el OCR entrega una caja
    inválida, se aborta la generación: modificar silenciosamente una geometría
    defectuosa haría que el PDF descargable y el documento enviado al parser
    dejaran de representar el mismo resultado OCR.
    """
    projected: list[dict[str, Any]] = []
    for position, word in enumerate(spatial_words):
        text = str(word.get("text") or "").strip()
        if not text:
            continue

        try:
            page = int(word.get("page", 1) or 1)
        except (TypeError, ValueError) as exc:
            raise OCRSearchablePDFError(
                f"La palabra OCR #{position + 1} no contiene un número de página válido."
            ) from exc
        if page < 1:
            raise OCRSearchablePDFError(
                f"La palabra OCR #{position + 1} contiene una página fuera de rango."
            )

        x0 = _number(word.get("x0"))
        x1 = _number(word.get("x1"))
        top = _number(word.get("top"))
        bottom = _number(word.get("bottom"))
        if x1 <= x0 or bottom <= top:
            raise OCRSearchablePDFError(
                f"La palabra OCR #{position + 1} contiene una caja espacial inválida."
            )

        projected.append(
            {
                "text": text,
                "page": page,
                "x0": x0,
                "x1": x1,
                "top": top,
                "bottom": bottom,
            }
        )
    return projected


def _character_map(words: Iterable[dict[str, Any]]) -> dict[str, int]:
    characters = {" "}
    for word in words:
        characters.update(str(word["text"]))

    if len(characters) > 65534:
        raise OCRSearchablePDFError(
            "La capa OCR contiene más caracteres Unicode únicos de los que admite "
            "el mapa CID del artefacto PDF."
        )

    return {
        character: cid
        for cid, character in enumerate(sorted(characters, key=ord), start=1)
    }


def _to_unicode_hex(character: str) -> str:
    return character.encode("utf-16-be").hex().upper()


def _build_to_unicode_cmap(character_map: dict[str, int]) -> bytes:
    header = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> def",
        "/CMapName /EstadoCuentaEngineOCR-ToUnicode def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
    ]

    entries = [
        f"<{cid:04X}> <{_to_unicode_hex(character)}>"
        for character, cid in character_map.items()
    ]
    body: list[str] = []
    # Mantener bloques pequeños evita límites de lectores PDF antiguos y hace el
    # CMap completamente determinista sin depender de una fuente externa.
    for start in range(0, len(entries), 100):
        chunk = entries[start : start + 100]
        body.append(f"{len(chunk)} beginbfchar")
        body.extend(chunk)
        body.append("endbfchar")

    footer = [
        "endcmap",
        "CMapName currentdict /CMap defineresource pop",
        "end",
        "end",
    ]
    return ("\n".join([*header, *body, *footer]) + "\n").encode("ascii")


def _build_glyphless_font(writer: PdfWriter, character_map: dict[str, int]):
    """Crea un CIDFont sin glifos visibles y con ToUnicode explícito.

    La capa siempre se pinta con ``Tr=3`` (texto invisible). Por tanto no se
    incorpora ningún archivo de fuente al artefacto: el font sólo define avance,
    métricas y el mapeo Unicode que necesitan los extractores de texto. Esto
    conserva acentos, Ñ y cualquier otro carácter Unicode reconocido por OCR.
    """
    descriptor = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/FontDescriptor"),
            NameObject("/FontName"): NameObject(f"/{OCR_FONT_BASENAME}"),
            NameObject("/Flags"): NumberObject(4),
            NameObject("/FontBBox"): ArrayObject(
                [
                    FloatObject(0),
                    FloatObject(_OCR_FONT_DESCENT),
                    FloatObject(1000),
                    FloatObject(_OCR_FONT_ASCENT),
                ]
            ),
            NameObject("/ItalicAngle"): FloatObject(0),
            NameObject("/Ascent"): FloatObject(_OCR_FONT_ASCENT),
            NameObject("/Descent"): FloatObject(_OCR_FONT_DESCENT),
            NameObject("/CapHeight"): FloatObject(_OCR_FONT_ASCENT),
            NameObject("/StemV"): FloatObject(80),
        }
    )
    descriptor_ref = writer._add_object(descriptor)

    cid_system_info = DictionaryObject(
        {
            NameObject("/Registry"): TextStringObject("Adobe"),
            NameObject("/Ordering"): TextStringObject("Identity"),
            NameObject("/Supplement"): NumberObject(0),
        }
    )
    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType2"),
            NameObject("/BaseFont"): NameObject(f"/{OCR_FONT_BASENAME}"),
            NameObject("/CIDSystemInfo"): cid_system_info,
            NameObject("/FontDescriptor"): descriptor_ref,
            # Todas las unidades avanzan 1000. El ancho real se fija mediante
            # Tz para que x0/x1 de cada palabra coincidan con la caja OCR.
            NameObject("/DW"): NumberObject(1000),
            NameObject("/CIDToGIDMap"): NameObject("/Identity"),
        }
    )
    descendant_ref = writer._add_object(descendant)

    cmap = DecodedStreamObject()
    cmap.set_data(_build_to_unicode_cmap(character_map))
    cmap_ref = writer._add_object(cmap)

    type0_font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject(f"/{OCR_FONT_BASENAME}"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject([descendant_ref]),
            NameObject("/ToUnicode"): cmap_ref,
        }
    )
    return writer._add_object(type0_font)


def _resource_dictionary(page, key: str) -> DictionaryObject:
    name = NameObject(key)
    current = page.get(name)
    if current is None:
        dictionary = DictionaryObject()
        page[name] = dictionary
        return dictionary
    resolved = current.get_object() if hasattr(current, "get_object") else current
    if not isinstance(resolved, DictionaryObject):
        raise OCRSearchablePDFError(f"El PDF contiene un recurso {key} inválido.")
    return resolved


def _install_font(page, font_ref) -> str:
    resources = _resource_dictionary(page, "/Resources")
    fonts = resources.get(NameObject("/Font"))
    if fonts is None:
        font_dictionary = DictionaryObject()
        resources[NameObject("/Font")] = font_dictionary
    else:
        font_dictionary = fonts.get_object() if hasattr(fonts, "get_object") else fonts
        if not isinstance(font_dictionary, DictionaryObject):
            raise OCRSearchablePDFError("El diccionario /Font del PDF es inválido.")

    suffix = 0
    while True:
        resource_name = (
            OCR_FONT_RESOURCE_PREFIX
            if suffix == 0
            else f"{OCR_FONT_RESOURCE_PREFIX}{suffix}"
        )
        pdf_name = NameObject(f"/{resource_name}")
        if pdf_name not in font_dictionary:
            font_dictionary[pdf_name] = font_ref
            return resource_name
        suffix += 1


def _encode_text(text: str, character_map: dict[str, int]) -> str:
    return "".join(f"{character_map[character]:04X}" for character in text)


def _word_commands(
    word: dict[str, Any],
    *,
    page_height: float,
    page_left: float,
    page_bottom: float,
    font_resource: str,
    character_map: dict[str, int],
) -> list[str]:
    text = word["text"]
    x0 = float(word["x0"])
    x1 = float(word["x1"])
    top = float(word["top"])
    bottom = float(word["bottom"])
    width = x1 - x0
    height = bottom - top

    font_size = height
    encoded = _encode_text(text, character_map)
    # DW=1000 => cada CID avanza exactamente ``font_size`` antes de Tz.
    horizontal_scale = width / (len(text) * font_size) * 100.0
    baseline = (
        page_bottom
        + page_height
        - bottom
        - (_OCR_FONT_DESCENT / 1000.0) * font_size
    )
    origin_x = page_left + x0

    space = _encode_text(" ", character_map)
    return [
        "BT",
        f"/{font_resource} {font_size:.8f} Tf",
        "3 Tr",
        f"{horizontal_scale:.10f} Tz",
        f"1 0 0 1 {origin_x:.8f} {baseline:.8f} Tm",
        f"<{encoded}> Tj",
        "ET",
        # Separador explícito de ancho despreciable. Evita que pdfplumber una
        # dos cajas OCR contiguas sin alterar x1/top/bottom de la palabra.
        "BT",
        f"/{font_resource} {font_size:.8f} Tf",
        "3 Tr",
        "0.001 Tz",
        f"1 0 0 1 {page_left + x1:.8f} {baseline:.8f} Tm",
        f"<{space}> Tj",
        "ET",
    ]


def _append_content_stream(writer: PdfWriter, page, data: bytes) -> None:
    stream = DecodedStreamObject()
    stream.set_data(data)
    stream_ref = writer._add_object(stream.flate_encode())

    contents_name = NameObject("/Contents")
    existing = page.get(contents_name)
    if existing is None:
        page[contents_name] = stream_ref
    elif isinstance(existing, ArrayObject):
        existing.append(stream_ref)
    else:
        page[contents_name] = ArrayObject([existing, stream_ref])


def _verify_projection(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    tolerance: float,
) -> None:
    if len(expected) != len(actual):
        raise OCRSearchablePDFError(
            "La verificación de la capa OCR falló: el número de palabras del PDF "
            f"({len(actual)}) no coincide con el OCR ({len(expected)})."
        )

    coordinate_fields = ("x0", "x1", "top", "bottom")
    for position, (source_word, projected_word) in enumerate(zip(expected, actual), start=1):
        if source_word["text"] != str(projected_word.get("text") or ""):
            raise OCRSearchablePDFError(
                "La verificación de la capa OCR falló: el texto de la palabra "
                f"#{position} no sobrevivió íntegramente a la proyección."
            )
        if int(source_word["page"]) != int(projected_word.get("page", 0) or 0):
            raise OCRSearchablePDFError(
                "La verificación de la capa OCR falló: la palabra "
                f"#{position} cambió de página."
            )
        for field in coordinate_fields:
            difference = abs(float(source_word[field]) - float(projected_word[field]))
            if difference > tolerance:
                raise OCRSearchablePDFError(
                    "La verificación de la capa OCR falló: la geometría de la palabra "
                    f"#{position} excede la tolerancia de {tolerance:.2f} puntos PDF."
                )


class OCRSearchablePDFWriter:
    """Incrusta una capa de texto OCR invisible y espacialmente verificable.

    El contenido visual original se conserva. La rotación declarativa de cada
    página se transfiere al contenido antes de añadir la capa, de modo que el
    sistema de coordenadas del PDF generado coincida con el espacio visual usado
    por Tesseract/PaddleOCR. La capa se etiqueta como ``EstadoCuentaEngineOCR``
    para que ``PDFWordReader`` pueda ignorar cualquier texto previo del escaneo.
    """

    @classmethod
    def write(
        cls,
        source_pdf: str | Path,
        spatial_words: Iterable[dict[str, Any]],
        output_pdf: str | Path,
        *,
        verify: bool = True,
        coordinate_tolerance: float = OCR_COORDINATE_TOLERANCE,
    ) -> Path:
        source_path = Path(source_pdf).expanduser().resolve()
        output_path = Path(output_pdf).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"No existe el PDF de origen: {source_path}")

        words = _projectable_words(spatial_words)
        if not words:
            raise OCRSearchablePDFError(
                "El motor OCR no produjo palabras espaciales para incrustar en el PDF."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_name(
            f".{output_path.name}.{uuid.uuid4().hex}.tmp"
        )

        try:
            reader = PdfReader(str(source_path), strict=False)
            writer = PdfWriter()
            writer.clone_document_from_reader(reader)

            max_page = max(int(word["page"]) for word in words)
            if max_page > len(writer.pages):
                raise OCRSearchablePDFError(
                    "La salida OCR hace referencia a una página que no existe en el PDF."
                )

            # El OCR trabaja sobre la orientación visual renderizada. Convertir
            # /Rotate en una transformación real mantiene la apariencia y deja
            # MediaBox/CropBox en el mismo sistema cartesiano de las cajas OCR.
            for page in writer.pages:
                if int(page.rotation or 0) % 360:
                    page.transfer_rotation_to_content()

            character_map = _character_map(words)
            font_ref = _build_glyphless_font(writer, character_map)
            words_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for word in words:
                words_by_page[int(word["page"])].append(word)

            for page_number, page in enumerate(writer.pages, start=1):
                page_words = words_by_page.get(page_number)
                if not page_words:
                    continue

                font_resource = _install_font(page, font_ref)
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
                page_left = float(page.mediabox.left)
                page_bottom = float(page.mediabox.bottom)

                commands = [f"/{OCR_LAYER_TAG} BMC", "q"]
                for word in page_words:
                    # Un margen de cinco puntos tolera redondeos de Crop/MediaBox,
                    # pero detecta transformaciones incompatibles antes del parser.
                    if (
                        word["x0"] < -5.0
                        or word["top"] < -5.0
                        or word["x1"] > page_width + 5.0
                        or word["bottom"] > page_height + 5.0
                    ):
                        raise OCRSearchablePDFError(
                            f"La geometría OCR de la página {page_number} no coincide "
                            "con las dimensiones del PDF de origen."
                        )
                    commands.extend(
                        _word_commands(
                            word,
                            page_height=page_height,
                            page_left=page_left,
                            page_bottom=page_bottom,
                            font_resource=font_resource,
                            character_map=character_map,
                        )
                    )
                commands.extend(["Q", "EMC", ""])
                _append_content_stream(
                    writer,
                    page,
                    "\n".join(commands).encode("ascii"),
                )

            with temporary_path.open("wb") as file_handle:
                writer.write(file_handle)

            if verify:
                projected_words = PDFWordReader.read(
                    temporary_path,
                    start_page=0,
                    layer_tag=OCR_LAYER_TAG,
                )
                _verify_projection(
                    words,
                    projected_words,
                    tolerance=max(float(coordinate_tolerance), 0.0),
                )

            os.replace(temporary_path, output_path)
            return output_path
        except Exception:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
