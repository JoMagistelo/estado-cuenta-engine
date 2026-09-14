from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Sequence

import pypdfium2 as pdfium
import pytesseract
from PIL import ImageOps
from pytesseract import Output

from readers.models.document_data import DocumentData
from readers.tesseract_pdf_reader import TesseractPDFReader


RESCUE_CONFIGS = (
    "--oem 3 --psm 6 -c preserve_interword_spaces=1",
    "--oem 3 --psm 11",
)


def _normalize(value: Any) -> str:
    text = str(value or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", text.upper()).strip()


def _float(word: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(word.get(key, default))
    except (TypeError, ValueError):
        return default


def _page(word: dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _center_x(word: dict[str, Any]) -> float:
    x0 = _float(word, "x0")
    return (x0 + _float(word, "x1", x0)) / 2.0


def _center_y(word: dict[str, Any]) -> float:
    top = _float(word, "top")
    return (top + _float(word, "bottom", top)) / 2.0


def _find_header(words: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    resumen_words = [word for word in words if "RESUMEN" in _normalize(word.get("text"))]
    saldos_words = [word for word in words if "SALDOS" in _normalize(word.get("text"))]
    candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []

    for resumen in resumen_words:
        for saldos in saldos_words:
            if _page(resumen) != _page(saldos):
                continue
            vertical = abs(_center_y(resumen) - _center_y(saldos))
            gap = _float(saldos, "x0") - _float(resumen, "x1")
            if vertical > 9.0 or not (-5.0 <= gap <= 80.0):
                continue
            if _center_x(resumen) > 320.0:
                continue
            candidates.append((vertical + abs(gap) * 0.05, resumen, saldos))

    if not candidates:
        return None

    _, resumen, saldos = min(candidates, key=lambda item: item[0])
    return resumen, saldos


def _looks_like_amount(word: dict[str, Any]) -> bool:
    text = str(word.get("text", "")).strip()
    if not text or "%" in text:
        return False
    digits = sum(char.isdigit() for char in text)
    return digits >= 2 and bool(re.search(r"[\d.,]", text))


def _existing_amount_count(
    words: Sequence[dict[str, Any]],
    resumen: dict[str, Any],
    saldos: dict[str, Any],
) -> int:
    page = _page(resumen)
    header_y = (_center_y(resumen) + _center_y(saldos)) / 2.0
    header_right = max(_float(resumen, "x1"), _float(saldos, "x1"))
    xmin = header_right + 1.0
    xmax = header_right + 65.0

    return sum(
        1
        for word in words
        if _page(word) == page
        and xmin <= _center_x(word) <= xmax
        and header_y + 10.0 <= _center_y(word) <= header_y + 205.0
        and _looks_like_amount(word)
    )


def _is_duplicate(
    candidate: dict[str, Any],
    existing: Sequence[dict[str, Any]],
) -> bool:
    text = _normalize(candidate.get("text"))
    for word in existing:
        if _page(word) != _page(candidate):
            continue
        if abs(_float(word, "x0") - _float(candidate, "x0")) > 7.0:
            continue
        if abs(_float(word, "top") - _float(candidate, "top")) > 5.0:
            continue
        other = _normalize(word.get("text"))
        if text == other:
            return True
        if (
            abs(_float(word, "x1") - _float(candidate, "x1")) <= 9.0
            and min(len(text), len(other)) >= 3
            and (text in other or other in text)
        ):
            return True
    return False


def _ocr_crop(
    image,
    *,
    page_width: float,
    page_height: float,
    logical_page: int,
    doctop_offset: float,
    resumen: dict[str, Any],
    saldos: dict[str, Any],
    existing: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    header_left = min(_float(resumen, "x0"), _float(saldos, "x0"))
    header_right = max(_float(resumen, "x1"), _float(saldos, "x1"))
    header_top = min(_float(resumen, "top"), _float(saldos, "top"))

    left = max(0.0, header_left - 80.0)
    right = min(page_width * 0.44, header_right + 85.0)
    top = max(0.0, header_top - 8.0)
    bottom = min(page_height, header_top + 210.0)
    if right <= left or bottom <= top:
        return []

    pixel_to_pdf = page_width / image.width
    px0 = max(0, int(left / pixel_to_pdf))
    py0 = max(0, int(top / pixel_to_pdf))
    px1 = min(image.width, int(right / pixel_to_pdf))
    py1 = min(image.height, int(bottom / pixel_to_pdf))
    if px1 <= px0 or py1 <= py0:
        return []

    crop = image.crop((px0, py0, px1, py1))
    collected: list[dict[str, Any]] = []

    for config in RESCUE_CONFIGS:
        try:
            data = pytesseract.image_to_data(
                crop,
                lang=TesseractPDFReader.LANGUAGE,
                config=config,
                output_type=Output.DICT,
                timeout=TesseractPDFReader.TIMEOUT_SECONDS,
            )
        except (RuntimeError, pytesseract.TesseractError):
            continue

        for index, raw_text in enumerate(data.get("text", [])):
            value = str(raw_text or "").strip()
            if not value:
                continue

            x0 = (px0 + float(data["left"][index])) * pixel_to_pdf
            y0 = (py0 + float(data["top"][index])) * pixel_to_pdf
            width = float(data["width"][index]) * pixel_to_pdf
            height = float(data["height"][index]) * pixel_to_pdf
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = -1.0

            word = {
                "text": value,
                "x0": x0,
                "x1": x0 + width,
                "top": y0,
                "bottom": y0 + height,
                "doctop": doctop_offset + y0,
                "width": width,
                "height": height,
                "upright": True,
                "direction": "ltr",
                "page": logical_page,
                "confidence": confidence,
            }

            if _is_duplicate(word, [*existing, *collected]):
                continue
            collected.append(word)

        combined = [*existing, *collected]
        if _existing_amount_count(combined, resumen, saldos) >= 8:
            break

    # No agregamos un segundo OCR que sólo duplique etiquetas. Debe haber
    # recuperado al menos un candidato monetario dentro de la columna real.
    header_right = max(_float(resumen, "x1"), _float(saldos, "x1"))
    value_words = [
        word
        for word in collected
        if header_right + 1.0 <= _center_x(word) <= header_right + 65.0
        and _looks_like_amount(word)
    ]
    return collected if value_words else []


def recover_resumen_saldos_words(document: DocumentData) -> list[dict[str, Any]]:
    """Añade un OCR focalizado sólo para el ``Resumen de Saldos`` de HSBC.

    El OCR general PSM 3 puede reconocer las etiquetas pero omitir importes
    dentro de la tabla con bordes. Cuando el documento proviene de Tesseract,
    se relee únicamente ese rectángulo con PSM 6/11 y se conservan las
    coordenadas PDF. Si el rescate falla, se devuelve intacta la salida original.
    """

    original = list(document.spatial_words or [])
    metadata = dict(document.metadata or {})
    if not original:
        return original
    if not metadata.get("ocr") or str(metadata.get("reader", "")).lower() != "tesseract":
        return original

    header = _find_header(original)
    if header is None:
        return original

    resumen, saldos = header
    if _existing_amount_count(original, resumen, saldos) >= 8:
        return original

    raw_source = metadata.get("source_path")
    if not raw_source:
        return original
    source = Path(str(raw_source)).expanduser()
    if not source.is_file():
        return original

    try:
        TesseractPDFReader._configure_tesseract()
        pdf = pdfium.PdfDocument(str(source))
        logical_page = _page(resumen)
        try:
            start_page = int(metadata.get("start_page", 0) or 0)
        except (TypeError, ValueError):
            start_page = 0
        physical_index = start_page + logical_page - 1
        if physical_index < 0 or physical_index >= len(pdf):
            return original

        page = pdf[physical_index]
        page_width, page_height = page.get_size()
        bitmap = page.render(scale=TesseractPDFReader.RENDER_DPI / 72)
        image = ImageOps.autocontrast(bitmap.to_pil().convert("L"))
        doctop_offset = _float(resumen, "doctop", _float(resumen, "top")) - _float(resumen, "top")

        extra = _ocr_crop(
            image,
            page_width=page_width,
            page_height=page_height,
            logical_page=logical_page,
            doctop_offset=doctop_offset,
            resumen=resumen,
            saldos=saldos,
            existing=original,
        )
    except Exception:
        # Es un rescate best-effort: nunca debe invalidar el OCR principal.
        return original

    return [*original, *extra]
