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
    safe_float,
    safe_page,
    word_center_x,
)


SpatialWord = Dict[str, Any]

RFC_RE = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b")
ACCOUNT_RE = re.compile(r"NUMERODECUENTA(\d{8,18})(?!\d)")
CLIENT_RE = re.compile(r"NUMERODECLIENTE(\d{4,20})(?!\d)")
CLABE_RE = re.compile(r"CLABE(\d{18})(?!\d)")
PRINTED_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*"
    r"(0?[1-9]|1[0-2])\s*\2\s*(\d{4})(?!\d)"
)

NON_NAME_MARKERS = (
    "BANCA",
    "CUENTA",
    "ESTADO",
    "INFORMACION",
    "MIFEL",
    "NUMERO",
    "PAGINA",
    "RFC",
)


def _page_one_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [line for line in group_words_into_lines(words) if line.page == 1]


def _page_one_words(words: Sequence[SpatialWord]) -> List[SpatialWord]:
    return [word for word in words if safe_page(word) == 1]


def _digits_after_label(
    lines: Sequence[SpatialLine],
    pattern: re.Pattern[str],
) -> Optional[str]:
    for line in lines:
        match = pattern.search(compact_text(line.text))
        if match:
            return match.group(1)
    return None


def extract_producto_principal(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        if "CUENTAALAVISTA" in compact_text(line.text):
            return "CUENTA A LA VISTA"
    return None


def extract_periodo_inicio(words: List[SpatialWord]) -> Optional[str]:
    start, _ = extract_statement_period(words)
    return format_statement_date(start)


def extract_periodo_fin(words: List[SpatialWord]) -> Optional[str]:
    _, end = extract_statement_period(words)
    return format_statement_date(end)


def extract_fecha_corte(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        if "FECHADECORTE" not in compact_text(line.text):
            continue
        match = PRINTED_DATE_RE.search(normalize_text(line.text))
        if match:
            day, separator, month, year = match.groups()
            return f"{int(day):02d}{separator}{int(month):02d}{separator}{year}"
    return extract_periodo_fin(words)


def extract_numero_cuenta(words: List[SpatialWord]) -> Optional[str]:
    return _digits_after_label(_page_one_lines(words), ACCOUNT_RE)


def extract_numero_cliente(words: List[SpatialWord]) -> Optional[str]:
    return _digits_after_label(_page_one_lines(words), CLIENT_RE)


def extract_clabe(words: List[SpatialWord]) -> Optional[str]:
    lines = _page_one_lines(words)
    direct = _digits_after_label(lines, CLABE_RE)
    if direct:
        return direct

    # Fallback para OCR que separa la CLABE en varios tokens contiguos.
    page_words = _page_one_words(words)
    for anchor in page_words:
        if "CLABE" not in compact_text(anchor.get("text", "")):
            continue
        anchor_y = (
            safe_float(anchor.get("top")) + safe_float(anchor.get("bottom"))
        ) / 2.0
        candidates = [
            word
            for word in page_words
            if abs(
                (
                    safe_float(word.get("top"))
                    + safe_float(word.get("bottom"))
                )
                / 2.0
                - anchor_y
            )
            <= 8.0
            and word_center_x(word) > word_center_x(anchor)
        ]
        candidates.sort(key=lambda word: safe_float(word.get("x0")))
        digits = "".join(
            re.sub(r"\D", "", normalize_text(word.get("text", "")))
            for word in candidates
        )
        match = re.search(r"\d{18}", digits)
        if match:
            return match.group(0)
    return None


def extract_rfc(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        if line.center_y > 250.0 or "RFC" not in compact_text(line.text):
            continue
        match = RFC_RE.search(normalize_upper(line.text))
        if match:
            return match.group(0)
    return None


def _name_before_information_label(line: SpatialLine) -> Optional[str]:
    label_starts = [
        safe_float(word.get("x0"))
        for word in line.words
        if "INFORMACION" in compact_text(word.get("text", ""))
    ]
    right = min(label_starts) if label_starts else 350.0
    values = [
        normalize_text(word.get("text", ""))
        for word in line.words
        if safe_float(word.get("x0")) < right
    ]
    candidate = " ".join(value for value in values if value).strip()
    compact = compact_text(candidate)
    if (
        len(candidate.split()) >= 3
        and not any(marker in compact for marker in NON_NAME_MARKERS)
        and not re.search(r"\d", candidate)
    ):
        return normalize_upper(candidate)
    return None


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    lines = _page_one_lines(words)

    for line in lines:
        if "INFORMACIONDELCLIENTE" in compact_text(line.text):
            candidate = _name_before_information_label(line)
            if candidate:
                return candidate

    # Fallback: nombre en el renglon inmediatamente anterior al numero de
    # cliente, util para layouts donde el titulo cambia de posicion.
    client_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "NUMERODECLIENTE" in compact_text(line.text)
        ),
        None,
    )
    if client_index is not None:
        for line in reversed(lines[max(0, client_index - 3) : client_index]):
            candidate = _name_before_information_label(line)
            if candidate:
                return candidate
    return None


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
    """Extrae datos de cuenta Mifel por anclas semanticas y formato."""

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
