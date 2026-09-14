from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from models.datos_cuenta import DatosCuenta

from .movimientos import (
    MONTH_NUMBERS,
    STATEMENT_DATE_RE,
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
    word_center_y,
)


SpatialWord = Dict[str, Any]

ACCOUNT_RE = re.compile(r"CUENTA(\d{8,14})(?!\d)")
CLABE_RE = re.compile(r"CLABE(\d{18})(?!\d)")
CLIENT_RE = re.compile(r"(?:NODECLIENTE|NUMEROCLIENTE)(\d{5,20})(?!\d)")
RFC_RE = re.compile(r"[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}")

ADDRESS_MARKERS = {
    "AND",
    "AV",
    "AVENIDA",
    "CALLE",
    "COL",
    "COLONIA",
    "CP",
    "C.P",
    "CR",
    "C.R",
    "DELEGACION",
    "DOMICILIO",
    "HAB",
    "ROSARIO",
    "SUC",
}

NON_NAME_MARKERS = {
    "BANCA",
    "CLABE",
    "CUENTA",
    "ESTADO",
    "FECHA",
    "MONEDA",
    "PAGINA",
    "PERIODO",
    "SCOTIA",
    "SCOTIABANK",
}


# ============================================================
# UTILIDADES DE PÁGINA Y FECHA
# ============================================================


def _page_one_words(words: Sequence[SpatialWord]) -> List[SpatialWord]:
    return [word for word in words if safe_page(word) == 1]


def _page_one_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [line for line in group_words_into_lines(words) if line.page == 1]


def _dates_from_text(value: Any) -> List[date]:
    result: List[date] = []

    for day_text, month_text, year_text in STATEMENT_DATE_RE.findall(
        normalize_upper(value)
    ):
        year = int(year_text)
        if year < 100:
            year += 2000

        try:
            result.append(
                date(
                    year,
                    MONTH_NUMBERS[month_text.upper()],
                    int(day_text),
                )
            )
        except (KeyError, ValueError):
            continue

    return result


def _nearby_words(
    words: Sequence[SpatialWord],
    anchor_y: float,
    y_tolerance: float = 8.0,
) -> List[SpatialWord]:
    selected = [
        word
        for word in _page_one_words(words)
        if abs(word_center_y(word) - anchor_y) <= y_tolerance
    ]
    selected.sort(key=lambda word: (word_center_y(word), safe_float(word.get("x0"))))
    return selected


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_producto_principal(words: List[SpatialWord]) -> Optional[str]:
    """Extrae el texto ubicado después de la etiqueta Estado de Cuenta."""

    for line in _page_one_lines(words):
        if "ESTADODECUENTA" not in compact_text(line.text):
            continue

        anchor_right: Optional[float] = None

        for word in line.words:
            compact = compact_text(word.get("text", ""))
            if "ESTADODECUENTA" in compact or compact == "CUENTA":
                anchor_right = max(
                    anchor_right or 0.0,
                    safe_float(word.get("x1")),
                )

        if anchor_right is None:
            continue

        values = [
            normalize_text(word.get("text", ""))
            for word in line.words
            if safe_float(word.get("x0")) > anchor_right + 3.0
            and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", normalize_text(word.get("text", "")))
        ]
        value = " ".join(item for item in values if item).strip()

        if value:
            return value

    return None


def extract_periodo_inicio(words: List[SpatialWord]) -> Optional[str]:
    start, _ = extract_statement_period(words)
    return format_statement_date(start)


def extract_periodo_fin(words: List[SpatialWord]) -> Optional[str]:
    _, end = extract_statement_period(words)
    return format_statement_date(end)


def extract_fecha_corte(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        compact = compact_text(line.text)
        if "FECHADECORTE" not in compact:
            continue

        dates = _dates_from_text(line.text)

        if not dates:
            nearby = _nearby_words(words, line.center_y)
            dates = _dates_from_text(
                " ".join(normalize_text(word.get("text", "")) for word in nearby)
            )

        if dates:
            return format_statement_date(dates[0])

    # En este layout la fecha de corte coincide con el fin del periodo.
    _, period_end = extract_statement_period(words)
    return format_statement_date(period_end)


def extract_numero_cuenta(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        match = ACCOUNT_RE.search(compact_text(line.text))
        if match:
            return match.group(1)
    return None


def extract_numero_cliente(words: List[SpatialWord]) -> Optional[str]:
    """Devuelve None si el layout no imprime un número de cliente."""

    for line in _page_one_lines(words):
        match = CLIENT_RE.search(compact_text(line.text))
        if match:
            return match.group(1)
    return None


def extract_clabe(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        match = CLABE_RE.search(compact_text(line.text))
        if match:
            return match.group(1)

    # Fallback espacial para OCR que separa la CLABE en varios tokens.
    page_words = _page_one_words(words)
    for anchor in page_words:
        if compact_text(anchor.get("text", "")) != "CLABE":
            continue

        values = [
            re.sub(r"\D", "", normalize_text(word.get("text", "")))
            for word in page_words
            if abs(word_center_y(word) - word_center_y(anchor)) <= 8.0
            and safe_float(word.get("x0")) >= safe_float(anchor.get("x1")) - 2.0
        ]
        digits = "".join(value for value in values if value)
        if len(digits) == 18:
            return digits

    return None


def extract_rfc(words: List[SpatialWord]) -> Optional[str]:
    for line in _page_one_lines(words):
        compact = compact_text(line.text)
        if "RFC" not in compact:
            continue

        match = RFC_RE.search(compact)
        if match:
            return match.group(0)
    return None


def _account_line_y(lines: Sequence[SpatialLine]) -> Optional[float]:
    for line in lines:
        if ACCOUNT_RE.search(compact_text(line.text)):
            return line.center_y
    return None


def _candidate_name_from_line(line: SpatialLine) -> Optional[str]:
    values: List[str] = []

    for word in line.words:
        center_x = word_center_x(word)
        if not (55.0 <= center_x <= 300.0):
            continue

        value = normalize_text(word.get("text", "")).strip("|_—–")
        normalized = normalize_upper(value).strip(".")

        if len(normalized) <= 1:
            continue
        if not re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ.&'-]+", normalize_upper(value)):
            continue

        values.append(value)

    if len(values) < 2 or len(values) > 6:
        return None

    normalized_tokens = {normalize_upper(value).strip(".") for value in values}
    if normalized_tokens & ADDRESS_MARKERS:
        return None
    if normalized_tokens & NON_NAME_MARKERS:
        return None

    return " ".join(values)


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    lines = _page_one_lines(words)
    account_y = _account_line_y(lines)

    candidates: List[tuple[float, str]] = []

    for line in lines:
        if not (45.0 <= line.center_y <= 135.0):
            continue

        value = _candidate_name_from_line(line)
        if value is None:
            continue

        if account_y is not None and line.center_y > account_y + 5.0:
            continue

        distance = abs(line.center_y - account_y) if account_y is not None else 0.0
        word_count = len(value.split())
        score = word_count * 10.0 - distance
        candidates.append((score, value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
    """
    Extrae datos generales de Scotiabank mediante anclas semánticas.

    No usa tops absolutos: los valores se localizan por etiqueta, cercanía
    vertical y validación de formato, por lo que funciona con words de PDF
    digital y con las coordenadas generadas por Tesseract.
    """

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
