from __future__ import annotations

from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter


def remove_first_page_if_empty(
    pdf_path: str | Path,
) -> Path:
    """
    Si la primera página del PDF no contiene texto,
    la elimina físicamente del PDF.

    Si la primera página sí contiene texto,
    devuelve el PDF original sin modificar.

    Retorna:
        Path del PDF que debe procesarse posteriormente.
    """

    pdf_path = Path(pdf_path)

    # ============================================================
    # VERIFICAR PRIMERA PÁGINA
    # ============================================================

    with pdfplumber.open(pdf_path) as pdf:

        if not pdf.pages:
            return pdf_path

        first_page = pdf.pages[0]

        text = first_page.extract_text()

    # ============================================================
    # SI HAY TEXTO, NO HACER NADA
    # ============================================================

    if text and text.strip():
        return pdf_path

    # ============================================================
    # PRIMERA PÁGINA SIN TEXTO -> ELIMINARLA
    # ============================================================

    reader = PdfReader(str(pdf_path))

    if len(reader.pages) <= 1:
        return pdf_path

    writer = PdfWriter()

    for page in reader.pages[1:]:
        writer.add_page(page)

    output_path = (
        pdf_path.parent
        / f"{pdf_path.stem}_sin_portada.pdf"
    )

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path