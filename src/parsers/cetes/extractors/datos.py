from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from models.datos_cuenta import DatosCuenta

from .movimientos import (
    SpatialLine,
    compact_text,
    extract_statement_period,
    format_statement_date,
    group_words_into_lines,
    normalize_text,
    normalize_upper,
)


SpatialWord = Dict[str, Any]

ACCOUNT_RE = re.compile(r"CONTRATOCUENTACLABE(\d{18})(?!\d)")
RFC_RE = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b")


def _page_one_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [line for line in group_words_into_lines(words) if line.page == 1]


def _account(words: Sequence[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        match = ACCOUNT_RE.search(compact_text(line.text))
        if match:
            return match.group(1)
    return None


def extract_producto_principal(words: List[SpatialWord]) -> Optional[str]:
    """
    Identifica CETESDIRECTO incluso si el lector digital omite el logotipo.

    Se exige la combinacion de la cuenta CLABE con el resumen de portafolio;
    asi el fallback no depende de que OCR reconozca la marca grafica.
    """

    lines = _page_one_lines(words)
    has_account = any("CONTRATOCUENTACLABE" in compact_text(line.text) for line in lines)
    has_portfolio = any("RESUMENDELPORTAFOLIO" in compact_text(line.text) for line in lines)
    has_brand = any("CETESDIRECTO" in compact_text(line.text) for line in lines)
    if has_brand or (has_account and has_portfolio):
        return "CETESDIRECTO"
    return None


def extract_periodo_inicio(words: List[SpatialWord]) -> Optional[str]:
    start, _ = extract_statement_period(words)
    return format_statement_date(start)


def extract_periodo_fin(words: List[SpatialWord]) -> Optional[str]:
    _, end = extract_statement_period(words)
    return format_statement_date(end)


def extract_fecha_corte(words: List[SpatialWord]) -> Optional[str]:
    # El layout no imprime una etiqueta separada de corte: corresponde al
    # ultimo dia del periodo reportado.
    return extract_periodo_fin(words)


def extract_numero_cuenta(words: List[SpatialWord]) -> Optional[str]:
    return _account(words)


def extract_numero_cliente(words: List[SpatialWord]) -> Optional[str]:
    # CETESDIRECTO no muestra un identificador adicional de cliente.
    return None


def extract_clabe(words: List[SpatialWord]) -> Optional[str]:
    return _account(words)


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        compact = compact_text(line.text)
        if not compact.startswith("NOMBRE"):
            continue

        # Los words pueden venir separados o la etiqueta puede contener dos
        # puntos; remover solo el prefijo conserva el orden bancario impreso.
        candidate = re.sub(
            r"^\s*NOMBRE\s*:\s*",
            "",
            normalize_text(line.text),
            flags=re.IGNORECASE,
        ).strip()
        if len(candidate.split()) >= 3 and not re.search(r"\d", candidate):
            return normalize_upper(candidate)
    return None


def extract_rfc(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        if "RFC" not in compact_text(line.text):
            continue
        match = RFC_RE.search(normalize_upper(line.text))
        if match:
            return match.group(0)
    return None


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
    """Extrae los datos generales del estado de cuenta CETESDIRECTO."""

    return DatosCuenta(
        producto_principal=extract_producto_principal(words),
        periodo_inicio=extract_periodo_inicio(words),
        periodo_fin=extract_periodo_fin(words),
        fecha_corte=extract_fecha_corte(words),
        numero_cuenta=extract_numero_cuenta(words),
        numero_cliente=extract_numero_cliente(words),
        clabe=extract_clabe(words),
        nombre_cliente=extract_nombre_cliente(words),
        rfc=extract_rfc(words),
    )


__all__ = [
    "extract_clabe",
    "extract_datos_cuenta_words",
    "extract_fecha_corte",
    "extract_nombre_cliente",
    "extract_numero_cliente",
    "extract_numero_cuenta",
    "extract_periodo_fin",
    "extract_periodo_inicio",
    "extract_producto_principal",
    "extract_rfc",
]
