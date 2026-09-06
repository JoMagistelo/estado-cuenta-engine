from __future__ import annotations

from types import SimpleNamespace

from exporters.export_snapshot import snapshot_results_for_export
from models.ocr_review import OCRCandidate, OCRReview
from models.processing_result import ProcessingResult
from readers.models import DocumentData


def _candidate(engine: str, marker: str) -> OCRCandidate:
    document = DocumentData(
        raw_text=marker,
        normalized_text=marker,
        metadata={"reader": engine, "ocr": True},
    )
    estado = SimpleNamespace(
        marker=marker,
        movimientos=[SimpleNamespace(marker=marker)],
    )
    return OCRCandidate(
        engine=engine,
        estado_cuenta=estado,
        document=document,
        validaciones=[],
    )


def _result(file_name: str, selected_engine: str) -> ProcessingResult:
    tesseract = _candidate("tesseract", f"{file_name}-T")
    paddle = _candidate("paddleocr", f"{file_name}-P")
    review = OCRReview(
        candidates={
            "tesseract": tesseract,
            "paddleocr": paddle,
        },
        recommended_engine="tesseract",
        selected_engine=selected_engine,
    )
    selected = review.get_candidate(selected_engine)
    return ProcessingResult(
        file_name=file_name,
        bank_key="hsbc",
        estado_cuenta=selected.estado_cuenta,
        raw_text=selected.document.raw_text,
        normalized_text=selected.document.normalized_text,
        validaciones=[],
        processing_method="OCR",
        ocr_review=review,
    )


def test_snapshot_preserves_independent_engine_selection_per_file():
    first = _result("uno.pdf", "tesseract")
    second = _result("dos.pdf", "paddleocr")

    snapshot = snapshot_results_for_export([first, second])

    assert snapshot[0].estado_cuenta.marker == "uno.pdf-T"
    assert snapshot[1].estado_cuenta.marker == "dos.pdf-P"
    assert snapshot[0].ocr_review is None
    assert snapshot[1].ocr_review is None

    # Cambiar la UI después del clic de exportación no altera el snapshot.
    first.select_ocr_engine("paddleocr")
    second.select_ocr_engine("tesseract")

    assert first.estado_cuenta.marker == "uno.pdf-P"
    assert second.estado_cuenta.marker == "dos.pdf-T"
    assert snapshot[0].estado_cuenta.marker == "uno.pdf-T"
    assert snapshot[1].estado_cuenta.marker == "dos.pdf-P"
