from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from parsers.bbva.utils.pdf_preprocessor import remove_first_page_if_empty

from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader


class ReaderManager:
    @staticmethod
    def read(file_path: str | Path) -> DocumentData:

        # ========================================================
        # PREPROCESAR PDF
        # ========================================================
        #
        # Si la primera página no contiene texto,
        # se elimina antes de cualquier lectura.
        #
        file_path = remove_first_page_if_empty(file_path)

        # ========================================================
        # TEXTO DIGITAL
        # ========================================================

        raw_text = PDFTextReader.read(file_path)

        # ========================================================
        # PALABRAS CON COORDENADAS
        # ========================================================

        spatial_words = PDFWordReader.read(file_path)

        # ========================================================
        # DOCUMENT DATA
        # ========================================================

        return DocumentData(
            raw_text=raw_text,
            normalized_text="",
            spatial_words=spatial_words,
            metadata={},
        )