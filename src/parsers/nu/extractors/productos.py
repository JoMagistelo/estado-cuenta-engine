from __future__ import annotations

from typing import Any, Dict, List

from models.otros_productos import OtrosProductos

SpatialWord = Dict[str, Any]
NA_VALUE = "N/A"


def extract_otros_productos_words(words: List[SpatialWord]) -> OtrosProductos:
    return OtrosProductos(
        contrato=NA_VALUE,
        producto=NA_VALUE,
        tasa_interes_anual=NA_VALUE,
        gat_nominal_anual=NA_VALUE,
        gat_real_anual=NA_VALUE,
        total_comisiones=NA_VALUE,
    )


__all__ = ["extract_otros_productos_words"]
