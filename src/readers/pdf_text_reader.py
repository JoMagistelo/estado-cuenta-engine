from __future__ import annotations

from pathlib import Path

import pdfplumber


class PDFTextReader:
    """
    Extrae texto digital de un PDF.

    Por diseño, únicamente procesa las primeras MAX_PAGES
    páginas a partir de start_page.

    start_page representa la página física del PDF usando
    índice base 0.

    Ejemplo:

        start_page=0
        -> página física 1

        start_page=2
        -> página física 3
    """

    MAX_PAGES = 5

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> str:
        """
        Extrae texto de las primeras MAX_PAGES páginas,
        comenzando desde start_page.

        No modifica el PDF.
        """

        file_path = Path(file_path)

        pages: list[str] = []

        with pdfplumber.open(file_path) as pdf:

            selected_pages = pdf.pages[
                start_page:
                start_page + PDFTextReader.MAX_PAGES
            ]

            for page in selected_pages:

                text = page.extract_text()

                if text:
                    pages.append(text)

        return "\n".join(pages)