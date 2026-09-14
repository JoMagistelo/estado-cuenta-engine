from __future__ import annotations

from types import SimpleNamespace

import pytest

from parsers.scotiabank.extractors import resumen as scotia_summary


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    *,
    page: int = 1,
) -> dict[str, object]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 6.0,
        "page": page,
    }


def _label_row(
    top: float,
    tokens: list[str],
    amount: str | None,
) -> list[dict[str, object]]:
    words: list[dict[str, object]] = []
    x = 68.0

    for token in tokens:
        width = max(8.0, min(28.0, len(token) * 3.0))
        words.append(_word(token, x, x + width, top))
        x += width + 2.2

    if amount is not None:
        words.append(_word(amount, 198.0, 238.0, top))

    return words


def _summary_words(
    *,
    omit_deposit_label: bool = False,
) -> list[dict[str, object]]:
    words: list[dict[str, object]] = [
        _word("Resumen", 118.0, 150.0, 266.0),
        _word("de", 153.0, 161.0, 266.0),
        _word("Saldos", 164.0, 188.0, 266.0),
    ]

    rows = [
        (282.0, ["Saldo", "inicial"], "$15,116.04"),
        (
            300.0,
            [] if omit_deposit_label else ["(+)", "Depósitos"],
            "$156,759.19",
        ),
        (
            318.0,
            ["(+)", "Intereses", "recibidos", "(Tasa", "0.00%)"],
            "$0.00",
        ),
        (336.0, ["(-)", "Retiros"], "$123,970.67"),
        (354.0, ["(-)", "Comisiones", "cobradas"], "$0.00"),
        (372.0, ["(-)", "Impuestos"], "$0.00"),
        (
            390.0,
            ["(=)", "Saldo", "final", "de", "la", "cuenta"],
            "$47,904.56",
        ),
    ]

    for top, tokens, amount in rows:
        words.extend(_label_row(top, tokens, amount))

    words.extend(
        _label_row(
            426.0,
            ["(=)", "Saldo", "final", "cuenta", "+", "inversiones"],
            "$47,904.56",
        )
    )
    words.extend(
        _label_row(
            444.0,
            ["Sdo.", "Prom.", "Mín.", "requerido", "en", "cuenta"],
            "$0.00",
        )
    )
    words.extend(
        _label_row(
            462.0,
            ["Sdo.", "Prom.", "(1)", "de", "la", "Cta."],
            "$25,971.21",
        )
    )

    # Importes de la gráfica deliberadamente incompatibles. El resumen debe
    # leer exclusivamente la columna izquierda de la tabla Resumen de Saldos.
    words.extend(
        [
            _word("$888,888.88", 430.0, 490.0, 300.0),
            _word("$777,777.77", 470.0, 530.0, 336.0),
            _word("$666,666.66", 480.0, 540.0, 390.0),
        ]
    )

    return words


def test_summary_uses_page_one_table_values_not_movement_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Si se reintrodujera el fallback histórico a movimientos, estos valores
    # incompatibles sustituirían a la tabla y la prueba fallaría.
    fake_movements = [
        SimpleNamespace(
            abono=900000.0,
            cargo=800000.0,
            saldo_operacion=700000.0,
        )
    ]
    monkeypatch.setattr(
        scotia_summary,
        "extract_movimientos_words",
        lambda _words: fake_movements,
        raising=False,
    )

    summary = scotia_summary.extract_resumen_financiero_words(
        _summary_words()
    )

    assert summary.saldo_anterior == pytest.approx(15116.04)
    assert summary.depositos_abonos == pytest.approx(156759.19)
    assert summary.retiros_cargos == pytest.approx(123970.67)
    assert summary.saldo_final == pytest.approx(47904.56)
    assert summary.saldo_promedio == pytest.approx(25971.21)
    assert summary.saldo_global == pytest.approx(47904.56)


def test_missing_label_uses_row_geometry_but_never_calculates_amount() -> None:
    summary = scotia_summary.extract_resumen_financiero_words(
        _summary_words(omit_deposit_label=True)
    )

    assert summary.depositos_abonos == pytest.approx(156759.19)

    words = [
        word
        for word in _summary_words(omit_deposit_label=True)
        if word.get("text") != "$156,759.19"
    ]
    missing_amount = scotia_summary.extract_resumen_financiero_words(words)

    assert missing_amount.depositos_abonos == 0.0


def test_explicit_inconsistent_balances_are_not_reconciled_or_overwritten() -> None:
    words = _summary_words()
    for word in words:
        if word.get("text") == "$15,116.04":
            word["text"] = "$10,000.00"
            break

    summary = scotia_summary.extract_resumen_financiero_words(words)

    # Aunque la ecuación no cierre, el extractor conserva el valor impreso.
    assert summary.saldo_anterior == pytest.approx(10000.0)
    assert summary.depositos_abonos == pytest.approx(156759.19)
    assert summary.retiros_cargos == pytest.approx(123970.67)
    assert summary.saldo_final == pytest.approx(47904.56)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$47,90456", 47904.56),
        ("$123,97067", 123970.67),
        ("$156,75919", 156759.19),
        ("$156,759.19", 156759.19),
    ],
)
def test_summary_money_repairs_only_unambiguous_missing_decimal(
    raw: str,
    expected: float,
) -> None:
    assert scotia_summary._money_text_value(raw) == pytest.approx(expected)


def test_ambiguous_ocr_amount_is_not_invented() -> None:
    assert scotia_summary._money_text_value("$15,1604") is None
