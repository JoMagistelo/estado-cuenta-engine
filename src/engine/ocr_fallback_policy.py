from __future__ import annotations

import os
from dataclasses import dataclass

from validators.resultado_validacion import ResultadoValidacion


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_PRIMARY_VALIDATION_NAMES = {
    "Total depósitos / abonos",
    "Total retiros / cargos",
}


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    total: int
    passed: int
    failed: int
    names: tuple[str, ...]
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
        "hsbc",
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
    names = tuple(validation.nombre for validation in validaciones)
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
        names=names,
        failed_names=failed_names,
    )


def fallback_trigger_reasons(
    validaciones: list[ResultadoValidacion],
    *,
    has_movements: bool,
) -> tuple[str, ...]:
    """Describe por qué conviene generar un segundo candidato OCR.

    Las razones son exclusivamente señales observables del resultado actual:
    ausencia de movimientos, validaciones con tache o validadores principales
    que no pudieron calcularse y por ello se muestran como guion en la UI.
    """
    reasons: list[str] = []
    profile = validation_profile(validaciones)

    if not has_movements:
        reasons.append("sin_movimientos")

    if profile.failed > 0:
        reasons.append("validacion_fallida")

    present_names = set(profile.names)
    if not _PRIMARY_VALIDATION_NAMES.issubset(present_names):
        reasons.append("validacion_principal_ausente")

    if profile.total == 0:
        reasons.append("sin_validaciones")

    return tuple(dict.fromkeys(reasons))


def should_attempt_paddle_fallback(
    bank_key: str,
    validaciones: list[ResultadoValidacion],
    *,
    has_movements: bool = True,
) -> bool:
    """Activa PaddleOCR cuando el OCR primario requiere revisión objetiva."""
    if not paddle_fallback_enabled(bank_key):
        return False

    return bool(
        fallback_trigger_reasons(
            validaciones,
            has_movements=has_movements,
        )
    )


def should_select_paddle_result(
    tesseract_validaciones: list[ResultadoValidacion],
    paddle_validaciones: list[ResultadoValidacion],
    *,
    tesseract_has_movements: bool = True,
    paddle_has_movements: bool = True,
) -> bool:
    """Genera una recomendación conservadora entre ambos candidatos OCR.

    La recomendación nunca elimina la posibilidad de selección manual en UI.
    Ante empate o evidencia insuficiente se conserva Tesseract.
    """
    tesseract = validation_profile(tesseract_validaciones)
    paddle = validation_profile(paddle_validaciones)

    if not tesseract_has_movements and paddle_has_movements:
        return True

    if tesseract_has_movements and not paddle_has_movements:
        return False

    tesseract_names = set(tesseract.names)
    paddle_names = set(paddle.names)

    # Paddle nunca se recomienda si pierde un validador que sí pudo calcular
    # Tesseract. Así no se confunde menor cobertura con una aparente mejora.
    if not tesseract_names.issubset(paddle_names):
        return False

    tesseract_primary = len(tesseract_names & _PRIMARY_VALIDATION_NAMES)
    paddle_primary = len(paddle_names & _PRIMARY_VALIDATION_NAMES)

    if paddle_primary > tesseract_primary and paddle.failed <= tesseract.failed:
        return True

    if paddle.failed < tesseract.failed:
        return True

    if tesseract.total == 0 and paddle.total > 0:
        return True

    return False
