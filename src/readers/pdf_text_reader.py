from __future__ import annotations

from pathlib import Path

import pdfplumber


class PDFTextReader:
    """
    Extrae texto digital de las primeras páginas de un PDF.

    Por diseño, únicamente lee las primeras 2 páginas porque
    actualmente la CLABE necesaria para la detección bancaria
    se encuentra siempre al inicio del estado de cuenta.

    Devuelve un único string con las páginas concatenadas.
    """

    MAX_PAGES = 5

    @staticmethod
    def read(file_path: str | Path) -> str:
        """
        Extrae texto de las primeras 2 páginas del PDF.

        No procesa el resto del documento.
        """

        file_path = Path(file_path)

        pages: list[str] = []

        with pdfplumber.open(file_path) as pdf:

            for page in pdf.pages[:PDFTextReader.MAX_PAGES]:

                text = page.extract_text()

                if text:
                    pages.append(text)

        return "\n".join(pages)