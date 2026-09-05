from __future__ import annotations

import os
from pathlib import Path

import pytest

from readers.pdf_word_reader import PDFWordReader


@pytest.mark.integration
def test_pdf_word_reader_with_authorized_fixture() -> None:
    """Ejecuta el reader espacial sólo con un PDF local autorizado."""
    raw_path = os.getenv("ESTADO_CUENTA_TEST_PDF")
    if not raw_path:
        pytest.skip("Defina ESTADO_CUENTA_TEST_PDF para ejecutar la prueba de integración.")

    pdf_path = Path(raw_path)
    if not pdf_path.is_file():
        pytest.skip(f"No está disponible el PDF de integración: {pdf_path}")

    spatial_words = PDFWordReader.read(pdf_path)

    assert isinstance(spatial_words, list)
    assert all(isinstance(word, dict) for word in spatial_words)
