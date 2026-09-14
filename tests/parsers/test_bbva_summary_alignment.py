from __future__ import annotations

import pytest

from parsers.bbva.extractors.resumen import extract_resumen_financiero_words


def _word(text: str, x: float, top: float, width: float = 42.0) -> dict:
    return {"text": text, "x0": x, "x1": x + width, "top": top,
            "bottom": top + 10.0, "page": 1}


def _behavior_rows(shift: float = 0.0, *, missing_deposit: bool = False) -> list[dict]:
    words: list[dict] = []
    rows = [
        ("Saldo", "Anterior", "2,671.26", 266.0),
        ("Depósitos", "Abonos", "138,000.00", 280.0),
        ("Retiros", "Cargos", "139,139.16", 294.0),
        ("Saldo", "Final", "1,532.10", 308.0),
    ]
    for first, second, amount, top in rows:
        y = top + shift
        words.extend((_word(first, 310.0, y), _word(second, 355.0, y)))
        if missing_deposit and first == "Depósitos":
            continue
        words.append(_word(amount, 540.0, y - 3.0, 47.0))
    words.extend((
        _word("Saldo", 310.0, 322.0 + shift),
        _word("Promedio", 355.0, 322.0 + shift),
        _word("Mínimo", 405.0, 322.0 + shift),
        _word("Mensual:", 449.0, 322.0 + shift, 37.0),
        _word("0.00", 566.0, 319.0 + shift, 21.0),
    ))
    return words


@pytest.mark.parametrize("shift", [0.0, 14.0, 28.0])
def test_bbva_behavior_uses_label_rows_not_fixed_vertical_boxes(shift: float) -> None:
    # Al desplazar una fila, las cajas históricas asignaban Saldo Anterior a
    # Depósitos, Depósitos a Retiros, y así sucesivamente.
    summary = extract_resumen_financiero_words(_behavior_rows(shift))

    assert summary.saldo_anterior == pytest.approx(2671.26)
    assert summary.depositos_abonos == pytest.approx(138000.00)
    assert summary.retiros_cargos == pytest.approx(139139.16)
    assert summary.saldo_final == pytest.approx(1532.10)
    assert summary.saldo_promedio_minimo_mensual == 0.0


def test_bbva_behavior_never_borrows_the_previous_row_when_amount_missing() -> None:
    summary = extract_resumen_financiero_words(
        _behavior_rows(14.0, missing_deposit=True)
    )

    assert summary.saldo_anterior == pytest.approx(2671.26)
    assert summary.depositos_abonos == 0.0
    assert summary.retiros_cargos == pytest.approx(139139.16)
    assert summary.saldo_final == pytest.approx(1532.10)


def test_bbva_behavior_ignores_the_movement_count_beside_the_amount() -> None:
    words = _behavior_rows(14.0)
    words.append(_word("11", 465.0, 291.0))
    summary = extract_resumen_financiero_words(words)

    assert summary.depositos_abonos == pytest.approx(138000.00)


def test_bbva_behavior_keeps_legacy_box_when_no_labels_are_available() -> None:
    words = [
        _word("1,000.00", 548.0, 260.0),
        _word("500.00", 548.0, 274.0),
        _word("200.00", 548.0, 288.0),
        _word("1,300.00", 548.0, 301.0),
    ]
    summary = extract_resumen_financiero_words(words)

    assert summary.saldo_anterior == 1000.0
    assert summary.depositos_abonos == 500.0
    assert summary.retiros_cargos == 200.0
    assert summary.saldo_final == 1300.0
