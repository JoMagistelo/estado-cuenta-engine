from __future__ import annotations

import os
from pathlib import Path

import pytest

from readers.reader_manager import ReaderManager


@pytest.mark.integration
def test_live_tesseract_and_paddleocr_both_produce_spatial_output():
    configured = os.getenv("ESTADO_CUENTA_TEST_PDF", "").strip()
    if not configured:
        pytest.skip("Define ESTADO_CUENTA_TEST_PDF para ejecutar UAT OCR local.")

    pdf_path = Path(configured).expanduser().resolve()
    if not pdf_path.is_file():
        pytest.skip("ESTADO_CUENTA_TEST_PDF no apunta a un PDF disponible.")

    tesseract = ReaderManager.read_ocr(pdf_path, start_page=0)
    paddle = ReaderManager.read_paddle_ocr(pdf_path, start_page=0)

    assert tesseract.metadata["reader"] == "tesseract"
    assert paddle.metadata["reader"] == "paddleocr"
    assert tesseract.spatial_words
    assert paddle.spatial_words
