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


def test_requested_paddle_failure_recovers_with_tesseract(monkeypatch):
    tesseract_document = _document("tesseract")
    estado = SimpleNamespace(movimientos=[], resumen_financiero=None)
    calls = []

    def _read(path, engine, start_page=0):
        calls.append(engine)
        if engine == "paddleocr":
            raise RuntimeError("paddle startup failed")
        return tesseract_document

    monkeypatch.setattr(pipeline.ReaderManager, "read_ocr_engine", _read)
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

    assert calls == ["paddleocr", "tesseract"]
    assert result.ocr_primary_engine == "tesseract"
    assert result.ocr_engine == "tesseract"
    assert tesseract_document.metadata["ocr_requested_primary_engine"] == "paddleocr"
    assert tesseract_document.metadata["ocr_unavailable_engine"] == "paddleocr"
    assert tesseract_document.metadata["ocr_startup_recovered"] is True
    assert tesseract_document.metadata["ocr_startup_error_type"] == "RuntimeError"


def test_primary_and_recovery_failure_still_surfaces_error(monkeypatch):
    calls = []

    def _read(path, engine, start_page=0):
        calls.append(engine)
        raise RuntimeError(f"{engine} unavailable")

    monkeypatch.setattr(pipeline.ReaderManager, "read_ocr_engine", _read)

    prepared = pipeline.PreparedStatement(
        file_name="statement.pdf",
        pdf_path="statement.pdf",
        document=None,
        processing_method="OCR",
    )

    with pytest.raises(RuntimeError, match="tesseract unavailable"):
        pipeline._process_prepared_statement(
            prepared,
            ocr_primary_engine="paddleocr",
        )

    assert calls == ["paddleocr", "tesseract"]
