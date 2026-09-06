from __future__ import annotations

from importlib import import_module
from typing import Callable

from engine.ocr_execution import secondary_ocr_engine
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


def _read_ocr_engine(
    engine: str,
    source_path: str,
    start_page: int,
) -> DocumentData:
    if engine == "tesseract":
        return ReaderManager.read_ocr(
            source_path,
            start_page=start_page,
        )

    if engine == "paddleocr":
        return ReaderManager.read_paddle_ocr(
            source_path,
            start_page=start_page,
        )

    raise ValueError(f"Motor OCR no soportado: {engine}")


def _recommended_engine(
    candidates: dict[str, OCRCandidate],
    primary_engine: str,
) -> str:
    tesseract_candidate = candidates.get("tesseract")
    paddle_candidate = candidates.get("paddleocr")

    if tesseract_candidate is None or paddle_candidate is None:
        return primary_engine

    recommend_paddle = should_select_paddle_result(
        tesseract_candidate.validaciones,
        paddle_candidate.validaciones,
        tesseract_has_movements=tesseract_candidate.movement_count > 0,
        paddle_has_movements=paddle_candidate.movement_count > 0,
    )
    return "paddleocr" if recommend_paddle else "tesseract"


def _comparison_metadata(
    candidates: dict[str, OCRCandidate],
    *,
    primary_engine: str,
    secondary_engine: str,
    recommended_engine: str,
) -> dict:
    metadata = {
        "ocr_review_attempted": True,
        "ocr_primary_engine": primary_engine,
        "ocr_secondary_engine": secondary_engine,
        "ocr_recommended_engine": recommended_engine,
    }

    tesseract_candidate = candidates.get("tesseract")
    paddle_candidate = candidates.get("paddleocr")

    if tesseract_candidate is not None:
        tesseract_profile = validation_profile(
            tesseract_candidate.validaciones
        )
        metadata.update(
            {
                "tesseract_validation_total": tesseract_profile.total,
                "tesseract_validation_failed": tesseract_profile.failed,
            }
        )

    if paddle_candidate is not None:
        paddle_profile = validation_profile(
            paddle_candidate.validaciones
        )
        metadata.update(
            {
                "paddle_fallback_attempted": True,
                "paddle_fallback_selected": (
                    recommended_engine == "paddleocr"
                ),
                "paddle_validation_total": paddle_profile.total,
                "paddle_validation_failed": paddle_profile.failed,
            }
        )

    return metadata


def _try_secondary_ocr_review(
    primary_candidate: OCRCandidate,
    bank_key: str,
    *,
    allow_secondary: bool = True,
) -> OCRReview | None:
    """Compara el OCR primario con el motor alternativo cuando hay señales.

    El motor primario puede ser Tesseract o PaddleOCR. La misma política objetiva
    de revisión decide si vale la pena ejecutar el segundo motor. Cuando Paddle
    actúa como secundario se respeta la habilitación por banco existente.
    """
    primary_engine = primary_candidate.engine
    secondary_engine = secondary_ocr_engine(primary_engine)

    if not allow_secondary:
        return None

    if (
        secondary_engine == "paddleocr"
        and not paddle_fallback_enabled(bank_key)
    ):
        return None

    reasons = fallback_trigger_reasons(
        primary_candidate.validaciones,
        has_movements=primary_candidate.movement_count > 0,
    )
    if not reasons:
        return None

    primary_document = primary_candidate.document
    metadata = primary_document.metadata or {}
    source_path = metadata.get("source_path")

    if not source_path:
        return OCRReview(
            candidates={primary_engine: primary_candidate},
            recommended_engine=primary_engine,
            selected_engine=primary_engine,
            trigger_reasons=reasons,
            paddle_error_type=(
                "SourcePathMissing"
                if secondary_engine == "paddleocr"
                else None
            ),
        )

    try:
        start_page = int(metadata.get("start_page", 0) or 0)
    except (TypeError, ValueError):
        start_page = 0

    try:
        secondary_document = _read_ocr_engine(
            secondary_engine,
            str(source_path),
            start_page,
        )
        secondary_estado, secondary_document = _process_once(
            secondary_document,
            bank_key,
        )
        secondary_candidate = _build_candidate(
            secondary_engine,
            secondary_estado,
            secondary_document,
        )
    except Exception as exc:
        error_type = type(exc).__name__
        failure_metadata = {
            "ocr_review_attempted": True,
            "ocr_primary_engine": primary_engine,
            "ocr_secondary_engine": secondary_engine,
            "ocr_secondary_error_type": error_type,
        }
        if secondary_engine == "paddleocr":
            failure_metadata.update(
                {
                    "paddle_fallback_attempted": True,
                    "paddle_fallback_selected": False,
                    "paddle_fallback_error_type": error_type,
                }
            )
        primary_document.metadata.update(failure_metadata)

        return OCRReview(
            candidates={primary_engine: primary_candidate},
            recommended_engine=primary_engine,
            selected_engine=primary_engine,
            trigger_reasons=reasons,
            paddle_error_type=(
                error_type
                if secondary_engine == "paddleocr"
                else None
            ),
        )

    candidates = {
        primary_engine: primary_candidate,
        secondary_engine: secondary_candidate,
    }
    recommended_engine = _recommended_engine(
        candidates,
        primary_engine,
    )

    comparison_metadata = _comparison_metadata(
        candidates,
        primary_engine=primary_engine,
        secondary_engine=secondary_engine,
        recommended_engine=recommended_engine,
    )
    primary_document.metadata.update(comparison_metadata)
    secondary_document.metadata.update(comparison_metadata)

    return OCRReview(
        candidates=candidates,
        recommended_engine=recommended_engine,
        selected_engine=recommended_engine,
        trigger_reasons=reasons,
    )


def _try_paddle_review(
    tesseract_candidate: OCRCandidate,
    bank_key: str,
) -> OCRReview | None:
    """Compatibilidad interna para el flujo histórico Tesseract → PaddleOCR."""
    if _reader_name(tesseract_candidate.document) != "tesseract":
        return None

    return _try_secondary_ocr_review(
        tesseract_candidate,
        bank_key,
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
    *,
    allow_secondary: bool = True,
):
    """Procesa el documento y conserva candidatos OCR cuando se comparan."""
    estado, document = _process_once(
        document,
        bank_key,
    )

    primary_engine = _reader_name(document)
    if primary_engine not in {"tesseract", "paddleocr"}:
        return estado, document, None

    primary_candidate = _build_candidate(
        primary_engine,
        estado,
        document,
    )
    review = _try_secondary_ocr_review(
        primary_candidate,
        bank_key,
        allow_secondary=allow_secondary,
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
