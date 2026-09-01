from __future__ import annotations

from typing import Any, Dict, List

from models.otros_productos import OtrosProductos


SpatialWord = Dict[str, Any]
NA_VALUE = "N/A"


def na_value() -> str:
    return NA_VALUE


def extract_contrato(words: List[SpatialWord]) -> str:
    return na_value()


def extract_producto(words: List[SpatialWord]) -> str:
    return na_value()


def extract_tasa_interes_anual(words: List[SpatialWord]) -> str:
    return na_value()


def extract_gat_nominal_anual(words: List[SpatialWord]) -> str:
    return na_value()


def extract_gat_real_anual(words: List[SpatialWord]) -> str:
    return na_value()


def extract_total_comisiones(words: List[SpatialWord]) -> str:
    return na_value()


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Mercado Pago no imprime una tabla separada de otros productos.

    Los rendimientos de GBM que aparecen como movimientos no publican
    contrato, GAT ni tasa agregada, por lo que no se infieren esos valores.
    """
    return OtrosProductos(
        contrato=extract_contrato(words),
        producto=extract_producto(words),
        tasa_interes_anual=extract_tasa_interes_anual(words),
        gat_nominal_anual=extract_gat_nominal_anual(words),
        gat_real_anual=extract_gat_real_anual(words),
        total_comisiones=extract_total_comisiones(words),
    )


__all__ = [
    "extract_contrato",
    "extract_gat_nominal_anual",
    "extract_gat_real_anual",
    "extract_otros_productos_words",
    "extract_producto",
    "extract_tasa_interes_anual",
    "extract_total_comisiones",
    "na_value",
]
