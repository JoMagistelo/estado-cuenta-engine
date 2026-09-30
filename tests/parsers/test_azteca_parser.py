"""Regresiones Azteca: nueve muestras OCR anonimizadas y casos parciales.

Las muestras conservan coordenadas, importes, fechas y errores del OCR; omiten
domicilios/CFDI y sustituyen nombres, RFC, cuentas, créditos y rastreos. El formato
compacto por línea es [página, [[texto, x0, x1, top, bottom], ...]].
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from detectors.bank_detector import identify_bank_key
from engine.statement_processor import process_single_statement
from models.movimiento import Movimiento
from models.processing_result import ProcessingResult
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from parsers.azteca import parse_azteca
from parsers.azteca.extractors.movimientos import enrich_movement_metadata_from_concepto
from readers.models.document_data import DocumentData
from validators.movimiento_validator import validar_movimientos

FIXTURES = Path(__file__).parent / "fixtures" / "azteca"
# Valores contrastados con los renglones OCR, sin ajustar diferencias al resumen.
# cantidad, abonos, cargos, inicio, fin, promedio, días impresos, saldo final
CASES = {
    "ene": (20, 2094.00, 2114.00, "29/12/2025", "27/01/2026", 61.63, 31, 0.92),
    "feb": (24, 3831.63, 3829.43, "28/01/2026", "27/02/2026", 26.41, 31, 3.55),
    "mar": (6, 2600.00, 2524.81, "28/02/2026", "27/03/2026", 3.62, 28, 79.55),
    "abr": (14, 2892.47, 2904.00, "28/03/2026", "27/04/2026", 64.16, 31, 68.02),
    "may": (13, 2403.94, 2423.00, "28/04/2026", "27/05/2026", 35.40, 30, 48.96),
    "jun": (12, 2321.00, 2332.00, "28/05/2026", "28/06/2026", 28.44, 31, 37.96),
    "jun_2": (3, 677.00, 550.00, "27/06/2026", "30/06/2026", 40.96, 4, 164.96),
    "jul": (16, 28288.00, 28260.00, "01/07/2026", "31/07/2026", 152.70, 31, 192.96),
    "ago": (12, 4400.00, 4592.00, "01/08/2026", "31/08/2026", 15.73, 31, 0.96),
}


def fixture_words(case: str) -> list[dict]:
    fixture = json.loads((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))
    words = []
    for page, row in fixture["lines"]:
        for text, x0, x1, top, bottom in row:
            words.append(
                {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "page": page}
            )
    return words


def line(text: str, y: float, page: int = 1, x: float = 130.0) -> list[dict]:
    words = []
    for token in text.split():
        width = len(token) * 4
        words.append(
            {"text": token, "x0": x, "x1": x + width, "top": y, "bottom": y + 10, "page": page}
        )
        x += width + 3
    return words


def row(date: str, concept: str, amount: str, y: float, page: int = 1) -> list[dict]:
    return (
        line(date, y, page, 65)
        + line(concept, y, page)
        + line(amount, y, page, 330)
        + line("SPEI", y, page, 490)
    )


def table_header(y: float, page: int = 1) -> list[dict]:
    return (
        line("Fecha", y, page, 75)
        + line("Concepto", y, page, 205)
        + line("Monto de la Operación", y, page, 332)
    )


@pytest.mark.parametrize("case", CASES)
def test_nine_ocr_layouts_extract_all_movements_and_account(case: str) -> None:
    words = fixture_words(case)
    before = copy.deepcopy(words)
    state, document = process_single_statement(
        DocumentData(spatial_words=words, metadata={"ocr": True, "reader": "paddleocr"}),
        "azteca",
    )
    count, abonos, cargos, start, end, average, days, final = CASES[case]
    account, summary = state.datos_cuenta, state.resumen_financiero
    assert len(state.movimientos) == count
    assert sum(m.abono for m in state.movimientos) == pytest.approx(abonos)
    assert sum(m.cargo for m in state.movimientos) == pytest.approx(cargos)
    assert account.periodo_inicio == start
    assert account.periodo_fin == account.fecha_corte == end
    assert account.producto_principal == "GUARDADITO DIGITAL"
    assert account.numero_cuenta == "90000000000000"
    assert account.clabe == "127180000000000001"
    recent = case in {"jun_2", "jul", "ago"}
    assert account.nombre_cliente == (
        "ANDREA PRUEBA EJEMPLO" if recent else "PRUEBA EJEMPLO ANDREA"
    )
    assert account.rfc == ("PEPA900101ABC" if recent else "XAXX010101000")
    assert account.numero_cliente == ("900000000" if recent else "90000000")
    assert summary.saldo_promedio == average
    assert summary.dias_periodo == days
    assert summary.saldo_final == summary.saldo_global == final
    assert summary.depositos_abonos == abonos
    assert summary.intereses_a_favor == summary.isr_retenido == 0.0
    assert summary.manejo_cuenta == (0.01 if case == "jul" else 0.0)
    assert state.otros_productos.producto == "N/A"
    for movement in state.movimientos:
        assert movement.fecha_operacion
        assert movement.fecha_liquidacion is None
        assert movement.tipo_operacion == ("ABONO" if movement.abono else "CARGO")
        assert not any(
            t in movement.concepto
            for t in [
                "Continúa",
                "Hoja",
                "Total ",
                "ELECT/SUCURSAL",
                "Este documento",
                "Saldo promedio",
                "Inversión Azteca",
                "Lugar o Canal",
            ]
        )
    assert words == before  # No normalización global ni mutación de las words.
    assert document.spatial_words is words


@pytest.mark.parametrize(
    "case,received", [("feb", 8), ("mar", 2), ("abr", 6), ("may", 5), ("jun", 4)]
)
def test_detailed_spei_metadata_and_concept_semantics(case: str, received: int) -> None:
    state = parse_azteca(DocumentData(spatial_words=fixture_words(case)))
    incoming = [m for m in state.movimientos if m.abono]
    assert len(incoming) == received
    for movement in incoming:
        assert movement.beneficiario == "ANDREA PRUEBA EJEMPLO"
        assert movement.cuenta_beneficiario == movement.clabe_beneficiario == "012180000000000001"
        assert movement.sucursal == "BBVA MEXICO"
        assert movement.clave_rastreo.startswith("TEST")
        assert movement.referencia == "0000001"
        assert movement.concepto_original in {"pago", "transferencia", "pagi"}
        assert movement.concepto.startswith(
            "TRANSFERENCIA SPEI A SU FAVOR EMISOR:"
        ) or movement.concepto.startswith("TRANSFEREÑCIA SPEI A SU FAVOR EMISOR:")
        assert "CUENTA:" in movement.concepto and "CONCEPTO:" in movement.concepto


def test_outgoing_spei_does_not_invent_account_or_include_disclaimer_in_name() -> None:
    state = parse_azteca(DocumentData(spatial_words=fixture_words("feb")))
    outgoing = [m for m in state.movimientos if m.cargo and m.clave_rastreo]
    assert [m.cargo for m in outgoing] == [600.0, 200.0]
    for movement in outgoing:
        assert movement.beneficiario == "Andrea Prueba"
        assert movement.sucursal == "BBVA MEXICO"
        assert movement.cuenta_beneficiario is movement.clabe_beneficiario is None
        assert movement.concepto_original == "j"
        assert "DATO NO VERIFICADO" in movement.concepto


@pytest.mark.parametrize("case", ["ene", "jun_2", "jul", "ago"])
def test_brief_spei_keeps_unknown_metadata_empty(case: str) -> None:
    state = parse_azteca(DocumentData(spatial_words=fixture_words(case)))
    for movement in state.movimientos:
        assert movement.beneficiario is None
        assert movement.cuenta_beneficiario is movement.clabe_beneficiario is None
        assert movement.concepto_original is None
        if movement.abono and "SPEI" in movement.concepto:
            assert movement.sucursal is None
    if case in {"jul", "ago"}:
        assert any(m.concepto == "RENOVACION PRESTAMOS PERSONALES" for m in state.movimientos)
        assert any("BAZ" in m.concepto for m in state.movimientos if m.cargo)


def test_unexplained_ocr_inconsistency_remains_visible() -> None:
    state = parse_azteca(DocumentData(spatial_words=fixture_words("jun_2")))
    assert state.resumen_financiero.retiros_cargos == 550.0
    failures = [
        r
        for r in validar_movimientos(state.movimientos, state.resumen_financiero)
        if not r.correcto
    ]
    assert [(r.nombre, round(r.diferencia, 2)) for r in failures] == [
        ("Ecuación financiera", -37.96)
    ]


@pytest.mark.parametrize("scale,offset", [(0.6, 0), (1.0, 25), (2.0, 10)])
def test_scaled_shifted_and_unordered_ocr_words(scale: float, offset: float) -> None:
    words = fixture_words("abr")
    expected = parse_azteca(DocumentData(spatial_words=words))
    for word in words:
        for key in ["x0", "x1", "top", "bottom"]:
            word[key] = word[key] * scale + offset
    assert parse_azteca(DocumentData(spatial_words=words[::-1])) == expected


def test_cross_page_detail_and_multiline_memo_with_bank_named_by_counterparty() -> None:
    words = (
        line("Total Depósitos del mes", 380)
        + table_header(415)
        + row("01/09/2026", "TRANSFERENCIA SPEI A SU FAVOR", "(+) $150.00", 440)
        + line("EMISOR: BANAMEX", 460)
        + line("CUENTA: 002180000000000001", 475)
        + line("NOM ORIGI: Persona", 490)
        + line("Ejemplo", 505)
        + line("RASTREO:", 520)
        + line("Continúa en la siguiente hoja", 700)
        + line("Este documento es una representación impresa de un CFDI", 750)
        + line("Banco Azteca", 40, 2, 350)
        + table_header(80, 2)
        + line("ABC123 REF: 1234567", 100, 2)
        + line("CONCEPTO: compra de", 120, 2)
        + line("comida", 135, 2)
        + row("02/09/2026", "TRANSFERENCIA SPEI A SU FAVOR", "(+) $20.00", 155, 2)
        + line("Total $170.00", 175, 2)
        + line("Para fines informativos", 200, 2)
        + row("03/09/2026", "NO ES MOVIMIENTO", "(+) $999.00", 220, 2)
    )
    movements = parse_azteca(DocumentData(spatial_words=words)).movimientos
    assert len(movements) == 2
    movement = movements[0]
    assert movement.beneficiario == "Persona Ejemplo"
    assert movement.sucursal == "BANAMEX"
    assert movement.cuenta_beneficiario == movement.clabe_beneficiario == "002180000000000001"
    assert movement.clave_rastreo == "ABC123"
    assert movement.referencia == "1234567"
    assert movement.concepto_original == "compra de comida"
    assert movement.concepto.endswith("CONCEPTO: compra de comida")
    assert movements[1].concepto_original is None


def test_partial_rows_and_unsigned_amounts_keep_table_direction_without_merging() -> None:
    words = (
        line("Total de Retiros del mes", 100)
        + table_header(120)
        + row("01/09/2026", "ABONO A CREDITO GLOBAL", "$15.00", 140)
        + row("02/09/2026", "CONCEPTO SIN MONTO", "", 165)
        + row("", "", "(-) $5.00", 190)
        + row("03/09/2026", "PAGO DE CREDITO", "-$10.00", 215)
        + line("Total $30.00", 240)
    )
    movements = parse_azteca(DocumentData(spatial_words=words)).movimientos
    assert len(movements) == 4
    assert [m.cargo for m in movements] == [15.0, 0.0, 5.0, 10.0]
    assert [m.concepto for m in movements] == [
        "ABONO A CREDITO GLOBAL",
        "CONCEPTO SIN MONTO",
        "",
        "PAGO DE CREDITO",
    ]
    assert movements[2].fecha_operacion == ""
    assert all(m.abono == 0.0 for m in movements)


def test_separate_account_and_clabe_and_other_labeled_metadata() -> None:
    movement = Movimiento(
        "01/09/2026",
        None,
        "ORDEN DE TRANSFERENCIA SPEI RECEPTOR: BANAMEX NOM BENEF: Persona Ejemplo "
        "CUENTA: 0001234567 CLABE: 002180000000000001 RASTREO: ABC123 REF: 9 "
        "RFC: PEPA900101ABC AUT: 0001 CAJA: 2 HORA: 10:30:00 CONCEPTO: compra de comida",
        "CARGO",
        10.0,
        0.0,
    )
    enriched = enrich_movement_metadata_from_concepto(movement)
    assert enriched.beneficiario == "Persona Ejemplo"
    assert enriched.cuenta_beneficiario == "0001234567"
    assert enriched.clabe_beneficiario == "002180000000000001"
    assert enriched.sucursal == "BANAMEX"
    assert enriched.rfc == "PEPA900101ABC"
    assert enriched.autorizacion == "0001"
    assert enriched.caja == "2"
    assert enriched.hora_operacion == "10:30:00"
    assert enriched.concepto_original == "compra de comida"


def test_user_memo_with_label_like_text_is_preserved_verbatim() -> None:
    movement = Movimiento(
        "01/09/2026",
        None,
        "TRANSFERENCIA SPEI A SU FAVOR EMISOR: BANAMEX REF: 123 "
        "CONCEPTO: compra de comida REF: cena RFC: pendiente",
        "ABONO",
        0.0,
        10.0,
    )
    enriched = enrich_movement_metadata_from_concepto(movement)
    assert enriched.concepto_original == "compra de comida REF: cena RFC: pendiente"
    assert enriched.referencia == "123"
    assert enriched.rfc is None


@pytest.mark.parametrize(
    "text,filename",
    [
        ("Cuenta CLABE: 127180000000000001", "archivo_renombrado.pdf"),
        ("", "12.3_Débito_Banco Azteca_Ene_ESCANEADO.pdf"),
        ("", "AZTECA.pdf"),
    ],
)
def test_azteca_bank_detection(text: str, filename: str) -> None:
    assert identify_bank_key(text, filename) == "azteca"


def test_missing_summary_does_not_synthesize_financial_totals() -> None:
    state = parse_azteca(DocumentData())
    assert state.movimientos == []
    assert state.resumen_financiero.saldo_anterior is None
    assert state.resumen_financiero.depositos_abonos is None
    assert state.resumen_financiero.retiros_cargos is None
    assert state.resumen_financiero.saldo_final is None


def test_existing_export_mapper_preserves_full_concept_and_user_memo() -> None:
    state = parse_azteca(DocumentData(spatial_words=fixture_words("abr")))
    result = ProcessingResult("Azteca.pdf", "azteca", state, "", "", processing_method="OCR")
    tables = estado_cuenta_to_tables([result])
    movement = tables["Movimientos"][0]
    assert movement["Concepto"] == state.movimientos[0].concepto
    assert movement["Concepto Original"] == "pago"
    assert movement["Beneficiario"] == "ANDREA PRUEBA EJEMPLO"
    assert movement["Sucursal"] == "BBVA MEXICO"
    assert movement["Cuenta del Beneficiario"] == "012180000000000001"
    assert movement["CLABE del Beneficiario"] == "012180000000000001"
