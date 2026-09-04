from __future__ import annotations

from models.movimiento import Movimiento
from parsers.hsbc.utils.movement_accounting_recovery import SupplementalMovement
from parsers.hsbc.utils.partial_movement_bridge import _resolve_partial_chain
from parsers.hsbc.extractors.movimientos import MovementRow


def _movement(
    *,
    cargo: float | None,
    abono: float | None,
    saldo: float | None,
    reference: str,
) -> Movimiento:
    return Movimiento(
        fecha_operacion="27/12/2024",
        fecha_liquidacion=None,
        concepto="MOVIMIENTO PARCIAL",
        tipo_operacion=None,
        cargo=cargo,  # type: ignore[arg-type]
        abono=abono,  # type: ignore[arg-type]
        referencia=reference,
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
        concepto_original="MOVIMIENTO PARCIAL",
    )


def _supplemental(movement: Movimiento, top: float = 100.0) -> SupplementalMovement:
    return SupplementalMovement(
        movement=movement,
        row=MovementRow(page=4, lines=[]),
        page=4,
        top=top,
    )


def test_partial_row_is_accepted_only_when_delta_closes_next_balance() -> None:
    candidate = _supplemental(
        _movement(
            cargo=258.0,
            abono=0.0,
            saldo=None,
            reference="11771645\n4224",
        )
    )

    resolved = _resolve_partial_chain(
        19471.19,
        19213.19,
        [candidate],
    )

    assert len(resolved) == 1
    assert resolved[0][0] is candidate
    assert resolved[0][1] == 19213.19


def test_partial_row_is_rejected_when_delta_does_not_close_gap() -> None:
    candidate = _supplemental(
        _movement(
            cargo=250.0,
            abono=0.0,
            saldo=None,
            reference="11771645\n4224",
        )
    )

    resolved = _resolve_partial_chain(
        19471.19,
        19213.19,
        [candidate],
    )

    assert resolved == []


def test_two_partial_rows_can_form_one_exact_chain() -> None:
    first = _supplemental(
        _movement(
            cargo=100.0,
            abono=0.0,
            saldo=None,
            reference="A",
        ),
        100.0,
    )
    second = _supplemental(
        _movement(
            cargo=158.0,
            abono=0.0,
            saldo=None,
            reference="B",
        ),
        120.0,
    )

    resolved = _resolve_partial_chain(
        19471.19,
        19213.19,
        [first, second],
    )

    assert [balance for _, balance in resolved] == [19371.19, 19213.19]
