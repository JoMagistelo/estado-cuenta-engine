from __future__ import annotations

from importlib import import_module
from typing import Callable

from engine.ocr_fallback_policy import (
    should_attempt_paddle_fallback,
    should_select_paddle_result,
    validation_profile,
)
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from utils.text_normalizer import normalize_text

from parsers.bbva import parse_bbva
from parsers.banamex import parse_banamex
from parsers.banorte import parse_banorte
from parsers.banorte_ocr import parse_banorte_ocr
from parsers.hsbc import parse_hsbc
from parsers.scotiabank import parse_scotiabank
from parsers.cetes import parse_cetes
from parsers.mifel import parse_mifel
from parsers.mercado_pago import parse_mercado_pago
from validators.movimiento_validator import validar_movimientos


# Registro público de parsers conocidos. `banorte_ocr` se conserva por
# compatibilidad histórica; para el flujo OCR normal se intenta además el
# descubrimiento dinámico de `parsers.<bank_key>_ocr`.
PARSER_REGISTRY = {
    "bbva": parse_bbva,
    "banamex": parse_banamex,
    "banorte": parse_banorte,
    "banorte_ocr": parse_banorte_ocr,
    "hsbc": parse_hsbc,
    "scotiabank": parse_scotiabank,
    "cetes": parse_cetes,
    "mifel": parse_mifel,
    "mercado_pago": parse_mercado_pago,
}


ParserFn = Callable[[DocumentData], object]
NormalizerFn = Callable[[list[dict]], list[dict]]


def _is_ocr_document(document: DocumentData) -> bool:
    """Indica si el documento fue producido por un reader OCR."""
    metadata = document.metadata or {}

    if bool(metadata.get("ocr")):
        return True

    reader = str(metadata.get("reader", "")).strip().lower()
    return reader in {"tesseract", "paddleocr"}


def _reader_name(document: DocumentData) -> str:
    metadata = document.metadata or {}
    return str(metadata.get("reader", "")).strip().lower()


def _import_optional_module(module_name: str):
    """Importa un módulo opcional sin ocultar errores internos de importación."""
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = str(exc.name or "")
        if missing == module_name or module_name.startswith(missing + "."):
            return None
        raise


def _get_optional_callable(
    module_name: str,
    *attribute_names: str,
):
    """Obtiene el primer callable disponible de un módulo opcional."""
    module = _import_optional_module(module_name)
    if module is None:
        return None

    for attribute_name in attribute_names:
        candidate = getattr(module, attribute_name, None)
        if callable(candidate):
            return candidate

    return None


def _resolve_ocr_parser(bank_key: str):
    """Resuelve `parsers.<bank_key>_ocr.parse_<bank_key>_ocr` si existe."""
    return _get_optional_callable(
        f"parsers.{bank_key}_ocr",
        f"parse_{bank_key}_ocr",
    )


def _resolve_coordinate_normalizer(bank_key: str):
    """Resuelve el normalizador espacial opcional asociado al banco."""
    return _get_optional_callable(
        f"parsers.normalizadores.{bank_key}",
        f"normalize_{bank_key}_words",
        "normalize_words",
    )


def _apply_coordinate_normalizer(
    document: DocumentData,
    normalizer_fn,
) -> DocumentData:
    """Aplica un normalizador y valida su contrato de salida."""
    normalized_words = normalizer_fn(document.spatial_words)

    if normalized_words is None:
        raise TypeError(
            "El normalizador de coordenadas devolvió None; "
            "debe devolver list[dict]."
        )

    if not isinstance(normalized_words, list):
        raise TypeError(
            "El normalizador de coordenadas debe devolver list[dict]."
        )

    document.spatial_words = normalized_words
    return document


def _process_once(
    document: DocumentData,
    bank_key: str,
):
    """Ejecuta una sola candidata de lectura sin fallback entre motores OCR."""
    document.normalized_text = normalize_text(document.raw_text)

    parser_fn = PARSER_REGISTRY.get(bank_key)
    if parser_fn is None:
        raise NotImplementedError(
            f"No existe parser para '{bank_key}'."
        )

    if _is_ocr_document(document):
        ocr_parser_fn = _resolve_ocr_parser(bank_key)
        if ocr_parser_fn is not None:
            estado = ocr_parser_fn(document)
            return estado, document

        normalizer_fn = _resolve_coordinate_normalizer(bank_key)
        if normalizer_fn is not None:
            document = _apply_coordinate_normalizer(
                document,
                normalizer_fn,
            )

    estado = parser_fn(document)
    return estado, document


def _validation_results(estado) -> list:
    """Obtiene la misma validación financiera usada por el pipeline."""
    movimientos = getattr(estado, "movimientos", None) or []
    resumen = getattr(estado, "resumen_financiero", None)

    if not movimientos or resumen is None:
        return []

    try:
        return validar_movimientos(
            movimientos=movimientos,
            resumen=resumen,
        )
    except Exception:
        # La evaluación opcional del fallback no debe introducir una nueva
        # falla sobre un resultado que el flujo histórico ya pudo parsear.
        return []


def _try_paddle_fallback(
    estado_tesseract,
    document_tesseract: DocumentData,
    bank_key: str,
):
    """Reintenta con PaddleOCR si Tesseract falla validación financiera.

    Tesseract se conserva salvo que PaddleOCR obtenga menos validaciones
    fallidas sin reducir la cantidad de validaciones disponibles.
    """
    if _reader_name(document_tesseract) != "tesseract":
        return estado_tesseract, document_tesseract

    tesseract_validaciones = _validation_results(estado_tesseract)
    if not should_attempt_paddle_fallback(
        bank_key,
        tesseract_validaciones,
    ):
        return estado_tesseract, document_tesseract

    metadata = document_tesseract.metadata or {}
    source_path = metadata.get("source_path")
    if not source_path:
        metadata["paddle_fallback_attempted"] = False
        metadata["paddle_fallback_skipped"] = "source_path_missing"
        document_tesseract.metadata = metadata
        return estado_tesseract, document_tesseract

    try:
        start_page = int(metadata.get("start_page", 0) or 0)
    except (TypeError, ValueError):
        start_page = 0

    tesseract_profile = validation_profile(tesseract_validaciones)

    try:
        paddle_document = ReaderManager.read_paddle_ocr(
            source_path,
            start_page=start_page,
        )
        estado_paddle, paddle_document = _process_once(
            paddle_document,
            bank_key,
        )
        paddle_validaciones = _validation_results(estado_paddle)
    except Exception as exc:
        metadata["paddle_fallback_attempted"] = True
        metadata["paddle_fallback_selected"] = False
        metadata["paddle_fallback_error_type"] = type(exc).__name__
        metadata["tesseract_validation_total"] = tesseract_profile.total
        metadata["tesseract_validation_failed"] = tesseract_profile.failed
        document_tesseract.metadata = metadata
        return estado_tesseract, document_tesseract

    paddle_profile = validation_profile(paddle_validaciones)
    select_paddle = should_select_paddle_result(
        tesseract_validaciones,
        paddle_validaciones,
    )

    comparison_metadata = {
        "paddle_fallback_attempted": True,
        "paddle_fallback_selected": select_paddle,
        "tesseract_validation_total": tesseract_profile.total,
        "tesseract_validation_failed": tesseract_profile.failed,
        "paddle_validation_total": paddle_profile.total,
        "paddle_validation_failed": paddle_profile.failed,
    }

    if select_paddle:
        paddle_document.metadata.update(comparison_metadata)
        paddle_document.metadata["fallback_from"] = "tesseract"
        return estado_paddle, paddle_document

    metadata.update(comparison_metadata)
    document_tesseract.metadata = metadata
    return estado_tesseract, document_tesseract


def process_single_statement(
    document: DocumentData,
    bank_key: str,
):
    """Procesa un documento con el parser correspondiente a su banco.

    Los documentos digitales conservan el flujo histórico. En OCR, Tesseract
    sigue siendo el motor primario. Si sus validaciones financieras contienen
    una falla explícita y el fallback está habilitado, se intenta PaddleOCR con
    modelos locales. Paddle sólo sustituye a Tesseract cuando mejora de forma
    medible la validación sin reducir su cobertura.
    """
    estado, document = _process_once(
        document,
        bank_key,
    )

    if _is_ocr_document(document):
        estado, document = _try_paddle_fallback(
            estado,
            document,
            bank_key,
        )

    return estado, document
