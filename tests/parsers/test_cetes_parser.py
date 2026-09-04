from __future__ import annotations

import random
from typing import Any

import pytest

from parsers.cetes.extractors.datos import extract_datos_cuenta_words
from parsers.cetes.extractors.movimientos import extract_movimientos_words
from parsers.cetes.extractors.resumen import extract_resumen_financiero_words
from validators.movimiento_validator import validar_movimientos


PAGE_WIDTH = 785.0
PAGE_HEIGHT = 600.0


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 8.0,
        "page": page,
    }


def _page_one(
    period: str,
    days: int,
    final_cash: str,
) -> list[dict[str, Any]]:
    return [
        _word("Nombre: PERSONA DE PRUEBA", 156, 350, 18),
        _word("RFC: TEST900101AB1", 156, 330, 42),
        _word("Contrato/Cuenta CLABE: 111000000000000001", 156, 350, 54),
        _word(f"Período del: {period}", 156, 360, 66),
        _word(f"Numero de dias del período: {days}", 156, 300, 78),
        _word("Composición Resumen del portafolio", 145, 610, 110),
        _word("ISR Retenidodel período:", 329, 500, 138),
        _word("0.17", 548, 578, 138),
        _word("Intereses del período:", 329, 500, 162),
        _word("14.680", 548, 585, 162),
        _word("Total de efectivo:", 600, 720, 162),
        _word(final_cash, 750, 784, 162),
        _word("Total final:", 600, 700, 174),
        _word(final_cash, 750, 784, 174),
    ]


def _movement_row(
    top: float,
    operation_date: str,
    settlement_date: str,
    folio: str,
    operation: str,
    issuer: str,
    series: str,
    charge: str,
    deposit: str,
    balance: str,
    *,
    page: int = 2,
    drift: bool = False,
    glued: bool = False,
) -> list[dict[str, Any]]:
    date_top = top + (4.5 if drift else 0.0)
    detail_top = top + (2.0 if drift else 0.0)
    amount_top = top - (1.0 if drift else 0.0)
    words = [
        _word(operation_date, 22, 54, date_top, page),
        _word(settlement_date, 71, 103, date_top - 0.5, page),
    ]
    if glued:
        words.append(_word(f"{folio}{operation}", 119, 250, detail_top, page))
    else:
        words.extend(
            [
                _word(folio, 119, 176, detail_top, page),
                _word(operation, 182, 250, detail_top - 0.5, page),
            ]
        )
    words.extend(
        [
            _word(issuer, 258, 295, detail_top - 1.0, page),
            _word(series, 307, 342, detail_top - 1.5, page),
            _word(charge, 603, 625, amount_top, page),
            _word(deposit, 677, 705, amount_top - 0.5, page),
            _word(balance, 751, 784, amount_top - 1.0, page),
        ]
    )
    return words


def _inverted(word: dict[str, Any]) -> dict[str, Any]:
    result = dict(word)
    result["x0"] = PAGE_WIDTH - word["x1"]
    result["x1"] = PAGE_WIDTH - word["x0"]
    result["top"] = PAGE_HEIGHT - word["bottom"]
    result["bottom"] = PAGE_HEIGHT - word["top"]
    result["text"] = word["text"][::-1]
    return result


def test_digital_layout_supports_glued_folio_and_summary_variants() -> None:
    words = _page_one("01/12/2024 al 31/12/2024", 31, "1.50")
    words.extend(
        [
            _word("Movimientos del período", 20, 150, 230, 2),
            _word("Saldo inicial", 22, 90, 260, 2),
            _word("1.50", 760, 784, 260, 2),
        ]
    )
    words.extend(
        _movement_row(
            280,
            "05/12/24",
            "05/12/24",
            "SVD100000001",
            "INGEFVO",
            "PESOS",
            "PESOS",
            "0.00",
            "100.00",
            "101.50",
        )
    )
    words.extend(
        _movement_row(
            292,
            "05/12/24",
            "05/12/24",
            "SVD100000002",
            "COMPSI",
            "BONDDIA",
            "PF2",
            "100.00",
            "0.00",
            "1.50",
            glued=True,
        )
    )

    datos = extract_datos_cuenta_words(words)
    resumen = extract_resumen_financiero_words(words)
    movimientos = extract_movimientos_words(words)

    assert datos.producto_principal == "CETESDIRECTO"
    assert datos.periodo_inicio == "01/12/2024"
    assert datos.periodo_fin == "31/12/2024"
    assert datos.clabe == "111000000000000001"
    assert datos.nombre_cliente == "PERSONA DE PRUEBA"
    assert resumen.intereses_a_favor == 14.68
    assert resumen.isr_retenido == 0.17
    assert resumen.saldo_anterior == 1.5
    assert resumen.depositos_abonos == 100.0
    assert resumen.retiros_cargos == 100.0
    assert resumen.saldo_final == 1.5
    assert [movement.referencia for movement in movimientos] == [
        "SVD100000001",
        "SVD100000002",
    ]
    assert movimientos[1].concepto == "COMPRA DE BONDDIA - BONDDIA PF2"
    assert all(result.correcto for result in validar_movimientos(movimientos, resumen))


def test_ocr_layout_joins_drifted_baselines_across_pages() -> None:
    words = _page_one("01/01/2023 al 31/12/2023", 365, "1.27")
    words.extend(
        [
            _word("Movimientos del período", 35, 145, 200, 2),
            _word("Saldo inicial", 37, 80, 232, 2),
            _word("0.00", 758, 784, 222, 2),
        ]
    )
    words.extend(
        _movement_row(
            242,
            "17/03/23",
            "17/03/23",
            "S$VD233728321",
            "INGEFVO",
            "PESOS",
            "PESOS",
            "0.00",
            "100.00",
            "100.00",
            drift=True,
        )
    )
    words.extend(
        _movement_row(
            128,
            "17/03/23",
            "17/03/23",
            "S$VD233728322",
            "VTSI",
            "BONDDIA",
            "PF2",
            "0.00",
            "98.73",
            "198.73",
            page=3,
            drift=True,
        )
    )
    words.extend(
        _movement_row(
            140,
            "17/03/23",
            "17/03/23",
            "S$VD233728323",
            "COMPSI",
            "BONDDIA",
            "PF2",
            "197.46",
            "0.00",
            "1.27",
            page=3,
            drift=True,
        )
    )
    words.append(_word("ISR RETENCION DE ISR", 190, 300, 300, 4))

    movimientos = extract_movimientos_words(words)
    resumen = extract_resumen_financiero_words(words)

    assert len(movimientos) == 3
    assert movimientos[0].referencia == "SVD233728321"
    assert movimientos[1].concepto == "VENTA DE BONDDIA - BONDDIA PF2"
    assert movimientos[-1].saldo_operacion == 1.27
    assert resumen.saldo_anterior == 0.0
    assert resumen.depositos_abonos == 198.73
    assert resumen.retiros_cargos == 197.46
    assert all(result.correcto for result in validar_movimientos(movimientos, resumen))


def test_inverted_pages_are_detected_and_reconciled_without_word_order() -> None:
    words = _page_one("01/06/2026 al 30/06/2026", 30, "1.00")
    logical_page = [
        _word("Movimientos del período", 20, 150, 230, 2),
        _word("Saldo inicial", 22, 90, 260, 2),
        _word("0.00", 760, 784, 260, 2),
    ]
    logical_page.extend(
        _movement_row(
            280,
            "03/06/26",
            "03/06/26",
            "SVD200000001",
            "INGEFVO",
            "PESOS",
            "PESOS",
            "0.00",
            "100.00",
            "100.00",
        )
    )
    logical_page.extend(
        _movement_row(
            292,
            "03/06/26",
            "03/06/26",
            "SVD200000002",
            "COMPSI",
            "BONDDIA",
            "PF2",
            "99.00",
            "0.00",
            "1.00",
        )
    )
    words.extend(_inverted(word) for word in logical_page)
    random.Random(7).shuffle(words)

    movimientos = extract_movimientos_words(words)
    resumen = extract_resumen_financiero_words(words)

    assert len(movimientos) == 2
    assert movimientos[0].fecha_operacion == "03/06/2026"
    assert movimientos[0].abono == 100.0
    assert movimientos[0].referencia == "SVD200000001"
    assert movimientos[1].cargo == 99.0
    assert movimientos[1].saldo_operacion == 1.0
    assert resumen.saldo_final == 1.0
    assert all(result.correcto for result in validar_movimientos(movimientos, resumen))


@pytest.mark.parametrize(
    ("value", "expected"),
    [("14.680", 14.68), ("$ 1,900.00", 1900.0), ("(10.25)", -10.25)],
)
def test_cetes_money_normalization(value: str, expected: float) -> None:
    from parsers.cetes.extractors.movimientos import parse_money

    assert parse_money(value) == expected
