from __future__ import annotations

from importlib import import_module
from typing import Callable

from engine.ocr_fallback_policy import (
    fallback_trigger_reasons,
    paddle_fallback_enabled,
    should_select_paddle_result,
    validation_profile,
)
from models.ocr_review import OCRCandidate, OCRReview
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
    metadata = document.metadata or {}

    if bool(metadata.get("ocr")):
        return True

    reader = str(metadata.get("reader", "")).strip().lower()
    return reader in {"tesseract", "paddleocr"}


def _reader_name(document: DocumentData) -> str:
    metadata = document.metadata or {}
    return str(metadata.get("reader", "")).strip().lower()


def _import_optional_module(module_name: str):
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
    module = _import_optional_module(module_name)
    if module is None:
        return None

    for attribute_name in attribute_names:
        candidate = getattr(module, attribute_name, None)
        if callable(candidate):
            return candidate

    return None


def _resolve_ocr_parser(bank_key: str):
    return _get_optional_callable(
        f"parsers.{bank_key}_ocr",
        f"parse_{bank_key}_ocr",
    )


def _resolve_coordinate_normalizer(bank_key: str):
    return _get_optional_callable(
        f"parsers.normalizadores.{bank_key}",
        f"normalize_{bank_key}_words",
        "normalize_words",
    )


def _apply_coordinate_normalizer(
    document: DocumentData,
    normalizer_fn,
) -> DocumentData:
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
    """Ejecuta un candidato de lectura sin alternar motores OCR."""
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
    """Obtiene exactamente los validadores financieros actuales."""
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
        return []


def _has_movements(estado) -> bool:
    return bool(getattr(estado, "movimientos", None) or [])


def _build_candidate(
    engine: str,
    estado,
    document: DocumentData,
) -> OCRCandidate:
    return OCRCandidate(
        engine=engine,
        estado_cuenta=estado,
        document=document,
        validaciones=_validation_results(estado),
    )


def _try_paddle_review(
    tesseract_candidate: OCRCandidate,
    bank_key: str,
) -> OCRReview | None:
    """Construye una revisión Tesseract/PaddleOCR cuando corresponde.

    Ambos resultados se conservan en memoria. La recomendación automática sólo
    define el candidato inicial; la interfaz puede cambiar la selección.
    """
    document_tesseract = tesseract_candidate.document
    if _reader_name(document_tesseract) != "tesseract":
        return None

    if not paddle_fallback_enabled(bank_key):
        return None

    reasons = fallback_trigger_reasons(
        tesseract_candidate.validaciones,
        has_movements=tesseract_candidate.movement_count > 0,
    )
    if not reasons:
        return None

    metadata = document_tesseract.metadata or {}
    source_path = metadata.get("source_path")
    if not source_path:
        return OCRReview(
            candidates={"tesseract": tesseract_candidate},
            recommended_engine="tesseract",
            selected_engine="tesseract",
            trigger_reasons=reasons,
            paddle_error_type="SourcePathMissing",
        )

    try:
        start_page = int(metadata.get("start_page", 0) or 0)
    except (TypeError, ValueError):
        start_page = 0

    try:
        paddle_document = ReaderManager.read_paddle_ocr(
            source_path,
            start_page=start_page,
        )
        estado_paddle, paddle_document = _process_once(
            paddle_document,
            bank_key,
        )
        paddle_candidate = _build_candidate(
            "paddleocr",
            estado_paddle,
            paddle_document,
        )
    except Exception as exc:
        tesseract_profile = validation_profile(
            tesseract_candidate.validaciones
        )
        metadata.update(
            {
                "paddle_fallback_attempted": True,
                "paddle_fallback_selected": False,
                "paddle_fallback_error_type": type(exc).__name__,
                "tesseract_validation_total": tesseract_profile.total,
                "tesseract_validation_failed": tesseract_profile.failed,
            }
        )
        document_tesseract.metadata = metadata
        return OCRReview(
            candidates={"tesseract": tesseract_candidate},
            recommended_engine="tesseract",
            selected_engine="tesseract",
            trigger_reasons=reasons,
            paddle_error_type=type(exc).__name__,
        )

    recommend_paddle = should_select_paddle_result(
        tesseract_candidate.validaciones,
        paddle_candidate.validaciones,
        tesseract_has_movements=tesseract_candidate.movement_count > 0,
        paddle_has_movements=paddle_candidate.movement_count > 0,
    )
    recommended_engine = "paddleocr" if recommend_paddle else "tesseract"

    tesseract_profile = validation_profile(tesseract_candidate.validaciones)
    paddle_profile = validation_profile(paddle_candidate.validaciones)
    comparison_metadata = {
        "paddle_fallback_attempted": True,
        "paddle_fallback_selected": recommend_paddle,
        "tesseract_validation_total": tesseract_profile.total,
        "tesseract_validation_failed": tesseract_profile.failed,
        "paddle_validation_total": paddle_profile.total,
        "paddle_validation_failed": paddle_profile.failed,
    }
    document_tesseract.metadata.update(comparison_metadata)
    paddle_document.metadata.update(comparison_metadata)

    return OCRReview(
        candidates={
            "tesseract": tesseract_candidate,
            "paddleocr": paddle_candidate,
        },
        recommended_engine=recommended_engine,
        selected_engine=recommended_engine,
        trigger_reasons=reasons,
    )


def _selected_review_candidate(
    review: OCRReview,
) -> OCRCandidate:
    return review.get_candidate(review.selected_engine)


def _try_paddle_fallback(
    estado_tesseract,
    document_tesseract: DocumentData,
    bank_key: str,
):
    """API interna compatible que devuelve el candidato recomendado."""
    tesseract_candidate = _build_candidate(
        "tesseract",
        estado_tesseract,
        document_tesseract,
    )
    review = _try_paddle_review(
        tesseract_candidate,
        bank_key,
    )
    if review is None:
        return estado_tesseract, document_tesseract

    selected = _selected_review_candidate(review)
    return selected.estado_cuenta, selected.document


def process_single_statement_with_ocr_review(
    document: DocumentData,
    bank_key: str,
):
    """Procesa el documento y conserva candidatos OCR cuando se comparan."""
    estado, document = _process_once(
        document,
        bank_key,
    )

    if _reader_name(document) != "tesseract":
        return estado, document, None

    tesseract_candidate = _build_candidate(
        "tesseract",
        estado,
        document,
    )
    review = _try_paddle_review(
        tesseract_candidate,
        bank_key,
    )
    if review is None:
        return estado, document, None

    selected = _selected_review_candidate(review)
    return selected.estado_cuenta, selected.document, review


def process_single_statement(
    document: DocumentData,
    bank_key: str,
):
    """Procesa un documento conservando compatibilidad con la API histórica."""
    estado, document, _ = process_single_statement_with_ocr_review(
        document=document,
        bank_key=bank_key,
    )
    return estado, document
