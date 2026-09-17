"""Asegura orden de exportación sin modificar el trabajo OCR ni los parsers."""

from __future__ import annotations

import pytest

from engine.ordered_processing_events import ordered_terminal_events
from engine.pipeline import ProcessingEvent


def event(kind: str, index: int) -> ProcessingEvent:
    return ProcessingEvent(kind=kind, index=index, file_name=f"{index}.pdf")


def test_out_of_order_completions_keep_started_live_and_excel_input_order():
    emitted = list(ordered_terminal_events([
        event("started", 0),
        event("started", 1),
        event("completed", 1),
        event("started", 2),
        event("completed", 2),
        event("completed", 0),
    ]))
    assert [(item.kind, item.index) for item in emitted] == [
        ("started", 0), ("started", 1), ("started", 2),
        ("completed", 0), ("completed", 1), ("completed", 2),
    ]


def test_error_and_cancelled_unblock_later_successful_results():
    emitted = list(ordered_terminal_events([
        event("completed", 2), event("cancelled", 1), event("error", 0),
    ]))
    assert [(item.kind, item.index) for item in emitted] == [
        ("error", 0), ("cancelled", 1), ("completed", 2),
    ]


def test_duplicate_terminal_event_is_rejected():
    with pytest.raises(ValueError, match="duplicado"):
        list(ordered_terminal_events([event("completed", 0), event("completed", 0)]))


def test_incomplete_producer_still_yields_completed_result():
    emitted = list(ordered_terminal_events([event("completed", 1)]))
    assert [(item.kind, item.index) for item in emitted] == [("completed", 1)]
