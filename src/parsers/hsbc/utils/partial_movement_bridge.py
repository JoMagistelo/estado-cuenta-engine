from __future__ import annotations

import re

from typing import List, Optional, Sequence, Tuple

from models.movimiento import Movimiento
from parsers.hsbc.utils.movement_accounting_recovery import (
    BALANCE_TOLERANCE,
    SupplementalMovement,
    build_supplemental_movements,
    reconcile_balances_if_statement_closes,
)
from parsers.hsbc.utils.summary_accounting_recovery import (
    extract_summary_accounting_candidates,
)


def _compact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _balance(movement: Movimiento) -> Optional[float]:
    value = movement.saldo_operacion
    if value is None:
        return None
    try:
        parsed = round(float(value), 2)
    except (TypeError, ValueError):
        return None

    # En una fila parcial, el cero histórico no es una frontera útil.
    if abs(parsed) < 0.01:
        return None

    return parsed


def _delta(movement: Movimiento) -> Optional[float]:
    if movement.cargo is None and movement.abono is None:
        return None
    try:
        return round(
            float(movement.abono or 0.0) - float(movement.cargo or 0.0),
            2,
        )
    except (TypeError, ValueError):
        return None


def _balance_before(movement: Movimiento) -> Optional[float]:
    balance = _balance(movement)
    delta = _delta(movement)
    if balance is None or delta is None:
        return None
    return round(balance - delta, 2)


def _same_identity(
    candidate: Movimiento,
    existing: Movimiento,
) -> bool:
    candidate_reference = _compact(candidate.referencia)
    existing_reference = _compact(existing.referencia)

    if candidate_reference and candidate_reference == existing_reference:
        return True

    candidate_concept = _compact(candidate.concepto)
    existing_concept = _compact(existing.concepto)

    return bool(
        candidate_concept
        and candidate_concept == existing_concept
        and candidate.fecha_operacion
        and candidate.fecha_operacion == existing.fecha_operacion
    )


def _is_new_partial_candidate(
    item: SupplementalMovement,
    movements: Sequence[Movimiento],
) -> bool:
    movement = item.movement
    if _delta(movement) is None:
        return False

    # Esta segunda estrategia está reservada a filas cuyo saldo no fue
    # legible. Las filas con saldo normal pertenecen al puente principal.
    if _balance(movement) is not None:
        return False

    return not any(
        _same_identity(movement, existing)
        for existing in movements
    )


def _resolve_partial_chain(
    start_balance: float,
    target_balance: float,
    candidates: Sequence[SupplementalMovement],
) -> List[Tuple[SupplementalMovement, float]]:
    """
    Busca una cadena cronológica usando únicamente deltas observados.

    Un saldo ausente se calcula en memoria como saldo_previo + delta,
    pero sólo se publica si la cadena completa termina exactamente en
    la siguiente frontera contable ya observada.
    """

    if abs(start_balance - target_balance) <= BALANCE_TOLERANCE:
        return []

    def search(
        current: float,
        start_index: int,
        path: List[Tuple[SupplementalMovement, float]],
    ) -> Optional[List[Tuple[SupplementalMovement, float]]]:
        if len(path) >= 8:
            return None

        for index in range(start_index, len(candidates)):
            item = candidates[index]
            delta = _delta(item.movement)
            if delta is None:
                continue

            inferred_after = round(current + delta, 2)
            next_path = [*path, (item, inferred_after)]

            if abs(inferred_after - target_balance) <= BALANCE_TOLERANCE:
                return next_path

            resolved = search(
                inferred_after,
                index + 1,
                next_path,
            )
            if resolved is not None:
                return resolved

        return None

    return search(start_balance, 0, []) or []


def _direct_summary_value(words, field: str) -> Optional[float]:
    candidates = extract_summary_accounting_candidates(words).get(field, [])
    if not candidates:
        return None

    counts: dict[float, int] = {}
    for candidate in candidates:
        rounded = round(candidate.value, 2)
        counts[rounded] = counts.get(rounded, 0) + 1

    best = min(
        candidates,
        key=lambda candidate: (
            -counts[round(candidate.value, 2)],
            candidate.distance,
            candidate.page,
            candidate.top,
        ),
    )
    return round(best.value, 2)


def insert_partial_accounting_bridges(
    words,
    movements: List[Movimiento],
) -> List[Movimiento]:
    """
    Recupera una fila OCR con importe visible pero saldo ausente.

    La fila sólo se inserta cuando su delta, o una secuencia corta de
    deltas parciales, conecta exactamente dos saldos independientes.
    Si no existe cierre exacto, no se modifica la lista ni se inventa
    ningún saldo.
    """

    if not words or len(movements) < 2:
        return movements

    supplemental = build_supplemental_movements(words)
    candidates = [
        item
        for item in supplemental
        if _is_new_partial_candidate(item, movements)
    ]
    if not candidates:
        return movements

    candidates.sort(key=lambda item: (item.page, item.top))
    used: set[int] = set()
    result: List[Movimiento] = [movements[0]]

    for index in range(len(movements) - 1):
        current = movements[index]
        following = movements[index + 1]
        start_balance = _balance(current)
        target_balance = _balance_before(following)

        if start_balance is not None and target_balance is not None:
            available = [
                item
                for item in candidates
                if id(item) not in used
            ]
            resolved = _resolve_partial_chain(
                start_balance,
                target_balance,
                available,
            )

            for item, inferred_balance in resolved:
                item.movement.saldo_operacion = inferred_balance
                result.append(item.movement)
                used.add(id(item))

        result.append(following)

    # La reconciliación total sigue siendo la última barrera. Si toda
    # la cuenta cierra, corrige cualquier saldo OCR residual; si no,
    # esta función no altera los importes ya existentes.
    opening_balance = _direct_summary_value(words, "saldo_anterior")
    closing_balance = _direct_summary_value(words, "saldo_final")

    reconcile_balances_if_statement_closes(
        result,
        opening_balance,
        closing_balance,
    )

    return result
