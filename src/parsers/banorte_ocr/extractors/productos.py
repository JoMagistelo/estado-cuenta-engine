from __future__ import annotations

from typing import Any

from models.otros_productos import OtrosProductos


SpatialWord = dict[str, Any]
NA_VALUE = "N/A"


def extract_contrato(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_producto(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_tasa_interes_anual(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_gat_nominal_anual(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_gat_real_anual(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_total_comisiones(words: list[SpatialWord]) -> str:
    return NA_VALUE


def extract_otros_productos_words(words: list[SpatialWord]) -> OtrosProductos:
    """
    Banorte mantiene el mismo contrato de salida del parser digital:
    esta sección no tiene extracción implementada y se representa
    explícitamente como "N/A".
    """
    return OtrosProductos(
        contrato=extract_contrato(words),
        producto=extract_producto(words),
        tasa_interes_anual=extract_tasa_interes_anual(words),
        gat_nominal_anual=extract_gat_nominal_anual(words),
        gat_real_anual=extract_gat_real_anual(words),
        total_comisiones=extract_total_comisiones(words),
    )
