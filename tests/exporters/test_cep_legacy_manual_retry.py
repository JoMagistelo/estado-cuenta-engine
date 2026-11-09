"""Regression coverage for all Excel generations and manual Banxico CEP retries.

Synthetic data only: never store real statement or personal details in git.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from cep.evidence import CepEvidence, match_evidence
from cep.package import MOVEMENT_CEP_COLUMNS, append_cep
from cep.queries import batch_texts, queries_from_workbook
from exporters.excel.normalization import get, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle


def clabe(prefix: str, account: str = "12345678901") -> str:
    stem = prefix + "180" + account
    total = sum((int(c) * (3, 7, 1)[i % 3]) % 10 for i, c in enumerate(stem))
    return stem + str((10 - total % 10) % 10)


OWN = clabe("012")
OTHER = clabe("072")
OTHER_HSBC = clabe("021")


def workbook(*, received=False, old=False, crossed=False, duplicate=False) -> bytes:
    wb = Workbook()
    wb.active.title = "Datos de la Cuenta"
    acc = wb.active
    acc.append(["id_estado", "Nombre del Archivo", "Banco", "Número de Cuenta",
                "CLABE", "Periodo de Inicio", "Periodo de Fin", "Fecha de Corte"])
    acc.append([1, "BBVA_1234_ENE_2026.pdf", "bbva", "12345678901",
                OWN, "15/12/2025", "14/01/2026", "14/01/2026"])
    ws = wb.create_sheet("Movimientos")
    labels = ["id_estado", "Nombre del Archivo", "Banco", "Fecha de Corte",
              "Número de Cuenta", "No. de Movimiento", "Fecha de Operación",
              "Cargo", "Abono", "Tipo de Operación", "Concepto",
              "CLABE del Beneficiario", "Cuenta del Beneficiario"]
    if not old:
        labels += ["CLABE Titular", "Clave de Rastreo"]
    if duplicate:
        labels += ["Cuenta Titular"]
    if crossed:
        labels += ["CEP Estado", "CEP Nombre Beneficiario", "CEP Banco Receptor"]
    ws.append(labels)
    vals = {
        "id_estado": 1,
        "Nombre del Archivo": "BBVA_1234_ENE_2026.pdf",
        "Banco": "bbva",
        "Fecha de Corte": "14/01/2026",
        "Número de Cuenta": "12345678901",
        "No. de Movimiento": 1,
        "Fecha de Operación": "03 ENE",
        "Cargo": 0 if received else 123.45,
        "Abono": 123.45 if received else 0,
        "Tipo de Operación": "SPEI",
        "Concepto": (
            "SPEI RECIBIDO BANORTE CLAVE RASTREO PRUEBA20260103001" if received
            else "SPEI ENVIADO BANORTE CLAVE RASTREO PRUEBA20260103001"
        ),
        "CLABE del Beneficiario": OTHER,
        "Cuenta del Beneficiario": OTHER,
        "CLABE Titular": OWN,
        "Clave de Rastreo": "PRUEBA20260103001",
        "Cuenta Titular": "12345678901",
        "CEP Estado": "EXITO",
        "CEP Nombre Beneficiario": "STALENOTUSE",
        "CEP Banco Receptor": "40044",
    }
    ws.append([vals.get(field) for field in labels])
    if crossed:
        wb.create_sheet("Control CEP").append(["CABECERA ANTIGUA"])
        wb.create_sheet("Datos CEP").append(["XML ANTIGUO"])
        wb.create_sheet("Revisión CEP").append(["OBSOLETO"])
        wb.create_sheet("Revisión Excel").append(["OBSOLETO"])
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


def edit(source: bytes, changes: dict) -> bytes:
    wb = load_workbook(BytesIO(source))
    ws = wb["Movimientos"]
    headers = {cell.value: cell.column for cell in ws[1]}
    for column, value in changes.items():
        if column not in headers:
            ws.cell(1, ws.max_column + 1, column)
            headers[column] = ws.max_column
        ws.cell(2, headers[column], value)
    data = BytesIO()
    wb.save(data)
    wb.close()
    return data.getvalue()


def read(source: bytes, sheet: str = "Movimientos"):
    wb = load_workbook(BytesIO(source))
    try:
        return rows_from_sheet(wb[sheet]), wb.sheetnames
    finally:
        wb.close()


def test_legacy_received_uses_holder_clabe_from_its_account_sheet_without_normalizing():
    original = workbook(old=True, received=True)
    bundle = WorkbookBundle.from_uploaded(original, source_name="historico.xlsx")
    assert bundle.original == original and bundle.improved == original
    q = queries_from_workbook(bundle.improved, today=date(2026, 11, 9))[0]
    assert q.ready, q.issues
    assert (q.operation_date, q.direction) == (date(2026, 1, 3), "RECIBIDO")
    assert (q.issuer, q.receiver, q.destination) == ("40072", "40012", OWN)
    assert q.line() == f"2026-01-03,PRUEBA20260103001,40072,40012,{OWN},123.45"


def test_legacy_without_tracking_column_reads_labelled_concept_only():
    original = workbook(old=True)
    bundle = WorkbookBundle.from_uploaded(original)
    assert bundle.original == original
    q = queries_from_workbook(bundle.improved)[0]
    assert q.ready, q.issues
    assert q.tracking == "PRUEBA20260103001"
    assert (q.issuer, q.receiver, q.destination) == ("40012", "40072", OTHER)


def test_edited_date_tracking_bank_account_and_amount_generate_txt_without_normalize():
    original = workbook()
    corrected = edit(original, {
        "Fecha de Operación": "04/01/2026",
        "Clave de Rastreo": "MANUAL20260104002",
        "Banco Receptor": "HSBC",
        "CLABE del Beneficiario": OTHER_HSBC,
        "Cuenta del Beneficiario": OTHER_HSBC,
        "Cargo": 890.12,
        "Estado de Fecha": "REVISAR",
    })
    bundle = WorkbookBundle.from_uploaded(corrected)
    assert bundle.improved == corrected
    q = queries_from_workbook(bundle.improved)[0]
    assert q.ready, q.issues
    assert q.line() == f"2026-01-04,MANUAL20260104002,40012,40021,{OTHER_HSBC},890.12"
    assert "MANUAL20260104002" in batch_texts([q], adjacent_days=True)["lote_001.txt"].decode()


def test_manual_received_holder_clabe_wins_over_legacy_donor_clabe():
    updated = clabe("012", "99999999999")
    original = edit(workbook(received=True), {"CLABE Titular": updated})
    q = queries_from_workbook(WorkbookBundle.from_uploaded(original).improved)[0]
    assert q.ready, q.issues
    assert q.destination == updated
    assert q.receiver == "40012"


def test_generated_cross_has_compact_movements_and_three_useful_cep_sheets():
    original = workbook(crossed=True, duplicate=True)
    bundle = WorkbookBundle.from_uploaded(original)
    qs = queries_from_workbook(bundle.improved)
    evidence = CepEvidence()
    output = append_cep(bundle.improved, match_evidence(qs, evidence), qs, evidence)
    data, names = read(output)
    assert "Cuenta Titular" not in data[0]
    assert get(data[0], "Número de Cuenta") == "12345678901"
    assert get(data[0], "CLABE Titular") == OWN
    headers = {k for k in data[0] if k.startswith("CEP ")}
    assert headers == set(MOVEMENT_CEP_COLUMNS)
    assert "Control CEP" in names and "Datos CEP" in names
    assert "Revisión CEP" not in names and "Revisión Excel" not in names
    control, _ = read(output, "Control CEP")
    assert len(control) == 1
    assert get(control[0], "Fecha TXT").date() == date(2026, 1, 3)
    assert get(control[0], "Clave de Rastreo TXT") == "PRUEBA20260103001"
    assert get(control[0], "Cuenta Beneficiaria TXT") == OTHER
    assert get(control[0], "Resultado CEP") == "NO_APARECE_EN_ZIP"
    assert get(control[0], "Datos por corregir") in ("", None)
    assert get(control[0], "Línea TXT (fecha base)") == qs[0].line()


def test_reimport_previous_cross_edit_movements_regenerates_new_query():
    original = workbook(crossed=True, duplicate=True)
    bundle = WorkbookBundle.from_uploaded(original)
    qs = queries_from_workbook(bundle.improved)
    crossed = append_cep(bundle.improved, match_evidence(qs, CepEvidence()), qs, CepEvidence())
    corrected = edit(crossed, {
        "Fecha de Operación": "05/01/2026",
        "Clave de Rastreo": "SEGUNDAVEZ20260105",
        "Cargo": 234.56,
    })
    uploaded_again = WorkbookBundle.from_uploaded(corrected)
    assert uploaded_again.original == corrected
    q = queries_from_workbook(uploaded_again.improved)[0]
    assert q.ready, q.issues
    assert q.line() == f"2026-01-05,SEGUNDAVEZ20260105,40012,40072,{OTHER},234.56"
    crossed_again = append_cep(
        uploaded_again.improved, match_evidence([q], CepEvidence()), [q], CepEvidence()
    )
    data, names = read(crossed_again)
    assert get(data[0], "Clave de Rastreo") == "SEGUNDAVEZ20260105"
    assert "Revisión CEP" not in names
    control, _ = read(crossed_again, "Control CEP")
    assert get(control[0], "Clave de Rastreo TXT") == "SEGUNDAVEZ20260105"


def test_conflicting_duplicate_holder_account_is_not_silently_discarded():
    source = edit(workbook(duplicate=True), {"Cuenta Titular": "99999999999"})
    bundle = WorkbookBundle.from_uploaded(source)
    assert bundle.improved == source  # still usable to inspect and prepare TXT
    with pytest.raises(ValueError, match="son distintos"):
        WorkbookBundle.from_excel(source)
    qs = queries_from_workbook(bundle.improved)
    with pytest.raises(ValueError, match="son distintos"):
        append_cep(source, match_evidence(qs, CepEvidence()), qs, CepEvidence())


def test_normalized_redundant_holder_column_removed_without_mutating_original():
    original = workbook(duplicate=True)
    normalized = WorkbookBundle.from_excel(original)
    assert normalized.original == original
    data, sheets = read(normalized.improved)
    assert "Cuenta Titular" not in data[0]
    assert get(data[0], "Número de Cuenta") == "12345678901"
    assert get(data[0], "CLABE Titular") == OWN
    assert "Revisión Excel" not in sheets
