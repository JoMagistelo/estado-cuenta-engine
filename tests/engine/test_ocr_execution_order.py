from __future__ import annotations

from types import SimpleNamespace

from engine import statement_processor
from engine.ocr_execution import (
    normalize_ocr_engine,
    secondary_ocr_engine,
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


def _estado(name: str, movement_count: int = 1):
    return SimpleNamespace(
        name=name,
        movimientos=[object() for _ in range(movement_count)],
        resumen_financiero=object(),
    )


def test_ocr_engine_preference_is_normalized_safely():
    assert normalize_ocr_engine("PaddleOCR") == "paddleocr"
    assert normalize_ocr_engine("tesseract") == "tesseract"
    assert normalize_ocr_engine("desconocido") == "tesseract"
    assert secondary_ocr_engine("paddleocr") == "tesseract"
    assert secondary_ocr_engine("tesseract") == "paddleocr"


def test_paddle_primary_can_trigger_tesseract_review(monkeypatch):
    paddle_estado = _estado("paddle", movement_count=2)
    tesseract_estado = _estado("tesseract", movement_count=2)

    paddle_document = DocumentData(
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
    tesseract_document = DocumentData(
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

    paddle_validations = [
        _validation("Total depósitos / abonos", False),
        _validation("Total retiros / cargos", True),
    ]
    tesseract_validations = [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
    ]

    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_ocr",
        lambda *args, **kwargs: tesseract_document,
    )
    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_paddle_ocr",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("PaddleOCR no debe ejecutarse dos veces")
        ),
    )
    monkeypatch.setattr(
        statement_processor,
        "_process_once",
        lambda document, bank_key: (
            paddle_estado
            if document.metadata.get("reader") == "paddleocr"
            else tesseract_estado,
            document,
        ),
    )
    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: (
            paddle_validations
            if estado is paddle_estado
            else tesseract_validations
        ),
    )

    estado, document, review = (
        statement_processor.process_single_statement_with_ocr_review(
            paddle_document,
            "hsbc",
        )
    )

    assert review is not None
    assert review.available_engines() == ("tesseract", "paddleocr")
    assert review.recommended_engine == "tesseract"
    assert review.selected_engine == "tesseract"
    assert estado is tesseract_estado
    assert document is tesseract_document


def test_good_paddle_primary_does_not_run_secondary_engine(monkeypatch):
    paddle_estado = _estado("paddle", movement_count=2)
    paddle_document = DocumentData(
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
    complete_ok = [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
    ]

    monkeypatch.setattr(
        statement_processor,
        "_process_once",
        lambda document, bank_key: (paddle_estado, document),
    )
    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: complete_ok,
    )
    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_ocr",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tesseract no debe ejecutarse sin señal de revisión")
        ),
    )

    estado, document, review = (
        statement_processor.process_single_statement_with_ocr_review(
            paddle_document,
            "hsbc",
        )
    )

    assert estado is paddle_estado
    assert document is paddle_document
    assert review is None
