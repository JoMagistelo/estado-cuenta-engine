from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from models.otros_productos import OtrosProductos

from .movimientos import (
    SpatialLine,
    compact_text,
    group_words_into_lines,
    normalize_text,
    normalize_upper,
    parse_money,
    word_center_x,
)


SpatialWord = Dict[str, Any]
NA_VALUE = "N/A"

PRODUCT_HEADER_MARKERS = (
    "CONTRATO",
    "PRODUCTO",
    "TASA",
    "GAT",
    "COMISION",
)


def na_value() -> str:
    return NA_VALUE


# ============================================================
# DETECCIÓN GENÉRICA DE TABLA DE OTROS PRODUCTOS
# ============================================================


def _is_product_header(line: SpatialLine) -> bool:
    normalized = normalize_upper(line.text)
    score = sum(marker in normalized for marker in PRODUCT_HEADER_MARKERS)
    return score >= 3 and ("PRODUCTO" in normalized or "CONTRATO" in normalized)


def _next_data_line(
    header: SpatialLine,
    lines: Sequence[SpatialLine],
) -> Optional[SpatialLine]:
    candidates = [
        line
        for line in lines
        if line.page == header.page
        and header.center_y < line.center_y <= header.center_y + 45.0
        and not _is_product_header(line)
        and line.text
    ]

    candidates.sort(key=lambda line: line.center_y)

    for line in candidates:
        useful_words = [
            word
            for word in line.words
            if normalize_text(word.get("text", ""))
            and re.search(
                r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9$%]",
                normalize_text(word.get("text", "")),
            )
        ]
        if len(useful_words) >= 2:
            return line

    return None


def _header_center(
    header: SpatialLine,
    *markers: str,
) -> Optional[float]:
    candidates = [
        word_center_x(word)
        for word in header.words
        if any(marker in compact_text(word.get("text", "")) for marker in markers)
    ]

    if not candidates:
        return None

    return sum(candidates) / len(candidates)


def _column_value(
    data_line: SpatialLine,
    center: Optional[float],
    neighboring_centers: Sequence[float],
) -> Optional[str]:
    if center is None:
        return None

    centers = sorted(set(neighboring_centers))
    index = centers.index(center)
    left = (
        (centers[index - 1] + center) / 2.0
        if index > 0
        else center - 50.0
    )
    right = (
        (center + centers[index + 1]) / 2.0
        if index < len(centers) - 1
        else center + 60.0
    )

    values = [
        normalize_text(word.get("text", ""))
        for word in data_line.words
        if left <= word_center_x(word) < right
    ]
    value = " ".join(item for item in values if item).strip()
    return value or None


def _extract_table_values(words: List[SpatialWord]) -> Dict[str, Optional[str]]:
    lines = group_words_into_lines(words)

    for header in lines:
        if not _is_product_header(header):
            continue

        data_line = _next_data_line(header, lines)
        if data_line is None:
            continue

        centers = {
            "contrato": _header_center(header, "CONTRATO"),
            "producto": _header_center(header, "PRODUCTO"),
            "tasa": _header_center(header, "TASA"),
            "gat_nominal": _header_center(header, "GATNOMINAL", "NOMINAL"),
            "gat_real": _header_center(header, "GATREAL", "REAL"),
            "comisiones": _header_center(header, "COMISION"),
        }
        available_centers = [
            center for center in centers.values() if center is not None
        ]

        if len(available_centers) < 3:
            continue

        return {
            key: _column_value(data_line, center, available_centers)
            for key, center in centers.items()
        }

    return {}


def _parse_percentage(value: Optional[str]) -> Optional[float | str]:
    if value is None:
        return None
    if compact_text(value) == "NA":
        return NA_VALUE

    amount = parse_money(value.replace("%", ""))
    return amount if amount is not None else value


def _parse_commissions(value: Optional[str]) -> Optional[float | str]:
    if value is None:
        return None
    if compact_text(value) == "NA":
        return NA_VALUE

    amount = parse_money(value)
    return amount if amount is not None else value


def _values(words: List[SpatialWord]) -> Dict[str, Any]:
    extracted = _extract_table_values(words)

    if not extracted:
        return {
            "contrato": NA_VALUE,
            "producto": NA_VALUE,
            "tasa": NA_VALUE,
            "gat_nominal": NA_VALUE,
            "gat_real": NA_VALUE,
            "comisiones": NA_VALUE,
        }

    parsed_tasa = _parse_percentage(extracted.get("tasa"))
    parsed_gat_nominal = _parse_percentage(extracted.get("gat_nominal"))
    parsed_gat_real = _parse_percentage(extracted.get("gat_real"))
    parsed_commissions = _parse_commissions(extracted.get("comisiones"))

    return {
        "contrato": extracted.get("contrato") or NA_VALUE,
        "producto": extracted.get("producto") or NA_VALUE,
        "tasa": parsed_tasa if parsed_tasa is not None else NA_VALUE,
        "gat_nominal": (
            parsed_gat_nominal
            if parsed_gat_nominal is not None
            else NA_VALUE
        ),
        "gat_real": parsed_gat_real if parsed_gat_real is not None else NA_VALUE,
        "comisiones": (
            parsed_commissions
            if parsed_commissions is not None
            else NA_VALUE
        ),
    }


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_contrato(words: List[SpatialWord]) -> Optional[str]:
    return _values(words)["contrato"]


def extract_producto(words: List[SpatialWord]) -> Optional[str]:
    return _values(words)["producto"]


def extract_tasa_interes_anual(words: List[SpatialWord]) -> Any:
    return _values(words)["tasa"]


def extract_gat_nominal_anual(words: List[SpatialWord]) -> Any:
    return _values(words)["gat_nominal"]


def extract_gat_real_anual(words: List[SpatialWord]) -> Any:
    return _values(words)["gat_real"]


def extract_total_comisiones(words: List[SpatialWord]) -> Any:
    return _values(words)["comisiones"]


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Extrae la tabla explícita de otros productos cuando exista.

    El estado de cuenta proporcionado no reporta un producto adicional;
    por ello se devuelve ``N/A`` en los seis campos, igual que los parsers
    existentes del motor. La detección de encabezados queda preparada para
    layouts Scotiabank que sí incluyan una tabla de inversiones.
    """

    values = _values(words)

    return OtrosProductos(
        contrato=values["contrato"],
        producto=values["producto"],
        tasa_interes_anual=values["tasa"],
        gat_nominal_anual=values["gat_nominal"],
        gat_real_anual=values["gat_real"],
        total_comisiones=values["comisiones"],
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
