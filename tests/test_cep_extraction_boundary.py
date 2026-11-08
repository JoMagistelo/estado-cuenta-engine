"""Ensure CEP never writes to parsers, the engine, or original Excel exports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from cep.queries import CepQuery, batch_texts


ROOT = Path(__file__).resolve().parents[1]


def test_cep_cannot_enrich_parser_or_engine_movements():
    processor = (ROOT / "src/engine/statement_processor.py").read_text(encoding="utf-8")
    bbva = (ROOT / "src/parsers/bbva/extractors/movimientos.py").read_text(encoding="utf-8")
    assert "enrich_missing_spei_fields" not in processor
    assert "utils.spei_metadata" not in processor
    assert "utils.spei_metadata" not in bbva
    assert "extract_clave_rastreo_from_concepto" not in bbva


def test_original_export_uses_pre_cep_writer_and_exporter():
    from exporters.excel import export_batch_excel
    from exporters.excel.workbook_bundle import original_from_results
    import inspect

    original = inspect.getsource(original_from_results)
    assert "export_batch_excel(results" in original
    assert "normalize_workbook" not in original
    assert callable(export_batch_excel)


def test_banxico_txt_is_six_fields_utf8_and_2_to_500_lines():
    queries = [
        CepQuery(
            row=i + 2,
            statement="SYNTHETIC",
            filename="synthetic.xlsx",
            movement=str(i + 1),
            candidate=True,
            direction="ENVIADO",
            operation_date=date(2026, 11, 6),
            tracking=f"SYNTHETIC{i:05d}",
            issuer="40012",
            receiver="40072",
            destination="0123456789",
            value=Decimal("123.45"),
        )
        for i in range(501)
    ]
    batches = batch_texts(queries, adjacent_days=False, today=date(2026, 11, 7))
    assert len(batches) == 2
    count = 0
    for blob in batches.values():
        assert not blob.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in blob
        lines = blob.decode("utf-8").splitlines()
        assert 2 <= len(lines) <= 500
        count += len(lines)
        for line in lines:
            parts = line.split(",")
            assert len(parts) == 6
            assert parts[0] == "2026-11-06"
            assert parts[2:4] == ["40012", "40072"]
            assert parts[4] == "0123456789"
            assert parts[5] == "123.45"
    assert count == 501


def test_original_excel_download_button_remains_in_extraction_tab():
    desktop = (ROOT / "app/main_flet.py").read_text(encoding="utf-8")
    streamlit = (ROOT / "app/main_streamlit.py").read_text(encoding="utf-8")
    assert "content='Generar Excel'" in desktop
    assert "file_name='reporte_estados_de_cuenta.xlsx'" in desktop
    assert "export_batch_excel(snapshot, path)" in desktop
    assert "Descargar Excel original" in streamlit


def test_native_pdf_drop_does_not_disappear_when_explorer_has_focus():
    source = (ROOT / "src/utils/windows_pdf_drop.py").read_text(encoding="utf-8")
    assert "GetForegroundWindow" not in source
    assert "self.visible and self.enabled and u.IsWindowVisible(parent)" in source
