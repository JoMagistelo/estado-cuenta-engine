from types import SimpleNamespace

from engine import pipeline, statement_processor
from engine.ocr_fallback_policy import (
    primary_validations_pass,
    secondary_ocr_engine,
    should_attempt_secondary_fallback,
)
from readers.models import DocumentData
from validators.resultado_validacion import ResultadoValidacion


def _validation(name: str, correcto: bool) -> ResultadoValidacion:
    return ResultadoValidacion(
        nombre=name,
        esperado=1.0,
        obtenido=1.0 if correcto else 2.0,
        diferencia=0.0 if correcto else 1.0,
        correcto=correcto,
        mensaje="test",
    )


def _primary_ok():
    return [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
    ]


def _primary_failed():
    return [
        _validation("Total depósitos / abonos", False),
        _validation("Total retiros / cargos", True),
    ]


def _estado(name: str):
    return SimpleNamespace(
        name=name,
        movimientos=[object()],
        resumen_financiero=object(),
    )


def test_secondary_engine_is_symmetric():
    assert secondary_ocr_engine("tesseract") == "paddleocr"
    assert secondary_ocr_engine("paddleocr") == "tesseract"


def test_fallback_depends_only_on_primary_financial_validations():
    assert primary_validations_pass(_primary_ok()) is True
    assert should_attempt_secondary_fallback(_primary_ok()) is False
    assert should_attempt_secondary_fallback(_primary_failed()) is True
    assert should_attempt_secondary_fallback([]) is True


def test_paddle_primary_does_not_run_tesseract_when_validations_pass(monkeypatch):
    primary_estado = _estado("paddle")
    primary_document = DocumentData(
        raw_text="HSBC PADDLE",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "paddleocr",
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )

    monkeypatch.setattr(
        statement_processor,
        "_process_once",
        lambda document, bank_key: (primary_estado, document),
    )
    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: _primary_ok(),
    )

    def _must_not_run(*args, **kwargs):
        raise AssertionError("Tesseract no debe ejecutarse si PaddleOCR validó bien")

    monkeypatch.setattr(statement_processor.ReaderManager, "read_ocr", _must_not_run)

    estado, document, review = statement_processor.process_single_statement_with_ocr_review(
        primary_document,
        "hsbc",
    )

    assert estado is primary_estado
    assert document is primary_document
    assert review is None
    assert primary_document.metadata["ocr_fallback_attempted"] is False


def test_paddle_primary_runs_tesseract_only_after_validation_failure(monkeypatch):
    primary_estado = _estado("paddle")
    secondary_estado = _estado("tesseract")
    primary_document = DocumentData(
        raw_text="HSBC PADDLE",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "paddleocr",
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )
    secondary_document = DocumentData(
        raw_text="HSBC TESSERACT",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "tesseract",
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )

    def _process(document, bank_key):
        if document is primary_document:
            return primary_estado, document
        return secondary_estado, document

    monkeypatch.setattr(statement_processor, "_process_once", _process)
    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: _primary_failed() if estado is primary_estado else _primary_ok(),
    )
    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_ocr",
        lambda *args, **kwargs: secondary_document,
    )

    estado, document, review = statement_processor.process_single_statement_with_ocr_review(
        primary_document,
        "hsbc",
    )

    assert review is not None
    assert review.selected_engine == "tesseract"
    assert estado is secondary_estado
    assert document is secondary_document
    assert secondary_document.metadata["ocr_fallback_attempted"] is True
    assert secondary_document.metadata["ocr_fallback_selected"] is True


def test_pipeline_passes_selected_primary_engine_to_ocr_reader(monkeypatch):
    captured = []
    document = DocumentData(
        raw_text="HSBC",
        normalized_text="",
        spatial_words=[],
        metadata={"ocr": True, "reader": "paddleocr"},
    )
    estado = SimpleNamespace(movimientos=[], resumen_financiero=None)

    def _read(path, engine, start_page=0):
        captured.append(engine)
        return document

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

    assert captured == ["paddleocr"]
    assert result.ocr_primary_engine == "paddleocr"
    assert result.ocr_engine == "paddleocr"
