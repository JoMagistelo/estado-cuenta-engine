from __future__ import annotations

from importlib import import_module
from typing import Callable

from engine.ocr_fallback_policy import (
    fallback_trigger_reasons,
    normalize_ocr_engine,
    secondary_ocr_engine,
    should_attempt_secondary_fallback,
    should_select_secondary_result,
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
    return normalize_ocr_engine(str(metadata.get("reader", "")), default="")


def _import_optional_module(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = str(exc.name or "")
        if missing == module_name or module_name.startswith(missing + "."):
            return None
        raise


def _get_optional_callable(module_name: str, *attribute_names: str):
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


def _process_once(document: DocumentData, bank_key: str):
    """Ejecuta parser/normalizador para un solo documento ya leído."""
    document.normalized_text = normalize_text(document.raw_text)

    parser_fn = PARSER_REGISTRY.get(bank_key)
    if parser_fn is None:
        raise NotImplementedError(f"No existe parser para '{bank_key}'.")

    if _is_ocr_document(document):
        ocr_parser_fn = _resolve_ocr_parser(bank_key)
        if ocr_parser_fn is not None:
            estado = ocr_parser_fn(document)
            return estado, document

        normalizer_fn = _resolve_coordinate_normalizer(bank_key)
        if normalizer_fn is not None:
            document = _apply_coordinate_normalizer(document, normalizer_fn)

    estado = parser_fn(document)
    return estado, document


def _validation_results(estado) -> list:
    """Obtiene las validaciones financieras actuales sin inventar resultados."""
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


def _build_candidate(engine: str, estado, document: DocumentData) -> OCRCandidate:
    return OCRCandidate(
        engine=normalize_ocr_engine(engine),
        estado_cuenta=estado,
        document=document,
        validaciones=_validation_results(estado),
    )


def _read_secondary_document(
    primary_candidate: OCRCandidate,
    secondary_engine: str,
) -> DocumentData:
    metadata = primary_candidate.document.metadata or {}
    source_path = metadata.get("source_path")
    if not source_path:
        raise RuntimeError("El documento OCR no conserva source_path para fallback.")

    try:
        start_page = int(metadata.get("start_page", 0) or 0)
    except (TypeError, ValueError):
        start_page = 0

    if normalize_ocr_engine(secondary_engine) == "paddleocr":
        return ReaderManager.read_paddle_ocr(
            source_path,
            start_page=start_page,
        )

    return ReaderManager.read_ocr(
        source_path,
        start_page=start_page,
    )


def _try_secondary_ocr_review(
    primary_candidate: OCRCandidate,
    bank_key: str,
    secondary_engine: str | None = None,
) -> OCRReview | None:
    """Ejecuta el OCR secundario sólo si falla la conciliación principal.

    El flujo es deliberadamente secuencial:
      1) el motor primario termina y se parsea;
      2) se calculan depósitos/abonos y retiros/cargos;
      3) si ambas validaciones pasan, termina aquí;
      4) sólo si alguna falta o falla se ejecuta el motor secundario.
    """
    primary_engine = normalize_ocr_engine(primary_candidate.engine)
    if primary_engine not in {"tesseract", "paddleocr"}:
        return None

    if not should_attempt_secondary_fallback(
        primary_candidate.validaciones,
        has_movements=primary_candidate.movement_count > 0,
    ):
        metadata = dict(primary_candidate.document.metadata or {})
        metadata.update(
            {
                "ocr_primary_engine": primary_engine,
                "ocr_fallback_attempted": False,
                "ocr_fallback_selected": False,
            }
        )
        primary_candidate.document.metadata = metadata
        return None

    secondary = normalize_ocr_engine(
        secondary_engine or secondary_ocr_engine(primary_engine)
    )
    if secondary == primary_engine:
        secondary = secondary_ocr_engine(primary_engine)

    reasons = fallback_trigger_reasons(
        primary_candidate.validaciones,
        has_movements=primary_candidate.movement_count > 0,
    )

    try:
        secondary_document = _read_secondary_document(
            primary_candidate,
            secondary,
        )
        secondary_estado, secondary_document = _process_once(
            secondary_document,
            bank_key,
        )
        secondary_candidate = _build_candidate(
            secondary,
            secondary_estado,
            secondary_document,
        )
    except Exception as exc:
        metadata = dict(primary_candidate.document.metadata or {})
        profile = validation_profile(primary_candidate.validaciones)
        metadata.update(
            {
                "ocr_primary_engine": primary_engine,
                "ocr_secondary_engine": secondary,
                "ocr_fallback_attempted": True,
                "ocr_fallback_selected": False,
                "ocr_fallback_error_type": type(exc).__name__,
                "primary_validation_total": profile.total,
                "primary_validation_failed": profile.failed,
            }
        )
        primary_candidate.document.metadata = metadata
        return OCRReview(
            candidates={primary_engine: primary_candidate},
            recommended_engine=primary_engine,
            selected_engine=primary_engine,
            trigger_reasons=reasons,
            paddle_error_type=(
                type(exc).__name__ if secondary == "paddleocr" else None
            ),
        )

    select_secondary = should_select_secondary_result(
        primary_candidate.validaciones,
        secondary_candidate.validaciones,
        primary_has_movements=primary_candidate.movement_count > 0,
        secondary_has_movements=secondary_candidate.movement_count > 0,
    )
    selected_engine = secondary if select_secondary else primary_engine

    primary_profile = validation_profile(primary_candidate.validaciones)
    secondary_profile = validation_profile(secondary_candidate.validaciones)
    comparison_metadata = {
        "ocr_primary_engine": primary_engine,
        "ocr_secondary_engine": secondary,
        "ocr_fallback_attempted": True,
        "ocr_fallback_selected": select_secondary,
        "primary_validation_total": primary_profile.total,
        "primary_validation_failed": primary_profile.failed,
        "secondary_validation_total": secondary_profile.total,
        "secondary_validation_failed": secondary_profile.failed,
    }
    primary_candidate.document.metadata = {
        **(primary_candidate.document.metadata or {}),
        **comparison_metadata,
    }
    secondary_candidate.document.metadata = {
        **(secondary_candidate.document.metadata or {}),
        **comparison_metadata,
    }

    return OCRReview(
        candidates={
            primary_engine: primary_candidate,
            secondary: secondary_candidate,
        },
        recommended_engine=selected_engine,
        selected_engine=selected_engine,
        trigger_reasons=reasons,
    )


def _try_paddle_review(
    tesseract_candidate: OCRCandidate,
    bank_key: str,
) -> OCRReview | None:
    """Wrapper histórico usado por pruebas/scripts existentes."""
    if normalize_ocr_engine(tesseract_candidate.engine) != "tesseract":
        return None
    return _try_secondary_ocr_review(
        tesseract_candidate,
        bank_key,
        secondary_engine="paddleocr",
    )


def _selected_review_candidate(review: OCRReview) -> OCRCandidate:
    return review.get_candidate(review.selected_engine)


def _try_paddle_fallback(
    estado_tesseract,
    document_tesseract: DocumentData,
    bank_key: str,
):
    """API interna histórica que devuelve el candidato seleccionado."""
    tesseract_candidate = _build_candidate(
        "tesseract",
        estado_tesseract,
        document_tesseract,
    )
    review = _try_paddle_review(tesseract_candidate, bank_key)
    if review is None:
        return estado_tesseract, document_tesseract
    selected = _selected_review_candidate(review)
    return selected.estado_cuenta, selected.document


def process_single_statement_with_ocr_review(
    document: DocumentData,
    bank_key: str,
):
    """Procesa un documento y aplica fallback simétrico si es OCR."""
    estado, document = _process_once(document, bank_key)
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
    )
    if review is None:
        return estado, document, None

    selected = _selected_review_candidate(review)
    return selected.estado_cuenta, selected.document, review


def process_single_statement(document: DocumentData, bank_key: str):
    """Procesa un documento conservando compatibilidad con la API histórica."""
    estado, document, _ = process_single_statement_with_ocr_review(
        document=document,
        bank_key=bank_key,
    )
    return estado, document
