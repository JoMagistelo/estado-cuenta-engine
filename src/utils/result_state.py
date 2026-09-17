from __future__ import annotations

from typing import Any


def replace_result_reference(
    results: list[Any],
    previous: Any,
    updated: Any,
) -> None:
    """Mantiene sincronizada la lista exportable después de reprocesar."""

    for index, candidate in enumerate(results):
        if candidate is previous:
            results[index] = updated
            return
    results.append(updated)


def remove_result_reference(results: list[Any], target: Any) -> bool:
    """Elimina por identidad para no confundir resultados con datos iguales."""

    for index, candidate in enumerate(results):
        if candidate is target:
            results.pop(index)
            return True
    return False


def _positive_amount(value: Any) -> bool:
    try:
        return float(value or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def movement_matches_kind(movement: Any, kind: str | None) -> bool:
    """Filtro visual; no altera el conjunto utilizado por la exportación."""

    if kind == "cargo":
        return _positive_amount(getattr(movement, "cargo", 0.0))
    if kind == "abono":
        return _positive_amount(getattr(movement, "abono", 0.0))
    return True
