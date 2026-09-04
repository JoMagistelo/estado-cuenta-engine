from __future__ import annotations

from typing import Any

from models.resumen_financiero import ResumenFinanciero
from parsers.hsbc.utils.summary_accounting_recovery import (
    strengthen_hsbc_summary_accounting,
)


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    page: int = 2,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 7.0,
        "page": page,
    }


def _summary(
    saldo_anterior: float,
    depositos: float,
    retiros: float,
    saldo_final: float,
) -> ResumenFinanciero:
    return ResumenFinanciero(
        saldo_promedio=0.0,
        dias_periodo=31,
        tasa_bruta_anual=0.0,
        saldo_promedio_gravable=0.0,
        intereses_a_favor=0.0,
        isr_retenido=0.0,
        cheques_pagados=0,
        manejo_cuenta=0.0,
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos,
        retiros_cargos=retiros,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=0.0,
        saldo_global=0.0,
    )


def test_repairs_shifted_summary_when_initial_amount_is_ocr_damaged() -> None:
    words = [
        _word("-Saldo", 368.6, 387.1, 125.3),
        _word("Inicial", 389.8, 408.2, 125.3),
        _word("del", 410.6, 420.2, 125.3),
        _word("$:15/445:63", 507.6, 547.7, 125.5),
        _word("Depósitos/", 368.6, 403.9, 144.0),
        _word("64,652.64", 513.6, 547.7, 144.5),
        _word("Retiros/Cargos", 368.6, 418.3, 161.8),
        _word("63,434.22", 513.6, 547.7, 161.8),
    ]
    summary = _summary(
        saldo_anterior=64652.64,
        depositos=64652.64,
        retiros=63434.22,
        saldo_final=65871.06,
    )

    assert strengthen_hsbc_summary_accounting(words, summary) is True
    assert summary.saldo_anterior == 15445.63
    assert summary.depositos_abonos == 64652.64
    assert summary.retiros_cargos == 63434.22
    assert summary.saldo_final == 16664.05


def test_repairs_december_2024_row_shift_with_accounting_identity() -> None:
    words = [
        _word("Saldo", 397.9, 417.0, 263.0, page=4),
        _word("Inicial", 421.0, 444.0, 263.0, page=4),
        _word("18,296.20", 472.6, 510.0, 261.8, page=4),
        _word("Depósitos/", 367.4, 402.7, 142.3),
        _word("69,937.00", 512.2, 546.2, 140.9),
        _word("Retiros/Cargos", 367.4, 417.4, 160.3),
        _word("74,755.01", 512.6, 545.0, 158.4),
        _word("Saldo", 413.5, 433.0, 274.1, page=4),
        _word("Final", 435.1, 451.0, 273.6, page=4),
        _word("$13,478.19", 453.1, 493.0, 273.4, page=4),
    ]
    summary = _summary(
        saldo_anterior=69937.0,
        depositos=74755.01,
        retiros=13478.19,
        saldo_final=0.0,
    )

    assert strengthen_hsbc_summary_accounting(words, summary) is True
    assert summary.saldo_anterior == 18296.20
    assert summary.depositos_abonos == 69937.00
    assert summary.retiros_cargos == 74755.01
    assert summary.saldo_final == 13478.19


def test_does_not_infer_when_two_accounting_values_are_missing() -> None:
    words = [
        _word("Saldo", 368.0, 388.0, 125.0),
        _word("Inicial", 390.0, 410.0, 125.0),
        _word("1,000.00", 515.0, 550.0, 125.0),
        _word("Retiros/Cargos", 368.0, 420.0, 160.0),
        _word("200.00", 520.0, 550.0, 160.0),
    ]
    summary = _summary(1000.0, 0.0, 200.0, 800.0)

    assert strengthen_hsbc_summary_accounting(words, summary) is False
    assert summary.saldo_anterior == 1000.0
    assert summary.depositos_abonos == 0.0
    assert summary.retiros_cargos == 200.0
    assert summary.saldo_final == 800.0
