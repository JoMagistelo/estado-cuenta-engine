from __future__ import annotations

import os
from pathlib import Path

import pytest

from engine.pipeline import process_bank_statements


@pytest.mark.integration
def test_process_multiple_batch() -> None:
    """Smoke test opcional para un lote de PDFs autorizado localmente."""
    raw_paths = os.getenv("ESTADO_CUENTA_TEST_PDFS", "")
    if not raw_paths.strip():
        pytest.skip("Defina ESTADO_CUENTA_TEST_PDFS para ejecutar la prueba de integración.")

    pdfs = [Path(item.strip()) for item in raw_paths.split(os.pathsep) if item.strip()]
    missing = [str(path) for path in pdfs if not path.is_file()]
    if missing:
        pytest.skip(f"No están disponibles los PDFs de integración: {missing}")

    results = process_bank_statements(pdfs)

    assert len(results) == len(pdfs)
    assert all(result.file_name for result in results)
    assert all(result.bank_key for result in results)
