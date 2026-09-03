from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from catalog.bank_signatures import BANK_SIGNATURES
from models.movimiento import Movimiento


SpatialWord = Dict[str, Any]

FULL_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*"
    r"(0?[1-9]|1[0-2])\s*\2\s*(\d{2}|\d{4})(?!\d)"
)
TRANSFER_RE = re.compile(
    r"\bTRANSFERENCIA(?:\s+(?:INTERBANCARIA|SPEI))?\s+"
    r"(RECIBIDA|ENVIADA)\b",
    re.IGNORECASE,
)
TRACKING_RE = re.compile(
    r"\b(?:CLAVE|CVE)\s*(?:DE\s+)?RASTREO(?:\s+SPEI)?\s*"
    r"[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{3,49})",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"\b(?:REFERENCIA|REF)\.?\s*[:#-]\s*"
    r"([A-Z0-9][A-Z0-9._/-]{1,49})",
    re.IGNORECASE,
)
AUTH_RE = re.compile(
    r"\b(?:AUTORIZACI[ÓO]N|AUT)\.?\s*[:#-]?\s*"
    r"([A-Z0-9][A-Z0-9._/-]{2,39})",
    re.IGNORECASE,
)
RFC_RE = re.compile(
    r"\bRFC\s*[:#-]?\s*"
    r"([A-Z&Ñ]{3,4}\s*\d{6}\s*[A-Z0-9]{3})\b",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b"
)

DEFAULT_COLUMNS = {
    "date": (25.0, 90.0),
    "description": (90.0, 210.0),
    "operation_id": (210.0, 285.0),
    "value": (285.0, 350.0),
    "balance": (350.0, 430.0),
}

METADATA_LABEL_PATTERN = (
    r"(?:"
    r"(?:NOMBRE\s+(?:DEL\s+)?)?(?:BENEFICIARI[AO]|ORDENANTE)|"
    r"REMITENTE|EMISOR|DESTINATARIO|RECEPTOR|"
    r"BANCO(?:\s+(?:DESTINO|ORIGEN|BENEFICIARI[AO]|ORDENANTE))?|"
    r"INSTITUCI[ÓO]N(?:\s+(?:DESTINO|ORIGEN))?|PARTICIPANTE|"
    r"CLABE|CTA\s*/\s*CLABE|CUENTA|CTA\.?|"
    r"CLAVE|CVE|REFERENCIA|REF\.?|RFC|"
    r"CONCEPTO|MOTIVO|HORA|AUTORIZACI[ÓO]N|AUT\.?)"
)

METADATA_LINE_RE = re.compile(
    rf"^{METADATA_LABEL_PATTERN}\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SpatialLine:
    page: int
    words: List[SpatialWord]

    @property
    def center_y(self) -> float:
        return sum(word_center_y(word) for word in self.words) / len(self.words)

    @property
    def text(self) -> str:
        return " ".join(
            value
            for value in (
                clean_word_text(word.get("text", "")) for word in self.words
            )
            if value
        ).strip()


@dataclass(slots=True)
class ColumnLayout:
    date: tuple[float, float]
    description: tuple[float, float]
    operation_id: tuple[float, float]
    value: tuple[float, float]
    balance: tuple[float, float]
    header_y: float


@dataclass(slots=True)
class MovementBand:
    page: int
    date: str
    anchor_y: float
    words: List[SpatialWord]
    columns: ColumnLayout


# ============================================================
# NORMALIZACIÓN Y GEOMETRÍA
# ============================================================


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_page(word: SpatialWord) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def word_center_x(word: SpatialWord) -> float:
    return (safe_float(word.get("x0")) + safe_float(word.get("x1"))) / 2.0


def word_center_y(word: SpatialWord) -> float:
    return (
        safe_float(word.get("top")) + safe_float(word.get("bottom"))
    ) / 2.0


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def normalize_upper(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.upper()


def compact_text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_upper(value))


def clean_word_text(value: Any) -> str:
    text = normalize_text(value)
    if not text or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9$]", text):
        return ""
    return text.strip(" _—–|¦")


def _line_tolerance(page_words: Sequence[SpatialWord]) -> float:
    heights = [
        safe_float(word.get("bottom")) - safe_float(word.get("top"))
        for word in page_words
    ]
    heights = [height for height in heights if 0.1 <= height <= 24.0]
    if not heights:
        return 2.5
    return max(1.5, min(4.0, statistics.median(heights) * 0.45))


def group_words_into_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        if clean_word_text(word.get("text", "")):
            pages.setdefault(safe_page(word), []).append(word)

    result: List[SpatialLine] = []
    for page in sorted(pages):
        page_words = pages[page]
        tolerance = _line_tolerance(page_words)
        groups: List[List[SpatialWord]] = []
        centers: List[float] = []

        for word in sorted(
            page_words,
            key=lambda item: (word_center_y(item), safe_float(item.get("x0"))),
        ):
            center_y = word_center_y(word)
            candidate: Optional[int] = None
            candidate_delta = float("inf")

            for index in range(max(0, len(groups) - 6), len(groups)):
                delta = abs(center_y - centers[index])
                if delta <= tolerance and delta < candidate_delta:
                    candidate = index
                    candidate_delta = delta

            if candidate is None:
                groups.append([word])
                centers.append(center_y)
            else:
                groups[candidate].append(word)
                centers[candidate] = sum(
                    word_center_y(item) for item in groups[candidate]
                ) / len(groups[candidate])

        for group in groups:
            group.sort(key=lambda item: safe_float(item.get("x0")))
            result.append(SpatialLine(page=page, words=group))

    result.sort(key=lambda line: (line.page, line.center_y))
    return result


def _word_in_column(
    word: SpatialWord,
    column: tuple[float, float],
) -> bool:
    center = word_center_x(word)
    return column[0] <= center < column[1]


def _column_words(
    words: Sequence[SpatialWord],
    column: tuple[float, float],
) -> List[SpatialWord]:
    return sorted(
        (word for word in words if _word_in_column(word, column)),
        key=lambda word: (word_center_y(word), safe_float(word.get("x0"))),
    )


def _header_word(line: SpatialLine, expected: str) -> Optional[SpatialWord]:
    for word in line.words:
        if compact_text(word.get("text", "")) == expected:
            return word
    return None


def is_movements_header(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return all(
        marker in compact
        for marker in ("FECHA", "DESCRIPCION", "VALOR", "SALDO")
    )


def _default_layout(header_y: float = 0.0) -> ColumnLayout:
    return ColumnLayout(
        date=DEFAULT_COLUMNS["date"],
        description=DEFAULT_COLUMNS["description"],
        operation_id=DEFAULT_COLUMNS["operation_id"],
        value=DEFAULT_COLUMNS["value"],
        balance=DEFAULT_COLUMNS["balance"],
        header_y=header_y,
    )


def _layout_from_header(
    header: SpatialLine,
    page_words: Sequence[SpatialWord],
) -> ColumnLayout:
    date_word = _header_word(header, "FECHA")
    description_word = _header_word(header, "DESCRIPCION")
    value_word = _header_word(header, "VALOR")
    balance_word = _header_word(header, "SALDO")

    if not all((date_word, description_word, value_word, balance_word)):
        return _default_layout(header.center_y)

    id_words = [
        word
        for word in page_words
        if compact_text(word.get("text", "")) == "ID"
        and abs(word_center_y(word) - header.center_y) <= 12.0
    ]

    date_left = max(0.0, safe_float(date_word.get("x0")) - 18.0)
    description_left = safe_float(description_word.get("x0")) - 3.0
    operation_left = (
        safe_float(id_words[0].get("x0")) - 3.0
        if id_words
        else description_left
        + (safe_float(value_word.get("x0")) - description_left) * 0.55
    )
    value_header_x = safe_float(value_word.get("x0"))
    balance_header_x = safe_float(balance_word.get("x0"))
    value_left = operation_left + (value_header_x - operation_left) * 0.70
    balance_left = value_header_x + (balance_header_x - value_header_x) * 0.50
    right = max(
        balance_header_x + 55.0,
        max((safe_float(word.get("x1")) for word in page_words), default=430.0) + 8.0,
    )

    return ColumnLayout(
        date=(date_left, description_left),
        description=(description_left, operation_left),
        operation_id=(operation_left, value_left),
        value=(value_left, balance_left),
        balance=(balance_left, right),
        header_y=header.center_y,
    )


def build_page_layouts(words: Sequence[SpatialWord]) -> Dict[int, ColumnLayout]:
    lines = group_words_into_lines(words)
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        pages.setdefault(safe_page(word), []).append(word)

    layouts: Dict[int, ColumnLayout] = {}
    for line in lines:
        if is_movements_header(line):
            layouts[line.page] = _layout_from_header(line, pages.get(line.page, []))

    fallback = next(iter(layouts.values()), _default_layout())
    for page in pages:
        layouts.setdefault(
            page,
            ColumnLayout(
                date=fallback.date,
                description=fallback.description,
                operation_id=fallback.operation_id,
                value=fallback.value,
                balance=fallback.balance,
                header_y=fallback.header_y,
            ),
        )

    return layouts


# ============================================================
# FECHAS, BANDAS Y COLUMNAS
# ============================================================


def normalize_date(value: str) -> Optional[str]:
    match = FULL_DATE_RE.search(normalize_text(value))
    if not match:
        return None
    day, separator, month, year = match.groups()
    parsed_year = int(year) + 2000 if len(year) == 2 else int(year)
    return f"{int(day):02d}{separator}{int(month):02d}{separator}{parsed_year:04d}"


def _date_rows(
    lines: Sequence[SpatialLine],
    layout: ColumnLayout,
    page: int,
) -> List[tuple[float, str]]:
    result: List[tuple[float, str]] = []
    for line in lines:
        if line.page != page or line.center_y <= layout.header_y + 5.0:
            continue
        date_words = _column_words(line.words, layout.date)
        date_text = " ".join(
            clean_word_text(word.get("text", "")) for word in date_words
        )
        date_value = normalize_date(date_text)
        if date_value:
            result.append((line.center_y, date_value))
    return result


def _footer_y(lines: Sequence[SpatialLine], page: int) -> Optional[float]:
    candidates = [
        line.center_y
        for line in lines
        if line.page == page
        and compact_text(line.text).startswith(
            ("FECHADEGENERACION", "MPAGREGADOR")
        )
    ]
    return min(candidates) if candidates else None


def build_movement_bands(words: Sequence[SpatialWord]) -> List[MovementBand]:
    lines = group_words_into_lines(words)
    layouts = build_page_layouts(words)
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        pages.setdefault(safe_page(word), []).append(word)

    bands: List[MovementBand] = []
    for page in sorted(pages):
        layout = layouts[page]
        date_rows = _date_rows(lines, layout, page)
        if not date_rows:
            continue

        footer_y = _footer_y(lines, page)
        page_words = pages[page]

        for index, (anchor_y, date_value) in enumerate(date_rows):
            lower = (
                layout.header_y + 5.0
                if index == 0
                else (date_rows[index - 1][0] + anchor_y) / 2.0
            )
            upper = (
                (anchor_y + date_rows[index + 1][0]) / 2.0
                if index + 1 < len(date_rows)
                else footer_y or float("inf")
            )
            selected = [
                word
                for word in page_words
                if lower <= word_center_y(word) < upper
            ]
            bands.append(
                MovementBand(
                    page=page,
                    date=date_value,
                    anchor_y=anchor_y,
                    words=selected,
                    columns=layout,
                )
            )

    return bands


def parse_money(value: Any) -> Optional[float]:
    original = normalize_text(value)
    if not original or not re.search(r"\d", original):
        return None
    if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ/]", original):
        return None

    negative = bool(re.search(r"-\s*\d", original)) or (
        "(" in original and ")" in original
    )
    compact = re.sub(r"[^0-9.,]", "", original)
    if not compact:
        return None

    decimal_position = max(compact.rfind("."), compact.rfind(","))
    decimals = (
        re.sub(r"\D", "", compact[decimal_position + 1 :])
        if decimal_position >= 0
        else ""
    )

    if decimal_position >= 0 and 1 <= len(decimals) <= 2:
        integer = re.sub(r"\D", "", compact[:decimal_position]) or "0"
        normalized = f"{integer}.{decimals.ljust(2, '0')}"
    else:
        normalized = re.sub(r"\D", "", compact)

    try:
        amount = float(normalized)
    except ValueError:
        return None
    return round(-amount if negative else amount, 2)


def _amount_from_column(
    band: MovementBand,
    column: tuple[float, float],
) -> Optional[float]:
    candidates: List[tuple[float, float]] = []
    for line in group_words_into_lines(_column_words(band.words, column)):
        amount = parse_money(line.text)
        if amount is not None:
            candidates.append((abs(line.center_y - band.anchor_y), amount))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _concept_from_band(band: MovementBand) -> str:
    lines = group_words_into_lines(
        _column_words(band.words, band.columns.description)
    )
    values = [
        normalize_text(line.text)
        for line in lines
        if normalize_text(line.text)
        and "DESCRIPCION" not in compact_text(line.text)
    ]
    return "\n".join(values).strip()


def _operation_id_from_band(band: MovementBand) -> Optional[str]:
    words = _column_words(band.words, band.columns.operation_id)
    tokens = [
        re.sub(r"[^A-Za-z0-9_-]", "", clean_word_text(word.get("text", "")))
        for word in words
    ]
    tokens = [token for token in tokens if token]
    if not tokens:
        return None

    if all(token.isdigit() for token in tokens):
        return "".join(tokens)

    candidates = [
        re.sub(r"[^A-Za-z0-9_-]", "", line.text)
        for line in group_words_into_lines(words)
    ]
    candidates = [candidate for candidate in candidates if candidate]
    return max(candidates, key=len) if candidates else None


# ============================================================
# DATOS ESTRUCTURADOS DEL CONCEPTO
# ============================================================


def get_concepto_lines(concepto: str) -> List[str]:
    return [
        normalize_text(line)
        for line in str(concepto or "").splitlines()
        if normalize_text(line)
    ]


def transfer_direction(concepto: str) -> Optional[str]:
    match = TRANSFER_RE.search(normalize_text(concepto).replace("\n", " "))
    return match.group(1).upper() if match else None


def _labelled_multiline_value(
    concepto: str,
    labels: str,
) -> Optional[str]:
    match = re.search(
        rf"(?:^|\n)\s*(?:{labels})\s*[:#-]\s*(.*?)"
        rf"(?=\n\s*{METADATA_LABEL_PATTERN}\b|\Z)",
        concepto,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    value = normalize_text(match.group(1))
    return value or None


def extract_beneficiario_from_concepto(concepto: str) -> Optional[str]:
    if not concepto or not transfer_direction(concepto):
        return None

    direction = transfer_direction(concepto)
    if direction == "RECIBIDA":
        labels = (
            r"(?:NOMBRE\s+(?:DEL\s+)?)?ORDENANTE|REMITENTE|EMISOR|"
            r"BENEFICIARI[AO]"
        )
    else:
        labels = (
            r"(?:NOMBRE\s+(?:DEL\s+)?)?BENEFICIARI[AO]|"
            r"DESTINATARIO|RECEPTOR|ORDENANTE"
        )

    labelled = _labelled_multiline_value(concepto, labels)
    if labelled:
        return labelled

    lines = get_concepto_lines(concepto)
    collected: List[str] = []
    collecting = False

    for line in lines:
        match = TRANSFER_RE.search(line)
        if match:
            collecting = True
            tail = normalize_text(line[match.end() :])
            tail = re.sub(r"^(?:A|DE|PARA)\s+", "", tail, flags=re.IGNORECASE)
            if tail:
                collected.append(tail)
            continue

        if not collecting:
            continue
        if METADATA_LINE_RE.match(line):
            break
        collected.append(line)

    value = normalize_text(" ".join(collected))
    return value or None


def _compact_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def extract_clabe_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto or not transfer_direction(concepto):
        return None

    patterns = (
        r"\b(?:CTA\s*/\s*CLABE|CLABE(?:\s+(?:BENEFICIARI[AO]|ORDENANTE|DESTINO|ORIGEN))?)"
        r"\s*[:#-]?\s*((?:\d[\s-]*){18})",
        r"\bCUENTA(?:\s+(?:BENEFICIARI[AO]|ORDENANTE|DESTINO|ORIGEN))?"
        r"\s*[:#-]\s*((?:\d[\s-]*){18})",
    )

    for pattern in patterns:
        match = re.search(pattern, concepto, re.IGNORECASE)
        if match:
            digits = _compact_digits(match.group(1))
            if len(digits) == 18:
                return digits

    for line in get_concepto_lines(concepto):
        digits = _compact_digits(line)
        if len(digits) == 18 and re.fullmatch(r"[\d\s-]+", line):
            return digits
    return None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto or not transfer_direction(concepto):
        return None

    match = re.search(
        r"\b(?:CUENTA|CTA\.?)\s*"
        r"(?:DEL?\s+)?(?:BENEFICIARI[AO]|ORDENANTE|DESTINO|ORIGEN)?"
        r"\s*[:#-]\s*((?:\d[\s-]*){4,20})",
        concepto,
        re.IGNORECASE,
    )
    if not match:
        return None
    digits = _compact_digits(match.group(1))
    return digits if 4 <= len(digits) <= 20 else None


def extract_clave_rastreo_from_concepto(concepto: str) -> Optional[str]:
    match = TRACKING_RE.search(concepto or "")
    return match.group(1).strip().upper() if match else None


def extract_referencia_from_concepto(concepto: str) -> Optional[str]:
    match = REFERENCE_RE.search(concepto or "")
    return match.group(1).strip() if match else None


def extract_autorizacion_from_concepto(concepto: str) -> Optional[str]:
    match = AUTH_RE.search(concepto or "")
    return match.group(1).strip() if match else None


def extract_rfc_from_concepto(concepto: str) -> Optional[str]:
    match = RFC_RE.search(concepto or "")
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(1)).upper()


def extract_hora_from_concepto(concepto: str) -> Optional[str]:
    match = TIME_RE.search(concepto or "")
    return match.group(0) if match else None


def _bank_from_clabe(clabe: Optional[str]) -> Optional[str]:
    if not clabe or len(clabe) != 18:
        return None
    prefix = clabe[:3]
    for data in BANK_SIGNATURES.values():
        if prefix in data.get("clabe_prefixes", []):
            return data.get("display_name")
    return None


def extract_sucursal_from_concepto(concepto: str) -> Optional[str]:
    """Devuelve la institución contraparte en el campo ``sucursal``."""
    if not concepto or not transfer_direction(concepto):
        return None

    match = re.search(
        r"(?:^|\n)\s*(?:"
        r"BANCO(?:\s+(?:DESTINO|ORIGEN|BENEFICIARI[AO]|ORDENANTE))?|"
        r"INSTITUCI[ÓO]N(?:\s+(?:DESTINO|ORIGEN))?|PARTICIPANTE"
        r")\s*[:#-]\s*([^\n]+)",
        concepto,
        re.IGNORECASE,
    )
    if match:
        value = normalize_text(match.group(1))
        if value:
            return value

    clabe_bank = _bank_from_clabe(
        extract_clabe_beneficiario_from_concepto(concepto)
    )
    if clabe_bank:
        return clabe_bank

    normalized = normalize_upper(concepto)
    aliases: List[tuple[str, str]] = []
    for data in BANK_SIGNATURES.values():
        display_name = str(data.get("display_name", ""))
        names = [display_name, *data.get("filename_keywords", [])]
        for name in names:
            alias = normalize_upper(name)
            if len(alias) >= 4:
                aliases.append((alias, display_name))

    for alias, display_name in sorted(
        aliases,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if re.search(rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])", normalized):
            return display_name
    return None


def extract_concepto_original_from_concepto(concepto: str) -> Optional[str]:
    labelled = _labelled_multiline_value(
        concepto,
        r"CONCEPTO(?:\s+(?:DE\s+)?PAGO)?|MOTIVO",
    )
    return labelled or normalize_text(concepto).replace(" \n ", "\n") or None


def extract_tipo_operacion(
    signed_value: Optional[float],
    concepto: str,
) -> Optional[str]:
    if signed_value is not None:
        if signed_value < 0:
            return "CARGO"
        if signed_value > 0:
            return "ABONO"

    direction = transfer_direction(concepto)
    if direction == "RECIBIDA":
        return "ABONO"
    if direction == "ENVIADA":
        return "CARGO"

    normalized = normalize_upper(concepto)
    if any(marker in normalized for marker in ("DINERO RECIBIDO", "GANANCIA", "ABONO")):
        return "ABONO"
    if any(
        marker in normalized
        for marker in ("PAGO", "RETIRO", "CARGO", "MONTO APARTADO")
    ):
        return "CARGO"
    return None


# ============================================================
# CONSTRUCCIÓN Y API PÚBLICA
# ============================================================


def movement_band_to_model(band: MovementBand) -> Optional[Movimiento]:
    concepto = _concept_from_band(band)
    operation_id = _operation_id_from_band(band)
    signed_value = _amount_from_column(band, band.columns.value)
    balance = _amount_from_column(band, band.columns.balance)

    if (
        not concepto
        and operation_id is None
        and signed_value is None
        and balance is None
    ):
        return None

    cargo = abs(signed_value) if signed_value is not None and signed_value < 0 else 0.0
    abono = signed_value if signed_value is not None and signed_value > 0 else 0.0

    return Movimiento(
        fecha_operacion=band.date,
        fecha_liquidacion=None,
        concepto=concepto,
        tipo_operacion=extract_tipo_operacion(signed_value, concepto),
        cargo=cargo,
        abono=abono,
        referencia=operation_id or extract_referencia_from_concepto(concepto),
        autorizacion=extract_autorizacion_from_concepto(concepto),
        beneficiario=extract_beneficiario_from_concepto(concepto),
        cuenta_beneficiario=extract_cuenta_beneficiario_from_concepto(concepto),
        clabe_beneficiario=extract_clabe_beneficiario_from_concepto(concepto),
        clave_rastreo=extract_clave_rastreo_from_concepto(concepto),
        rfc=extract_rfc_from_concepto(concepto),
        sucursal=extract_sucursal_from_concepto(concepto),
        caja=None,
        hora_operacion=extract_hora_from_concepto(concepto),
        saldo_operacion=balance or 0.0,
        saldo_liquidacion=0.0,
        concepto_original=extract_concepto_original_from_concepto(concepto),
    )


def extract_movimientos_words(words: List[SpatialWord]) -> List[Movimiento]:
    movimientos: List[Movimiento] = []
    for band in build_movement_bands(words):
        movimiento = movement_band_to_model(band)
        if movimiento is not None:
            movimientos.append(movimiento)
    return movimientos


__all__ = [
    "ColumnLayout",
    "MovementBand",
    "SpatialLine",
    "build_movement_bands",
    "build_page_layouts",
    "compact_text",
    "extract_beneficiario_from_concepto",
    "extract_clabe_beneficiario_from_concepto",
    "extract_clave_rastreo_from_concepto",
    "extract_cuenta_beneficiario_from_concepto",
    "extract_movimientos_words",
    "extract_referencia_from_concepto",
    "extract_sucursal_from_concepto",
    "group_words_into_lines",
    "normalize_text",
    "normalize_upper",
    "parse_money",
    "safe_float",
    "safe_page",
    "transfer_direction",
    "word_center_x",
    "word_center_y",
]
