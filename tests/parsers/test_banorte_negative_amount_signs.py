from __future__ import annotations

from types import SimpleNamespace

import pytest

from parsers.banorte.extractors.movimientos import is_money, parse_amount
from parsers.banorte.utils.amount_sign_hardening import (
    ensure_signed_amount_operation_types,
    normalize_trailing_negative_amount_token,
    normalize_trailing_negative_amount_words,
)
from parsers.banorte_ocr.extractors.movimientos import _normalize_amount_token


@pytest.mark.parametrize(
    ("raw", "normalized", "expected"),
    [
        ("53.00-", "-53.00", -53.0),
        ("$1,253.40-", "-$1,253.40", -1253.40),
        ("0.50-", "-0.50", -0.50),
    ],
)
def test_trailing_negative_amount_is_understood_by_digital_and_ocr(
    raw: str,
    normalized: str,
    expected: float,
) -> None:
    token = normalize_trailing_negative_amount_token(raw)

    assert token == normalized

    # El parser digital histórico ya entiende el signo cuando está al inicio.
    assert is_money(token)
    assert parse_amount(token) == pytest.approx(expected)

    # El parser OCR comparte la misma semántica monetaria después de normalizar.
    assert _normalize_amount_token(token) == pytest.approx(expected)


def test_ocr_decimal_comma_with_trailing_minus_is_preserved_as_negative() -> None:
    token = normalize_trailing_negative_amount_token("53,00-")

    assert token == "-53,00"
    assert _normalize_amount_token(token) == pytest.approx(-53.0)


def test_regular_amounts_and_non_money_hyphens_are_not_modified() -> None:
    assert normalize_trailing_negative_amount_token("53.00") == "53.00"
    assert normalize_trailing_negative_amount_token("-53.00") == "-53.00"
    assert normalize_trailing_negative_amount_token("+53.00") == "+53.00"
    assert normalize_trailing_negative_amount_token("(53.00)") == "(53.00)"
    assert normalize_trailing_negative_amount_token("123-") == "123-"
    assert normalize_trailing_negative_amount_token("REFERENCIA-") == "REFERENCIA-"
    assert normalize_trailing_negative_amount_token("ABC-123-") == "ABC-123-"


def test_spatial_word_normalization_uses_a_copy_and_preserves_coordinates() -> None:
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
