from __future__ import annotations

from concurrent.futures import CancelledError
from io import BytesIO
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import pytesseract
from pypdf import PdfReader, PdfWriter

from readers.tesseract_pdf_reader import TesseractPDFReader


class TesseractPDFInjector:
    """Genera una copia searchable de un PDF usando una capa OCR de Tesseract.

    Esta clase no participa todavía en el pipeline principal de parsing. Su primera
    función es permitir validar de forma aislada la hipótesis arquitectónica de
    Estado Cuenta Engine: OCR -> PDF con texto -> PDFWordReader -> parser digital.

    Cada página se renderiza a la misma resolución usada por el reader actual y
    Tesseract produce un PDF que conserva la imagen renderizada con una capa de
    texto seleccionable/invisible. Después se unen las páginas en un único PDF.
    """

    RENDER_DPI = TesseractPDFReader.RENDER_DPI
    LANGUAGE = TesseractPDFReader.LANGUAGE
    TIMEOUT_SECONDS = TesseractPDFReader.TIMEOUT_SECONDS

    @staticmethod
    def _cancel_requested(cancel_event: Any | None) -> bool:
        if cancel_event is None:
            return False
        is_set = getattr(cancel_event, "is_set", None)
        return bool(callable(is_set) and is_set())

    @classmethod
    def generate(
        cls,
        source_pdf: str | Path,
        output_pdf: str | Path,
        *,
        start_page: int = 0,
        cancel_event: Any | None = None,
    ) -> Path:
        source_pdf = Path(source_pdf)
        output_pdf = Path(output_pdf)

        if not source_pdf.is_file():
            raise FileNotFoundError(f"No existe el PDF: {source_pdf}")
        if source_pdf.resolve() == output_pdf.resolve():
            raise ValueError("El PDF OCR debe guardarse en una ruta distinta al original.")
        if cls._cancel_requested(cancel_event):
            raise CancelledError()

        # Reutilizamos exactamente la resolución de Tesseract instalada/bundled
        # que ya valida Estado Cuenta Engine. No se introduce otra dependencia de
        # sistema ni una segunda búsqueda de tessdata.
        TesseractPDFReader._configure_tesseract()

        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_pdf.with_name(f".{output_pdf.name}.tmp")
        writer = PdfWriter()
        source = pdfium.PdfDocument(str(source_pdf))

        config = f"{TesseractPDFReader.CONFIG} --dpi {cls.RENDER_DPI}"

        try:
            for physical_index in range(start_page, len(source)):
                if cls._cancel_requested(cancel_event):
                    raise CancelledError()

                page = source[physical_index]
                bitmap = page.render(scale=cls.RENDER_DPI / 72.0)
                image = bitmap.to_pil().convert("RGB")

                page_pdf = pytesseract.image_to_pdf_or_hocr(
                    image,
                    extension="pdf",
                    lang=cls.LANGUAGE,
                    config=config,
                    timeout=cls.TIMEOUT_SECONDS,
                )
                page_reader = PdfReader(BytesIO(page_pdf))
                for searchable_page in page_reader.pages:
                    writer.add_page(searchable_page)

            if len(writer.pages) == 0:
                raise RuntimeError("Tesseract no generó páginas para el PDF OCR.")

            with temporary_path.open("wb") as output_handle:
                writer.write(output_handle)

            temporary_path.replace(output_pdf)
            return output_pdf
        finally:
            try:
                source.close()
            except Exception:
                pass
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
