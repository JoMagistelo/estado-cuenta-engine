from __future__ import annotations

from importlib import import_module
from typing import Callable

from readers.models import DocumentData
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
    """Indica si el documento fue producido por el reader OCR actual."""
    metadata = document.metadata or {}

    if bool(metadata.get("ocr")):
        return True

    reader = str(metadata.get("reader", "")).strip().lower()
    return reader == "tesseract"


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


def process_single_statement(
    document: DocumentData,
    bank_key: str,
):
    """Procesa un documento con el parser correspondiente a su banco.

    Los documentos digitales utilizan el parser base. Para OCR se intenta,
    en orden, un parser OCR especializado, un normalizador de coordenadas y,
    finalmente, el parser base. La firma y el orden de resolución se mantienen
    para preservar compatibilidad con el pipeline existente.
    """
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
