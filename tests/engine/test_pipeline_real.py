from __future__ import annotations

import os
from pathlib import Path

import pytest

from engine.pipeline import process_bank_statements


@pytest.mark.integration
def test_pipeline_real_pdf() -> None:
    """Smoke test opcional contra un PDF autorizado fuera del repositorio."""
    raw_path = os.getenv("ESTADO_CUENTA_TEST_PDF")
    if not raw_path:
        pytest.skip("Defina ESTADO_CUENTA_TEST_PDF para ejecutar la prueba de integración.")

    pdf_path = Path(raw_path)
    if not pdf_path.is_file():
        pytest.skip(f"No está disponible el PDF de integración: {pdf_path}")

    results = process_bank_statements([pdf_path])

    assert len(results) == 1
    result = results[0]
    assert result.file_name
    assert result.bank_key
    assert result.estado_cuenta is not None
