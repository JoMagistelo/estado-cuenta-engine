from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from .paddleocr_pdf_reader import PaddleOCRPDFReader
from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader
from .tesseract_pdf_reader import TesseractPDFReader


class PDFTextStageResult:
    """Resultado de la etapa inicial de lectura de texto.

    `document` contiene `raw_text` y todavía no incluye palabras espaciales.
    `initial_empty_pages` indica cuántas páginas iniciales no aportaron texto y
    `has_extractable_text` permite al pipeline decidir si requiere OCR.
    """

    __slots__ = (
        "document",
        "initial_empty_pages",
        "has_extractable_text",
    )

    def __init__(
        self,
        document: DocumentData,
        initial_empty_pages: int,
        has_extractable_text: bool,
    ) -> None:
        self.document = document
        self.initial_empty_pages = initial_empty_pages
        self.has_extractable_text = has_extractable_text


class ReaderManager:
    """Fachada de lectura digital y OCR utilizada por el pipeline."""

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """Lee texto y palabras espaciales desde `start_page`."""
        file_path = Path(file_path)

        raw_text = PDFTextReader.read(
            file_path,
            start_page=start_page,
        )
        spatial_words = PDFWordReader.read(
            file_path,
            start_page=start_page,
        )

        return DocumentData(
            raw_text=raw_text,
            normalized_text="",
            spatial_words=spatial_words,
            metadata={"start_page": start_page},
        )

    @staticmethod
    def read_text_stage(
        file_path: str | Path,
        start_page: int = 0,
    ) -> PDFTextStageResult:
        """Lee sólo texto para clasificar el documento antes del reader espacial."""
        file_path = Path(file_path)
        result = PDFTextReader.read_stage(
            file_path,
            start_page=start_page,
        )

        document = DocumentData(
            raw_text=result.raw_text,
            normalized_text="",
            spatial_words=[],
            metadata={"start_page": start_page},
        )

        return PDFTextStageResult(
            document=document,
            initial_empty_pages=result.initial_empty_pages,
            has_extractable_text=result.has_extractable_text,
        )

    @staticmethod
    def read_spatial_words(
        file_path: str | Path,
        start_page: int = 0,
    ) -> list[dict]:
        """Extrae únicamente palabras y coordenadas para parsers digitales."""
        file_path = Path(file_path)
        return PDFWordReader.read(
            file_path,
            start_page=start_page,
        )

    @staticmethod
    def read_ocr(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """Procesa el PDF con Tesseract, OCR primario del engine."""
        file_path = Path(file_path)
        document = TesseractPDFReader.read(
            file_path,
            start_page=start_page,
        )
        document.metadata["source_path"] = str(file_path.resolve())
        return document

    @staticmethod
    def read_paddle_ocr(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """Procesa el PDF con PaddleOCR como fallback local controlado."""
        file_path = Path(file_path)
        return PaddleOCRPDFReader.read(
            file_path,
            start_page=start_page,
        )
