"""Regresiones del parser Azteca con datos exclusivamente sintéticos."""

from __future__ import annotations

import copy

import pytest

from detectors.bank_detector import identify_bank_key
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from models.movimiento import Movimiento
from models.processing_result import ProcessingResult
from parsers.azteca import parse_azteca
from parsers.azteca.extractors.movimientos import enrich_movement_metadata_from_concepto
from readers.models.document_data import DocumentData


def line(text: str, y: float, page: int = 1, x: float = 130.0) -> list[dict]:
    words = []
    for token in text.split():
        width = len(token) * 4
        words.append(
            {
                "text": token,
                "x0": x,
                "x1": x + width,
                "top": y,
                "bottom": y + 10,
                "page": page,
            }
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


def synthetic_statement_words() -> list[dict]:
    """Estado representativo construido a mano, sin contenido de documentos reales."""
    return (
        line("Banco Azteca", 20, x=350)
        + line("PERSONA PRUEBA", 45, x=55)
        + line("No. Cliente: 90000000", 60, x=55)
        + line("RFC: XAXX010101000", 75, x=55)
        + line("No. Cuenta: 90000000000000", 90, x=55)
        + line("Cuenta CLABE: 127180000000000001", 105, x=55)
        + line("Tipo de Cuenta: GUARDADITO DIGITAL", 120, x=55)
        + line(
            "Periodo: del 01 de septiembre 2026 al 30 de septiembre 2026",
            135,
            x=55,
        )
        + line("Fecha de corte: 30 de septiembre 2026", 150, x=55)
        + line("Resumen Mensual", 175, x=65)
        + line("Saldo Inicial al 31 de agosto 2026 = $100.00", 195, x=65)
        + line("Depósitos del Periodo $150.00", 210, x=65)
        + line("Retiros del Periodo $120.00", 225, x=65)
        + line("Saldo Final al 30 de septiembre 2026 = $130.00", 240, x=65)
        + line("Saldo promedio del mes* $110.00", 255, x=65)
        + line("# de días del mes 30", 270, x=65)
        + line("Tasa de interés anualizada 0.01%", 285, x=65)
        + line("Interés Recibido $0.00", 300, x=65)
        + line("Impuesto Retenido = $0.00", 315, x=65)
        + line("Comisiones (-) $0.00", 330, x=65)
        + line("Total Depósitos del mes", 360, x=65)
        + table_header(375)
        + row("05/09/2026", "TRANSFERENCIA SPEI A SU FAVOR", "(+) $150.00", 395)
        + line("EMISOR: BBVA MEXICO", 410)
        + line("CUENTA: 012180000000000001", 425)
        + line("NOM ORIGI: PERSONA EJEMPLO", 440)
        + line("RASTREO: TEST-IN-0001", 455)
        + line("REF: 0000001", 470)
        + line("CONCEPTO: prueba", 485)
        + line("Total $150.00", 500, x=65)
        + line("Total de Retiros del mes", 530, x=65)
        + table_header(545)
        + row("10/09/2026", "PAGO SERVICIO", "(-) $100.00", 565)
        + row("20/09/2026", "ORDEN DE TRANSFERENCIA SPEI", "(-) $20.00", 590)
        + line("RECEPTOR: BBVA MEXICO", 605)
        + line(
            "NOM BENEF: PERSONA EJEMPLO DATO NO VERIFICADO POR ESTA INSTITUCION.",
            620,
        )
        + line("RASTREO: TEST-OUT-0001", 635)
        + line("REF: 0000002", 650)
        + line("CONCEPTO: prueba", 665)
        + line("Total $120.00", 680, x=65)
    )


def test_synthetic_statement_extracts_account_summary_and_movements() -> None:
    words = synthetic_statement_words()
    before = copy.deepcopy(words)
    state = parse_azteca(DocumentData(spatial_words=words))
    account = state.datos_cuenta
    summary = state.resumen_financiero

    assert account.nombre_cliente == "PERSONA PRUEBA"
    assert account.rfc == "XAXX010101000"
    assert account.numero_cliente == "90000000"
    assert account.numero_cuenta == "90000000000000"
    assert account.clabe == "127180000000000001"
    assert account.producto_principal == "GUARDADITO DIGITAL"
    assert account.periodo_inicio == "01/09/2026"
    assert account.periodo_fin == account.fecha_corte == "30/09/2026"

    assert summary.saldo_anterior == 100.0
    assert summary.depositos_abonos == 150.0
    assert summary.retiros_cargos == 120.0
    assert summary.total_retiros_tabla == 120.0
    assert summary.saldo_final == summary.saldo_global == 130.0
    assert summary.saldo_promedio == 110.0
    assert summary.dias_periodo == 30
    assert summary.tasa_bruta_anual == 0.01
    assert summary.intereses_a_favor == summary.isr_retenido == 0.0

    assert len(state.movimientos) == 3
    assert sum(m.abono for m in state.movimientos) == 150.0
    assert sum(m.cargo for m in state.movimientos) == 120.0
    incoming = state.movimientos[0]
    assert incoming.beneficiario == "PERSONA EJEMPLO"
    assert incoming.cuenta_beneficiario == incoming.clabe_beneficiario == "012180000000000001"
    assert incoming.sucursal == "BBVA MEXICO"
    assert incoming.clave_rastreo == "TEST-IN-0001"
    assert incoming.referencia == "0000001"
    assert incoming.concepto_original == "prueba"
    outgoing = state.movimientos[-1]
    assert outgoing.beneficiario == "PERSONA EJEMPLO"
    assert outgoing.sucursal == "BBVA MEXICO"
    assert outgoing.clave_rastreo == "TEST-OUT-0001"
    assert outgoing.referencia == "0000002"
    assert outgoing.concepto_original == "prueba"
    assert state.otros_productos.producto == "N/A"
    assert words == before


@pytest.mark.parametrize("scale,offset", [(0.6, 0), (1.0, 25), (2.0, 10)])
def test_scaled_shifted_and_unordered_synthetic_words(scale: float, offset: float) -> None:
    words = synthetic_statement_words()
    expected = parse_azteca(DocumentData(spatial_words=copy.deepcopy(words)))
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
        + line("TEST-CROSS-0001 REF: 1234567", 100, 2)
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
    assert movement.clave_rastreo == "TEST-CROSS-0001"
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
        "CUENTA: 0000000001 CLABE: 002180000000000001 RASTREO: TEST-META-0001 REF: 9 "
        "RFC: XAXX010101000 AUT: 0001 CAJA: 2 HORA: 10:30:00 CONCEPTO: compra de comida",
        "CARGO",
        10.0,
        0.0,
    )
    enriched = enrich_movement_metadata_from_concepto(movement)
    assert enriched.beneficiario == "Persona Ejemplo"
    assert enriched.cuenta_beneficiario == "0000000001"
    assert enriched.clabe_beneficiario == "002180000000000001"
    assert enriched.sucursal == "BANAMEX"
    assert enriched.rfc == "XAXX010101000"
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


def test_existing_export_mapper_preserves_full_synthetic_concept_and_memo() -> None:
    state = parse_azteca(DocumentData(spatial_words=synthetic_statement_words()))
    result = ProcessingResult("Azteca.pdf", "azteca", state, "", "", processing_method="OCR")
    tables = estado_cuenta_to_tables([result])
    movement = tables["Movimientos"][0]
    assert movement["Concepto"] == state.movimientos[0].concepto
    assert movement["Concepto Original"] == "prueba"
    assert movement["Beneficiario"] == "PERSONA EJEMPLO"
    assert movement["Sucursal"] == "BBVA MEXICO"
    assert movement["Cuenta del Beneficiario"] == "012180000000000001"
    assert movement["CLABE del Beneficiario"] == "012180000000000001"
