from __future__ import annotations

import os
from dataclasses import dataclass

from validators.resultado_validacion import ResultadoValidacion


OCR_ENGINES = ("tesseract", "paddleocr")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
PRIMARY_VALIDATION_NAMES = (
    "Total depósitos / abonos",
    "Total retiros / cargos",
)
_PRIMARY_VALIDATION_NAMES = set(PRIMARY_VALIDATION_NAMES)


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    total: int
    passed: int
    failed: int
    names: tuple[str, ...]
    failed_names: tuple[str, ...]


def normalize_ocr_engine(value: str | None, default: str = "tesseract") -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "paddle": "paddleocr",
        "paddle_ocr": "paddleocr",
        "tess": "tesseract",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in OCR_ENGINES:
        return normalized
    return default


def secondary_ocr_engine(primary_engine: str | None) -> str:
    primary = normalize_ocr_engine(primary_engine)
    return "paddleocr" if primary == "tesseract" else "tesseract"


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
    """Compatibilidad con la configuración histórica del fallback PaddleOCR.

    El flujo nuevo de UI ya no necesita esta bandera: cuando el usuario elige
    Tesseract como primario, PaddleOCR es el secundario y sólo se ejecuta si
    falla una validación financiera principal. La función se conserva para
    scripts y pruebas existentes.
    """
    if not _env_flag("PADDLEOCR_FALLBACK_ENABLED", default=False):
        return False

    configured = os.getenv("PADDLEOCR_FALLBACK_BANKS", "hsbc").strip().lower()
    if configured in _FALSE_VALUES or configured == "none":
        return False
    if configured == "*":
        return True

    allowed = {item.strip() for item in configured.split(",") if item.strip()}
    return bank_key.strip().lower() in allowed


def validation_profile(validaciones: list[ResultadoValidacion]) -> ValidationProfile:
    names = tuple(validation.nombre for validation in validaciones)
    failed_names = tuple(
        validation.nombre for validation in validaciones if not validation.correcto
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


def _primary_validation_map(validaciones: list[ResultadoValidacion]) -> dict[str, bool]:
    return {
        validation.nombre: bool(validation.correcto)
        for validation in validaciones
        if validation.nombre in _PRIMARY_VALIDATION_NAMES
    }


def primary_validations_pass(validaciones: list[ResultadoValidacion]) -> bool:
    """True sólo cuando las dos conciliaciones principales existen y pasan."""
    status = _primary_validation_map(validaciones)
    return all(status.get(name) is True for name in PRIMARY_VALIDATION_NAMES)


def primary_validation_score(validaciones: list[ResultadoValidacion]) -> tuple[int, int]:
    """Devuelve (correctas, presentes) para comparar candidato primario/secundario."""
    status = _primary_validation_map(validaciones)
    present = len(status)
    passed = sum(1 for value in status.values() if value)
    return passed, present


def fallback_trigger_reasons(
    validaciones: list[ResultadoValidacion],
    *,
    has_movements: bool,
) -> tuple[str, ...]:
    """Razones de fallback limitadas a las dos validaciones financieras clave.

    No se activa un segundo OCR por cantidad de movimientos, campos opcionales,
    score heurístico ni por simple disponibilidad. Si no hay movimientos, las
    validaciones principales no podrán existir y eso se representa como
    ``validacion_principal_ausente``.
    """
    status = _primary_validation_map(validaciones)
    reasons: list[str] = []

    missing = [name for name in PRIMARY_VALIDATION_NAMES if name not in status]
    failed = [name for name, ok in status.items() if not ok]

    # Se conservan estas etiquetas diagnósticas por compatibilidad, pero la
    # decisión de fallback se toma únicamente por validaciones principales.
    if not has_movements:
        reasons.append("sin_movimientos")
    if not validaciones:
        reasons.append("sin_validaciones")
    if missing:
        reasons.append("validacion_principal_ausente")
    if failed:
        reasons.append("validacion_principal_fallida")

    return tuple(reasons)


def should_attempt_secondary_fallback(
    validaciones: list[ResultadoValidacion],
    *,
    has_movements: bool = True,
) -> bool:
    reasons = fallback_trigger_reasons(
        validaciones,
        has_movements=has_movements,
    )
    return any(
        reason in {
            "validacion_principal_ausente",
            "validacion_principal_fallida",
        }
        for reason in reasons
    )


def should_attempt_paddle_fallback(
    bank_key: str,
    validaciones: list[ResultadoValidacion],
    *,
    has_movements: bool = True,
) -> bool:
    """API histórica: respeta la bandera vieja y el nuevo criterio estricto."""
    if not paddle_fallback_enabled(bank_key):
        return False
    return should_attempt_secondary_fallback(
        validaciones,
        has_movements=has_movements,
    )


def should_select_secondary_result(
    primary_validaciones: list[ResultadoValidacion],
    secondary_validaciones: list[ResultadoValidacion],
    *,
    primary_has_movements: bool = True,
    secondary_has_movements: bool = True,
) -> bool:
    """Selecciona el secundario sólo si mejora la conciliación principal."""
    primary_score = primary_validation_score(primary_validaciones)
    secondary_score = primary_validation_score(secondary_validaciones)

    if primary_validations_pass(secondary_validaciones):
        return True

    if not secondary_has_movements and primary_has_movements:
        return False
    if secondary_has_movements and not primary_has_movements:
        return secondary_score >= primary_score

    return secondary_score > primary_score


def should_select_paddle_result(
    tesseract_validaciones: list[ResultadoValidacion],
    paddle_validaciones: list[ResultadoValidacion],
    *,
    tesseract_has_movements: bool = True,
    paddle_has_movements: bool = True,
) -> bool:
    """Compatibilidad con la heurística histórica Tesseract -> PaddleOCR."""
    tesseract = validation_profile(tesseract_validaciones)
    paddle = validation_profile(paddle_validaciones)

    if not tesseract_has_movements and paddle_has_movements:
        return True
    if tesseract_has_movements and not paddle_has_movements:
        return False

    tesseract_names = set(tesseract.names)
    paddle_names = set(paddle.names)
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
