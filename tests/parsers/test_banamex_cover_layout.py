"""Regresiones ficticias de portadas etiquetadas y fin de detalle Banamex."""

from __future__ import annotations

import copy
import random
from dataclasses import asdict

import pytest

from parsers.banamex import parse_banamex
from parsers.banamex.extractors.movimientos import normalize_movement_date_text
from parsers.banamex.extractors.movimientos import is_money, parse_amount
from readers.models import DocumentData
from validators.movimiento_validator import validar_movimientos


def line(text, y, x=30, page=1):
    result = []
    for token in text.split():
        width = len(token) * 3
        result.append(dict(text=token, x0=x, x1=x + width, top=y, bottom=y + 8, page=page))
        x += width + 2
    return result


def cover_words(*, opening=1200, deposit=700, charge=225, month="enero", end="febrero", days=31):
    final = opening + deposit - charge
    words = (
        line("Estado de Cuenta", 65, 320)
        + line("PERSONA DEMOSTRACION", 85, 45)
        + line("MiCuenta", 85, 320)
        + line(f"Periodo del 16 de {month} al 15 de {end} del 2030", 120, 320)
        + line("Fecha de Corte", 155)
        + line(f"15 de {end} de 2030", 155, 185)
    )
    for y, label, value in (
        (200, "Numero de contrato", "12345000000"),
        (215, "Numero de cuenta de cheques", "12345000001"),
        (230, "Numero de cliente", "10000001"),
        (245, "CLABE Interbancaria", "002180000000000001"),
        (260, "RFC", "DEMO010101AA1"),
    ):
        words += line(label, y) + line(value, y, 205)
    words += line("Resumen En Pesos Moneda Nacional", 330)
    for y, label, value in (
        (345, "Saldo anterior", opening),
        (357, "Depositos", deposit),
        (369, "Retiros en efectivo", 25),
        (381, "Otros cargos", charge - 25),
        (393, "Saldo al corte", final),
        (405, "Saldo promedio mensual", opening + 100),
    ):
        words += line(label, y) + line(f"{value:,.2f}", y, 250)
    # El gráfico de la columna derecha no aporta valores al resumen.
    words += line("Saldo anterior $99,999.00", 345, 365)
    words += line("Depositos $88,888.00", 357, 365)
    words += line("Comisiones efectivamente cobradas $0.00", 185, 320)
    words += line(f"Resumen del 16 de {month} al 15 de {end} del 2030", 75, page=2)
    for y, label, value in (
        (95, "Saldo anterior En pesos M.N.", opening),
        (107, "(+) 1 Depositos", deposit),
        (119, "(-) 1 Retiros/Otros cargos", charge),
        (131, "Saldo al Corte", final),
        (155, "Saldo promedio mensual", opening + 100),
        (179, "Intereses", 0),
        (191, "Impuesto Sobre la Renta retenido", 0),
    ):
        words += line(label, y, page=2) + line(f"{value:,.2f}", y, 480, 2)
    words += line(f"Dias del periodo {days}", 143, page=2)
    words += line("Tasa de interes Bruta 0.1500%", 167, page=2)
    words += line("Detalle de Operaciones", 210, page=2)
    for label, x in (
        ("FECHA", 30),
        ("CONCEPTO", 100),
        ("RETIROS", 350),
        ("DEPOSITOS", 430),
        ("SALDO", 520),
    ):
        words += line(label, 230, x, 2)
    abbreviation = "ENE" if month == "enero" else "FEB"
    words += line(f"17 {abbreviation}", 250, page=2) + line("ABONO PRUEBA", 250, 100, 2)
    words += line(f"{deposit:,.2f}", 250, 440, 2) + line(f"{opening + deposit:,.2f}", 250, 530, 2)
    words += line(f"18 {abbreviation}", 275, page=2) + line("CARGO PRUEBA", 275, 100, 2)
    words += line(f"{charge:,.2f}", 275, 360, 2) + line(f"{final:,.2f}", 275, 530, 2)
    words += line("CONTINUACION DE LA REFERENCIA", 287, 100, 2)
    words += line("Resumen Operaciones Tarjeta", 315, 100, 2)
    words += line("VARIOS", 335, 100, 2) + line("3", 335, 360, 2)
    words += line("TOTAL GENERAL", 350, 100, 2) + line("3", 350, 360, 2)
    words += line("19 ENE", 100, page=3) + line("NO ES UN MOVIMIENTO", 100, 100, 3)
    words += line("999.00", 100, 360, 3) + line("999.00", 100, 530, 3)
    return words


def parse(words):
    return parse_banamex(DocumentData(spatial_words=words))


@pytest.mark.parametrize("scale,offset,skew", [(1, 0, 0), (1.2, 25, -0.012), (0.85, 8, 0.01)])
def test_cover_fields_summary_and_real_movements_are_geometric(scale, offset, skew):
    words = cover_words()
    for w in words:
        x = (w["x0"] + w["x1"]) / 2
        for key in ("top", "bottom"):
            w[key] = (w[key] + skew * x) * scale + offset
        for key in ("x0", "x1"):
            w[key] = w[key] * scale + offset
    random.Random(12).shuffle(words)
    original = copy.deepcopy(words)
    result = parse(words)
    assert result.datos_cuenta.numero_cuenta == "12345000001"
    assert result.datos_cuenta.numero_cliente == "10000001"
    assert result.datos_cuenta.clabe == "002180000000000001"
    assert result.datos_cuenta.nombre_cliente == "PERSONA DEMOSTRACION"
    assert result.datos_cuenta.rfc == "DEMO010101AA1"
    assert result.datos_cuenta.periodo_inicio == "16/01/2030"
    assert result.datos_cuenta.periodo_fin == "15/02/2030"
    assert result.datos_cuenta.fecha_corte == "15/02/2030"
    summary = result.resumen_financiero
    assert (
        summary.saldo_anterior,
        summary.depositos_abonos,
        summary.retiros_cargos,
        summary.saldo_final,
    ) == (1200, 700, 225, 1675)
    assert summary.saldo_promedio == 1300
    assert summary.dias_periodo == 31
    assert [(m.cargo, m.abono, m.saldo_operacion) for m in result.movimientos] == [
        (0, 700, 1900),
        (225, 0, 1675),
    ]
    assert "CONTINUACION" in result.movimientos[-1].concepto
    assert all(v.correcto for v in validar_movimientos(result.movimientos, summary))
    assert words == original


def test_both_periods_keep_their_independent_summaries_and_table_boundaries():
    first = cover_words()
    second = cover_words(
        opening=1675, deposit=300, charge=125, month="febrero", end="marzo", days=28
    )
    second = [{**w, "page": w["page"] + 3} for w in second]
    result = parse(first + second)
    assert len(result.movimientos) == 4
    assert result.datos_cuenta.periodo_inicio == "16/01/2030"
    assert result.datos_cuenta.periodo_fin == "15/03/2030"
    summary = result.resumen_financiero
    assert (
        summary.saldo_anterior,
        summary.depositos_abonos,
        summary.retiros_cargos,
        summary.saldo_final,
    ) == (1200, 1000, 350, 1850)
    assert len(summary.periods) == 2
    assert all(v.correcto for v in validar_movimientos(result.movimientos, summary))
    # Las omisiones reales siguen fallando, aunque el resumen consolide periodos.
    result.movimientos.pop()
    assert not all(v.correcto for v in validar_movimientos(result.movimientos, summary))


def test_missing_printed_opening_is_not_manufactured_from_movements():
    words = [
        w
        for w in cover_words()
        if not (w["page"] == 1 and w["top"] == 345) and not (w["page"] == 2 and w["top"] == 95)
    ]
    result = parse(words)
    assert result.resumen_financiero.saldo_anterior is None


def test_wrapped_card_summary_still_stops_the_detail():
    words = [w for w in cover_words() if not (w["page"] == 2 and w["top"] == 315)]
    words += line("Resumen de Operaciones", 315, 100, 2) + line("de Tarjeta", 326, 100, 2)
    assert len(parse(words).movimientos) == 2


def test_implicit_initial_year_can_cross_the_calendar_boundary():
    result = parse([w for w in cover_words(month="diciembre", end="enero") if w["page"] == 1])
    assert result.datos_cuenta.periodo_inicio == "16/12/2029"
    assert result.datos_cuenta.periodo_fin == "15/01/2030"


def test_two_complete_amounts_are_never_concatenated_into_a_larger_number():
    words = cover_words() + line("0.00", 275, 380, 2)
    result = parse(words)
    assert result.movimientos[-1].cargo == 0
    assert not all(
        v.correcto for v in validar_movimientos(result.movimientos, result.resumen_financiero)
    )


@pytest.mark.parametrize(
    "value,expected", [("_17 NOV", "17 NOV"), ("-27 NOV", "27 NOV"), ("21 _NQV", "21 NOV")]
)
def test_rules_on_scanned_dates_do_not_hide_the_row(value, expected):
    assert normalize_movement_date_text(value) == expected


@pytest.mark.parametrize("amount", ["1,234.56", "1.234.56", "1,234,56"])
def test_complete_ocr_separator_variants_preserve_all_digits(amount):
    assert is_money(amount)
    assert parse_amount(amount) == 1234.56


def test_two_charges_with_a_missing_date_keep_both_financial_rows():
    words = [
        w for w in cover_words() if not (w["page"] == 2 and w["top"] >= 275) and w["page"] != 3
    ]
    words += line("18 ENE", 275, page=2) + line("CARGO UNO", 275, 100, 2)
    words += line("REFERENCIA DE PRUEBA", 287, 100, 2)
    words += line("100.00", 299, 360, 2) + line("1.800.00", 299, 530, 2)
    words += line("CARGO DOS", 311, 100, 2)
    words += line("REFERENCIA SEGUNDA", 323, 100, 2)
    words += line("125,00", 335, 360, 2) + line("1,675", 335, 530, 2) + line("00", 335, 547, 2)
    words += line("Resumen Operaciones Tarjeta", 355, 100, 2)
    result = parse(words)
    assert [m.cargo for m in result.movimientos] == [0, 100, 125]
    assert [m.saldo_operacion for m in result.movimientos] == [1900, 1800, 1675]
    assert result.movimientos[1].fecha_operacion == result.movimientos[2].fecha_operacion
    assert "REFERENCIA DE PRUEBA" in result.movimientos[1].concepto
    assert "REFERENCIA SEGUNDA" in result.movimientos[2].concepto
    assert all(
        v.correcto for v in validar_movimientos(result.movimientos, result.resumen_financiero)
    )
