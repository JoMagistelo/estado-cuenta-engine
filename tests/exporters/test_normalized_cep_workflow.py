from __future__ import annotations

import zipfile
from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from cep.catalog import INSTITUTIONS, bank_code, valid_clabe
from cep.evidence import CepEvidence, match_evidence, parse_cep_xml
from cep.package import export_cep_zip
from cep.queries import batch_texts, queries_from_workbook
from exporters.excel.normalization import filename_family, get, reconstruct_owners, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle, verify_pair
from utils.statement_dates import resolve_date


def clabe(prefix="012", account="12345678901"):
    base = prefix + "180" + account
    total = sum(int(c) * (3, 7, 1)[i % 3] % 10 for i, c in enumerate(base))
    return base + str((10 - total % 10) % 10)


OWN = clabe("012")
OTHER = clabe("072", "98765432109")


def account_row(number=1, account="12345678901", own=OWN, name="BBVA_1234_ENERO_2026.pdf"):
    return {"id_estado": number, "Nombre del Archivo": name, "Banco": "bbva",
            "Número de Cuenta": account, "CLABE": own, "Nombre del Cliente": "PERSONA SINTETICA",
            "RFC": "XXXX010101XXX", "Número de Cliente": "000001",
            "Periodo de Inicio": "15/12/2025", "Periodo de Fin": "14/01/2026", "Fecha de Corte": "14/01/2026"}


def movement_row(number=1, **overrides):
    return {"id_estado": 1, "Nombre del Archivo": "BBVA_1234_ENERO_2026.pdf", "Banco": "bbva",
            "Fecha de Corte": "14/01/2026", "Número de Cuenta": "12345678901", "No. de Movimiento": number,
            "Fecha de Operación": "03 ENE", "Fecha de Liquidación": "04/ENE",
            "Cargo": 125.25, "Abono": 0, "Concepto": "SPEI ENVIADO BANORTE",
            "Clave de Rastreo": "PRUEBASINTETICA001", "Referencia": "0000123",
            "CLABE del Beneficiario": OTHER, "Cuenta del Beneficiario": "", "Sucursal": "",
            "Concepto Original": "SPEI ENVIADO BANORTE", "Beneficiario manual": "Conservar edición",
            **overrides}


def excel(accounts=None, movements=None, *, formula=False):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in (("Datos de la Cuenta", accounts if accounts is not None else [account_row()]),
                       ("Movimientos", movements if movements is not None else [movement_row()])):
        ws = wb.create_sheet(name)
        if not rows:
            ws.append(["Sin información"])
            continue
        headers = list(dict.fromkeys(k for row in rows for k in row))
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    if formula:
        wb.create_sheet("Notas")["A1"] = "=Movimientos!G2"
    data = BytesIO()
    wb.save(data)
    return data.getvalue()


def rows(data, sheet="Movimientos"):
    wb = load_workbook(BytesIO(data))
    result = rows_from_sheet(wb[sheet])
    wb.close()
    return result


@pytest.mark.parametrize("value", ["03 ENE", "3ENE", "3/01", "03/ENE", "03-ENE-26", "03/01/26",
                                    "03/01/2026", "2026-01-03", "3 de enero de 2026", "03 ENERO 2026", "03"])
def test_all_parser_date_shapes_cross_year(value):
    assert resolve_date(value, "15/12/2025", "14/01/2026").value == date(2026, 1, 3)


def test_december_cutoff_in_january_and_leap_year():
    assert resolve_date("20 DIC", cutoff="14/01/2026").value == date(2025, 12, 20)
    assert resolve_date("29/FEB", "15/02/2024", "14/03/2024").value == date(2024, 2, 29)
    assert resolve_date("29/FEB", "15/02/2025", "14/03/2025").value is None
    assert resolve_date("03/01/2025", "15/12/2025", "14/01/2026").status == "FUERA_DE_PERIODO"
    assert resolve_date("03 ENE", cutoff="31/12/2025").value is None
    assert resolve_date("03 ENE").value is None
    assert resolve_date("03 ENE", "01/01/2025", "31/12/2026").value is None
    assert resolve_date("03", "01/12/2025", "31/01/2026").value is None


def test_normalization_replaces_date_cells_and_preserves_original_bytes_and_edits():
    original = excel(formula=True)
    bundle = WorkbookBundle.from_excel(original)
    assert bundle.original == original
    row = rows(bundle.improved)[0]
    assert get(row, "Fecha de Operación") == datetime(2026, 1, 3)
    assert get(row, "Fecha de Operación Original") == "03 ENE"
    assert get(row, "Fecha de Liquidación") == datetime(2026, 1, 4)
    assert get(row, "Cuenta Titular") == "12345678901"
    assert get(row, "CLABE Titular") == OWN
    assert get(row, "Sucursal") == "BANORTE"
    assert get(row, "Banco del Beneficiario") == "BANORTE"
    assert get(row, "Referencia") == "0000123"
    assert get(row, "Beneficiario manual") == "Conservar edición"
    assert get(row, "Cargo") == 125.25
    wb = load_workbook(BytesIO(bundle.improved))
    assert wb["Notas"]["A1"].value == "=Movimientos!G2"
    # A formula-bearing workbook keeps its original column coordinates.
    assert [c.value for c in wb["Movimientos"][1]][6] == "Fecha de Operación"
    date_cell = next(c for c in wb["Movimientos"][2] if c.value == datetime(2026, 1, 3))
    assert date_cell.data_type == "d" and date_cell.number_format == "dd/mm/yyyy"
    wb.close()
    assert verify_pair(original, bundle.improved) == 1


def test_holder_columns_follow_cutoff_in_engine_layout():
    bundle = WorkbookBundle.from_excel(excel())
    headers = list(rows(bundle.improved)[0])
    index = headers.index("Fecha de Corte")
    assert headers[index + 1:index + 3] == ["Cuenta Titular", "CLABE Titular"]


def test_recover_labelled_accounts_tracking_and_reference():
    text = f"SPEI ENVIADO CLABE BENEFICIARIO: {OTHER[:3]} {OTHER[3:6]} {OTHER[6:17]} {OTHER[-1]} CLAVE DE RASTREO: NUEVARASTREO01 REFERENCIA: 0000007"
    bundle = WorkbookBundle.from_excel(excel(movements=[movement_row(**{
        "Clave de Rastreo": None, "Referencia": None, "CLABE del Beneficiario": "MAL",
        "Concepto": text, "Concepto Original": text})]))
    row = rows(bundle.improved)[0]
    assert get(row, "CLABE del Beneficiario") == OTHER
    assert get(row, "Clave de Rastreo") == "NUEVARASTREO01"
    assert get(row, "Referencia") == "0000007"
    assert get(row, "Código Banco Beneficiario") == "40072"


def test_reconstruct_multiple_accounts_without_mixing_same_bank():
    a = account_row()
    missing = account_row(2, None, None, "BBVA_1234_DICIEMBRE_2025.pdf")
    missing.update({"Nombre del Cliente": None, "RFC": None})
    other = account_row(3, "88888888888", clabe("012", "88888888888"), "BBVA_8888_ENERO_2026.pdf")
    resolved = reconstruct_owners([a, missing, other])
    assert resolved[1].account == a["Número de Cuenta"] and resolved[1].clabe == OWN
    assert resolved[1].row["RFC"] == a["RFC"]
    assert resolved[2].clabe != OWN
    ambiguous = account_row(4, None, None, a["Nombre del Archivo"])
    other["Nombre del Archivo"] = a["Nombre del Archivo"]
    assert not reconstruct_owners([a, other, ambiguous])[2].clabe


def test_catalogue_checksum_unknown_prefix_and_precision_loss():
    assert valid_clabe(OWN) and not valid_clabe(OWN[:-1] + str((int(OWN[-1]) + 1) % 10))
    assert not valid_clabe(int(OWN))
    assert bank_code("mercado_pago") == "90722"
    assert bank_code("NU") == "40638"
    assert all(bank_code(code) == code for code in INSTITUTIONS)


def test_missing_date_and_placeholder_tracking_are_reviewed():
    bundle = WorkbookBundle.from_excel(excel(movements=[movement_row(**{"Fecha de Operación": None, "Clave de Rastreo": "N/A"})]))
    assert bundle.report.dates_review == 1
    query = queries_from_workbook(bundle.improved)[0]
    assert not query.ready and not query.tracking


def test_holder_identifiers_already_in_movement_are_kept_when_metadata_is_missing():
    bundle = WorkbookBundle.from_excel(excel(accounts=[account_row(account=None, own=None)],
        movements=[movement_row(**{"Número de Cuenta": None, "Cuenta Titular": "12345678901", "CLABE Titular": OWN,
                                  "Cargo": 0, "Abono": 125.25, "Concepto": "SPEI RECIBIDO BANORTE"})]))
    row = rows(bundle.improved)[0]
    assert get(row, "Cuenta Titular") == "12345678901"
    assert get(row, "CLABE Titular") == OWN
    query = queries_from_workbook(bundle.improved)[0]
    assert query.ready and query.destination == OWN


def test_txt_uses_improved_date_and_three_variants_without_bom():
    bundle = WorkbookBundle.from_excel(excel())
    queries = queries_from_workbook(bundle.improved)
    assert queries[0].ready, queries[0].issues
    lines = batch_texts(queries)["lote_001.txt"]
    assert not lines.startswith(b"\xef\xbb\xbf")
    assert [line.split(",")[0] for line in lines.decode().splitlines()] == ["2026-01-03", "2026-01-02", "2026-01-04"]
    assert all(line.endswith(f",40012,40072,{OTHER},125.25") for line in lines.decode().splitlines())


def test_received_txt_uses_each_holders_own_account():
    accounts = [account_row(), account_row(2, "88888888888", clabe("012", "88888888888"), "BBVA_8888_ENERO_2026.pdf")]
    movements = [movement_row(**{"Cargo": 0, "Abono": 125.25, "Concepto": "SPEI RECIBIDO BANORTE"}),
                 movement_row(2, **{"id_estado": 2, "Nombre del Archivo": accounts[1]["Nombre del Archivo"],
                                     "Cargo": 0, "Abono": 126, "Concepto": "SPEI RECIBIDO BANORTE"})]
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel(accounts, movements)).improved)
    assert all(q.ready for q in qs)
    assert qs[0].destination == OWN and qs[1].destination == accounts[1]["CLABE"]
    assert qs[0].issuer == "40072" and qs[0].receiver == "40012"


def test_hsbc_received_uses_participant_bank_and_keeps_sender_distinct_from_holder():
    own_hsbc = clabe("021")
    source_bbva = clabe("012", "55555555555")
    account = account_row(own=own_hsbc)
    account["Banco"] = "hsbc"
    row = movement_row(**{"Banco": "hsbc", "Cargo": 0, "Abono": 125.25,
                           "CLABE del Beneficiario": source_bbva, "Cuenta del Beneficiario": "55555555555",
                           "Sucursal": "BBVA MEXICO", "Concepto": "SPEI RECIBIDO", "Concepto Original": "PAGO"})
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel([account], [row])).improved)
    query = qs[0]
    assert query.ready, query.issues
    assert query.issuer == "40012" and query.receiver == "40021"
    assert query.destination == own_hsbc
    assert source_bbva in query.origin_aliases
    official = xml_cep(destination=own_hsbc, origin=source_bbva).replace(b'bancoReceptor="40072"', b'bancoReceptor="40021"')
    evidence = CepEvidence()
    evidence.add_zip(zipped(official))
    assert match_evidence(qs, evidence)[2]["CEP Estado"] == "EXITO"
    wrong = CepEvidence()
    wrong.add_zip(zipped(official.replace(source_bbva.encode(), OTHER.encode())))
    assert match_evidence(qs, wrong)[2]["CEP Estado"] == "REVISAR"


def xml_cep(tracking="PRUEBASINTETICA001", value="125.25", when="03/01/2026", destination=OTHER, origin=OWN):
    return (f'<SPEI_Tercero fechaOperacion="{when}" claveRastreo="{tracking}">'
            f'<Ordenante nombre="ORDENANTE XML" rfc="XXXX010101XXX" cuenta="{origin}" bancoEmisor="40012"/>'
            f'<Beneficiario nombre="BENEFICIARIO XML" rfc="YYYY010101XXX" cuenta="{destination}" bancoReceptor="40072"/>'
            f'<DatosPago monto="{value}" concepto="PRUEBA" referenciaNumerica="0000123"/>'
            '</SPEI_Tercero>').encode()


def zipped(xml=None, *, pdf=True):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("lote/pago.xml", xml or xml_cep())
        if pdf:
            archive.writestr("lote/pago.pdf", b"%PDF-1.4\nsynthetic")
    return output.getvalue()


def test_official_zip_matching_and_both_enriched_workbooks(tmp_path):
    bundle = WorkbookBundle.from_excel(excel(movements=[movement_row(), movement_row(2, **{"Clave de Rastreo": "OTRORASTREO02", "Cargo": 200})]))
    queries = queries_from_workbook(bundle.improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped())
    matches = match_evidence(queries, evidence)
    assert matches[2]["CEP Estado"] == "EXITO"
    assert matches[3]["CEP Estado"] == "NO_APARECE_EN_ZIP"
    output = tmp_path / "final.zip"
    export_cep_zip(bundle, queries, evidence, output)
    with zipfile.ZipFile(output) as archive:
        raw = rows(archive.read("excel_original_con_CEP.xlsx"))
        clean = rows(archive.read("excel_mejorado_con_CEP.xlsx"))
        assert get(raw[0], "Fecha de Operación") == "03 ENE"
        assert get(clean[0], "Fecha de Operación") == datetime(2026, 1, 3)
        for row in (raw[0], clean[0]):
            assert get(row, "CEP Nombre Beneficiario") == "BENEFICIARIO XML"
            assert get(row, "CEP Archivo PDF") in archive.namelist()
            assert get(row, "CEP Archivo XML") in archive.namelist()
        for name in ("excel_original_con_CEP.xlsx", "excel_mejorado_con_CEP.xlsx"):
            workbook = load_workbook(BytesIO(archive.read(name)))
            ws = workbook["Movimientos"]
            columns = {cell.value: cell.column for cell in ws[1]}
            for label in ("CEP Archivo PDF", "CEP Archivo XML"):
                cell = ws.cell(2, columns[label])
                assert cell.hyperlink.target == cell.value
                assert cell.hyperlink.target in archive.namelist()
            assert ws.cell(3, columns["CEP Archivo PDF"]).hyperlink is None
            workbook.close()
        assert get(raw[1], "CEP Nombre Beneficiario") is None


@pytest.mark.parametrize("kwargs", [{"value": "125.26"}, {"destination": OWN}, {"origin": OTHER}, {"when": "05/01/2026"}])
def test_same_tracking_never_overrides_conflicting_financial_evidence(kwargs):
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel()).improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped(xml_cep(**kwargs)))
    assert match_evidence(qs, evidence)[2]["CEP Estado"] == "REVISAR"


def test_zip_date_retry_duplicates_pdf_upgrade_and_ambiguous_xml():
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel()).improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped(xml_cep(when="04/01/2026"), pdf=False))
    assert match_evidence(qs, evidence)[2]["CEP Estado"] == "EXITO_FECHA_ALTERNATIVA"
    evidence.add_zip(zipped(xml_cep(when="04/01/2026")))
    assert len(evidence.records) == 1 and evidence.records[0].pdf
    evidence.add_zip(zipped(xml_cep(when="02/01/2026")))
    assert match_evidence(qs, evidence)[2]["CEP Estado"] == "REVISAR"


def test_xml_entities_are_rejected():
    with pytest.raises(ValueError):
        parse_cep_xml(b'<!DOCTYPE a [<!ENTITY x "evil">]><a>&x;</a>')


def test_identical_tracking_in_two_rows_does_not_duplicate_cep_assignment():
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel(movements=[movement_row(), movement_row(2)])).improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped())
    assert all(v["CEP Estado"] == "REVISAR" for v in match_evidence(qs, evidence).values())


def test_exact_date_wins_over_competing_adjacent_day_row():
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel(movements=[movement_row(), movement_row(2, **{"Fecha de Operación": "04 ENE"})])).improved)
    evidence = CepEvidence()
    evidence.add_zip(zipped())
    result = match_evidence(qs, evidence)
    assert result[2]["CEP Estado"] == "EXITO"
    assert result[3]["CEP Estado"] == "REVISAR"


def test_reloading_normalized_workbook_keeps_dates_and_audit_history():
    bundle = WorkbookBundle.from_excel(excel())
    reloaded = WorkbookBundle.from_excel(bundle.improved)
    assert get(rows(reloaded.improved)[0], "Fecha de Operación Original") == "03 ENE"
    assert get(rows(reloaded.improved)[0], "Fecha de Operación") == datetime(2026, 1, 3)
    assert len(rows(reloaded.improved, "Revisión Excel")) >= len(rows(bundle.improved, "Revisión Excel"))


def test_batch_splitting_501_queries_does_not_leave_a_single_line():
    qs = queries_from_workbook(WorkbookBundle.from_excel(excel()).improved)
    from dataclasses import replace
    queries = [replace(qs[0], tracking=f"SYNTHETIC{i:06d}") for i in range(501)]
    batches = batch_texts(queries, adjacent_days=False)
    assert [len(data.splitlines()) for data in batches.values()] == [499, 2]


@pytest.mark.parametrize("received", [False, True])
def test_bbva_recovery_on_old_exports_feeds_txt_with_correct_parties(received):
    heading = "SPEI RECIBIDOBANORTE" if received else "SPEI ENVIADO BANORTE"
    concept = f"{heading}\n0000007PRUEBA\n00{OTHER}\nMBAN20260103000000000001\nPERSONA SINTETICA"
    original = excel(movements=[movement_row(**{
        "Concepto": concept, "Concepto Original": "0000007PRUEBA", "Clave de Rastreo": None,
        "CLABE del Beneficiario": None, "Referencia": None,
        "Cargo": 0 if received else 125.25, "Abono": 125.25 if received else 0,
    })])
    bundle = WorkbookBundle.from_excel(original)
    assert bundle.original == original
    q = queries_from_workbook(bundle.improved)[0]
    assert q.ready, q.issues
    assert q.tracking == "MBAN20260103000000000001"
    assert q.destination == (OWN if received else OTHER)
    assert (q.issuer, q.receiver) == (("40072", "40012") if received else ("40012", "40072"))
    assert len(batch_texts([q])["lote_001.txt"].splitlines()) == 3


def test_bbva_statement_reference_and_payment_reference_are_distinct_and_audited():
    concept = f"SPEI ENVIADO BANORTE\n0000007PRUEBA\n00{OTHER}\nMBAN20260103000000000001\nPERSONA SINTETICA"
    bundle = WorkbookBundle.from_excel(excel(movements=[movement_row(**{
        "Concepto": concept, "Concepto Original": "0000007PRUEBA", "Referencia": "0000001234 072",
    })]))
    row = rows(bundle.improved)[0]
    assert get(row, "Referencia") == "0000001234"
    assert get(row, "Referencia Original") == "0000001234 072"
    assert get(row, "Referencia SPEI") == "0000007"
    assert queries_from_workbook(bundle.improved)[0].reference == "0000007"
    assert any(c["Campo"] == "Referencia" and c["Original"] == "0000001234 072" for c in bundle.report.changes)
    reloaded = rows(WorkbookBundle.from_excel(bundle.improved).improved)[0]
    assert get(reloaded, "Referencia") == "0000001234"
    assert get(reloaded, "Referencia Original") == "0000001234 072"
    conflict = WorkbookBundle.from_excel(excel(movements=[movement_row(**{
        "Concepto": concept, "Concepto Original": "0000007PRUEBA", "Referencia": "0000001234 014",
    })]))
    assert get(rows(conflict.improved)[0], "Referencia") == "0000001234 014"
    assert "no concordante" in get(rows(conflict.improved)[0], "Revisión Normalización")
