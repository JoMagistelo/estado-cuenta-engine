from validators.resultado_validacion import ResultadoValidacion

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

    assert should_select_paddle_result(tesseract, paddle_better) is True
    assert should_select_paddle_result(tesseract, paddle_equal) is False
    assert should_select_paddle_result(tesseract, paddle_less_coverage) is False


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
    assert profile.failed_names == ("Abonos",)
