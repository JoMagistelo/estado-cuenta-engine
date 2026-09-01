from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.otros_productos import OtrosProductos

from .datos import extract_numero_cuenta, extract_producto_principal
from .movimientos import (
    compact_text,
    group_words_into_lines,
    parse_money,
)


SpatialWord = Dict[str, Any]
NA_VALUE = "N/A"


def na_value() -> str:
    return NA_VALUE


def _total_commissions(words: List[SpatialWord]) -> Optional[float]:
    for line in group_words_into_lines(words):
        if (
            line.page != 1
            or "SERVICIOSDECOMISIONMERCANTIL" not in compact_text(line.text)
        ):
            continue
        values = [parse_money(word.get("text", "")) for word in line.words]
        parsed = [value for value in values if value is not None]
        if parsed:
            return parsed[0]
    return None


def extract_contrato(words: List[SpatialWord]) -> Optional[str]:
    return extract_numero_cuenta(words) or NA_VALUE


def extract_producto(words: List[SpatialWord]) -> Optional[str]:
    return extract_producto_principal(words) or NA_VALUE


def extract_tasa_interes_anual(words: List[SpatialWord]) -> Any:
    # Hay tasas distintas por serie y plazo; el estado no publica una tasa
    # anual unica para el contrato completo.
    return NA_VALUE


def extract_gat_nominal_anual(words: List[SpatialWord]) -> Any:
    return NA_VALUE


def extract_gat_real_anual(words: List[SpatialWord]) -> Any:
    return NA_VALUE


def extract_total_comisiones(words: List[SpatialWord]) -> Any:
    value = _total_commissions(words)
    return value if value is not None else NA_VALUE


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Resume el contrato CETESDIRECTO sin inventar una tasa agregada.

    Las tasas impresas pertenecen a posiciones individuales de CETES; por
    eso tasa y GAT permanecen en ``N/A``. La comision mercantil si se extrae
    del valor explicitamente reportado.
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
