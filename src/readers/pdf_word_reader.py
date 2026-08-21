from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber


class PDFWordReader:
    """
    Extrae cada palabra del PDF con sus coordenadas.

    El número de página entregado al resto del sistema
    representa la página lógica del documento.

    Ejemplo:

        start_page=0

        física 1 -> página 1
        física 2 -> página 2
        física 3 -> página 3

    Con:

        start_page=2

        física 3 -> página 1
        física 4 -> página 2
        física 5 -> página 3
    """

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> list[dict[str, Any]]:

        file_path = Path(file_path)

        all_words: list[dict[str, Any]] = []

        with pdfplumber.open(file_path) as pdf:

            for physical_page_index, page in enumerate(
                pdf.pages[start_page:],
                start=start_page,
            ):

                words = page.extract_words(
                    keep_blank_chars=False,
                    use_text_flow=True,
                )

                logical_page = (
                    physical_page_index
                    - start_page
                    + 1
                )

                for word in words:

                    word["page"] = logical_page

                    all_words.append(word)

        return all_words