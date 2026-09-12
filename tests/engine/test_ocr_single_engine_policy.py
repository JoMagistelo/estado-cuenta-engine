from types import SimpleNamespace

import pytest

from engine import pipeline
from readers.models import DocumentData


def _document(engine: str) -> DocumentData:
    return DocumentData(
        raw_text="HSBC",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": engine,
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )


def test_selected_engine_is_the_only_ocr_used_by_standard_processing(monkeypatch):
    document = _document("paddleocr")
    estado = SimpleNamespace(movimientos=[], resumen_financiero=None)
    calls: list[str] = []

    def _read(path, engine, start_page=0, cancel_event=None, *, artifact_dir=None):
        calls.append(engine)
        return document

    monkeypatch.setattr(pipeline.ReaderManager, "read_ocr_for_parser", _read)
    monkeypatch.setattr(pipeline, "identify_bank_key", lambda **kwargs: "hsbc")
    monkeypatch.setattr(
        pipeline,
        "process_single_statement_with_ocr_review",
        lambda document, bank_key: (estado, document, None),
    )

    prepared = pipeline.PreparedStatement(
        file_name="statement.pdf",
        pdf_path="statement.pdf",
        document=None,
        processing_method="OCR",
    )
    result = pipeline._process_prepared_statement(
        prepared,
        ocr_primary_engine="paddleocr",
    )

    assert calls == ["paddleocr"]
    assert result.ocr_requested_primary_engine == "paddleocr"
    assert result.ocr_primary_engine == "paddleocr"
    assert result.ocr_engine == "paddleocr"
    assert result.ocr_secondary_engine is None
    assert result.fallback_attempted is False
    assert result.fallback_used is False
    assert document.metadata["ocr_requested_primary_engine"] == "paddleocr"
    assert document.metadata["ocr_primary_engine"] == "paddleocr"
    assert document.metadata["ocr_secondary_engine"] is None
    assert document.metadata["ocr_fallback_attempted"] is False


def test_selected_engine_startup_failure_is_not_recovered_automatically(monkeypatch):
    calls: list[str] = []

    def _read(path, engine, start_page=0, cancel_event=None, *, artifact_dir=None):
        calls.append(engine)
        raise RuntimeError(f"{engine} unavailable")

    monkeypatch.setattr(pipeline.ReaderManager, "read_ocr_for_parser", _read)

    prepared = pipeline.PreparedStatement(
        file_name="statement.pdf",
        pdf_path="statement.pdf",
        document=None,
        processing_method="OCR",
    )

    with pytest.raises(RuntimeError, match="paddleocr unavailable"):
        pipeline._process_prepared_statement(
            prepared,
            ocr_primary_engine="paddleocr",
        )

    assert calls == ["paddleocr"]
