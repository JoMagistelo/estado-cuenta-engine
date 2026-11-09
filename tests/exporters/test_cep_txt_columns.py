"""The analyst edits six visible TXT cells without changing parser evidence."""

from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from cep.catalog import INSTITUTIONS
from cep.columns import CEP_COLUMNS, TRACE_COLUMNS, TXT_COLUMNS
from cep.evidence import CepEvidence, match_evidence
from cep.package import append_cep
from cep.queries import batch_texts, queries_from_workbook
from exporters.excel.cells import get, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle, original_from_results
from models.movimiento import Movimiento

from test_cep_legacy_manual_retry import OWN, OTHER, edit, workbook
from test_normalized_cep_workflow import xml_cep, zipped


def read(content):
    wb = load_workbook(BytesIO(content))
    try:
        return rows_from_sheet(wb["Movimientos"])
    finally:
        wb.close()


def save(wb):
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


def normalized():
    return WorkbookBundle.from_excel(workbook()).improved


def test_exported_original_keeps_the_v5_v6_movement_contract():
    # The mapper, writer, batch exporter and styles were compared byte-for-byte
    # with 425a676 (5.0.0) and 78d5614 (6.0.0). Freeze their original headers.
    from test_excel_layout_contract import _result
    result = _result()
    result.estado_cuenta.movimientos = [Movimiento(
        "03 ENE", None, "CONCEPTO SINTETICO", "CARGO", 125.25, 0,
        referencia="0000007", clave_rastreo="SINTETICO001", clabe_beneficiario=OTHER,
    )]
    content = original_from_results([result])
    wb = load_workbook(BytesIO(content))
    try:
        assert [c.value for c in wb["Movimientos"][1]] == [
            "id_estado", "Nombre del Archivo", "Banco", "Fecha de Corte", "Número de Cuenta",
            "No. de Movimiento", "Fecha de Operación", "Fecha de Liquidación", "Concepto",
            "Tipo de Operación", "Cargo", "Abono", "Saldo de Operación", "Saldo de liquidacion",
            "Referencia", "Clave de Rastreo", "Autorizacion", "Beneficiario",
            "Cuenta del Beneficiario", "CLABE del Beneficiario", "RFC", "Sucursal", "Caja",
            "Hora de Operación", "Concepto Original",
        ]
        assert wb.sheetnames == ["Datos de la Cuenta", "Resumen Financiero", "Movimientos", "Otros Productos"]
    finally:
        wb.close()


@pytest.mark.parametrize("generation", ["v5", "v6", "v7_original", "v7_normalizado", "v7_cruzado"])
def test_every_legacy_generation_can_fill_missing_fields_and_preserve_existing_spei_values(generation):
    original = workbook(old=generation in {"v5", "v6"}, crossed=generation == "v7_cruzado")
    if generation == "v7_normalizado":
        original = edit(original, {
            "Fecha de Operación": "05/01/2026", "Clave de Rastreo": "CORRECCIONANTIGUA001",
            "Revisión Normalización": "", "Banco del Beneficiario": "BANORTE",
            "Código Banco Beneficiario": "40072", "Código Plaza/Producto CLABE": "180",
        })
    before = read(original)[0]
    uploaded = WorkbookBundle.from_uploaded(original)
    assert uploaded.original == uploaded.improved == original
    bundle = WorkbookBundle.from_excel(original)
    assert bundle.original == original
    after = read(bundle.improved)[0]
    for label in ("Concepto", "Clave de Rastreo", "Referencia", "CLABE del Beneficiario",
                  "Cuenta del Beneficiario", "Cargo", "Abono", "Banco del Beneficiario"):
        if get(before, label) is not None and str(get(before, label)).strip():
            assert get(before, label) == get(after, label)
    for label in ("Concepto", "Cargo", "Abono", "Tipo de Operación"):
        assert get(before, label) == get(after, label)
    q = queries_from_workbook(bundle.improved)[0]
    assert q.ready, q.issues
    assert get(after, "TXT Cuenta Beneficiaria") == OTHER
    if generation == "v7_normalizado":
        assert q.tracking == "CORRECCIONANTIGUA001" and q.operation_date.day == 5


def test_all_six_blue_edits_override_the_green_parser_columns_without_renormalizing():
    content = normalized()
    corrected = edit(content, {
        TXT_COLUMNS[0]: "07/02/2026", TXT_COLUMNS[1]: "MANUAL20260207001",
        TXT_COLUMNS[2]: "40021", TXT_COLUMNS[3]: "40072",
        TXT_COLUMNS[4]: "00123456789", TXT_COLUMNS[5]: 987.65,
    })
    uploaded = WorkbookBundle.from_uploaded(corrected)
    assert uploaded.prepared
    assert uploaded.original == uploaded.improved == corrected
    q = queries_from_workbook(uploaded.improved)[0]
    expected = "2026-02-07,MANUAL20260207001,40021,40072,00123456789,987.65"
    assert q.ready, q.issues
    assert q.line() == expected
    assert batch_texts([q])["lote_001.txt"].decode().splitlines()[0] == expected
    # Even an explicit second normalization cannot restore older green data.
    again = WorkbookBundle.from_excel(corrected).improved
    assert queries_from_workbook(again)[0].line() == expected
    for label in TXT_COLUMNS:
        assert get(read(again)[0], label) == get(read(corrected)[0], label)
    assert get(read(again)[0], "Clave de Rastreo") == "PRUEBA20260103001"
    assert get(read(again)[0], "Cargo") == 123.45


@pytest.mark.parametrize("label", TXT_COLUMNS)
def test_clearing_a_blue_cell_never_falls_back_to_the_original_parser_value(label):
    corrected = edit(normalized(), {label: None})
    q = queries_from_workbook(corrected)[0]
    assert q.candidate and not q.ready
    assert any(label in issue for issue in q.issues)
    again = WorkbookBundle.from_excel(corrected).improved
    assert get(read(again)[0], label) is None
    assert not queries_from_workbook(again)[0].ready


@pytest.mark.parametrize("destination", [
    "123456789", "00123456789", "4111111111111113", OTHER,
    "004111111111111113", "00123456789012345678", "1" + "234567890" * 4,
])
def test_tracking_is_kept_for_accounts_cards_and_clabes_without_a_length_filter(destination):
    corrected = edit(normalized(), {TXT_COLUMNS[4]: destination})
    q = queries_from_workbook(corrected)[0]
    assert q.candidate and q.ready, q.issues
    assert q.destination == destination
    assert q.line().split(",")[4] == destination


def test_partial_and_duplicate_txt_headers_do_not_silently_mix_sources():
    partial = edit(workbook(), {TXT_COLUMNS[1]: "MANUALPARCIAL001"})
    q = queries_from_workbook(partial)[0]
    assert q.tracking == "MANUALPARCIAL001" and q.operation_date is None
    assert q.candidate and not q.ready
    wb = load_workbook(BytesIO(normalized()))
    ws = wb["Movimientos"]
    ws.cell(1, ws.max_column + 1, TXT_COLUMNS[1])
    duplicated = save(wb)
    with pytest.raises(ValueError, match="TXT duplicadas"):
        queries_from_workbook(duplicated)


def test_bad_numeric_blue_dates_and_precision_loss_are_not_repaired_from_old_data():
    wb = load_workbook(BytesIO(normalized()))
    columns = {c.value: c.column for c in wb["Movimientos"][1]}
    cell = wb["Movimientos"].cell(2, columns[TXT_COLUMNS[0]])
    cell.value, cell.number_format = 45000, "General"
    wb["Movimientos"].cell(2, columns[TXT_COLUMNS[4]]).value = 123456789012345678
    corrected = save(wb)
    q = queries_from_workbook(corrected)[0]
    assert q.candidate and not q.ready
    again = WorkbookBundle.from_excel(corrected).improved
    assert get(read(again)[0], TXT_COLUMNS[0]) == 45000
    assert not queries_from_workbook(again)[0].ready


def test_an_unreliable_numeric_tracking_cell_keeps_the_row_as_spei_for_correction():
    original = edit(workbook(), {"Concepto": "TRANSFERENCIA", "Tipo de Operación": "CARGO",
        "Clave de Rastreo": 123456789012345678})
    result = WorkbookBundle.from_excel(original).improved
    q = queries_from_workbook(result)[0]
    assert q.candidate and not q.ready
    assert any("TXT Clave de Rastreo" in issue for issue in q.issues)
    assert len(read(result)) == 1


def test_filtered_hidden_rows_and_spei_without_destination_remain_in_movimientos():
    wb = load_workbook(BytesIO(workbook()))
    ws = wb["Movimientos"]
    columns = {c.value: c.column for c in ws[1]}
    ws.append([c.value for c in ws[2]])
    ws.cell(3, columns["Clave de Rastreo"], "SINDESTINO001")
    ws.cell(3, columns["CLABE del Beneficiario"], None)
    ws.cell(3, columns["Cuenta del Beneficiario"], None)
    # Passing None to cell() does not clear an existing value.
    ws.cell(3, columns["CLABE del Beneficiario"]).value = None
    ws.cell(3, columns["Cuenta del Beneficiario"]).value = None
    ws.row_dimensions[3].hidden = True
    ws.auto_filter.ref = ws.dimensions
    original = save(wb)
    bundle = WorkbookBundle.from_excel(original)
    rows = read(bundle.improved)
    assert len(rows) == bundle.report.movements == 2
    queries = queries_from_workbook(bundle.improved)
    assert queries[0].ready
    assert queries[1].candidate and queries[1].tracking == "SINDESTINO001"
    assert not queries[1].ready
    assert "TXT Cuenta Beneficiaria" in get(rows[1], "Revisión Normalización")


def test_original_widths_and_filters_follow_their_columns_when_legacy_layout_is_prepared():
    wb = load_workbook(BytesIO(workbook(old=True)))
    ws = wb["Movimientos"]
    ws.cell(1, ws.max_column + 1, "Revisión Normalización")
    ws.cell(1, ws.max_column + 1, "Anotación del analista")
    ws.cell(2, ws.max_column, "CONSERVAR")
    widths = {}
    for cell in ws[1]:
        width = 20 + cell.column / 10
        ws.column_dimensions[get_column_letter(cell.column)].width = width
        widths[cell.value] = width
    labels = [c.value for c in ws[1]]
    filtered = ["Cuenta del Beneficiario", "Anotación del analista"]
    ws.auto_filter.ref = ws.dimensions
    for label in filtered:
        ws.auto_filter.add_filter_column(labels.index(label), ["VALOR"])
    result = WorkbookBundle.from_excel(save(wb)).improved
    wb = load_workbook(BytesIO(result))
    try:
        ws = wb["Movimientos"]
        final_labels = [c.value for c in ws[1]]
        assert {final_labels[c.colId] for c in ws.auto_filter.filterColumn} == set(filtered)
        for cell in ws[1]:
            if cell.value in widths:
                assert ws.column_dimensions[get_column_letter(cell.column)].width == widths[cell.value]
        assert get(rows_from_sheet(ws)[0], "Anotación del analista") == "CONSERVAR"
    finally:
        wb.close()


def test_old_holder_conflicts_cannot_override_or_block_an_explicit_txt_block():
    corrected = edit(normalized(), {"Cuenta Titular": "99999999999", "Banco": "HSBC"})
    before = queries_from_workbook(corrected)[0]
    assert before.ready
    again = WorkbookBundle.from_excel(corrected).improved
    assert queries_from_workbook(again)[0].line() == before.line()
    evidence = CepEvidence()
    crossed = append_cep(again, match_evidence([before], evidence), [before], evidence)
    assert get(read(crossed)[0], "Cuenta Titular") == "99999999999"
    assert queries_from_workbook(crossed)[0].line() == before.line()


def test_layout_hides_trace_and_puts_complete_official_results_after_blue_inputs():
    bundle = WorkbookBundle.from_excel(workbook())
    qs = queries_from_workbook(bundle.improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped(xml_cep(tracking=qs[0].tracking, value="123.45", destination=OTHER, origin=OWN)))
    crossed = append_cep(bundle.improved, match_evidence(qs, evidence), qs, evidence)
    wb = load_workbook(BytesIO(crossed))
    try:
        ws = wb["Movimientos"]
        headers = [c.value for c in ws[1]]
        start = headers.index("Revisión Normalización") + 1
        assert headers[start:start + 6] == list(TXT_COLUMNS)
        assert headers[start + 6:] == list(CEP_COLUMNS)
        for c in ws[1]:
            expected = "00156082" if c.value in TXT_COLUMNS else "00F4B183" if c.value in CEP_COLUMNS else "001F4D3A"
            assert c.fill.fgColor.rgb == expected
            if c.value in TRACE_COLUMNS:
                assert ws.column_dimensions[get_column_letter(c.column)].hidden
        row = rows_from_sheet(ws)[0]
        assert get(row, "CEP Estado") == "EXITO"
        assert get(row, "CEP Nombre Beneficiario") == "BENEFICIARIO XML"
        assert get(row, "CEP Cuenta Beneficiaria") == OTHER
        assert get(row, "CEP Archivo PDF")
        assert "Control CEP" not in wb and "Revisión CEP" not in wb and "Revisión Excel" not in wb
        catalog = rows_from_sheet(wb["Catálogo Bancos"])
        assert {get(r, "Código Banxico") for r in catalog} == set(INSTITUTIONS)
    finally:
        wb.close()
    assert queries_from_workbook(crossed)[0].line() == qs[0].line()
    # Crossing again replaces evidence without touching the blue inputs.
    empty = CepEvidence()
    retried = append_cep(crossed, match_evidence(qs, empty), qs, empty)
    assert get(read(retried)[0], "CEP Nombre Beneficiario") is None
    assert get(read(retried)[0], "CEP Estado") == "NO_APARECE_EN_ZIP"
