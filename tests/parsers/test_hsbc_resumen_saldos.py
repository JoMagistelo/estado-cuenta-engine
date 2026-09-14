from __future__ import annotations

from typing import Any

import pytest

from parsers.hsbc.extractors.resumen_saldos import extract_resumen_saldos_words


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    *,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 6.0,
        "doctop": top,
        "width": x1 - x0,
        "height": 6.0,
        "upright": True,
        "direction": "ltr",
        "page": page,
        "confidence": 90.0,
    }


def test_resumen_de_saldos_uses_left_table_and_ignores_comparison_noise() -> None:
    words = [
        _word("Resumen", 118.56, 150.72, 266.4),
        _word("de", 153.36, 161.52, 266.4),
        _word("Saldos", 164.16, 187.68, 266.4),
        # La tabla/gráfica contigua contiene otros importes y no debe participar.
        _word("Saldo", 382.32, 394.80, 272.16),
        _word("inicial", 398.16, 412.08, 272.16),
        _word("$15,1604", 424.08, 444.00, 272.16),
        _word("Saldo", 452.88, 465.12, 272.16),
        _word("final=", 468.48, 483.84, 272.16),
        _word("$47,90456", 487.44, 511.20, 272.16),
        _word("168,000.00", 271.44, 294.24, 298.32),
        _word("126,000.00", 271.44, 293.76, 308.64),
        # Resumen de Saldos real.
        _word("Saldo", 126.0, 149.0, 284.0),
        _word("inicial", 151.0, 178.0, 284.0),
        _word("$15,116.04", 207.0, 241.0, 284.0),
        _word("(+) Depósitos", 116.0, 178.0, 301.0),
        _word("$156,759.19", 201.0, 241.0, 301.0),
        _word("(+) Intereses", 66.0, 115.0, 318.5),
        _word("recibidos", 117.0, 151.0, 318.5),
        _word("(Tasa", 153.0, 169.0, 318.5),
        _word("0.00%)", 170.0, 187.0, 318.5),
        _word("$0.00", 221.0, 241.0, 318.5),
        _word("(-) Retiros", 145.0, 178.0, 334.8),
        # Puntuación degradada observada en Tesseract.
        _word("$123,97067", 202.0, 241.0, 334.8),
        _word("(-) Comisiones", 105.0, 151.0, 352.6),
        _word("cobradas", 153.0, 179.0, 352.6),
        _word("$0.00", 221.0, 241.0, 352.6),
        _word("(-) Impuestos", 138.0, 178.0, 370.1),
        _word("$0.00", 221.0, 241.0, 370.1),
        _word("(=) Saldo final de la cuenta", 100.0, 178.0, 388.3),
        _word("$47,90456", 205.0, 241.0, 388.3),
        _word("(+) Saldo final inversiones a plazo", 82.0, 178.0, 409.0),
        _word("$0.00", 221.0, 241.0, 409.0),
        _word("(=) Saldo final cuenta + inversiones", 76.0, 179.0, 426.7),
        _word("$47,90456", 205.0, 241.0, 426.7),
        _word("Sdo. Prom. Mín. requerido en cuenta", 70.0, 178.0, 444.0),
        _word("$0.00", 221.0, 241.0, 444.0),
        _word("Sdo. Prom. (1) de la Cta.", 106.0, 178.0, 457.7),
        # Otro error OCR observado: separadores duplicados.
        _word("25.971.21", 206.9, 237.8, 462.0),
    ]

    result = extract_resumen_saldos_words(words)

    assert result is not None
    assert result.saldo_anterior == pytest.approx(15116.04)
    assert result.depositos_abonos == pytest.approx(156759.19)
    assert result.intereses_a_favor == pytest.approx(0.0)
    assert result.retiros_cargos == pytest.approx(123970.67)
    assert result.manejo_cuenta == pytest.approx(0.0)
    assert result.isr_retenido == pytest.approx(0.0)
    assert result.saldo_final == pytest.approx(47904.56)
    assert result.saldo_global == pytest.approx(47904.56)
    assert result.saldo_promedio_minimo_mensual == pytest.approx(0.0)
    assert result.saldo_promedio == pytest.approx(25971.21)
    assert result.tasa_bruta_anual == pytest.approx(0.0)

    # En este layout se conserva lo impreso; no se añade ningún concepto
    # a depósitos/retiros ni se reemplazan celdas con la tabla contigua.
    assert result.depositos_abonos != pytest.approx(168000.0)
    assert result.retiros_cargos != pytest.approx(126000.0)
