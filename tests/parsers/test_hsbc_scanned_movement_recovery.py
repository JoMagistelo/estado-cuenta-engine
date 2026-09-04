from __future__ import annotations

from typing import Any

from models.movimiento import Movimiento
from parsers.hsbc.utils.movement_accounting_recovery import (
    SupplementalMovement,
    build_supplemental_movements,
    extract_spei_rows_with_header_recovery,
    infer_single_missing_amount,
    insert_accounting_bridge_movements,
    reconcile_balances_if_statement_closes,
)
from parsers.hsbc.extractors.movimientos import MovementRow
from parsers.hsbc.utils.words_footer_filter import filter_page_footer


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
        "bottom": top + 7.0,
        "page": page,
    }


def _movement(
    number: int,
    *,
    cargo: float | None,
    abono: float | None,
    saldo: float | None,
    reference: str | None = None,
) -> Movimiento:
    return Movimiento(
        fecha_operacion=f"{number:02d}/01/2025",
        fecha_liquidacion=None,
        concepto=f"MOVIMIENTO {number}",
        tipo_operacion=None,
        cargo=cargo,  # type: ignore[arg-type]
        abono=abono,  # type: ignore[arg-type]
        referencia=reference or f"REF{number}",
        autorizacion=None,
        beneficiario=None,
        cuenta_beneficiario=None,
        clabe_beneficiario=None,
        clave_rastreo=None,
        rfc=None,
        sucursal=None,
        caja=None,
        hora_operacion=None,
        saldo_operacion=saldo,  # type: ignore[arg-type]
        saldo_liquidacion=0.0,
        concepto_original=f"MOVIMIENTO {number}",
    )


def test_inserts_only_missing_chain_that_bridges_known_balances() -> None:
    first = _movement(1, cargo=0.0, abono=0.0, saldo=1000.0)
    following = _movement(3, cargo=100.0, abono=0.0, saldo=700.0)
    missing = _movement(2, cargo=200.0, abono=0.0, saldo=800.0)

    supplemental = [
        SupplementalMovement(
            movement=missing,
            row=MovementRow(page=3, lines=[]),
            page=3,
            top=200.0,
        )
    ]

    result = insert_accounting_bridge_movements(
        [first, following],
        supplemental,
        opening_balance=None,
        closing_balance=None,
    )

    assert [movement.referencia for movement in result] == [
        "REF1",
        "REF2",
        "REF3",
    ]


def test_does_not_insert_candidate_that_does_not_close_gap() -> None:
    first = _movement(1, cargo=0.0, abono=0.0, saldo=1000.0)
    following = _movement(3, cargo=100.0, abono=0.0, saldo=700.0)
    unrelated = _movement(2, cargo=50.0, abono=0.0, saldo=950.0)

    supplemental = [
        SupplementalMovement(
            movement=unrelated,
            row=MovementRow(page=3, lines=[]),
            page=3,
            top=200.0,
        )
    ]

    result = insert_accounting_bridge_movements(
        [first, following],
        supplemental,
        opening_balance=None,
        closing_balance=None,
    )

    assert [movement.referencia for movement in result] == ["REF1", "REF3"]


def test_infers_exactly_one_missing_amount_and_reconciles_balances() -> None:
    first = _movement(1, cargo=100.0, abono=0.0, saldo=999999.0)
    missing = _movement(2, cargo=None, abono=None, saldo=None)
    movements = [first, missing]

    assert infer_single_missing_amount(
        movements,
        opening_balance=1000.0,
        closing_balance=800.0,
    ) is True
    assert missing.cargo == 100.0
    assert missing.abono == 0.0

    assert reconcile_balances_if_statement_closes(
        movements,
        opening_balance=1000.0,
        closing_balance=800.0,
    ) is True
    assert first.saldo_operacion == 900.0
    assert missing.saldo_operacion == 800.0


def test_does_not_infer_when_two_amounts_are_missing() -> None:
    first = _movement(1, cargo=None, abono=None, saldo=None)
    second = _movement(2, cargo=None, abono=None, saldo=None)

    assert infer_single_missing_amount(
        [first, second],
        opening_balance=1000.0,
        closing_balance=800.0,
    ) is False
    assert first.cargo is None
    assert second.cargo is None


def test_recovers_movement_page_when_ocr_lost_detail_header() -> None:
    words = [
        _word("Periodo del 01/01/2025 al 31/01/2025", 350, 555, 80),
        _word("01", 45, 54, 150),
        _word("CGO", 70, 90, 150),
        _word("UNO", 94, 120, 150),
        _word("08040001", 285, 330, 150),
        _word("100.00", 365, 400, 150),
        _word("900.00", 525, 560, 150),
        _word("111111", 295, 330, 159),
        _word("02", 45, 54, 175),
        _word("CGO", 70, 90, 175),
        _word("DOS", 94, 120, 175),
        _word("08040002", 285, 330, 175),
        _word("100.00", 365, 400, 175),
        _word("800.00", 525, 560, 175),
        _word("222222", 295, 330, 184),
    ]

    recovered = build_supplemental_movements(words)

    assert len(recovered) == 2
    assert [item.movement.fecha_operacion for item in recovered] == [
        "01/01/2025",
        "02/01/2025",
    ]
    assert [item.movement.saldo_operacion for item in recovered] == [
        900.0,
        800.0,
    ]


def test_recovers_received_spei_section_from_period_only_header() -> None:
    words = [
        _word("eriodo del 01/01/2025 al 31/01/2025", 320, 445, 100, page=4),
        _word("01/01/2025", 45, 80, 130, page=4),
        _word("10:00:00", 87, 116, 130, page=4),
        _word("BBVA", 130, 150, 130, page=4),
        _word("ORDENANTE", 190, 235, 130, page=4),
        _word("000121800153349584", 252, 330, 130, page=4),
        _word("PAGO", 340, 375, 130, page=4),
        _word("100.00", 405, 435, 130, page=4),
        _word("MBAN0100", 470, 510, 130, page=4),
        _word("00000001", 520, 558, 130, page=4),
        _word("02/01/2025", 45, 80, 160, page=4),
        _word("11:00:00", 87, 116, 160, page=4),
        _word("BBVA", 130, 150, 160, page=4),
        _word("OTRO", 190, 220, 160, page=4),
        _word("000121800153349585", 252, 330, 160, page=4),
        _word("PAGO", 340, 375, 160, page=4),
        _word("200.00", 405, 435, 160, page=4),
        _word("MBAN0200", 470, 510, 160, page=4),
        _word("00000002", 520, 558, 160, page=4),
    ]

    rows = extract_spei_rows_with_header_recovery(words)

    assert len(rows) == 2
    assert all(row.tipo == "recibidos" for row in rows)
    assert [row.monto for row in rows] == [100.0, 200.0]


def test_fuzzy_footer_signature_does_not_cut_last_movement() -> None:
    words = [
        _word("31", 45, 55, 690, page=3),
        _word("CGO", 70, 90, 690, page=3),
        _word("1,000.00", 365, 405, 690, page=3),
        _word("13,478.19", 525, 565, 690, page=3),
        _word("Emitido", 35, 70, 730, page=3),
        _word("por:", 73, 90, 730, page=3),
        _word("HSEC", 95, 120, 730, page=3),
        _word("México", 123, 155, 730, page=3),
    ]

    filtered = filter_page_footer(words)
    texts = [word["text"] for word in filtered]

    assert "31" in texts
    assert "CGO" in texts
    assert "Emitido" not in texts
    assert "HSEC" not in texts
