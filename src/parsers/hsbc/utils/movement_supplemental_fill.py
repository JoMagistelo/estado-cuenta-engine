from __future__ import annotations

import re

from typing import List, Optional, Sequence

from models.movimiento import Movimiento
from parsers.hsbc.utils.movement_accounting_recovery import (
    SupplementalMovement,
    build_supplemental_movements,
)


def _compact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _amount_delta(movement: Movimiento) -> Optional[float]:
    if movement.cargo is None and movement.abono is None:
        return None
    try:
        return round(
            float(movement.abono or 0.0) - float(movement.cargo or 0.0),
            2,
        )
    except (TypeError, ValueError):
        return None


def _find_exact_reference_match(
    candidate: Movimiento,
    movements: Sequence[Movimiento],
) -> Optional[Movimiento]:
    reference = _compact(candidate.referencia)
    if not reference:
        return None

    matches = [
        movement
        for movement in movements
        if _compact(movement.referencia) == reference
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) <= 1:
        return None

    candidate_delta = _amount_delta(candidate)
    if candidate_delta is None:
        return None

    amount_matches = [
        movement
        for movement in matches
        if (
            _amount_delta(movement) is not None
            and abs(_amount_delta(movement) - candidate_delta) < 0.01  # type: ignore[operator]
        )
    ]

    return amount_matches[0] if len(amount_matches) == 1 else None


def _fill_missing_fields(
    target: Movimiento,
    source: Movimiento,
) -> bool:
    changed = False

    if not target.fecha_operacion and source.fecha_operacion:
        target.fecha_operacion = source.fecha_operacion
        changed = True

    if (
        target.cargo is None
        and target.abono is None
        and not (source.cargo is None and source.abono is None)
    ):
        target.cargo = source.cargo
        target.abono = source.abono
        changed = True

    if target.saldo_operacion is None and source.saldo_operacion is not None:
        target.saldo_operacion = source.saldo_operacion
        changed = True

    if not target.concepto and source.concepto:
        target.concepto = source.concepto
        changed = True

    if not target.concepto_original and source.concepto_original:
        target.concepto_original = source.concepto_original
        changed = True

    return changed


def fill_existing_movements_from_supplemental(
    words,
    movements: List[Movimiento],
) -> List[SupplementalMovement]:
    """
    Completa únicamente campos ausentes de una fila ya aceptada.

    La llave primaria es la Referencia/Serial completa y debe producir
    una coincidencia única. Nunca sustituye un importe o saldo que el
    parser histórico ya publicó; las correcciones de valores existentes
    quedan reservadas a la validación contable global.
    """

    if not words or not movements:
        return []

    supplemental = build_supplemental_movements(words)

    for item in supplemental:
        target = _find_exact_reference_match(item.movement, movements)
        if target is None:
            continue
        _fill_missing_fields(target, item.movement)

    return supplemental
