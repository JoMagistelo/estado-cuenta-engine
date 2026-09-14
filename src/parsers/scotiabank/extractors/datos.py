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


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", normalize_text(value))


def _right_side_digit_candidates(
    words: Sequence[SpatialWord],
    anchor: SpatialWord,
    *,
    min_length: int,
    max_length: int,
    y_tolerance: float = 9.0,
    max_distance: float = 230.0,
) -> List[str]:
    """Busca números impresos a la derecha de una etiqueta OCR.

    Tesseract puede separar ``Cuenta``/``CLABE`` del valor o colocarlos en
    renglones distintos por pocos puntos. Este helper usa geometría, no una
    posición absoluta de la página.
    """

    anchor_right = safe_float(anchor.get("x1"))
    anchor_y = word_center_y(anchor)
    nearby = [
        word
        for word in _page_one_words(words)
        if abs(word_center_y(word) - anchor_y) <= y_tolerance
        and safe_float(word.get("x0")) >= anchor_right - 2.0
        and safe_float(word.get("x0")) <= anchor_right + max_distance
    ]
    nearby.sort(key=lambda word: safe_float(word.get("x0")))

    result: List[str] = []
    for word in nearby:
        value = _digits(word.get("text", ""))
        if min_length <= len(value) <= max_length:
            result.append(value)

    # OCR también puede partir una cifra en varios tokens consecutivos.
    joined = ""
    for word in nearby:
        value = _digits(word.get("text", ""))
        if not value:
            if joined:
                break
            continue
        joined += value
        if min_length <= len(joined) <= max_length:
            result.append(joined)
        if len(joined) > max_length:
            break

    # Deduplicación estable.
    return list(dict.fromkeys(result))


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
    # Ruta histórica: etiqueta y valor quedan en el mismo SpatialLine.
    for line in _page_one_lines(words):
        match = ACCOUNT_RE.search(compact_text(line.text))
        if match:
            return match.group(1)

    # OCR: la etiqueta puede quedar separada varios puntos del valor.
    for anchor in _page_one_words(words):
        signature = compact_text(anchor.get("text", ""))
        if signature != "CUENTA":
            continue

        candidates = _right_side_digit_candidates(
            words,
            anchor,
            min_length=8,
            max_length=14,
        )
        if candidates:
            # Se prefiere el candidato más largo; evita tomar folios cortos.
            return max(candidates, key=len)

    # En este layout Scotiabank el número de cuenta impreso coincide con los
    # 11 dígitos de cuenta contenidos en la CLABE. Se usa sólo como último
    # fallback cuando OCR perdió la cifra junto a ``Cuenta``.
    clabe = extract_clabe(words)
    if clabe and len(clabe) == 18 and clabe.startswith("044"):
        return clabe[6:17]

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

    page_words = _page_one_words(words)

    # Fallback espacial para OCR que separa la CLABE en varios tokens.
    for anchor in page_words:
        if compact_text(anchor.get("text", "")) != "CLABE":
            continue

        candidates = _right_side_digit_candidates(
            words,
            anchor,
            min_length=18,
            max_length=18,
            y_tolerance=10.0,
            max_distance=260.0,
        )
        for digits in candidates:
            if len(digits) == 18:
                return digits

    # Último fallback: una CLABE Scotiabank completa es una señal estructurada
    # inequívoca por su longitud y prefijo 044, aunque OCR haya perdido la
    # palabra ``CLABE``.
    for word in page_words:
        digits = _digits(word.get("text", ""))
        if len(digits) == 18 and digits.startswith("044"):
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
        compact = compact_text(line.text)
        if ACCOUNT_RE.search(compact):
            return line.center_y
        if "CUENTA" in compact and re.search(r"\d{8,14}", compact):
            return line.center_y
    return None


def _candidate_name_from_words(words: Sequence[SpatialWord]) -> Optional[str]:
    values: List[str] = []

    for word in sorted(words, key=lambda item: safe_float(item.get("x0"))):
        value = normalize_text(word.get("text", "")).strip("|_—–:;")
        normalized = normalize_upper(value).strip(".")

        if len(normalized) <= 1:
            continue
        if not re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ.&'-]+", normalize_upper(value)):
            continue
        values.append(value)

    if len(values) < 2 or len(values) > 7:
        return None

    normalized_tokens = {normalize_upper(value).strip(".") for value in values}
    if normalized_tokens & ADDRESS_MARKERS:
        return None
    if normalized_tokens & NON_NAME_MARKERS:
        return None

    return " ".join(values)


def _candidate_name_from_line(line: SpatialLine) -> Optional[str]:
    return _candidate_name_from_words(
        [
            word
            for word in line.words
            if 40.0 <= word_center_x(word) <= 340.0
        ]
    )


def _explicit_name_after_label(words: Sequence[SpatialWord]) -> Optional[str]:
    page_words = _page_one_words(words)

    for anchor in page_words:
        signature = compact_text(anchor.get("text", ""))
        if signature not in {"CLIENTE", "NOMBRE", "NOMBRECLIENTE"}:
            continue

        nearby = [
            word
            for word in page_words
            if abs(word_center_y(word) - word_center_y(anchor)) <= 10.0
            and safe_float(word.get("x0")) >= safe_float(anchor.get("x1")) - 2.0
            and safe_float(word.get("x0")) <= safe_float(anchor.get("x1")) + 300.0
        ]
        value = _candidate_name_from_words(nearby)
        if value:
            return value

    return None


def extract_nombre_cliente(words: List[SpatialWord]) -> Optional[str]:
    explicit = _explicit_name_after_label(words)
    if explicit:
        return explicit

    lines = _page_one_lines(words)
    account_y = _account_line_y(lines)

    summary_y: Optional[float] = None
    for line in lines:
        if "RESUMENDESALDOS" in compact_text(line.text):
            summary_y = line.center_y
            break

    candidates: List[tuple[float, str]] = []

    for line in lines:
        # El OCR puede desplazar verticalmente el encabezado. En lugar de una
        # banda fija 45-135, se usa como límite el bloque del resumen y, cuando
        # existe, la fila de cuenta.
        if line.center_y < 30.0:
            continue
        if summary_y is not None and line.center_y >= summary_y - 8.0:
            continue
        if account_y is not None and line.center_y > account_y + 7.0:
            continue

        value = _candidate_name_from_line(line)
        if value is None:
            continue

        distance = abs(line.center_y - account_y) if account_y is not None else 0.0
        word_count = len(value.split())
        score = word_count * 12.0 - distance * 0.35
        candidates.append((score, value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================


def extract_datos_cuenta_words(words: List[SpatialWord]) -> DatosCuenta:
    """Extrae los datos generales Scotiabank desde words digitales u OCR.

    Los fallbacks OCR se apoyan en etiquetas, cercanía vertical y validación de
    formato. No cambian el flujo de identificación del banco ni dependen del
    nombre del archivo para inventar valores.
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
