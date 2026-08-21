from __future__ import annotations

from pathlib import Path

import pdfplumber


def count_initial_empty_pages(
    pdf_path: str | Path,
) -> int:
    """
    Cuenta cuántas páginas iniciales del PDF no contienen texto
    extraíble.

    La función NO modifica el PDF y NO crea ningún archivo.

    Ejemplo:

        página 1 -> sin texto
        página 2 -> sin texto
        página 3 -> contiene texto

    Resultado:

        2

    Si la primera página ya contiene texto:

        0

    Esta función debe utilizarse únicamente después de haber
    determinado que el documento es un PDF digital.

    Para documentos escaneados / imagen no debe utilizarse.
    """

    pdf_path = Path(pdf_path)

    empty_pages = 0

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            text = page.extract_text()

            if text and text.strip():
                break

            empty_pages += 1

    return empty_pages