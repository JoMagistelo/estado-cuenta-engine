from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from models.datos_cuenta import DatosCuenta

from .movimientos import (
    SpatialLine,
    compact_text,
    group_words_into_lines,
    normalize_text,
    normalize_upper,
)


SpatialWord = Dict[str, Any]

MONTH_NUMBERS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}

PERIOD_RE = re.compile(
    r"\bDEL\s+(\d{1,2})(?:\s+DE\s+([A-Z]+))?\s+"
    r"AL\s+(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})\b"
)
NUMERIC_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*"
    r"(0?[1-9]|1[0-2])\s*\2\s*(\d{4})(?!\d)"
)
RFC_CURP_RE = re.compile(
    r"\bRFC\s*/?\s*CURP\s*[:#-]?\s*([A-Z0-9&Ñ]{10,20})\b",
    re.IGNORECASE,
)
RFC_RE = re.compile(
    r"\bRFC\s*[:#-]?\s*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b",
    re.IGNORECASE,
)
CUSTOMER_RE = re.compile(
    r"\b(?:CUST(?:OMER)?|CLIENTE)\s*(?:ID|NO\.?|N[ÚU]MERO)?\s*"
    r"[:#-]?\s*([A-Z0-9-]{4,24})\b",
    re.IGNORECASE,
)
ACCOUNT_RE = re.compile(
    r"\b(?:N[ÚU]MERO\s+DE\s+)?CUENTA\s*[:#-]\s*"
    r"([A-Z0-9-]{6,24})\b",
    re.IGNORECASE,
)
CLABE_RE = re.compile(
    r"\b(?:CUENTA\s+CLABE|CLABE(?:\s+INTERBANCARIA)?)\s*"
    r"[:#-]?\s*((?:\d[\s-]*){18})",
    re.IGNORECASE,
)

NON_NAME_MARKERS = (
    "DIRECCION",
    "ESTADO",
    "FECHA",
    "MERCADO",
    "MOVIMIENTOS",
    "PERIODO",
    "RFC",
    "SALDO",
)


def _header_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [
        line
        for line in group_words_into_lines(words)
        if line.page == 1 and line.center_y < 180.0
    ]


def _format_date(value: Optional[date]) -> Optional[str]:
    return value.strftime("%d/%m/%Y") if value is not None else None


def extract_period(
    words: Sequence[SpatialWord],
) -> tuple[Optional[date], Optional[date]]:
    for line in _header_lines(words):
        if "PERIODO" not in compact_text(line.text):
            continue

        normalized = normalize_upper(line.text)
        match = PERIOD_RE.search(normalized)
        if match:
            start_day, start_month_name, end_day, end_month_name, year_text = (
                match.groups()
            )
            end_month = MONTH_NUMBERS.get(end_month_name)
            start_month = MONTH_NUMBERS.get(start_month_name or end_month_name)
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

        numeric_dates = NUMERIC_DATE_RE.findall(line.text)
        if len(numeric_dates) >= 2:
            values: List[date] = []
            for day, _, month, year in numeric_dates[:2]:
                try:
                    values.append(date(int(year), int(month), int(day)))
                except ValueError:
                    break
            if len(values) == 2:
                return values[0], values[1]

    return None, None


def extract_producto_principal(words: List[SpatialWord]) -> Optional[str]:
    for line in group_words_into_lines(words):
        if "MERCADOPAGO" in compact_text(line.text):
            return "MERCADO PAGO"
    return None


def extract_periodo_inicio(words: List[SpatialWord]) -> Optional[str]:
    start, _ = extract_period(words)
    return _format_date(start)


def extract_periodo_fin(words: List[SpatialWord]) -> Optional[str]:
    _, end = extract_period(words)
    return _format_date(end)


def extract_fecha_corte(words: List[SpatialWord]) -> Optional[str]:
    return extract_periodo_fin(words)


def extract_numero_cuenta(words: List[SpatialWord]) -> Optional[str]:
    for line in _header_lines(words):
        match = ACCOUNT_RE.search(line.text)
        if match:
            return match.group(1).replace("-", "")
    return None


def extract_numero_cliente(words: List[SpatialWord]) -> Optional[str]:
    for line in _header_lines(words):
        match = CUSTOMER_RE.search(line.text)
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
        match = RFC_CURP_RE.search(line.text) or RFC_RE.search(line.text)
        if match:
            return match.group(1).upper()
    return None


def _is_name_candidate(value: str) -> bool:
    normalized = normalize_upper(value)
    tokens = value.split()
    return (
        2 <= len(tokens) <= 8
        and not re.search(r"\d", value)
        and not any(marker in normalized for marker in NON_NAME_MARKERS)
        and all(
            re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.'-]+", token)
            for token in tokens
        )
    )


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    lines = _header_lines(words)
    rfc_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "RFC" in normalize_upper(line.text)
        ),
        None,
    )

    if rfc_index is not None:
        for line in reversed(lines[max(0, rfc_index - 3) : rfc_index]):
            value = normalize_text(line.text)
            if _is_name_candidate(value):
                return value

    for line in lines:
        value = normalize_text(line.text)
        if _is_name_candidate(value):
            return value
    return None


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
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
    "extract_period",
    "extract_periodo_fin",
    "extract_periodo_inicio",
    "extract_producto_principal",
    "extract_rfc",
]
