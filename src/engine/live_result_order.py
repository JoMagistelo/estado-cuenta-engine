"""Keep export order stable without delaying live processing events.

Flet can display each result as soon as it finishes. Only the snapshot passed to
Excel is sorted by the original position in the selected batches.
"""

from __future__ import annotations

from typing import Any


class LiveResultOrder:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._next_index = 0
        # Hold identity references: id() alone can be reused after deletion.
        self._positions: dict[int, tuple[Any, int]] = {}

    def reserve_batch(self, count: int) -> int:
        if count < 0:
            raise ValueError("El tamaño del lote no puede ser negativo")
        start = self._next_index
        self._next_index += count
        return start

    def register(self, result: Any, absolute_index: int) -> None:
        if result is not None:
            self._positions[id(result)] = (result, absolute_index)

    def transfer(self, previous: Any, updated: Any) -> None:
        """Retain the original position after a manual secondary-OCR replacement."""
        if previous is None or updated is None:
            return
        recorded = self._positions.get(id(previous))
        if recorded is not None and recorded[0] is previous:
            self._positions[id(updated)] = (updated, recorded[1])

    def ordered(self, results: list[Any]) -> list[Any]:
        """Return a sorted copy; never mutate Flet's live result collection."""
        def position(result: Any) -> int:
            recorded = self._positions.get(id(result))
            if recorded is not None and recorded[0] is result:
                return recorded[1]
            return self._next_index  # Stable sort keeps unknown results in their current order.

        return sorted(results, key=position)
