from __future__ import annotations

import os
from importlib import import_module
from typing import Callable

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


# ============================================================
# REGISTRO DE PARSERS NORMALES
# ============================================================


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


# ============================================================
# DETECCIÓN DE DOCUMENTO OCR
# ============================================================


def _is_ocr_document(document: DocumentData) -> bool:
    """Determina si el DocumentData provino de un motor OCR."""
    metadata = document.metadata or {}

    if bool(metadata.get("ocr")):
        return True

    reader = str(metadata.get("reader", "")).strip().lower()
    return reader in {
        "tesseract",
        "paddleocr",
    }


def _reader_name(document: DocumentData) -> str:
    metadata = document.metadata or {}
    return str(
        metadata.get("reader", "")
    ).strip().lower()


# ============================================================
# IMPORTACIÓN OPCIONAL SEGURA
# ============================================================


def _import_optional_module(module_name: str):
    """
    Importa un módulo opcional.

    Sólo considera "no disponible" cuando falta el módulo opcional
    solicitado (o uno de sus paquetes padre). Si el módulo existe
    pero dentro tiene un import roto, la excepción se vuelve a lanzar.
    """
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


# ============================================================
# RESOLUCIÓN DE PARSER OCR
# ============================================================


def _resolve_ocr_parser(bank_key: str):
    return _get_optional_callable(
        f"parsers.{bank_key}_ocr",
        f"parse_{bank_key}_ocr",
    )


# ============================================================
# RESOLUCIÓN DE NORMALIZADOR DE COORDENADAS
# ============================================================


def _resolve_coordinate_normalizer(bank_key: str):
    return _get_optional_callable(
        f"parsers.normalizadores.{bank_key}",
        f"normalize_{bank_key}_words",
        "normalize_words",
    )


# ============================================================
# APLICAR NORMALIZADOR
# ============================================================


def _apply_coordinate_normalizer(
    document: DocumentData,
    normalizer_fn,
) -> DocumentData:
    normalized_words = normalizer_fn(
        document.spatial_words
    )

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


# ============================================================
# PARSEO DE UNA SOLA CANDIDATA OCR/DIGITAL
# ============================================================


def _process_once(
    document: DocumentData,
    bank_key: str,
):
    """
    Ejecuta exactamente una vez el parser correspondiente.

    Esta función no intenta ningún motor OCR alterno. Así se puede
    comparar Tesseract contra PaddleOCR sin recursión ni efectos laterales.
    """
    document.normalized_text = normalize_text(
        document.raw_text
    )

    parser_fn = PARSER_REGISTRY.get(
        bank_key
    )

    if parser_fn is None:
        raise NotImplementedError(
            f"No existe parser para '{bank_key}'."
        )

    if _is_ocr_document(document):
        ocr_parser_fn = _resolve_ocr_parser(
            bank_key
        )

        if ocr_parser_fn is not None:
            estado = ocr_parser_fn(
                document
            )
            return estado, document

        normalizer_fn = _resolve_coordinate_normalizer(
            bank_key
        )

        if normalizer_fn is not None:
            document = _apply_coordinate_normalizer(
                document,
                normalizer_fn,
            )

    estado = parser_fn(
        document
    )

    return estado, document


# ============================================================
# CALIDAD DE UNA CANDIDATA OCR
# ============================================================


def _validation_results(estado) -> list:
    movimientos = getattr(
        estado,
        "movimientos",
        None,
    ) or []
    resumen = getattr(
        estado,
        "resumen_financiero",
        None,
    )

    if not movimientos or resumen is None:
        return []

    try:
        return validar_movimientos(
            movimientos=movimientos,
            resumen=resumen,
        )
    except Exception:
        # La evaluación de fallback nunca debe romper un resultado que ya
        # pudo ser parseado por Tesseract.
        return []


def _core_summary_values(estado) -> tuple:
    resumen = getattr(
        estado,
        "resumen_financiero",
        None,
    )

    if resumen is None:
        return (
            None,
            None,
            None,
            None,
        )

    return (
        getattr(resumen, "saldo_anterior", None),
        getattr(resumen, "depositos_abonos", None),
        getattr(resumen, "retiros_cargos", None),
        getattr(resumen, "saldo_final", None),
    )


def _account_identity_values(estado) -> tuple:
    datos = getattr(
        estado,
        "datos_cuenta",
        None,
    )

    if datos is None:
        return (
            None,
            None,
            None,
            None,
        )

    return (
        getattr(datos, "numero_cuenta", None),
        getattr(datos, "numero_cliente", None),
        getattr(datos, "nombre_cliente", None),
        getattr(datos, "rfc", None),
    )


def _ocr_quality_score(estado) -> float:
    """
    Puntúa una candidata OCR.

    Las validaciones financieras dominan la decisión. La cantidad de
    movimientos y la completitud del resumen/datos sirven como desempate.
    PaddleOCR sólo reemplaza a Tesseract cuando obtiene una puntuación
    estrictamente superior.
    """
    movimientos = getattr(
        estado,
        "movimientos",
        None,
    ) or []

    score = min(
        float(len(movimientos)) * 0.10,
        5.0,
    )

    for value in _core_summary_values(estado):
        if value is not None:
            score += 2.0

    for value in _account_identity_values(estado):
        if value not in (
            None,
            "",
            "N/A",
        ):
            score += 0.75

    validaciones = _validation_results(estado)

    for validation in validaciones:
        if bool(
            getattr(validation, "correcto", False)
        ):
            score += 12.0
        else:
            score -= 12.0

    return score


def _result_needs_paddle_fallback(estado) -> bool:
    movimientos = getattr(
        estado,
        "movimientos",
        None,
    ) or []

    if not movimientos:
        return True

    validaciones = _validation_results(estado)

    if any(
        not bool(
            getattr(validation, "correcto", False)
        )
        for validation in validaciones
    ):
        return True

    # Si el validador no pudo ejecutarse porque faltan datos críticos,
    # también vale la pena intentar PaddleOCR.
    missing_core = sum(
        value is None
        for value in _core_summary_values(estado)
    )

    if missing_core >= 2:
        return True

    missing_identity = sum(
        value in (
            None,
            "",
            "N/A",
        )
        for value in _account_identity_values(estado)
    )

    return missing_identity >= 3


# ============================================================
# CONFIGURACIÓN DEL FALLBACK PADDLEOCR
# ============================================================


def _paddle_fallback_enabled_for_bank(
    bank_key: str,
) -> bool:
    """
    Por seguridad el fallback inicia sólo para HSBC.

    Variable opcional:

        PADDLEOCR_FALLBACK_BANKS=hsbc
        PADDLEOCR_FALLBACK_BANKS=hsbc,banorte
        PADDLEOCR_FALLBACK_BANKS=*
        PADDLEOCR_FALLBACK_BANKS=off
    """
    configured = os.getenv(
        "PADDLEOCR_FALLBACK_BANKS",
        "hsbc",
    ).strip().lower()

    if configured in {
        "",
        "0",
        "false",
        "off",
        "none",
    }:
        return False

    if configured == "*":
        return True

    allowed = {
        item.strip()
        for item in configured.split(",")
        if item.strip()
    }

    return bank_key.lower() in allowed


# ============================================================
# FALLBACK TESSERACT -> PADDLEOCR
# ============================================================


def _try_paddle_fallback(
    estado_tesseract,
    document_tesseract: DocumentData,
    bank_key: str,
):
    """
    Intenta PaddleOCR sólo cuando Tesseract produjo un resultado débil.

    Si PaddleOCR no está instalado, falla durante inicialización o produce
    un resultado peor, se conserva exactamente el resultado Tesseract.
    """
    if _reader_name(document_tesseract) != "tesseract":
        return estado_tesseract, document_tesseract

    if not _paddle_fallback_enabled_for_bank(bank_key):
        return estado_tesseract, document_tesseract

    if not _result_needs_paddle_fallback(
        estado_tesseract
    ):
        return estado_tesseract, document_tesseract

    metadata = document_tesseract.metadata or {}
    source_path = metadata.get("source_path")

    if not source_path:
        document_tesseract.metadata[
            "paddle_fallback_skipped"
        ] = "source_path_missing"
        return estado_tesseract, document_tesseract

    start_page = metadata.get(
        "start_page",
        0,
    )

    try:
        start_page = int(start_page or 0)
    except (
        TypeError,
        ValueError,
    ):
        start_page = 0

    tesseract_score = _ocr_quality_score(
        estado_tesseract
    )

    try:
        paddle_document = ReaderManager.read_paddle_ocr(
            source_path,
            start_page=start_page,
        )

        estado_paddle, paddle_document = _process_once(
            paddle_document,
            bank_key,
        )

        paddle_score = _ocr_quality_score(
            estado_paddle
        )

    except Exception as exc:
        document_tesseract.metadata[
            "paddle_fallback_attempted"
        ] = True
        document_tesseract.metadata[
            "paddle_fallback_selected"
        ] = False
        document_tesseract.metadata[
            "paddle_fallback_error"
        ] = f"{type(exc).__name__}: {exc}"
        document_tesseract.metadata[
            "tesseract_quality_score"
        ] = tesseract_score

        return estado_tesseract, document_tesseract

    if paddle_score > tesseract_score:
        paddle_document.metadata[
            "paddle_fallback_attempted"
        ] = True
        paddle_document.metadata[
            "paddle_fallback_selected"
        ] = True
        paddle_document.metadata[
            "fallback_from"
        ] = "tesseract"
        paddle_document.metadata[
            "tesseract_quality_score"
        ] = tesseract_score
        paddle_document.metadata[
            "paddle_quality_score"
        ] = paddle_score

        return estado_paddle, paddle_document

    document_tesseract.metadata[
        "paddle_fallback_attempted"
    ] = True
    document_tesseract.metadata[
        "paddle_fallback_selected"
    ] = False
    document_tesseract.metadata[
        "tesseract_quality_score"
    ] = tesseract_score
    document_tesseract.metadata[
        "paddle_quality_score"
    ] = paddle_score

    return estado_tesseract, document_tesseract


# ============================================================
# PROCESAMIENTO PÚBLICO DE DOCUMENTO
# ============================================================


def process_single_statement(
    document: DocumentData,
    bank_key: str,
):
    """
    Procesa un documento leído por ReaderManager.

    Flujo OCR por defecto para HSBC:

        Tesseract
            ↓
        parser + validator
            ↓
        ¿resultado suficiente?
          ├── SÍ -> conservar Tesseract
          └── NO -> PaddleOCR
                       ↓
                  parser + validator
                       ↓
                  comparar calidad
                       ↓
                  conservar el mejor

    PaddleOCR es completamente opcional. Si no está instalado o falla,
    Tesseract sigue siendo la salida sin interrumpir el procesamiento.
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
