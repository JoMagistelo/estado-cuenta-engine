from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber


class PDFWordReader:
    """
    Extrae cada palabra del PDF con sus coordenadas.
    No realiza ninguna transformación específica del banco.
    """

    @staticmethod
    def read(file_path: str | Path) -> list[dict[str, Any]]:
        file_path = Path(file_path)

        all_words = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):

                words = page.extract_words(
                    keep_blank_chars=False,
                    use_text_flow=True
                )

                for word in words:
                    word["page"] = page_num + 1
                    all_words.append(word)

        return all_words