"""
Reader especializado en extracción de texto.

Toda extracción textual del sistema
debe pasar por esta clase.

Ningún parser debe utilizar
pdfplumber directamente.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber


class PDFTextReader:
    """
    Extrae texto de un PDF.

    Devuelve un único string con todas
    las páginas concatenadas.
    """

    @staticmethod
    def read(
        file_path: str | Path
    ) -> str:

        file_path = Path(file_path)

        pages = []

        with pdfplumber.open(file_path) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if text:

                    pages.append(text)

        return "\n".join(
            pages
        )