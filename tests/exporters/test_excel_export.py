from __future__ import annotations

import os
from pathlib import Path

import pytest

from engine.pipeline import process_bank_statements
from exporters.excel.batch_exporter import export_batch_excel


@pytest.mark.integration
def test_excel_export_with_authorized_fixtures(tmp_path: Path) -> None:
    """Exporta un lote real sólo cuando se proporcionan PDFs autorizados."""
    raw_paths = os.getenv("ESTADO_CUENTA_TEST_PDFS", "")
    if not raw_paths.strip():
        pytest.skip("Defina ESTADO_CUENTA_TEST_PDFS para ejecutar la prueba de integración.")

    pdfs = [Path(item.strip()) for item in raw_paths.split(os.pathsep) if item.strip()]
    if not pdfs or any(not path.is_file() for path in pdfs):
        pytest.skip("Los PDFs de integración no están disponibles.")

    results = process_bank_statements(pdfs)
    output_path = export_batch_excel(results, tmp_path / "resultado.xlsx")

    assert output_path.is_file()
    assert output_path.stat().st_size > 0
