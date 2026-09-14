from __future__ import annotations

import pytest

from parsers.bbva.extractors.resumen import extract_resumen_financiero_words


def _word(text: str, x: float, top: float, width: float = 42.0,
          *, page: int = 1) -> dict:
    return {"text": text, "x0": x, "x1": x + width, "top": top,
            "bottom": top + 10.0, "page": page}


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


def _financial_table(*, page: int, x_shift: float = 0, y_shift: float = 0,
                     missing_deposit: bool = False) -> list[dict]:
    """Reproduce las dos columnas de la captura, sin depender de cajas fijas."""
    words = [
        _word("Rendimiento", 15 + x_shift, 250 + y_shift, 60, page=page),
        _word("Comportamiento", 312 + x_shift, 250 + y_shift, 82, page=page),
    ]
    left_rows = [
        (["Saldo", "Promedio"], "20,412.56", 266),
        (["Días", "del", "Periodo"], "29", 281),
        (["Tasa", "Bruta", "Anual"], "0.000", 295),
        (["Saldo", "Promedio", "Gravable"], "0.00", 309),
        (["Intereses", "a", "Favor"], "0.00", 323),
        (["ISR", "Retenido"], "0.00", 337),
        (["Cheques", "pagados"], "0", 365),
        (["Manejo", "de", "Cuenta"], "0.00", 379),
        (["Cargos", "Objetados"], "0.00", 407),
        (["Abonos", "Objetados"], "0.00", 421),
    ]
    for labels, value, y in left_rows:
        for index, token in enumerate(labels):
            words.append(_word(token, 15 + x_shift + index * 42,
                               y + y_shift, 40, page=page))
        if labels == ["Cheques", "pagados"]:
            words.append(_word("0.00", 280 + x_shift, y + y_shift - 2, 24, page=page))
        words.append(_word(value, (185 if labels == ["Cheques", "pagados"] else 265)
                           + x_shift, y + y_shift - 2, 38, page=page))
    right_rows = [
        (["Saldo", "Anterior"], "10,874.54", 266),
        (["Depósitos", "/", "Abonos", "(+)"], "264,026.94", 281),
        (["Retiros", "/", "Cargos", "(-)"], "274,037.14", 295),
        (["Saldo", "Final"], "864.34", 309),
        (["Saldo", "Promedio", "Mínimo", "Mensual"], "0.00", 323),
    ]
    for labels, value, y in right_rows:
        for index, token in enumerate(labels):
            words.append(_word(token, 312 + x_shift + index * 37,
                               y + y_shift, 36, page=page))
        if labels[0] in ("Depósitos", "Retiros"):
            words.append(_word("11", 465 + x_shift, y + y_shift - 2, 12, page=page))
        if not (missing_deposit and labels[0] == "Depósitos"):
            words.append(_word(value, 540 + x_shift, y + y_shift - 3,
                               48, page=page))
    return words


@pytest.mark.parametrize("page,x_shift,y_shift", [(1, 80, 100), (2, 0, 95)])
def test_bbva_summary_follows_both_tables_to_new_page_and_geometry(
    page: int, x_shift: float, y_shift: float,
) -> None:
    words = _financial_table(page=page, x_shift=x_shift, y_shift=y_shift)
    if page == 2:
        # Cantidades que ocuparían las cajas antiguas de la página 1.
        words += [_word("999.00", 548, 260), _word("888.00", 548, 274)]
    result = extract_resumen_financiero_words(words)

    assert result.saldo_anterior == pytest.approx(10874.54)
    assert result.depositos_abonos == pytest.approx(264026.94)
    assert result.retiros_cargos == pytest.approx(274037.14)
    assert result.saldo_final == pytest.approx(864.34)
    assert result.saldo_promedio_minimo_mensual == 0.0
    assert result.saldo_promedio == pytest.approx(20412.56)
    assert result.dias_periodo == 29
    assert result.cheques_pagados == 0


def test_bbva_summary_does_not_borrow_monetary_value_from_neighboring_row() -> None:
    result = extract_resumen_financiero_words(
        _financial_table(page=2, missing_deposit=True)
    )
    assert result.saldo_anterior == pytest.approx(10874.54)
    assert result.depositos_abonos == 0.0
    assert result.retiros_cargos == pytest.approx(274037.14)
    assert result.saldo_final == pytest.approx(864.34)


def test_bbva_summary_recovers_rows_when_ocr_loses_table_heading() -> None:
    words = [w for w in _financial_table(page=2) if w["text"] != "Comportamiento"]
    result = extract_resumen_financiero_words(words)
    assert result.depositos_abonos == pytest.approx(264026.94)
    assert result.saldo_final == pytest.approx(864.34)


def test_bbva_summary_december_amounts_and_merged_ocr_label() -> None:
    words = _financial_table(page=1, x_shift=50, y_shift=80)
    replacements = {
        "10,874.54": "864.34",
        "264,026.94": "344,499.32",
        "274,037.14": "157,194.98",
        "864.34": "188,168.68",
    }
    for word in words:
        if word["text"] in replacements:
            word["text"] = replacements[word["text"]]
    # Algunos motores OCR unen la etiqueta completa en una sola palabra.
    words = [w for w in words if not (w["text"] in {"Depósitos", "Abonos", "/", "(+)"}
                                      and w["top"] == 361)]
    words.append(_word("Depósitos/Abonos(+)", 362, 361, 115))

    result = extract_resumen_financiero_words(words)
    assert result.saldo_anterior == pytest.approx(864.34)
    assert result.depositos_abonos == pytest.approx(344499.32)
    assert result.retiros_cargos == pytest.approx(157194.98)
    assert result.saldo_final == pytest.approx(188168.68)


def test_bbva_summary_prefers_complete_table_on_second_page() -> None:
    partial = [w for w in _financial_table(page=1)
               if w["text"] in {"Comportamiento", "Saldo", "Anterior", "10,874.54"}
               and w["top"] < 280]
    result = extract_resumen_financiero_words(partial + _financial_table(page=2))
    assert result.depositos_abonos == pytest.approx(264026.94)
    assert result.saldo_final == pytest.approx(864.34)


def test_bbva_summary_discards_ocr_cell_borders_without_shifting_rows() -> None:
    words = _financial_table(page=2, x_shift=90, y_shift=80)
    for word in words:
        if word["text"] == "264,026.94":
            word["text"] = "264,026.94]"
        elif word["text"] == "864.34":
            word["text"] = "864.34)"
    summary = extract_resumen_financiero_words(words)
    assert summary.saldo_anterior == pytest.approx(10874.54)
    assert summary.depositos_abonos == pytest.approx(264026.94)
    assert summary.retiros_cargos == pytest.approx(274037.14)
    assert summary.saldo_final == pytest.approx(864.34)
