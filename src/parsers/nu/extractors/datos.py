from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from models.datos_cuenta import DatosCuenta

from .common import SpatialLine, compact_text, group_words_into_lines, normalize_text, normalize_upper

SpatialWord = Dict[str, Any]

MONTH_NUMBERS = {
    "ENE": 1,
    "ENERO": 1,
    "FEB": 2,
    "FEBRERO": 2,
    "MAR": 3,
    "MARZO": 3,
    "ABR": 4,
    "ABRIL": 4,
    "MAY": 5,
    "MAYO": 5,
    "JUN": 6,
    "JUNIO": 6,
    "JUL": 7,
    "JULIO": 7,
    "AGO": 8,
    "AGOSTO": 8,
    "SEP": 9,
    "SEPT": 9,
    "SEPTIEMBRE": 9,
    "SET": 9,
    "SETIEMBRE": 9,
    "OCT": 10,
    "OCTUBRE": 10,
    "NOV": 11,
    "NOVIEMBRE": 11,
    "DIC": 12,
    "DICIEMBRE": 12,
}

ACCOUNT_RE = re.compile(r"\bCUENTA\s+NU\s*[:#-]?\s*([0-9]{6,24})\b", re.IGNORECASE)
RFC_RE = re.compile(r"\bRFC\s*[:#-]?\s*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b", re.IGNORECASE)
CLABE_RE = re.compile(r"\bCLABE\s*[:#-]?\s*((?:\d[\s-]*){18})", re.IGNORECASE)
PERIOD_RE = re.compile(
    r"\bPERIODO\s*[:#-]?\s*DEL\s+(\d{1,2})"
    r"(?:\s+([A-ZÁÉÍÓÚ]{3,12}))?\s+AL\s+(\d{1,2})\s+"
    r"([A-ZÁÉÍÓÚ]{3,12})\s+(\d{4})\b",
    re.IGNORECASE,
)


def _header_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [
        line
        for line in group_words_into_lines(words)
        if line.page == 1 and line.center_y < 145.0
    ]


def _month_number(value: str | None) -> Optional[int]:
    if not value:
        return None
    key = normalize_upper(value)
    return MONTH_NUMBERS.get(key) or MONTH_NUMBERS.get(key[:3])


def extract_period(words: Sequence[SpatialWord]) -> tuple[Optional[date], Optional[date]]:
    for line in _header_lines(words):
        match = PERIOD_RE.search(normalize_upper(line.text))
        if not match:
            continue
        start_day, start_month_name, end_day, end_month_name, year_text = match.groups()
        end_month = _month_number(end_month_name)
        start_month = _month_number(start_month_name) or end_month
        if start_month is None or end_month is None:
            continue
        end_year = int(year_text)
        start_year = end_year - 1 if start_month > end_month else end_year
        try:
            return (
                date(start_year, start_month, int(start_day)),
                date(end_year, end_month, int(end_day)),
            )
        except ValueError:
            continue
    return None, None


def _format_date(value: Optional[date]) -> Optional[str]:
    return value.strftime("%d/%m/%Y") if value is not None else None


def extract_producto_principal(words: List[SpatialWord]) -> Optional[str]:
    if any("CUENTANU" in compact_text(line.text) for line in _header_lines(words)):
        return "Cuenta Nu"
    return None


def extract_numero_cuenta(words: List[SpatialWord]) -> Optional[str]:
    for line in _header_lines(words):
        match = ACCOUNT_RE.search(line.text)
        if match:
            return match.group(1)
    return None


def extract_clabe(words: List[SpatialWord]) -> Optional[str]:
    for line in _header_lines(words):
        match = CLABE_RE.search(line.text)
        if not match:
            continue
        digits = re.sub(r"\D", "", match.group(1))
        if len(digits) == 18:
            return digits
    return None


def extract_rfc(words: List[SpatialWord]) -> Optional[str]:
    for line in _header_lines(words):
        match = RFC_RE.search(normalize_upper(line.text))
        if match:
            return match.group(1).upper()
    return None


def _is_name_candidate(value: str) -> bool:
    tokens = value.replace(",", " ").split()
    normalized = normalize_upper(value)
    return (
        2 <= len(tokens) <= 8
        and not re.search(r"\d", value)
        and not any(marker in normalized for marker in ("CUENTA", "RFC", "CLABE", "PERIODO", "NU MEXICO"))
        and all(re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.'-]+", token) for token in tokens)
    )


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    lines = _header_lines(words)
    account_index = next(
        (index for index, line in enumerate(lines) if ACCOUNT_RE.search(line.text)),
        None,
    )
    if account_index is not None:
        for line in reversed(lines[max(0, account_index - 3) : account_index]):
            candidate = normalize_text(line.text)
            if _is_name_candidate(candidate):
                return candidate
    return None


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
    start, end = extract_period(words)
    return DatosCuenta(
        producto_principal=extract_producto_principal(words),
        periodo_inicio=_format_date(start),
        periodo_fin=_format_date(end),
        fecha_corte=_format_date(end),
        numero_cuenta=extract_numero_cuenta(words),
        numero_cliente=None,
        clabe=extract_clabe(words),
        nombre_cliente=extract_nombre_cliente(words),
        rfc=extract_rfc(words),
    )


__all__ = [
    "extract_clabe",
    "extract_datos_cuenta_words",
    "extract_nombre_cliente",
    "extract_numero_cuenta",
    "extract_period",
    "extract_producto_principal",
    "extract_rfc",
]
