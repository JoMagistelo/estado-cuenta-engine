from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.otros_productos import OtrosProductos

from .datos import extract_numero_cuenta, extract_producto_principal
from .movimientos import (
    compact_text,
    group_words_into_lines,
    normalize_text,
    parse_money,
)


SpatialWord = Dict[str, Any]
NA_VALUE = "N/A"


def na_value() -> str:
    return NA_VALUE


def _percentage(words: List[SpatialWord], marker: str) -> Optional[float]:
    for line in group_words_into_lines(words):
        if line.page != 1 or marker not in compact_text(line.text):
            continue
        for word in line.words:
            text = normalize_text(word.get("text", ""))
            if "%" not in text:
                continue
            value = parse_money(text.replace("%", ""))
            if value is not None:
                return value
    return None


def _commissions(words: List[SpatialWord]) -> Optional[float]:
    for line in group_words_into_lines(words):
        if (
            line.page != 1
            or "COMISIONESEFECTIVAMENTECOBRADAS" not in compact_text(line.text)
        ):
            continue
        values = [parse_money(word.get("text", "")) for word in line.words]
        parsed = [value for value in values if value is not None]
        if parsed:
            return parsed[-1]
    return None


def extract_contrato(words: List[SpatialWord]) -> Optional[str]:
    return extract_numero_cuenta(words) or NA_VALUE


def extract_producto(words: List[SpatialWord]) -> Optional[str]:
    return extract_producto_principal(words) or NA_VALUE


def extract_tasa_interes_anual(words: List[SpatialWord]) -> Any:
    value = _percentage(words, "TASAANUAL")
    return value if value is not None else NA_VALUE


def extract_gat_nominal_anual(words: List[SpatialWord]) -> Any:
    value = _percentage(words, "GATNOMINAL")
    return value if value is not None else NA_VALUE


def extract_gat_real_anual(words: List[SpatialWord]) -> Any:
    value = _percentage(words, "GATREAL")
    return value if value is not None else NA_VALUE


def extract_total_comisiones(words: List[SpatialWord]) -> Any:
    value = _commissions(words)
    return value if value is not None else NA_VALUE


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Expone la Cuenta a la Vista y sus indicadores financieros.

    Se usan anclas de texto en vez de un top fijo para soportar cambios de
    altura entre el lector digital y Tesseract, y futuros desplazamientos del
    bloque de resumen dentro de la primera pagina.
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
