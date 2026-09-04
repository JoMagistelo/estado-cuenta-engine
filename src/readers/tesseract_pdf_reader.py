from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output

from readers.models import DocumentData


class TesseractPDFReader:
    """
    Convierte un PDF a DocumentData mediante Tesseract OCR.

    Busca automáticamente Tesseract en:

    1. TESSERACT_CMD
    2. vendor/tesseract/tesseract.exe del proyecto
    3. vendor/tesseract/tesseract.exe del ejecutable empaquetado
    4. tesseract/tesseract.exe junto al ejecutable
    5. PATH del sistema

    Estructura esperada:

        estado-cuenta-engine/
        ├── vendor/
        │   └── tesseract/
        │       ├── tesseract.exe
        │       ├── *.dll
        │       └── tessdata/
        │           ├── spa.traineddata
        │           ├── eng.traineddata
        │           └── osd.traineddata
        ├── src/
        └── app/
    """

    # ============================================================
    # CONFIGURACIÓN
    # ============================================================

    MAX_TEXT_PAGES = 5

    RENDER_DPI = 300

    LANGUAGE = "spa"

    CONFIG = "--oem 3 --psm 3"

    TIMEOUT_SECONDS = 90

    REQUIRED_LANGUAGES = (
        "spa.traineddata",
    )

    # ============================================================
    # LECTURA PRINCIPAL
    # ============================================================

    @classmethod
    def read(
        cls,
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:

        file_path = Path(file_path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"No existe el PDF: {file_path}"
            )

        # --------------------------------------------------------
        # CONFIGURAR TESSERACT
        # --------------------------------------------------------

        tesseract_cmd, tessdata_dir = (
            cls._configure_tesseract()
        )

        # --------------------------------------------------------
        # ABRIR PDF
        # --------------------------------------------------------

        pdf = pdfium.PdfDocument(
            str(file_path)
        )

        all_words: list[dict[str, Any]] = []

        text_pages: list[str] = []

        doctop_offset = 0.0

        # --------------------------------------------------------
        # PROCESAR PÁGINAS
        # --------------------------------------------------------

        for physical_index in range(
            start_page,
            len(pdf),
        ):

            page = pdf[physical_index]

            page_width, page_height = (
                page.get_size()
            )

            bitmap = page.render(
                scale=cls.RENDER_DPI / 72
            )

            image = cls._preprocess(
                bitmap.to_pil()
            )

            logical_page = (
                physical_index
                - start_page
                + 1
            )

            words, page_text = cls._read_page(
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                tessdata_dir=tessdata_dir,
            )

            # Todas las palabras.
            all_words.extend(words)

            # Solo las primeras 5 páginas para
            # el texto usado por detección.
            if logical_page <= cls.MAX_TEXT_PAGES:
                text_pages.append(page_text)

            doctop_offset += page_height

        # --------------------------------------------------------
        # RESULTADO
        # --------------------------------------------------------

        return DocumentData(
            raw_text="\n".join(text_pages),
            normalized_text="",
            spatial_words=all_words,
            metadata={
                "start_page": start_page,
                "reader": "tesseract",
                "ocr": True,
                "dpi": cls.RENDER_DPI,
                "language": cls.LANGUAGE,
                "tesseract_cmd": str(
                    tesseract_cmd
                ),
                "tessdata_dir": str(
                    tessdata_dir
                ),
            },
        )

    # ============================================================
    # CONFIGURACIÓN TESSERACT
    # ============================================================

    @classmethod
    def _configure_tesseract(
        cls,
    ) -> tuple[Path, Path]:

        # --------------------------------------------------------
        # ENCONTRAR EJECUTABLE
        # --------------------------------------------------------

        tesseract_cmd = cls._find_tesseract()

        if tesseract_cmd is None:
            raise RuntimeError(
                "No se encontró Tesseract.\n\n"
                "Se esperaba en:\n"
                "  vendor/tesseract/tesseract.exe\n\n"
                "También puedes definir:\n"
                "  TESSERACT_CMD"
            )

        # --------------------------------------------------------
        # ENCONTRAR TESSDATA
        # --------------------------------------------------------

        tessdata_dir = cls._find_tessdata(
            tesseract_cmd
        )

        if tessdata_dir is None:
            raise RuntimeError(
                "No se encontró la carpeta tessdata.\n\n"
                f"Tesseract encontrado en:\n"
                f"  {tesseract_cmd}\n\n"
                "Debe existir:\n"
                "  tessdata/spa.traineddata\n"
                "  tessdata/eng.traineddata\n"
                "  tessdata/osd.traineddata"
            )

        # --------------------------------------------------------
        # VERIFICAR IDIOMAS
        # --------------------------------------------------------

        missing = [
            language_file
            for language_file in cls.REQUIRED_LANGUAGES
            if not (
                tessdata_dir / language_file
            ).is_file()
        ]

        if missing:
            raise RuntimeError(
                "Faltan archivos de idioma de Tesseract:\n"
                + "\n".join(
                    f"  - {name}"
                    for name in missing
                )
                + "\n\n"
                f"Directorio encontrado:\n"
                f"  {tessdata_dir}"
            )

        # --------------------------------------------------------
        # CONFIGURAR PYTESSERACT
        # --------------------------------------------------------

        pytesseract.pytesseract.tesseract_cmd = (
            str(tesseract_cmd)
        )

        # --------------------------------------------------------
        # DLLs DE TESSERACT
        # --------------------------------------------------------

        tesseract_dir = str(
            tesseract_cmd.parent
        )

        current_path = os.environ.get(
            "PATH",
            ""
        )

        path_entries = current_path.split(
            os.pathsep
        )

        if tesseract_dir not in path_entries:

            if current_path:
                os.environ["PATH"] = (
                    tesseract_dir
                    + os.pathsep
                    + current_path
                )
            else:
                os.environ["PATH"] = (
                    tesseract_dir
                )

        # --------------------------------------------------------
        # TESSDATA_PREFIX
        # --------------------------------------------------------
        #
        # Dejamos que Tesseract encuentre directamente
        # la carpeta donde están spa/eng/osd.
        #
        # Esto evita depender de un --tessdata-dir
        # con comillas dentro de pytesseract.
        # --------------------------------------------------------

        os.environ["TESSDATA_PREFIX"] = str(
            tessdata_dir
        )

        return (
            tesseract_cmd,
            tessdata_dir,
        )

    # ============================================================
    # BUSCAR TESSERACT
    # ============================================================

    @classmethod
    def _find_tesseract(
        cls,
    ) -> Path | None:

        candidates: list[Path] = []

        # --------------------------------------------------------
        # 1. TESSERACT_CMD
        # --------------------------------------------------------

        configured = os.getenv(
            "TESSERACT_CMD"
        )

        if configured:

            configured_path = Path(
                configured.strip('"')
                .strip("'")
            ).expanduser()

            if not configured_path.is_absolute():

                configured_path = (
                    Path.cwd()
                    / configured_path
                )

            candidates.append(
                configured_path
            )

        # --------------------------------------------------------
        # 2. PYINSTALLER / FLET
        # --------------------------------------------------------

        meipass = getattr(
            sys,
            "_MEIPASS",
            None,
        )

        if meipass:

            packaged_root = Path(
                meipass
            )

            candidates.append(
                packaged_root
                / "vendor"
                / "tesseract"
                / "tesseract.exe"
            )

            candidates.append(
                packaged_root
                / "tesseract"
                / "tesseract.exe"
            )

        # --------------------------------------------------------
        # 3. JUNTO AL EJECUTABLE
        # --------------------------------------------------------

        executable_dir = (
            Path(sys.executable)
            .resolve()
            .parent
        )

        candidates.append(
            executable_dir
            / "vendor"
            / "tesseract"
            / "tesseract.exe"
        )

        candidates.append(
            executable_dir
            / "tesseract"
            / "tesseract.exe"
        )

        # --------------------------------------------------------
        # 4. RAÍZ DEL PROYECTO
        # --------------------------------------------------------

        try:

            project_root = (
                Path(__file__)
                .resolve()
                .parents[2]
            )

            candidates.append(
                project_root
                / "vendor"
                / "tesseract"
                / "tesseract.exe"
            )

        except IndexError:

            pass

        # --------------------------------------------------------
        # 5. DIRECTORIO ACTUAL
        # --------------------------------------------------------

        candidates.append(
            Path.cwd()
            / "vendor"
            / "tesseract"
            / "tesseract.exe"
        )

        # --------------------------------------------------------
        # 6. PATH
        # --------------------------------------------------------

        path_tesseract = shutil.which(
            "tesseract"
        )

        if path_tesseract:

            candidates.append(
                Path(path_tesseract)
            )

        # --------------------------------------------------------
        # RESOLVER
        # --------------------------------------------------------

        seen: set[Path] = set()

        for candidate in candidates:

            try:

                candidate = (
                    candidate.resolve()
                )

            except OSError:

                continue

            if candidate in seen:
                continue

            seen.add(candidate)

            if candidate.is_file():

                return candidate

        return None

    # ============================================================
    # BUSCAR TESSDATA
    # ============================================================

    @classmethod
    def _find_tessdata(
        cls,
        tesseract_cmd: Path,
    ) -> Path | None:

        candidates: list[Path] = []

        # --------------------------------------------------------
        # 1. TESSDATA_DIR
        # --------------------------------------------------------

        configured = os.getenv(
            "TESSDATA_DIR"
        )

        if configured:

            configured_path = Path(
                configured.strip('"')
                .strip("'")
            ).expanduser()

            if not configured_path.is_absolute():

                configured_path = (
                    Path.cwd()
                    / configured_path
                )

            candidates.append(
                configured_path
            )

        # --------------------------------------------------------
        # 2. JUNTO A TESSERACT
        # --------------------------------------------------------

        candidates.append(
            tesseract_cmd.parent
            / "tessdata"
        )

        # --------------------------------------------------------
        # 3. UN NIVEL ARRIBA
        # --------------------------------------------------------

        candidates.append(
            tesseract_cmd.parent.parent
            / "tessdata"
        )

        # --------------------------------------------------------
        # RESOLVER
        # --------------------------------------------------------

        seen: set[Path] = set()

        for candidate in candidates:

            try:

                candidate = (
                    candidate.resolve()
                )

            except OSError:

                continue

            if candidate in seen:
                continue

            seen.add(candidate)

            if candidate.is_dir():

                return candidate

        return None

    # ============================================================
    # PREPROCESAMIENTO
    # ============================================================

    @classmethod
    def _preprocess(
        cls,
        image: Image.Image,
    ) -> Image.Image:

        # Conservador.
        # Tesseract realiza su propia binarización.

        return ImageOps.autocontrast(
            image.convert("L")
        )

    # ============================================================
    # LEER UNA PÁGINA
    # ============================================================

    @classmethod
    def _read_page(
        cls,
        image: Image.Image,
        logical_page: int,
        page_width: float,
        doctop_offset: float,
        tessdata_dir: Path,
    ) -> tuple[
        list[dict[str, Any]],
        str,
    ]:

        # --------------------------------------------------------
        # CONFIG TESSERACT
        # --------------------------------------------------------
        #
        # IMPORTANTE:
        #
        # NO hacemos:
        #
        # --tessdata-dir "C:\...\tessdata"
        #
        # porque en Windows/pytesseract la combinación
        # de comillas puede terminar llegando incorrectamente
        # a Tesseract.
        #
        # TESSDATA_PREFIX ya fue configurado en
        # _configure_tesseract().
        # --------------------------------------------------------

        config = cls.CONFIG

        # --------------------------------------------------------
        # OCR
        # --------------------------------------------------------

        try:
            data = pytesseract.image_to_data(
                image,
                lang=cls.LANGUAGE,
                config=config,
                output_type=Output.DICT,
                timeout=cls.TIMEOUT_SECONDS,
            )
        except RuntimeError as e:
            if 'timeout' in str(e).lower():
                return [], ""
            raise e

        # --------------------------------------------------------
        # CONVERSIÓN PIXEL -> PDF
        # --------------------------------------------------------

        image_width, _ = image.size

        pixel_to_pdf = (
            page_width
            / image_width
        )

        words: list[
            dict[str, Any]
        ] = []

        lines: dict[
            tuple[int, int, int],
            list[str],
        ] = {}

        # --------------------------------------------------------
        # PALABRAS
        # --------------------------------------------------------

        for index, raw_text in enumerate(
            data["text"]
        ):

            text = raw_text.strip()

            if not text:
                continue

            x0 = (
                float(data["left"][index])
                * pixel_to_pdf
            )

            top = (
                float(data["top"][index])
                * pixel_to_pdf
            )

            width = (
                float(data["width"][index])
                * pixel_to_pdf
            )

            height = (
                float(data["height"][index])
                * pixel_to_pdf
            )

            try:

                confidence = float(
                    data["conf"][index]
                )

            except (
                ValueError,
                TypeError,
            ):

                confidence = -1.0

            words.append(
                {
                    "text": text,
                    "x0": x0,
                    "x1": x0 + width,
                    "top": top,
                    "bottom": top + height,
                    "doctop": (
                        doctop_offset
                        + top
                    ),
                    "width": width,
                    "height": height,
                    "upright": True,
                    "direction": "ltr",
                    "page": logical_page,
                    "confidence": confidence,
                }
            )

            # ----------------------------------------------------
            # AGRUPACIÓN POR LÍNEA
            # ----------------------------------------------------

            line_key = (
                int(
                    data["block_num"][index]
                ),
                int(
                    data["par_num"][index]
                ),
                int(
                    data["line_num"][index]
                ),
            )

            lines.setdefault(
                line_key,
                [],
            ).append(text)

        # --------------------------------------------------------
        # TEXTO DE LA PÁGINA
        # --------------------------------------------------------

        page_text = "\n".join(
            " ".join(line_words)
            for line_words in lines.values()
        )

        return (
            words,
            page_text,
        )