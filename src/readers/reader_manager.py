from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader


class ReaderManager:

    # ========================================================
    # LECTURA ORIGINAL
    # ========================================================

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        """
        Lee un PDF sin modificarlo físicamente.

        start_page:
            Índice físico base 0 desde donde comienza la lectura.

        Ejemplo:

            start_page=0
            -> página física 1 = página lógica 1

            start_page=2
            -> página física 3 = página lógica 1
        """

        file_path = Path(file_path)

        # ====================================================
        # TEXTO DIGITAL
        # ====================================================

        raw_text = PDFTextReader.read(
            file_path,
            start_page=start_page,
        )

        # ====================================================
        # PALABRAS CON COORDENADAS
        # ====================================================

        spatial_words = PDFWordReader.read(
            file_path,
            start_page=start_page,
        )

        # ====================================================
        # DOCUMENT DATA
        # ====================================================

        return DocumentData(
            raw_text=raw_text,
            normalized_text="",
            spatial_words=spatial_words,
            metadata={
                "start_page": start_page,
            },
        )