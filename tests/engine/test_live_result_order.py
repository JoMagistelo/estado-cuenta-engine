"""Regresiones de orden de exportación sin retrasar la interfaz."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from engine.live_result_order import LiveResultOrder


@dataclass(eq=True)
class Result:
    file_name: str
    value: int


def test_out_of_order_completions_stay_live_but_export_in_selection_order():
    order = LiveResultOrder()
    base = order.reserve_batch(3)
    first = Result("scan.pdf", 1)
    digital = Result("digital.pdf", 2)
    other = Result("scan2.pdf", 3)
    live = []
    for index, result in [(1, digital), (2, other), (0, first)]:
        order.register(result, base + index)
        live.append(result)
        assert order.ordered(live) == sorted(live, key=lambda item: item.value)
    assert live == [digital, other, first]  # No reordenar los eventos de Flet.
    assert order.ordered(live) == [first, digital, other]


def test_duplicate_filenames_use_identity_not_name_or_equality():
    order = LiveResultOrder()
    first = Result("same.pdf", 1)
    second = Result("same.pdf", 1)
    order.register(first, 0)
    order.register(second, 1)
    assert order.ordered([second, first]) == [first, second]


def test_manual_ocr_replacement_preserves_position_and_does_not_mutate_results():
    order = LiveResultOrder()
    first = Result("scan.pdf", 1)
    digital = Result("digital.pdf", 2)
    replacement = Result("scan.pdf", 10)
    order.register(first, 0)
    order.register(digital, 1)
    order.transfer(first, replacement)
    live = [digital, replacement]
    assert order.ordered(live) == [replacement, digital]
    assert live == [digital, replacement]


def test_appended_batch_retains_previous_order_and_new_batch_can_reset():
    order = LiveResultOrder()
    first = Result("old.pdf", 1)
    newer = Result("new.pdf", 2)
    assert order.reserve_batch(1) == 0
    order.register(first, 0)
    assert order.reserve_batch(1) == 1
    order.register(newer, 1)
    assert order.ordered([newer, first]) == [first, newer]
    order.reset()
    assert order.reserve_batch(1) == 0
    assert order.ordered([newer, first]) == [newer, first]


def test_untracked_results_keep_relative_order_and_invalid_batch_rejected():
    order = LiveResultOrder()
    a, b = Result("a.pdf", 1), Result("b.pdf", 2)
    assert order.ordered([b, a]) == [b, a]
    with pytest.raises(ValueError):
        order.reserve_batch(-1)
