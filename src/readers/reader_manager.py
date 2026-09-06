from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from .paddleocr_pdf_reader import PaddleOCRPDFReader
from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader
from .tesseract_pdf_reader import TesseractPDFReader


class PDFTextStageResult:
    """Resultado de la etapa inicial de lectura de texto."""

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
        """Alias histórico de Tesseract."""
        return ReaderManager.read_ocr_engine(
            file_path,
            engine="tesseract",
            start_page=start_page,
        )

    @staticmethod
    def read_paddle_ocr(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        file_path = Path(file_path)
        document = PaddleOCRPDFReader.read(
            file_path,
            start_page=start_page,
        )
        document.metadata = dict(document.metadata or {})
        document.metadata.setdefault("source_path", str(file_path.resolve()))
        document.metadata.setdefault("reader", "paddleocr")
        document.metadata.setdefault("ocr", True)
        return document

    @staticmethod
    def read_ocr_engine(
        file_path: str | Path,
        engine: str,
        start_page: int = 0,
    ) -> DocumentData:
        """Ejecuta exactamente un motor OCR.

        Esta función no prueba el otro motor. La decisión de fallback pertenece
        al processor y sólo ocurre después de validar el resultado primario.
        """
        file_path = Path(file_path)
        normalized = str(engine or "").strip().lower()

        if normalized in {"paddle", "paddle_ocr"}:
            normalized = "paddleocr"
        elif normalized == "tess":
            normalized = "tesseract"

        if normalized == "tesseract":
            document = TesseractPDFReader.read(
                file_path,
                start_page=start_page,
            )
            document.metadata = dict(document.metadata or {})
            document.metadata["source_path"] = str(file_path.resolve())
            document.metadata.setdefault("reader", "tesseract")
            document.metadata.setdefault("ocr", True)
            return document

        if normalized == "paddleocr":
            return ReaderManager.read_paddle_ocr(
                file_path,
                start_page=start_page,
            )

        raise ValueError(
            f"Motor OCR no soportado: {engine!r}. "
            "Use 'tesseract' o 'paddleocr'."
        )
