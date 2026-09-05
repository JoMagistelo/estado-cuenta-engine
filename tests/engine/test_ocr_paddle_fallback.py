from types import SimpleNamespace

from readers.models import DocumentData
from validators.resultado_validacion import ResultadoValidacion

from engine import statement_processor
from engine.ocr_fallback_policy import (
    paddle_fallback_enabled,
    should_attempt_paddle_fallback,
    should_select_paddle_result,
    validation_profile,
)


def _validation(name: str, correcto: bool) -> ResultadoValidacion:
    return ResultadoValidacion(
        nombre=name,
        esperado=1.0,
        obtenido=1.0 if correcto else 2.0,
        diferencia=0.0 if correcto else 1.0,
        correcto=correcto,
        mensaje="test",
    )


def test_paddle_fallback_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PADDLEOCR_FALLBACK_ENABLED", raising=False)
    monkeypatch.delenv("PADDLEOCR_FALLBACK_BANKS", raising=False)

    assert paddle_fallback_enabled("hsbc") is False


def test_enabled_fallback_defaults_to_hsbc_only(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.delenv("PADDLEOCR_FALLBACK_BANKS", raising=False)

    assert paddle_fallback_enabled("hsbc") is True
    assert paddle_fallback_enabled("bbva") is False


def test_paddle_fallback_can_be_restricted_by_bank(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "hsbc,banorte")

    assert paddle_fallback_enabled("hsbc") is True
    assert paddle_fallback_enabled("banorte") is True
    assert paddle_fallback_enabled("bbva") is False


def test_fallback_only_starts_after_explicit_validation_failure(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "*")

    assert should_attempt_paddle_fallback("hsbc", []) is False
    assert should_attempt_paddle_fallback(
        "hsbc",
        [_validation("Saldo final", True)],
    ) is False
    assert should_attempt_paddle_fallback(
        "hsbc",
        [_validation("Saldo final", False)],
    ) is True


def test_paddle_must_improve_failures_without_reducing_coverage():
    tesseract = [
        _validation("Abonos", False),
        _validation("Cargos", True),
    ]

    paddle_better = [
        _validation("Abonos", True),
        _validation("Cargos", True),
    ]
    paddle_equal = [
        _validation("Abonos", False),
        _validation("Cargos", True),
    ]
    paddle_less_coverage = [
        _validation("Abonos", True),
    ]
    paddle_different_validators = [
        _validation("Saldo final", True),
        _validation("Ecuación financiera", True),
    ]

    assert should_select_paddle_result(tesseract, paddle_better) is True
    assert should_select_paddle_result(tesseract, paddle_equal) is False
    assert should_select_paddle_result(tesseract, paddle_less_coverage) is False
    assert should_select_paddle_result(tesseract, paddle_different_validators) is False


def test_validation_profile_contains_no_financial_values():
    profile = validation_profile(
        [
            _validation("Abonos", False),
            _validation("Cargos", True),
        ]
    )

    assert profile.total == 2
    assert profile.passed == 1
    assert profile.failed == 1
    assert profile.names == ("Abonos", "Cargos")
    assert profile.failed_names == ("Abonos",)


def test_failed_tesseract_validation_can_select_better_paddle(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "hsbc")

    tesseract_estado = SimpleNamespace(name="tesseract")
    paddle_estado = SimpleNamespace(name="paddle")

    tesseract_document = DocumentData(
        raw_text="HSBC",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "tesseract",
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )
    paddle_document = DocumentData(
        raw_text="HSBC",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "paddleocr",
        },
    )

    tesseract_validations = [
        _validation("Abonos", False),
        _validation("Cargos", True),
    ]
    paddle_validations = [
        _validation("Abonos", True),
        _validation("Cargos", True),
    ]

    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_paddle_ocr",
        lambda *args, **kwargs: paddle_document,
    )
    monkeypatch.setattr(
        statement_processor,
        "_process_once",
        lambda document, bank_key: (paddle_estado, document),
    )
    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: (
            tesseract_validations
            if estado is tesseract_estado
            else paddle_validations
        ),
    )

    estado, document = statement_processor._try_paddle_fallback(
        tesseract_estado,
        tesseract_document,
        "hsbc",
    )

    assert estado is paddle_estado
    assert document is paddle_document
    assert document.metadata["paddle_fallback_selected"] is True
    assert document.metadata["fallback_from"] == "tesseract"


def test_paddle_error_preserves_tesseract_result(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "hsbc")

    tesseract_estado = SimpleNamespace(name="tesseract")
    tesseract_document = DocumentData(
        raw_text="HSBC",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "tesseract",
            "source_path": "statement.pdf",
            "start_page": 0,
        },
    )

    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda estado: [_validation("Abonos", False)],
    )

    def _raise(*args, **kwargs):
        raise RuntimeError("reader unavailable")

    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_paddle_ocr",
        _raise,
    )

    estado, document = statement_processor._try_paddle_fallback(
        tesseract_estado,
        tesseract_document,
        "hsbc",
    )

    assert estado is tesseract_estado
    assert document is tesseract_document
    assert document.metadata["paddle_fallback_selected"] is False
    assert document.metadata["paddle_fallback_error_type"] == "RuntimeError"
