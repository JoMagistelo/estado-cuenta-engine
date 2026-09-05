from __future__ import annotations

import os
from dataclasses import dataclass

from validators.resultado_validacion import ResultadoValidacion


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    total: int
    passed: int
    failed: int
    failed_names: tuple[str, ...]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False

    return default


def paddle_fallback_enabled(bank_key: str) -> bool:
    """Indica si el fallback PaddleOCR está habilitado para el banco."""
    if not _env_flag("PADDLEOCR_FALLBACK_ENABLED", default=False):
        return False

    configured = os.getenv(
        "PADDLEOCR_FALLBACK_BANKS",
        "*",
    ).strip().lower()

    if configured in _FALSE_VALUES or configured == "none":
        return False

    if configured == "*":
        return True

    allowed = {
        item.strip()
        for item in configured.split(",")
        if item.strip()
    }
    return bank_key.strip().lower() in allowed


def validation_profile(
    validaciones: list[ResultadoValidacion],
) -> ValidationProfile:
    failed_names = tuple(
        validation.nombre
        for validation in validaciones
        if not validation.correcto
    )
    failed = len(failed_names)
    total = len(validaciones)

    return ValidationProfile(
        total=total,
        passed=total - failed,
        failed=failed,
        failed_names=failed_names,
    )


def should_attempt_paddle_fallback(
    bank_key: str,
    validaciones: list[ResultadoValidacion],
) -> bool:
    """Activa PaddleOCR sólo ante una falla explícita de validación."""
    if not paddle_fallback_enabled(bank_key):
        return False

    profile = validation_profile(validaciones)
    return profile.total > 0 and profile.failed > 0


def should_select_paddle_result(
    tesseract_validaciones: list[ResultadoValidacion],
    paddle_validaciones: list[ResultadoValidacion],
) -> bool:
    """Selecciona Paddle sólo si mejora fallas sin reducir cobertura."""
    tesseract = validation_profile(tesseract_validaciones)
    paddle = validation_profile(paddle_validaciones)

    if tesseract.failed == 0:
        return False

    if paddle.total == 0:
        return False

    if paddle.total < tesseract.total:
        return False

    return paddle.failed < tesseract.failed
