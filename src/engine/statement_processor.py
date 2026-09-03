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


# ============================================================
# REGISTRO DE PARSERS NORMALES
# ============================================================
#
# Este registro se conserva como fuente oficial de parsers base.
# No se agregan aquí los parsers OCR: se descubren dinámicamente
# con la convención:
#
#     parsers.<bank_key>_ocr
#     parse_<bank_key>_ocr
#
# Así un nuevo parser OCR no obliga a modificar este archivo.
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
    """
    Determina si el DocumentData provino de Tesseract.

    ReaderManager/TesseractPDFReader ya deja esta información en
    metadata, por lo que no es necesario cambiar la firma pública
    de process_single_statement() ni pasar processing_method por
    todo el pipeline.
    """
    metadata = document.metadata or {}

    if bool(metadata.get("ocr")):
        return True

    reader = str(metadata.get("reader", "")).strip().lower()
    return reader == "tesseract"


# ============================================================
# IMPORTACIÓN OPCIONAL SEGURA
# ============================================================


def _import_optional_module(module_name: str):
    """
    Importa un módulo opcional.

    Sólo considera "no disponible" cuando falta el módulo opcional
    solicitado (o uno de sus paquetes padre). Si el módulo existe
    pero dentro tiene un import roto, la excepción se vuelve a lanzar
    para no esconder errores reales de programación.
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
    """
    Convención:

        banco: banorte
        módulo: parsers.banorte_ocr
        callable: parse_banorte_ocr
    """
    return _get_optional_callable(
        f"parsers.{bank_key}_ocr",
        f"parse_{bank_key}_ocr",
    )


# ============================================================
# RESOLUCIÓN DE NORMALIZADOR DE COORDENADAS
# ============================================================


def _resolve_coordinate_normalizer(bank_key: str):
    """
    Convención principal:

        parsers.normalizadores.<bank_key>
        normalize_<bank_key>_words

    También acepta `normalize_words` como alias genérico.
    """
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
# PROCESAMIENTO DE DOCUMENTO
# ============================================================


def process_single_statement(
    document: DocumentData,
    bank_key: str,
):
    """
    Procesa un documento leído por ReaderManager.

    Flujo Digital:

        DocumentData
            ↓
        parser normal

    Flujo OCR:

        DocumentData OCR
            ↓
        ¿existe parsers.<banco>_ocr?
          ├── SÍ -> parser OCR
          └── NO
                ↓
        ¿existe normalizador del banco?
          ├── SÍ -> normalizar spatial_words -> parser normal
          └── NO -> parser normal sin normalizar

    La firma pública se conserva exactamente para no alterar a los
    demás consumidores del engine.
    """

    document.normalized_text = normalize_text(
        document.raw_text
    )

    # ========================================================
    # PARSER NORMAL OBLIGATORIO
    # ========================================================

    parser_fn = PARSER_REGISTRY.get(
        bank_key
    )

    if parser_fn is None:
        raise NotImplementedError(
            f"No existe parser para '{bank_key}'."
        )

    # ========================================================
    # OCR: PRIORIDAD 1 — PARSER ESPECIALIZADO
    # ========================================================

    if _is_ocr_document(document):
        ocr_parser_fn = _resolve_ocr_parser(
            bank_key
        )

        if ocr_parser_fn is not None:
            estado = ocr_parser_fn(
                document
            )
            return estado, document

        # ====================================================
        # OCR: PRIORIDAD 2 — NORMALIZADOR + PARSER NORMAL
        # ====================================================

        normalizer_fn = _resolve_coordinate_normalizer(
            bank_key
        )

        if normalizer_fn is not None:
            document = _apply_coordinate_normalizer(
                document,
                normalizer_fn,
            )

    # ========================================================
    # DIGITAL O FALLBACK OCR — PARSER NORMAL
    # ========================================================

    estado = parser_fn(
        document
    )

    return estado, document
