from __future__ import annotations

import pytest

from parsers.scotiabank.extractors import movimientos as scotia


LAYOUT = scotia.ColumnLayout(
    page_width=612.0,
    date_right=88.74,
    reference_start=250.0,
    deposit_start=360.0,
    withdrawal_start=440.0,
    balance_start=520.0,
)


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
        "bottom": top + 8.0,
        "page": page,
    }


def _movement_line(
    *,
    top: float,
    concept: list[str],
    reference: str,
    deposit: str | None = None,
    withdrawal: str | None = None,
    balance: str,
    month_crosses_date_boundary: bool = False,
) -> scotia.SpatialLine:
    month_x0, month_x1 = (
        (84.0, 100.0)
        if month_crosses_date_boundary
        else (52.0, 72.0)
    )

    words = [
        _word("17", 20.0, 34.0, top),
        _word("NOV", month_x0, month_x1, top),
    ]

    cursor = 108.0
    for token in concept:
        width = max(18.0, min(50.0, len(token) * 4.5))
        words.append(_word(token, cursor, cursor + width, top))
        cursor += width + 4.0

    words.append(_word(reference, 270.0, 335.0, top))

    if deposit is not None:
        words.append(_word(deposit, 375.0, 425.0, top))
    if withdrawal is not None:
        words.append(_word(withdrawal, 455.0, 505.0, top))

    words.append(_word(balance, 535.0, 600.0, top))
    words.sort(key=lambda word: float(word["x0"]))
    return scotia.SpatialLine(page=1, words=words)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-1,599.00", -1599.00),
        ("-$1,599.00", -1599.00),
        ("$-1,599.00", -1599.00),
        ("1,599.00-", -1599.00),
        ("$1,599.00-", -1599.00),
        ("1,599.00\u2212", -1599.00),
        ("1,599.00\u2013", -1599.00),
        ("(1,599.00)", -1599.00),
        ("1,599.00", 1599.00),
    ],
)
def test_parse_money_preserves_leading_and_trailing_negative_signs(
    raw: str,
    expected: float,
) -> None:
    assert scotia.is_money_text(raw)
    assert scotia.parse_money(raw) == pytest.approx(expected)


def test_negative_amount_keeps_operation_type_from_its_column() -> None:
    charge_line = _movement_line(
        top=100.0,
        concept=["STRIPE", "UBER", "TRIP"],
        reference="00000000332108428260",
        withdrawal="$199.98-",
        balance="$81,563.42-",
    )
    deposit_line = _movement_line(
        top=120.0,
        concept=["TRANSF", "INTERBANCARIA", "SPEI"],
        reference="782708092",
        deposit="-$74,459.01",
        balance="$81,763.40",
    )

    charge = scotia._movement_from_block(
        scotia.MovementBlock(lines=[charge_line]),
        LAYOUT,
        None,
        None,
    )
    deposit = scotia._movement_from_block(
        scotia.MovementBlock(lines=[deposit_line]),
        LAYOUT,
        None,
        None,
    )

    assert charge.cargo == pytest.approx(-199.98)
    assert charge.saldo_operacion == pytest.approx(-81563.42)
    assert charge.tipo_operacion == "CARGO"

    assert deposit.abono == pytest.approx(-74459.01)
    assert deposit.tipo_operacion == "ABONO"


def test_month_crossing_date_boundary_still_starts_a_new_movement() -> None:
    lines = [
        _movement_line(
            top=100.0,
            concept=["DISNEY", "PLUS", "PPERIF", "SUR"],
            reference="00000000785970728127",
            withdrawal="$1,599.00",
            balance="$7,304.39",
        ),
        _movement_line(
            top=120.0,
            concept=["TRANSF", "INTERBANCARIA", "SPEI"],
            reference="782708092",
            deposit="$74,459.01",
            balance="$81,763.40",
            month_crosses_date_boundary=True,
        ),
        _movement_line(
            top=140.0,
            concept=["STRIPE", "UBER", "TRIP", "CIU"],
            reference="00000000332108428260",
            withdrawal="$199.98",
            balance="$81,563.42",
            month_crosses_date_boundary=True,
        ),
        _movement_line(
            top=160.0,
            concept=["RETIRO", "CAJERO", "AUTOMATICO", "RED"],
            reference="00000000319900944286",
            withdrawal="$1,500.00",
            balance="$80,063.42",
            month_crosses_date_boundary=True,
        ),
    ]

    blocks = scotia.build_movement_blocks(lines, LAYOUT)

    assert len(blocks) == 4

    movements = [
        scotia._movement_from_block(block, LAYOUT, None, None)
        for block in blocks
    ]

    assert [movement.fecha_operacion for movement in movements] == [
        "17 NOV",
        "17 NOV",
        "17 NOV",
        "17 NOV",
    ]
    assert movements[0].cargo == pytest.approx(1599.00)
    assert movements[1].abono == pytest.approx(74459.01)
    assert movements[2].cargo == pytest.approx(199.98)
    assert movements[3].cargo == pytest.approx(1500.00)

    first_lines = [movement.concepto.splitlines()[0] for movement in movements]
    assert first_lines == [
        "DISNEY PLUS PPERIF SUR",
        "TRANSF INTERBANCARIA SPEI",
        "STRIPE UBER TRIP CIU",
        "RETIRO CAJERO AUTOMATICO RED",
    ]
    assert all(not concept.startswith("NOV ") for concept in first_lines)
