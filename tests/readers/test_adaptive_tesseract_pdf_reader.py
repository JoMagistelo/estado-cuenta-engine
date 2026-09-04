from __future__ import annotations

from typing import Any

from readers.adaptive_tesseract_pdf_reader import AdaptiveTesseractPDFReader


def _word(
    text: str,
    x0: float,
    top: float,
    confidence: float = 90.0,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x0 + max(8.0, len(text) * 4.0),
        "top": top,
        "bottom": top + 7.0,
        "page": 1,
        "confidence": confidence,
    }


def _financial_row(day: int, top: float, confidence: float = 90.0):
    return [
        _word(str(day), 45.0, top, confidence),
        _word("MOVIMIENTO", 80.0, top, confidence),
        _word("100.00", 370.0, top, confidence),
        _word("900.00", 525.0, top, confidence),
    ]


def test_prefers_recovery_only_when_structured_rows_increase() -> None:
    primary = [
        word
        for day, top in ((1, 100.0), (2, 125.0))
        for word in _financial_row(day, top)
    ]
    recovery = [
        word
        for day, top in ((1, 100.0), (2, 125.0), (3, 150.0))
        for word in _financial_row(day, top)
    ]

    assert AdaptiveTesseractPDFReader.should_use_recovery_page(
        primary,
        recovery,
    ) is True


def test_keeps_primary_when_recovery_has_same_number_of_rows() -> None:
    primary = [
        word
        for day, top in ((1, 100.0), (2, 125.0))
        for word in _financial_row(day, top)
    ]
    recovery = [
        word
        for day, top in ((1, 100.0), (2, 125.0))
        for word in _financial_row(day, top)
    ]

    assert AdaptiveTesseractPDFReader.should_use_recovery_page(
        primary,
        recovery,
    ) is False


def test_rejects_recovery_that_gains_rows_but_loses_confidence() -> None:
    primary = [
        word
        for day, top in ((1, 100.0), (2, 125.0))
        for word in _financial_row(day, top, 92.0)
    ]
    recovery = [
        word
        for day, top in ((1, 100.0), (2, 125.0), (3, 150.0))
        for word in _financial_row(day, top, 20.0)
    ]

    assert AdaptiveTesseractPDFReader.should_use_recovery_page(
        primary,
        recovery,
    ) is False


def test_does_not_trigger_on_non_tabular_page() -> None:
    primary = [
        _word("HSBC", 80.0, 100.0),
        _word("Estado", 250.0, 120.0),
        _word("de", 300.0, 120.0),
        _word("Cuenta", 320.0, 120.0),
    ]
    recovery = [*primary, *_financial_row(1, 180.0)]

    assert AdaptiveTesseractPDFReader.should_use_recovery_page(
        primary,
        recovery,
    ) is False
