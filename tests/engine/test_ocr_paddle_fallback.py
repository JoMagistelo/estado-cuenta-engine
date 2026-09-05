from types import SimpleNamespace

from engine import statement_processor
from engine.ocr_fallback_policy import (
    fallback_trigger_reasons,
    paddle_fallback_enabled,
    should_attempt_paddle_fallback,
    should_select_paddle_result,
    validation_profile,
)
from models.ocr_review import OCRCandidate, OCRReview
from models.processing_result import ProcessingResult
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


def test_fallback_starts_for_tache_dash_or_missing_movements(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "*")

    complete_ok = [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
    ]
    one_failed = [
        _validation("Total depósitos / abonos", False),
        _validation("Total retiros / cargos", True),
    ]
    one_missing = [
        _validation("Total depósitos / abonos", True),
    ]

    assert should_attempt_paddle_fallback(
        "hsbc",
        complete_ok,
        has_movements=True,
    ) is False
    assert should_attempt_paddle_fallback(
        "hsbc",
        one_failed,
        has_movements=True,
    ) is True
    assert should_attempt_paddle_fallback(
        "hsbc",
        one_missing,
        has_movements=True,
    ) is True
    assert should_attempt_paddle_fallback(
        "hsbc",
        [],
        has_movements=False,
    ) is True


def test_trigger_reasons_are_technical_only():
    reasons = fallback_trigger_reasons(
        [],
        has_movements=False,
    )

    assert "sin_movimientos" in reasons
    assert "validacion_principal_ausente" in reasons
    assert "sin_validaciones" in reasons


def test_paddle_recommendation_preserves_existing_validator_coverage():
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


def test_paddle_is_recommended_if_tesseract_has_no_movements():
    assert should_select_paddle_result(
        [],
        [],
        tesseract_has_movements=False,
        paddle_has_movements=True,
    ) is True


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


def test_failed_tesseract_result_builds_two_review_candidates(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "hsbc")

    tesseract_estado = _estado("tesseract")
    paddle_estado = _estado("paddle", movement_count=2)

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
    paddle_document = DocumentData(
        raw_text="HSBC PADDLE",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "paddleocr",
        },
    )

    tesseract_validations = [
        _validation("Total depósitos / abonos", False),
        _validation("Total retiros / cargos", True),
    ]
    paddle_validations = [
        _validation("Total depósitos / abonos", True),
        _validation("Total retiros / cargos", True),
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

    candidate = OCRCandidate(
        engine="tesseract",
        estado_cuenta=tesseract_estado,
        document=tesseract_document,
        validaciones=tesseract_validations,
    )
    review = statement_processor._try_paddle_review(candidate, "hsbc")

    assert review is not None
    assert review.available_engines() == ("tesseract", "paddleocr")
    assert review.recommended_engine == "paddleocr"
    assert review.selected_engine == "paddleocr"
    assert review.get_candidate("tesseract").movement_count == 1
    assert review.get_candidate("paddleocr").movement_count == 2


def test_processing_result_can_switch_between_ocr_candidates():
    tesseract_document = DocumentData(
        raw_text="TESSERACT",
        normalized_text="TESSERACT",
        metadata={"reader": "tesseract", "ocr": True},
    )
    paddle_document = DocumentData(
        raw_text="PADDLE",
        normalized_text="PADDLE",
        metadata={"reader": "paddleocr", "ocr": True},
    )
    tesseract_estado = _estado("tesseract", movement_count=1)
    paddle_estado = _estado("paddle", movement_count=3)
    tesseract_validations = [_validation("Abonos", False)]
    paddle_validations = [_validation("Abonos", True)]

    review = OCRReview(
        candidates={
            "tesseract": OCRCandidate(
                "tesseract",
                tesseract_estado,
                tesseract_document,
                tesseract_validations,
            ),
            "paddleocr": OCRCandidate(
                "paddleocr",
                paddle_estado,
                paddle_document,
                paddle_validations,
            ),
        },
        recommended_engine="paddleocr",
        selected_engine="paddleocr",
    )
    result = ProcessingResult(
        file_name="test.pdf",
        bank_key="hsbc",
        estado_cuenta=paddle_estado,
        raw_text=paddle_document.raw_text,
        normalized_text=paddle_document.normalized_text,
        validaciones=list(paddle_validations),
        processing_method="OCR",
        ocr_review=review,
    )

    result.select_ocr_engine("tesseract")

    assert result.selected_ocr_engine == "tesseract"
    assert result.estado_cuenta is tesseract_estado
    assert result.raw_text == "TESSERACT"
    assert result.validaciones == tesseract_validations


def test_paddle_error_keeps_tesseract_as_only_candidate(monkeypatch):
    monkeypatch.setenv("PADDLEOCR_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("PADDLEOCR_FALLBACK_BANKS", "hsbc")

    tesseract_estado = _estado("tesseract")
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
    tesseract_validations = [
        _validation("Total depósitos / abonos", False),
        _validation("Total retiros / cargos", True),
    ]

    def _raise(*args, **kwargs):
        raise RuntimeError("reader unavailable")

    monkeypatch.setattr(
        statement_processor.ReaderManager,
        "read_paddle_ocr",
        _raise,
    )

    candidate = OCRCandidate(
        "tesseract",
        tesseract_estado,
        tesseract_document,
        tesseract_validations,
    )
    review = statement_processor._try_paddle_review(candidate, "hsbc")

    assert review is not None
    assert review.available_engines() == ("tesseract",)
    assert review.selected_engine == "tesseract"
    assert review.paddle_error_type == "RuntimeError"
