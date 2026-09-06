from types import SimpleNamespace

from engine import pipeline, statement_processor
from engine.ocr_fallback_policy import (
    fallback_trigger_reasons,
    should_attempt_secondary_fallback,
)
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
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


def _primary_ok() -> list[ResultadoValidacion]:
    return [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
    ]


def _estado(name: str):
    return SimpleNamespace(
        name=name,
        movimientos=[object()],
        resumen_financiero=object(),
    )


def _document(engine: str) -> DocumentData:
    return DocumentData(
        raw_text=f"HSBC {engine}",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": engine,
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )


def test_any_failed_validation_requests_secondary_ocr():
    validations = [*_primary_ok(), _validation("Saldo final", False)]

    reasons = fallback_trigger_reasons(validations, has_movements=True)

    assert "validacion_fallida" in reasons
    assert should_attempt_secondary_fallback(validations, has_movements=True) is True


def test_tesseract_non_primary_tache_runs_paddle_and_keeps_both_candidates(monkeypatch):
    tesseract_document = _document("tesseract")
    paddle_document = _document("paddleocr")
    tesseract_estado = _estado("tesseract")
    paddle_estado = _estado("paddleocr")
    paddle_calls: list[str] = []

    tesseract_validations = [*_primary_ok(), _validation("Saldo final", False)]
    paddle_validations = [*_primary_ok(), _validation("Saldo final", True)]

    def _process(document, bank_key):
        assert bank_key == "hsbc"
        if document is tesseract_document:
            return tesseract_estado, document
        return paddle_estado, document

    def _validations(estado):
        if estado is tesseract_estado:
            return tesseract_validations
        return paddle_validations

    def _read_paddle(*args, **kwargs):
        paddle_calls.append("paddleocr")
        return paddle_document

    monkeypatch.setattr(statement_processor, "_process_once", _process)
    monkeypatch.setattr(statement_processor, "_validation_results", _validations)
    monkeypatch.setattr(statement_processor.ReaderManager, "read_paddle_ocr", _read_paddle)

    _estado_result, _document_result, review = (
        statement_processor.process_single_statement_with_ocr_review(
            tesseract_document,
            "hsbc",
        )
    )

    assert paddle_calls == ["paddleocr"]
    assert review is not None
    assert review.available_engines() == ("tesseract", "paddleocr")
    assert review.requires_user_selection is True
    assert review.get_candidate("tesseract").validaciones == tesseract_validations
    assert review.get_candidate("paddleocr").validaciones == paddle_validations


def test_reader_manager_routes_selected_paddle_engine_to_paddle_reader(monkeypatch):
    paddle_document = _document("paddleocr")
    calls: list[str] = []

    def _read_paddle(file_path, start_page=0, cancel_event=None):
        calls.append(str(file_path))
        return paddle_document

    monkeypatch.setattr(ReaderManager, "read_paddle_ocr", staticmethod(_read_paddle))

    result = ReaderManager.read_ocr_engine(
        "statement.pdf",
        engine="paddleocr",
        start_page=0,
    )

    assert calls == ["statement.pdf"]
    assert result is paddle_document
    assert result.metadata["reader"] == "paddleocr"


def test_pipeline_preserves_requested_engine_for_ui_trace(monkeypatch):
    tesseract_document = _document("tesseract")
    estado = SimpleNamespace(movimientos=[], resumen_financiero=None)
    calls: list[str] = []

    def _read(path, engine, start_page=0):
        calls.append(engine)
        if engine == "paddleocr":
            raise RuntimeError("paddle unavailable")
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
    assert result.ocr_requested_primary_engine == "paddleocr"
    assert result.ocr_primary_engine == "tesseract"
    assert result.ocr_engine == "tesseract"
