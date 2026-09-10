from __future__ import annotations

from types import SimpleNamespace

import pytest

from parsers.bbva.extractors.movimientos import (
    COLS_NORMAL,
    extract_abono,
    extract_cargo,
    extract_saldo_liquidacion,
    extract_saldo_operacion,
    parse_amount,
)
from parsers.bbva.utils.amount_sign_hardening import (
    ensure_signed_amount_operation_types,
    normalize_trailing_negative_amount_token,
    normalize_trailing_negative_amount_words,
)


@pytest.mark.parametrize(
    ("raw", "normalized", "expected"),
    [
        ("53.00-", "-53.00", -53.0),
        ("1,253.40-", "-1,253.40", -1253.40),
        ("0.50\u2212", "-0.50", -0.50),
    ],
)
def test_trailing_negative_amount_is_preserved_by_bbva_parser(
    raw: str,
    normalized: str,
    expected: float,
) -> None:
    token = normalize_trailing_negative_amount_token(raw)

    assert token == normalized
    assert parse_amount(token) == pytest.approx(expected)


def test_regular_amounts_and_non_money_hyphens_are_not_modified() -> None:
    assert normalize_trailing_negative_amount_token("53.00") == "53.00"
    assert normalize_trailing_negative_amount_token("-53.00") == "-53.00"
    assert normalize_trailing_negative_amount_token("+53.00") == "+53.00"
    assert normalize_trailing_negative_amount_token("123-") == "123-"
    assert normalize_trailing_negative_amount_token("REFERENCIA-") == "REFERENCIA-"
    assert normalize_trailing_negative_amount_token("ABC-123-") == "ABC-123-"


def test_negative_values_are_preserved_in_all_bbva_monetary_columns() -> None:
    line = [
        {"text": "125.50-", "x0": 390.0, "x1": 410.0},
        {"text": "80.25-", "x0": 430.0, "x1": 450.0},
        {"text": "1,000.00-", "x0": 490.0, "x1": 510.0},
        {"text": "900.75-", "x0": 550.0, "x1": 570.0},
    ]

    normalized_line = normalize_trailing_negative_amount_words(line)

    assert extract_cargo(normalized_line, COLS_NORMAL) == pytest.approx(-125.50)
    assert extract_abono(normalized_line, COLS_NORMAL) == pytest.approx(-80.25)
    assert extract_saldo_operacion(normalized_line, COLS_NORMAL) == pytest.approx(-1000.00)
    assert extract_saldo_liquidacion(normalized_line, COLS_NORMAL) == pytest.approx(-900.75)


def test_spatial_normalization_uses_copy_and_preserves_coordinates() -> None:
    original = {
        "text": "53.00-",
        "x0": 430.0,
        "x1": 475.0,
        "top": 350.0,
        "bottom": 360.0,
        "doctop": 1800.0,
        "page": 3,
    }

    normalized = normalize_trailing_negative_amount_words([original])

    assert original["text"] == "53.00-"
    assert normalized[0] is not original
    assert normalized[0]["text"] == "-53.00"

    for key in ("x0", "x1", "top", "bottom", "doctop", "page"):
        assert normalized[0][key] == original[key]


def test_unaffected_spatial_words_retain_identity() -> None:
    original = {
        "text": "53.00",
        "x0": 430.0,
        "x1": 475.0,
        "top": 350.0,
        "bottom": 360.0,
        "page": 3,
    }

    normalized = normalize_trailing_negative_amount_words([original])

    assert normalized[0] is original


def test_negative_amount_keeps_operation_type_from_its_monetary_column() -> None:
    negative_charge = SimpleNamespace(
        tipo_operacion=None,
        cargo=-53.0,
        abono=0.0,
    )
    negative_deposit = SimpleNamespace(
        tipo_operacion=None,
        cargo=0.0,
        abono=-25.5,
    )
    existing = SimpleNamespace(
        tipo_operacion="CARGO",
        cargo=10.0,
        abono=0.0,
    )

    movements = [negative_charge, negative_deposit, existing]
    returned = ensure_signed_amount_operation_types(movements)

    assert returned is movements
    assert negative_charge.tipo_operacion == "CARGO"
    assert negative_deposit.tipo_operacion == "ABONO"
    assert existing.tipo_operacion == "CARGO"
