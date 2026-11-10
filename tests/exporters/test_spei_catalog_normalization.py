"""Synthetic regression cases only: never copy payments from a user's catalogue."""

from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from cep.columns import RETIRED_KEYS, TRACE_COLUMNS, TXT_COLUMNS
from cep.evidence import CepEvidence, match_evidence
from cep.queries import queries_from_workbook
from cep.spei_classifier import (
    CLASSIFICATION_COLUMN, CLASSIFIER_RULES, INTERNAL, RECEIVED, RETURNED, SENT,
    TRANSFER, classify_spei,
)
from cep.spei_recovery import extract_metadata
from exporters.excel.cells import get, header_key, put_columns
from exporters.excel.workbook_bundle import WorkbookBundle, verify_pair

from test_normalized_cep_workflow import account_row, clabe, excel, movement_row, rows


KEY = "SYNTHETIC20260103000001"
OTHER = clabe("072", "98765432109")
BBVA = clabe("012", "22222222222")
CARD = "4111111111111111"


def source(bank, concept, *, received=False, **changes):
    codes = {"banamex": "002", "bbva": "012", "banorte": "072", "azteca": "127",
             "hsbc": "021", "santander": "014", "nu": "638", "scotiabank": "044"}
    own = clabe(codes[bank], "12345678901")
    owner = account_row(own=own)
    owner["Banco"] = bank
    values = movement_row(**{
        "Banco": bank, "Concepto": concept, "Concepto Original": concept,
        "Cargo": 0 if received else 125.25, "Abono": 125.25 if received else 0,
        "Tipo de Operación": "ABONO" if received else "CARGO",
        "Clave de Rastreo": None, "Referencia": None,
        "CLABE del Beneficiario": None, "Cuenta del Beneficiario": None,
        "Sucursal": "SUCURSAL SIN CAMBIOS", **changes,
    })
    return excel(accounts=[owner], movements=[values]), own


def edit(content, values):
    wb = load_workbook(BytesIO(content))
    put_columns(wb["Movimientos"], 2, values)
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


@pytest.mark.parametrize("canonical,variant,label", CLASSIFIER_RULES)
def test_every_catalogue_keyword_and_ocr_variant_is_searchable(canonical, variant, label):
    received = label in {RECEIVED, RETURNED}
    for phrase in {canonical, variant}:
        row = {"Concepto": phrase + " TEXTO SINTETICO", "Cargo": 0 if received else 1,
               "Abono": 1 if received else 0}
        assert classify_spei(row).label == label


@pytest.mark.parametrize("concept,received,label", [
    ("DEPOSITO EN EFECTIVO", True, ""),
    ("DEVOLUCION COMPRA TARJETA", True, ""),
    ("NOMINA", True, ""),
    ("RETIRO ATM", False, ""),
    ("CARGO SERVICIOCGO", False, ""),
    ("PAGO RECIBIDO DE SU REF.0000007 PERSONA SINTETICA", True, INTERNAL),
    ("PAGO RECIBIDO DE PERSONA SINTETICA", True, INTERNAL),
    ("PAGO CUENTA DE TERCERO CONCEPTO: SPEI ENVIADO", False, INTERNAL),
    ("TRASPASO CUENTAS PROPIAS", True, TRANSFER),
    ("PAGO INTERBANCARIO A BBVA MEXICO", False, SENT),
    ("TRANSFERENCIA SPEI", True, RECEIVED),
    ("TRANSFERENCIA SPEI", False, SENT),
    ("PAGO RECIBIDO DE BBVA MEXICO POR ORDEN DE PERSONA SINTETICA", True, RECEIVED),
    ("SPEI DEVUELTOBANAMEX", True, RETURNED),
    ("ABONO X DEV DE OP REF.0000007", True, RETURNED),
])
def test_classification_distinguishes_credits_returns_and_internal_movements(concept, received, label):
    original, _ = source("banamex", concept, received=received)
    bundle = WorkbookBundle.from_excel(original)
    row = rows(bundle.improved)[0]
    assert get(row, "Tipo de Operación") == (label or ("ABONO" if received else "CARGO"))
    assert "Clasificación SPEI" not in row
    query = queries_from_workbook(bundle.improved)[0]
    assert query.candidate == label.startswith("SPEI")
    assert bundle.original == original


CASES = [
    ("banamex", False,
     f"PAGO INTERBANCARIO A BANORTE AL BENEF. PERSONA SINTETICA "
     f"CTA,BENEFICIARIO [{OTHER} CLAVE RASTREQ: {KEY} REF.0000007", OTHER, "40072"),
    ("banamex", True,
     f"PAGO RECIBIDO DE BBVA MEXICO POR ORDEN DE PERSONA SINTETICA "
     f"CTA.ORDENANTE {BBVA} REF.0000007 RASTREO: [{KEY}", BBVA, "40012"),
    ("banorte", False,
     f"COMPRA 0RDEN DE PAG0 SPEl 0000007 =REFERENCIA CTA/CLABE: {CARD}, "
     f"SPEI BCO:012 BENEF:PERSONA SINTETICA CVE RASTREO: {KEY} RFC: ND", CARD, "40012"),
    ("banorte", True,
     f"{KEY} SPEI RECIBIDO, BCO:0012 BBVA MEXICO DEL CLIENTE PERSONA SINTETICA "
     f"DE LA CLABE {BBVA} CON RFC XXXX010101XXX CONCEPTO: PAGO SINTETICO "
     f"REFERENCIA: 0000007 CVE RAST: {KEY}", BBVA, "40012"),
    ("santander", False,
     f"PAGO TRANSFERENCIA SPE! HORA 12:00:00 ENVIADO A BANORTE A LA CUENTA {OTHER} "
     f"AL CLIENTE PERSONA SINTETICA CLAVE DE RASTREO {KEY} REF 0000007 CONCEPTO PAGO", OTHER, "40072"),
    ("santander", True,
     f"ABONO TRANSFERENCIA SPEI RECIBIDO DE BBVA MEXICO DE LA CUENTA {BBVA} "
     f"DEL CLIENTE PERSONA SINTETICA CLAVE DE RASTREO {KEY} REF 0000007 CONCEPTO PAGO", BBVA, "40012"),
    ("azteca", False,
     f"ORDEN DE TRANSFERENCIA SPEI RECEPTOR: BBVA MEXICO BENEF: PERSONA SINTETICA "
     f"CUENTA: {CARD} RASTREO: {KEY} REF: 0000007 CONCEPTO: PAGO", CARD, "40012"),
    ("azteca", True,
     f"TRANSFERENCIA SPEI A SU FAVOR EMISOR: BBVA MEXICO CUENTA: {BBVA} "
     f"NOM ORIGI: PERSONA SINTETICA RASTREO: {KEY} REF: 0000007 CONCEPTO: PAGO", BBVA, "40012"),
    ("bbva", False,
     f"SPEI ENVIADO BANORTE\n0000007PAGO SINTETICO\n00{OTHER}\n{KEY}\nPERSONA SINTETICA", OTHER, "40072"),
    ("bbva", True,
     f"SPEI RECIBIDOBANORTE\n0000007PAGO SINTETICO\n00{OTHER}\n{KEY}\nPERSONA SINTETICA", OTHER, "40072"),
    ("hsbc", False,
     f"CGO SPEI CUENTA BENEFICIARIO: {CARD} BANCO RECEPTOR: 40012 "
     f"CLAVE DE RASTREO: {KEY} REFERENCIA: 0000007", CARD, "40012"),
    ("nu", True,
     f"SPEI RECIBIDO BANCO EMISOR: BBVA MEXICO CUENTA ORDENANTE: {BBVA} "
     f"RASTREO: {KEY} REF: 0000007", BBVA, "40012"),
    ("scotiabank", False,
     f"SPEI ENVIADO BANCO RECEPTOR: BANORTE CUENTA BENEFICIARIO: {OTHER} "
     f"RASTREO: {KEY} REF: 0000007", OTHER, "40072"),
]


@pytest.mark.parametrize("bank,received,concept,counterparty,other_bank", CASES)
def test_recovery_fills_source_columns_and_all_six_txt_fields_with_correct_roles(bank, received, concept, counterparty, other_bank):
    original, own = source(bank, concept, received=received)
    bundle = WorkbookBundle.from_excel(original)
    row = rows(bundle.improved)[0]
    query = queries_from_workbook(bundle.improved)[0]
    assert query.ready, query.issues
    assert get(row, "Clave de Rastreo") == get(row, TXT_COLUMNS[1]) == KEY
    assert "Referencia SPEI" not in row
    original_row = rows(original)[0]
    assert extract_metadata(original_row, classify_spei(original_row)).reference == "0000007"
    assert query.operation_date == datetime(2026, 1, 3).date()
    assert str(query.value) == "125.25"
    assert query.destination == (own if received else counterparty)
    assert (query.issuer if received else query.receiver) == other_bank
    if received:
        assert "Cuenta del Ordenante" not in row and "CLABE del Ordenante" not in row
    else:
        assert get(row, "Cuenta del Beneficiario") == counterparty
    assert get(row, "Tipo de Operación") == (RECEIVED if received else SENT)
    for field in ("Concepto", "Concepto Original", "Cargo", "Abono", "Sucursal"):
        assert get(row, field) == get(rows(original)[0], field)
    assert bundle.original == original
    assert bundle.report.metadata_recovered > 0
    assert verify_pair(original, bundle.improved) == 1


@pytest.mark.parametrize("account", ["00" + CARD, "072180987654321099"])
@pytest.mark.parametrize("flattened", [False, True])
def test_bbva_account_checksum_never_suppresses_a_positioned_tracking_key(account, flattened):
    parts = ["SPEI ENVIADO BANORTE", "0000007PAGO", "00" + account, KEY, "PERSONA SINTETICA"]
    concept = (" " if flattened else "\n").join(parts)
    original, _ = source("bbva", concept)
    bundle = WorkbookBundle.from_excel(original)
    row = rows(bundle.improved)[0]
    assert get(row, "Clave de Rastreo") == KEY
    query = queries_from_workbook(bundle.improved)[0]
    assert query.ready, query.issues
    assert query.destination == (CARD if account == "00" + CARD else account)


def test_banorte_labeled_footer_wins_over_truncated_prefix_and_memo_imitations():
    concept = (f"SYNTHETIC2026 SPEI RECIBIDO, BCO:0012 DE LA CLABE {BBVA} "
               f"CONCEPTO: RASTREO: MEMOFALSO999 REFERENCIA: 0000007 CVE RAST: {KEY}")
    row = {"Banco": "banorte", "Concepto": concept, "Cargo": 0, "Abono": 125.25}
    md = extract_metadata(row, classify_spei(row))
    assert md.tracking == KEY and md.origin == BBVA
    assert md.notes


@pytest.mark.parametrize("corrupted", ["072180123O56789019", "072180 123O56789019", "072180 O12345678901"])
def test_an_ocr_letter_inside_an_account_cannot_produce_a_truncated_numeric_destination(corrupted):
    original, _ = source("banamex", f"PAGO INTERBANCARIO A BANORTE CTA.BENEFICIARIO {corrupted} CLAVE RASTREO {KEY}")
    bundle = WorkbookBundle.from_excel(original)
    query = queries_from_workbook(bundle.improved)[0]
    assert query.tracking == KEY and query.candidate and not query.ready
    assert not query.destination


def test_short_bco_codes_are_institutions_not_plazas():
    row = {"Banco": "banorte", "Concepto": f"COMPRA ORDEN DE PAGO SPEI CTA/CLABE: {CARD}, BCO:02 BENEF: PERSONA SINTETICA CVE RAST: {KEY}",
           "Cargo": 125.25, "Abono": 0}
    metadata = extract_metadata(row, classify_spei(row))
    assert metadata.bank == "40002" and metadata.destination == CARD


def test_bbva_bank_block_ignores_labels_inside_the_payment_memo_and_layout_noise():
    concept = (f"SPEI ENVIADO BANORTE\n0000007 RASTREO: MEMOFALSO999\n"
               f"NO. DE\nNO. DE\n00{OTHER}\n{KEY}\nPERSONA SINTETICA")
    original, _ = source("bbva", concept)
    query = queries_from_workbook(WorkbookBundle.from_excel(original).improved)[0]
    assert query.ready and query.tracking == KEY and query.destination == OTHER


def test_existing_txt_gaps_can_receive_new_evidence_without_overwriting_manual_values():
    concept = f"SPEI ENVIADO BANORTE\n0000007PAGO\n0000{CARD}\n{KEY}\nPERSONA SINTETICA"
    original, _ = source("bbva", concept)
    old = edit(original, dict(zip(TXT_COLUMNS, ["06/01/2026", None, "40012", "40072", None, 876.54])))
    bundle = WorkbookBundle.from_excel(old)
    query = queries_from_workbook(bundle.improved)[0]
    assert query.ready and query.tracking == KEY and query.destination == CARD
    assert query.operation_date.day == 6 and str(query.value) == "876.54"
    # Once recovered, clearing a blue cell is deliberate and stays cleared.
    cleared = edit(bundle.improved, {TXT_COLUMNS[1]: None})
    again = WorkbookBundle.from_excel(cleared).improved
    assert get(rows(again)[0], TXT_COLUMNS[1]) is None
    assert not queries_from_workbook(again)[0].ready


def test_newly_classified_cgo_in_a_prepared_workbook_keeps_the_movement_visible():
    original, _ = source("hsbc", "CGO PAGO SINTETICO")
    prepared = edit(original, {label: None for label in TXT_COLUMNS})
    bundle = WorkbookBundle.from_excel(prepared)
    query = queries_from_workbook(bundle.improved)[0]
    assert query.candidate and not query.ready
    assert get(rows(bundle.improved)[0], CLASSIFICATION_COLUMN) == SENT
    assert get(rows(bundle.improved)[0], TXT_COLUMNS[0]) is not None
    assert get(rows(bundle.improved)[0], TXT_COLUMNS[1]) is None


def test_excel_precision_loss_keeps_a_tracking_movement_classified_for_correction():
    original, _ = source("banamex", "TRANSFERENCIA", **{"Clave de Rastreo": 123456789012345678})
    bundle = WorkbookBundle.from_excel(original)
    query = queries_from_workbook(bundle.improved)[0]
    assert get(rows(bundle.improved)[0], CLASSIFICATION_COLUMN) == SENT
    assert query.candidate and not query.ready and not query.tracking


def test_explicit_tracking_in_a_generic_transfer_heading_prevents_losing_a_spei():
    concept = f"TRANSFERENCIA RECIBIDA BANCO EMISOR: BBVA MEXICO CLABE ORDENANTE: {BBVA} RASTREQ: {KEY}"
    original, own = source("nu", concept, received=True)
    bundle = WorkbookBundle.from_excel(original)
    query = queries_from_workbook(bundle.improved)[0]
    assert get(rows(bundle.improved)[0], CLASSIFICATION_COLUMN) == RECEIVED
    assert query.ready and query.tracking == KEY and query.destination == own


def test_returns_are_visible_but_not_routed_as_received_credits():
    original, _ = source("banorte", f"DEV.SPE: BCO:40012 CVE.RASTR: {KEY} REFERENCIA:0000007", received=True)
    bundle = WorkbookBundle.from_excel(original)
    query = queries_from_workbook(bundle.improved)[0]
    assert query.candidate and query.direction == "DEVUELTO" and not query.ready
    assert query.tracking == KEY and not query.destination
    assert not query.issuer and not query.receiver
    status = match_evidence([query], CepEvidence())[query.row]
    assert status["CEP Estado"] == "NO_CONSULTABLE"
    assert "TXT Cuenta Beneficiaria" in status["CEP Detalle"]
    corrected = edit(bundle.improved, dict(zip(TXT_COLUMNS, ["03/01/2026", KEY, "40072", "40012", CARD, 125.25])))
    assert queries_from_workbook(corrected)[0].ready


def test_existing_source_identifiers_and_all_manual_blue_values_win_over_recovery():
    concept = CASES[0][2]
    original, _ = source("banamex", concept, **{"Clave de Rastreo": "MANUALGREEN001"})
    manual = dict(zip(TXT_COLUMNS, ["07/01/2026", "MANUALBLUE002", "40021", "40012", CARD, 999.00]))
    original = edit(original, manual)
    bundle = WorkbookBundle.from_excel(original)
    row = rows(bundle.improved)[0]
    for label, value in manual.items():
        assert get(row, label) == value
    assert get(row, "Clave de Rastreo") == "MANUALGREEN001"
    assert "Revisión Normalización" not in row


@pytest.mark.parametrize("second_label", ["RASTREO", "RASTREQ"])
def test_multiple_labeled_keys_and_conflicting_banks_require_review(second_label):
    original, _ = source("banamex", f"PAGO INTERBANCARIO A BBVA MEXICO CTA.BENEFICIARIO {OTHER} "
                         f"RASTREO: {KEY} {second_label}: OTRACANDIDATA002")
    bundle = WorkbookBundle.from_excel(original)
    row = rows(bundle.improved)[0]
    assert get(row, "Clave de Rastreo") is None
    assert get(row, TXT_COLUMNS[1]) is None
    assert get(row, TXT_COLUMNS[3]) is None
    assert not queries_from_workbook(bundle.improved)[0].ready
    query = queries_from_workbook(bundle.improved)[0]
    status = match_evidence([query], CepEvidence())[query.row]
    assert status["CEP Estado"] == "NO_CONSULTABLE"
    assert "TXT Clave de Rastreo" in status["CEP Detalle"]


def test_verification_rejects_changes_to_existing_source_and_manual_txt_data():
    original, _ = source("banamex", CASES[0][2], **{"Clave de Rastreo": "MANUALGREEN001"})
    bundle = WorkbookBundle.from_excel(original)
    for label, value in [("Cargo", 9999), ("Concepto", "ALTERADO"), ("Clave de Rastreo", "ALTERADO002")]:
        with pytest.raises(ValueError, match="detectó cambio"):
            verify_pair(original, edit(bundle.improved, {label: value}), report=bundle.report)
    prepared = bundle.improved
    rerun = WorkbookBundle.from_excel(prepared)
    with pytest.raises(ValueError, match="detectó cambio"):
        verify_pair(prepared, edit(rerun.improved, {TXT_COLUMNS[5]: 9999}), report=rerun.report)


def test_classifier_is_only_in_the_application_and_layout_colors_remain_separate():
    original, _ = source("banamex", CASES[0][2])
    bundle = WorkbookBundle.from_excel(original)
    wb = load_workbook(BytesIO(bundle.improved))
    try:
        assert "Clasificador SPEI" not in wb
        assert len(CLASSIFIER_RULES) == 57
        assert wb["Catálogo Bancos"].max_row == 98
        ws = wb["Movimientos"]
        headers = {cell.value: cell for cell in ws[1]}
        assert headers[CLASSIFICATION_COLUMN].fill.fgColor.rgb == "001F4D3A"
        names = list(headers)
        start = names.index(TXT_COLUMNS[0])
        assert names[start - len(TRACE_COLUMNS):start] == list(TRACE_COLUMNS)
        assert not any(header_key(name) in RETIRED_KEYS for name in names)
        assert all(headers[label].fill.fgColor.rgb == "00156082" for label in TXT_COLUMNS)
    finally:
        wb.close()
