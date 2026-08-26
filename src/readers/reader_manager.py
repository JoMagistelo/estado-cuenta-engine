from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader
from .tesseract_pdf_reader import TesseractPDFReader


# ============================================================
# RESULTADO DE LA PRIMERA ETAPA
# ============================================================


class PDFTextStageResult:
    """
    Resultado de la primera etapa de lectura.

    Contiene:

        document
            -> DocumentData con raw_text pero todavía sin
               spatial_words.

        initial_empty_pages
            -> páginas iniciales sin texto.

        has_extractable_text
            -> indica si existe texto extraíble.
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


# ============================================================
# READER MANAGER
# ============================================================


class ReaderManager:

    # ========================================================
    # LECTURA COMPLETA
    # ========================================================

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """
        Lee texto y palabras espaciales.

        Esta función conserva el comportamiento original
        de ReaderManager.read().
        """

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
            metadata={
                "start_page": start_page,
            },
        )

    # ========================================================
    # PRIMERA ETAPA: SOLO TEXTO
    # ========================================================

    @staticmethod
    def read_text_stage(
        file_path: str | Path,
        start_page: int = 0,
    ) -> PDFTextStageResult:
        """
        Primera etapa del pipeline.

        Lee únicamente texto.

        NO ejecuta PDFWordReader.

        Esta operación permite decidir posteriormente si
        el documento debe tratarse como:

            - PDF digital
            - PDF con extracción sospechosa
            - PDF imagen / OCR
        """

        file_path = Path(file_path)

        result = PDFTextReader.read_stage(
            file_path,
            start_page=start_page,
        )

        document = DocumentData(
            raw_text=result.raw_text,
            normalized_text="",
            spatial_words=[],
            metadata={
                "start_page": start_page,
            },
        )

        return PDFTextStageResult(
            document=document,
            initial_empty_pages=result.initial_empty_pages,
            has_extractable_text=result.has_extractable_text,
        )

    # ========================================================
    # SOLO PALABRAS ESPACIALES
    # ========================================================

    @staticmethod
    def read_spatial_words(
        file_path: str | Path,
        start_page: int = 0,
    ) -> list[dict]:
        """
        Extrae únicamente las palabras espaciales.

        No ejecuta PDFTextReader.

        Esta es la lectura principal utilizada por los parsers
        de documentos digitales.
        """

        file_path = Path(file_path)

        return PDFWordReader.read(
            file_path,
            start_page=start_page,
        )

    # ========================================================
    # OCR
    # ========================================================

    @staticmethod
    def read_ocr(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """
        Procesa el PDF mediante Tesseract OCR.
        """

        file_path = Path(file_path)

        return TesseractPDFReader.read(
            file_path,
            start_page=start_page,
        )