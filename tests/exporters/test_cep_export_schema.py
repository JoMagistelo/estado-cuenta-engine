"""Freeze the user-facing workbook, independently of internal recovery fields."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from cep.columns import CEP_COLUMNS, TRACE_COLUMNS, TXT_COLUMNS
from cep.evidence import CepEvidence, match_evidence
from cep.package import append_cep, export_cep_zip
from cep.queries import queries_from_workbook
from exporters.excel.cells import get, put_columns, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle, verify_pair

from test_normalized_cep_workflow import excel, rows, xml_cep, zipped
from test_spei_catalog_normalization import KEY, OTHER, source


# Original v5/v6 movement contract, not a generated list of recovery fields.
ENGINE_HEADERS = [
    "id_estado", "Nombre del Archivo", "Banco", "Fecha de Corte", "Número de Cuenta",
    "No. de Movimiento", "Fecha de Operación", "Fecha de Liquidación", "Concepto",
    "Tipo de Operación", "Cargo", "Abono", "Saldo de Operación", "Saldo de liquidacion",
    "Referencia", "Clave de Rastreo", "Autorizacion", "Beneficiario",
    "Cuenta del Beneficiario", "CLABE del Beneficiario", "RFC", "Sucursal", "Caja",
    "Hora de Operación", "Concepto Original",
]
REMOVED = [
    "Banco del Beneficiario", "Código Banco Beneficiario", "Código Plaza/Producto CLABE",
    "Banco Emisor", "Banco Receptor", "Cuenta del Ordenante", "CLABE del Ordenante",
    "Revisión Normalización", "Clasificación SPEI", "Referencia SPEI", "Referencia Original",
    "Origen Datos Titular",
]


def canonical_source():
    raw, own = source("banamex", f"PAGO INTERBANCARIO A BANORTE CTA.BENEFICIARIO {OTHER} RASTREO: {KEY} REF:0000007")
    movement = {h: get(rows(raw)[0], h) for h in ENGINE_HEADERS}
    accounts = [{k: v for k, v in row.items() if k != "_row"}
                for row in rows(raw, "Datos de la Cuenta")]
    return excel(accounts, [movement]), own


def serialized(wb):
    stream = BytesIO()
    wb.save(stream)
    wb.close()
    return stream.getvalue()


def assert_clean_schema(content, expected):
    wb = load_workbook(BytesIO(content))
    try:
        assert "Clasificador SPEI" not in wb
        assert "Catálogo Bancos" in wb
        ws = wb["Movimientos"]
        headers = [cell.value for cell in ws[1]]
        assert headers == expected
        assert not set(headers) & set(REMOVED)
        assert len(headers) == len(set(headers))
        start = headers.index(TXT_COLUMNS[0])
        assert headers[start:start + 6] == list(TXT_COLUMNS)
        for cell in ws[1]:
            color = "00156082" if cell.value in TXT_COLUMNS else "00F4B183" if cell.value in CEP_COLUMNS else "001F4D3A"
            assert cell.fill.fgColor.rgb == color
            if cell.value in TRACE_COLUMNS:
                assert ws.column_dimensions[get_column_letter(cell.column)].hidden
        assert get(rows_from_sheet(ws)[0], "Tipo de Operación") == "SPEI Enviado"
    finally:
        wb.close()


def test_exact_schema_survives_normalization_both_crossed_files_and_reload(tmp_path):
    original, own = canonical_source()
    bundle = WorkbookBundle.from_excel(original)
    normalized_headers = ENGINE_HEADERS[:4] + ["CLABE Titular"] + ENGINE_HEADERS[4:] + list(TRACE_COLUMNS) + list(TXT_COLUMNS)
    assert_clean_schema(bundle.improved, normalized_headers)
    assert bundle.original == original
    queries = queries_from_workbook(bundle.improved)
    assert queries[0].ready
    evidence = CepEvidence()
    official = xml_cep(tracking=KEY, destination=OTHER, origin=own).replace(b'bancoEmisor="40012"', b'bancoEmisor="40002"')
    evidence.add_zip(zipped(official))
    path = tmp_path / "synthetic.zip"
    assert export_cep_zip(bundle, queries, evidence, path) == {"EXITO": 1}
    with ZipFile(path) as archive:
        for name, expected in [
            ("excel_original_con_CEP.xlsx", ENGINE_HEADERS + list(TXT_COLUMNS) + list(CEP_COLUMNS)),
            ("excel_mejorado_con_CEP.xlsx", normalized_headers + list(CEP_COLUMNS)),
        ]:
            content = archive.read(name)
            assert_clean_schema(content, expected)
            uploaded = WorkbookBundle.from_uploaded(content)
            assert uploaded.original == content
            assert queries_from_workbook(uploaded.improved)[0].line() == queries[0].line()


@pytest.mark.parametrize("action", ["normalize", "cross"])
def test_pr97_columns_and_classifier_sheet_are_removed_without_losing_blue_edits(action):
    original, _ = canonical_source()
    prepared = WorkbookBundle.from_excel(original).improved
    wb = load_workbook(BytesIO(prepared))
    ws = wb["Movimientos"]
    manual = dict(zip(TXT_COLUMNS, ["07/02/2026", "MANUALBLUE002", "40021", "40012", "00123456789", 876.54]))
    put_columns(ws, 2, manual | {h: "LEGACY" for h in REMOVED})
    # Simulate the PR97 layout: classification was outside Tipo de Operación.
    put_columns(ws, 2, {"Tipo de Operación": "CARGO", "Clasificación SPEI": "SPEI Enviado"})
    wb.create_sheet("Clasificador SPEI").append(["Palabra sin errores", "Palabra con errores", "Clasificación"])
    imported = serialized(wb)
    previous = queries_from_workbook(imported)[0]
    assert previous.ready
    if action == "normalize":
        result = WorkbookBundle.from_excel(imported).improved
    else:
        evidence = CepEvidence()
        result = append_cep(imported, match_evidence([previous], evidence), [previous], evidence)
    wb = load_workbook(BytesIO(result))
    try:
        assert "Clasificador SPEI" not in wb
        row = rows_from_sheet(wb["Movimientos"])[0]
        assert not set(row) & set(REMOVED)
        assert get(row, "Tipo de Operación") == "SPEI Enviado"
        assert all(get(row, h) == v for h, v in manual.items())
    finally:
        wb.close()
    assert queries_from_workbook(result)[0].line() == previous.line()


def test_a_current_manual_type_wins_over_a_retired_classification_on_cross():
    original, _ = canonical_source()
    wb = load_workbook(BytesIO(WorkbookBundle.from_excel(original).improved))
    put_columns(wb["Movimientos"], 2, {"Tipo de Operación": "SPEI Devuelto", "Clasificación SPEI": "SPEI Enviado"})
    content = serialized(wb)
    queries = queries_from_workbook(content)
    evidence = CepEvidence()
    crossed = append_cep(content, match_evidence(queries, evidence), queries, evidence)
    assert get(rows(crossed)[0], "Tipo de Operación") == "SPEI Devuelto"
    assert "Clasificación SPEI" not in rows(crossed)[0]


def test_clean_import_does_not_modify_the_file_or_rerun_normalization():
    original, _ = canonical_source()
    content = WorkbookBundle.from_excel(original).improved
    uploaded = WorkbookBundle.from_uploaded(content)
    assert uploaded.original == uploaded.improved == content
    assert verify_pair(original, content) == 1


def test_clean_blue_block_keeps_blanks_even_when_only_new_recovery_can_find_a_bank():
    concept = f"SPEI RECIBIDO BCO:0012 DE LA CLABE 012180222222222226 CVE RAST: {KEY}"
    original, _ = source("banorte", concept, received=True)
    content = WorkbookBundle.from_excel(original).improved
    assert queries_from_workbook(content)[0].issuer == "40012"
    wb = load_workbook(BytesIO(content))
    put_columns(wb["Movimientos"], 2, {"TXT Banco Emisor": None})
    cleared = serialized(wb)
    again = WorkbookBundle.from_excel(cleared).improved
    assert get(rows(again)[0], "TXT Banco Emisor") is None
    assert not queries_from_workbook(again)[0].ready


def test_legacy_header_capitalization_does_not_duplicate_or_block_recovered_fields():
    original, _ = canonical_source()
    wb = load_workbook(BytesIO(original))
    for cell in wb["Movimientos"][1]:
        if cell.value in {"Clave de Rastreo", "Referencia", "Tipo de Operación", "Fecha de Operación"}:
            cell.value = cell.value.lower()
    content = serialized(wb)
    bundle = WorkbookBundle.from_excel(content)
    query = queries_from_workbook(bundle.improved)[0]
    assert query.ready and query.tracking == KEY
    row = rows(bundle.improved)[0]
    assert get(row, "Tipo de Operación") == "SPEI Enviado"
    assert "tipo de operación" in row and "Tipo de Operación" not in row
