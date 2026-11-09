"""Known SPEI bank roles and preservation of the analyst's workbook format.

All identifiers, concepts and participants below are synthetic.
"""

from copy import copy
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from cep.evidence import CepEvidence, match_evidence
from cep.package import append_cep
from cep.queries import queries_from_workbook
from exporters.excel.normalization import CEP_QUERY_INPUT_HEADERS, get, header_key, rows_from_sheet
from exporters.excel.workbook_bundle import WorkbookBundle


def clabe(prefix):
    stem = prefix + "18012345678901"
    total = sum(int(c) * (3, 7, 1)[i % 3] % 10 for i, c in enumerate(stem))
    return stem + str((10 - total % 10) % 10)


HOLDER = clabe("002")
SENDER = clabe("012")
CARD = "4111111111111111"


def source(*, received=True, old=False, third_bank="BBVA MEXICO", changes=None):
    wb = Workbook()
    acc = wb.active
    acc.title = "Datos de la Cuenta"
    acc.append(["id_estado", "Nombre del Archivo", "Banco", "Número de Cuenta",
                "CLABE", "Periodo de Inicio", "Periodo de Fin", "Fecha de Corte"])
    acc.append([1, "SINTETICO.pdf", "banamex", "12345678901", HOLDER,
                "01/01/2026", "31/01/2026", "31/01/2026"])
    concept = (f"PAGO RECIBIDO DE {third_bank} POR ORDEN DE PERSONA SINTETICA "
               "REF.0000007 RASTREO: SINTETICORECIBIDO001" if received else
               f"PAGO INTERBANCARIO A {third_bank} AL BENEF. PERSONA SINTETICA "
               f"CTA.BENEFICIARIO 00{CARD} CLAVE RASTREO SINTETICOENVIADO001")
    values = {
        "id_estado": 1, "Nombre del Archivo": "SINTETICO.pdf", "Banco": "banamex",
        "Fecha de Corte": "31/01/2026", "Número de Cuenta": "12345678901",
        "No. de Movimiento": 1, "Fecha de Operación": "17/01/2026",
        "Concepto": concept, "Tipo de Operación": "ABONO" if received else "CARGO",
        "Cargo": 0 if received else 2000, "Abono": 2000 if received else 0,
        "Saldo de Operación": 5000, "Referencia": "0000007",
        "Clave de Rastreo": "SINTETICORECIBIDO001" if received else "SINTETICOENVIADO001",
        "Beneficiario": "PERSONA SINTETICA", "CLABE del Beneficiario": None if received else "00" + CARD,
        "Cuenta del Beneficiario": None if received else "00" + CARD,
        "Sucursal": third_bank, "Banco del Beneficiario": None,
        "Código Banco Beneficiario": None, "Código Plaza/Producto CLABE": None,
        "CLABE del Ordenante": None,
    }
    if not old:
        values["CLABE Titular"] = HOLDER
    values.update(changes or {})
    ws = wb.create_sheet("Movimientos")
    ws.append(list(values))
    ws.append(list(values.values()))
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="1F4D3A")
        cell.font = Font(name="Arial", color="FFFFFF", bold=True, size=11)
    data = BytesIO()
    wb.save(data)
    wb.close()
    return data.getvalue()


def movement(content):
    wb = load_workbook(BytesIO(content))
    try:
        return rows_from_sheet(wb["Movimientos"])[0]
    finally:
        wb.close()


@pytest.mark.parametrize("old", [False, True])
def test_received_banks_use_the_holder_and_no_sender_clabe_is_invented(old):
    original = source(old=old)
    before = queries_from_workbook(WorkbookBundle.from_uploaded(original).improved)[0]
    bundle = WorkbookBundle.from_excel(original)
    row = movement(bundle.improved)
    assert bundle.original == original
    assert get(row, "Banco del Beneficiario") == "BANAMEX"
    assert get(row, "Código Banco Beneficiario") == "40002"
    assert get(row, "Código Plaza/Producto CLABE") == "180"
    assert get(row, "Banco Emisor") == "BBVA MEXICO"
    assert get(row, "CLABE del Ordenante") is None
    assert get(row, "Sucursal") == "BBVA MEXICO"
    after = queries_from_workbook(bundle.improved)[0]
    assert before.ready and after.ready
    assert before.line() == after.line()
    assert (after.issuer, after.receiver, after.destination) == ("40012", "40002", HOLDER)
    assert after.line().endswith(f",40012,40002,{HOLDER},2000.00")
    again = WorkbookBundle.from_excel(bundle.improved).improved
    assert queries_from_workbook(again)[0].line() == after.line()
    wb = load_workbook(BytesIO(again))
    labels = [c.value for c in wb["Movimientos"][1]]
    assert labels.count("Banco del Beneficiario") == labels.count("Banco Emisor") == 1
    wb.close()


@pytest.mark.parametrize("bank,code", [("BBVA MEXICO", "40012"), ("AZTECA", "40127")])
def test_sent_card_gets_labelled_bank_and_code_but_no_fabricated_plaza(bank, code):
    original = source(received=False, third_bank=bank)
    before = queries_from_workbook(original)[0]
    bundle = WorkbookBundle.from_excel(original)
    row = movement(bundle.improved)
    assert get(row, "Banco del Beneficiario") == bank
    assert get(row, "Código Banco Beneficiario") == code
    assert get(row, "Código Plaza/Producto CLABE") is None
    assert get(row, "CLABE del Beneficiario") == "00" + CARD
    after = queries_from_workbook(bundle.improved)[0]
    assert before.ready and after.ready and before.line() == after.line()
    assert after.destination == CARD and after.receiver == code


def test_unknown_card_bank_is_not_guessed_from_the_sixteen_digits():
    bundle = WorkbookBundle.from_excel(source(received=False, third_bank="DESCONOCIDO"))
    row = movement(bundle.improved)
    assert get(row, "Banco del Beneficiario") is None
    assert get(row, "Código Banco Beneficiario") is None
    assert get(row, "Código Plaza/Producto CLABE") is None
    assert not queries_from_workbook(bundle.improved)[0].ready


def test_received_sender_clabe_is_preserved_when_the_statement_actually_provides_it():
    original = source(changes={"CLABE del Ordenante": SENDER})
    bundle = WorkbookBundle.from_excel(original)
    assert get(movement(bundle.improved), "CLABE del Ordenante") == SENDER
    q = queries_from_workbook(bundle.improved)[0]
    assert q.ready and q.destination == HOLDER and SENDER in q.origin_aliases


def test_user_corrections_in_bank_columns_are_preserved():
    original = source(changes={"Banco del Beneficiario": "CITIBANAMEX",
        "Código Banco Beneficiario": "002", "Código Plaza/Producto CLABE": "999"})
    row = movement(WorkbookBundle.from_excel(original).improved)
    assert get(row, "Banco del Beneficiario") == "CITIBANAMEX"
    assert get(row, "Código Banco Beneficiario") == "002"
    assert get(row, "Código Plaza/Producto CLABE") == "999"


@pytest.mark.parametrize("cross", [False, True])
def test_yellow_txt_headers_keep_other_green_headers_and_body_styles(cross):
    original = source()
    bundle = WorkbookBundle.from_excel(original)
    evidence = CepEvidence()
    qs = queries_from_workbook(bundle.improved)
    content = (append_cep(bundle.improved, match_evidence(qs, evidence), qs, evidence)
               if cross else bundle.improved)
    wb, result = (load_workbook(BytesIO(data)) for data in (original, content))
    try:
        source_ws, final_ws = wb["Movimientos"], result["Movimientos"]
        old_headers = {c.value: c for c in source_ws[1]}
        final_headers = {c.value: c for c in final_ws[1]}
        for label, old in old_headers.items():
            new = final_headers[label]
            if header_key(label) in CEP_QUERY_INPUT_HEADERS:
                assert new.fill.fgColor.rgb == "00FFF2CC"
                assert new.font.color.rgb == "00202124"
                assert (new.font.name, new.font.bold, new.font.sz) == (old.font.name, old.font.bold, old.font.sz)
            else:
                assert copy(new.fill) == copy(old.fill)
                assert copy(new.font) == copy(old.font)
                assert new.fill.fgColor.rgb == "001F4D3A"
            old_body = source_ws.cell(2, old.column)
            new_body = final_ws.cell(2, new.column)
            assert copy(new_body.fill) == copy(old_body.fill)
            assert copy(new_body.font) == copy(old_body.font)
    finally:
        wb.close()
        result.close()
