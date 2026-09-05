from __future__ import annotations

import os
from pathlib import Path

import pytest

from readers.tesseract_pdf_reader import TesseractPDFReader


@pytest.mark.integration
def test_tesseract_reader_with_authorized_fixture() -> None:
    """Ejecuta OCR sólo con un PDF local autorizado fuera del repositorio."""
    raw_path = os.getenv("ESTADO_CUENTA_TEST_PDF")
    if not raw_path:
        pytest.skip("Defina ESTADO_CUENTA_TEST_PDF para ejecutar la prueba de integración.")

    pdf_path = Path(raw_path)
    if not pdf_path.is_file():
        pytest.skip(f"No está disponible el PDF de integración: {pdf_path}")

    document = TesseractPDFReader.read(pdf_path)

    assert isinstance(document.spatial_words, list)
    assert document.metadata.get("ocr") is True
