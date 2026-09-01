from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento


SpatialWord = Dict[str, Any]

FULL_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*"
    r"(0?[1-9]|1[0-2])\s*\2\s*(\d{2}|\d{4})(?!\d)"
)
ROW_DATE_RE = re.compile(
    r"^\s*(0?[1-9]|[12]\d|3[01])\s*[/.-]\s*"
    r"(0?[1-9]|1[0-2])\s*[/.-]\s*(\d{2}|\d{4})\s*$"
)
MONEY_RE = re.compile(
    r"^\s*[-(]?\s*\$?\s*\d[\d\s,.'’]*"
    r"(?:[.,]\d{1,2})?\s*\)?\s*$"
)
FOLIO_RE = re.compile(r"^(SVD\d+)([A-Z][A-Z0-9]*)$", re.IGNORECASE)

OPERATION_NAMES = {
    "AMORTIZACION": "AMORTIZACION DE TITULOS",
    "COMPRA": "COMPRA DE TITULOS",
    "COMPSI": "COMPRA DE BONDDIA",
    "EGREFVO": "EGRESO DE EFECTIVO",
    "INGEFVO": "INGRESO DE EFECTIVO",
    "ISR": "RETENCION DE ISR",
    "VTASI": "VENTA DE BONDDIA",
}


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
    width: float
    registration_right: float
    liquidation_right: float
    folio_right: float
    issuer_right: float
    series_right: float
    titles_right: float
    price_right: float
    term_right: float
    rate_right: float
    charge_right: float
    deposit_right: float


@dataclass(slots=True)
class ParsedMovement:
    operation_date: str
    settlement_date: str
    reference: Optional[str]
    operation_code: str
    issuer: str
    series: str
    charge: float
    deposit: float
    balance: Optional[float]


# ============================================================
# UTILIDADES GENERALES
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
    heights = [height for height in heights if 0.1 <= height <= 20.0]
    if not heights:
        return 2.0
    return max(1.25, min(3.25, statistics.median(heights) * 0.42))


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
            for index in range(max(0, len(groups) - 5), len(groups)):
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


# ============================================================
# FECHAS E IMPORTES
# ============================================================


def _year(value: str) -> int:
    parsed = int(value)
    return parsed + 2000 if parsed < 100 else parsed


def dates_from_text(value: Any) -> List[date]:
    result: List[date] = []
    for day, _, month, year in FULL_DATE_RE.findall(normalize_text(value)):
        try:
            result.append(date(_year(year), int(month), int(day)))
        except ValueError:
            continue
    return result


def extract_statement_period(
    words: Sequence[SpatialWord],
) -> Tuple[Optional[date], Optional[date]]:
    lines = group_words_into_lines(words)
    for line in lines:
        if line.page != 1 or "PERIODO" not in compact_text(line.text):
            continue
        values = dates_from_text(line.text)
        if len(values) >= 2:
            return values[0], values[1]
    return None, None


def format_statement_date(value: Optional[date]) -> Optional[str]:
    return value.strftime("%d/%m/%Y") if value is not None else None


def parse_money(value: Any) -> Optional[float]:
    original = normalize_text(value)
    if not original or not MONEY_RE.match(original):
        return None

    negative = original.lstrip().startswith("-") or (
        "(" in original and ")" in original
    )
    text = re.sub(r"[^0-9,.'’]", "", original).replace("’", "'")
    if not text or not re.search(r"\d", text):
        return None

    decimal_index = -1
    for separator in (".", ","):
        index = text.rfind(separator)
        decimals = re.sub(r"\D", "", text[index + 1 :]) if index >= 0 else ""
        if index >= 0 and 1 <= len(decimals) <= 2 and index > decimal_index:
            decimal_index = index

    if decimal_index >= 0:
        integer = re.sub(r"\D", "", text[:decimal_index]) or "0"
        decimal = re.sub(r"\D", "", text[decimal_index + 1 :])[:2]
        normalized = f"{integer}.{decimal.ljust(2, '0')}"
    else:
        normalized = re.sub(r"\D", "", text)

    try:
        amount = float(normalized)
    except ValueError:
        return None
    return round(-amount if negative else amount, 2)


def is_money_text(value: Any) -> bool:
    return parse_money(value) is not None


# ============================================================
# TABLA DE MOVIMIENTOS
# ============================================================


def _document_width(words: Sequence[SpatialWord]) -> float:
    observed = max((safe_float(word.get("x1")) for word in words), default=785.0)
    return max(780.0, observed)


def build_column_layout(words: Sequence[SpatialWord]) -> ColumnLayout:
    """Columnas relativas al ancho para tolerar escalado digital/OCR."""

    width = _document_width(words)
    return ColumnLayout(
        width=width,
        registration_right=width * 0.080,
        liquidation_right=width * 0.158,
        folio_right=width * 0.323,
        issuer_right=width * 0.382,
        series_right=width * 0.447,
        titles_right=width * 0.535,
        price_right=width * 0.615,
        term_right=width * 0.651,
        rate_right=width * 0.713,
        charge_right=width * 0.815,
        deposit_right=width * 0.915,
    )


def _text_in_range(line: SpatialLine, left: float, right: float) -> str:
    values = [
        clean_word_text(word.get("text", ""))
        for word in line.words
        if left <= word_center_x(word) < right
    ]
    return " ".join(value for value in values if value).strip()


def _money_in_range(
    line: SpatialLine,
    left: float,
    right: float,
) -> Optional[float]:
    candidates = [
        (word_center_x(word), parse_money(word.get("text", "")))
        for word in line.words
        if left <= word_center_x(word) < right
    ]
    values = [value for _, value in sorted(candidates) if value is not None]
    return values[-1] if values else None


def _parse_row_date(value: str) -> Optional[str]:
    match = ROW_DATE_RE.match(value)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(_year(year), int(month), int(day)).strftime("%d/%m/%Y")
    except ValueError:
        return None


def _is_title(line: SpatialLine) -> bool:
    return "MOVIMIENTOSDELPERIODO" in compact_text(line.text)


def _section_lines(lines: Sequence[SpatialLine]) -> List[SpatialLine]:
    title_index = next(
        (index for index, line in enumerate(lines) if _is_title(line)),
        None,
    )
    if title_index is None:
        return []

    result: List[SpatialLine] = []
    for line in lines[title_index + 1 :]:
        compact = compact_text(line.text)
        if "SALDOFINAL" in compact:
            break
        result.append(line)
    return result


def _initial_balance(section: Sequence[SpatialLine]) -> Optional[float]:
    for line in section:
        if "SALDOINICIAL" not in compact_text(line.text):
            continue
        values = [parse_money(word.get("text", "")) for word in line.words]
        parsed = [value for value in values if value is not None]
        if parsed:
            return parsed[-1]
    return None


def _split_folio(value: str) -> Tuple[Optional[str], str]:
    compact = compact_text(value)
    match = FOLIO_RE.match(compact)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    return (compact or None), "OPERACION"


def _parse_rows(
    section: Sequence[SpatialLine],
    layout: ColumnLayout,
) -> List[ParsedMovement]:
    result: List[ParsedMovement] = []

    for line in section:
        registration = _parse_row_date(
            _text_in_range(line, 0.0, layout.registration_right)
        )
        if registration is None:
            continue
        settlement = _parse_row_date(
            _text_in_range(
                line,
                layout.registration_right,
                layout.liquidation_right,
            )
        )
        if settlement is None:
            settlement = registration

        folio_text = _text_in_range(
            line,
            layout.liquidation_right,
            layout.folio_right,
        )
        reference, operation_code = _split_folio(folio_text)
        issuer = _text_in_range(line, layout.folio_right, layout.issuer_right)
        series = _text_in_range(line, layout.issuer_right, layout.series_right)

        charge = _money_in_range(
            line,
            layout.rate_right,
            layout.charge_right,
        )
        deposit = _money_in_range(
            line,
            layout.charge_right,
            layout.deposit_right,
        )
        balance = _money_in_range(
            line,
            layout.deposit_right,
            float("inf"),
        )

        result.append(
            ParsedMovement(
                operation_date=registration,
                settlement_date=settlement,
                reference=reference,
                operation_code=operation_code,
                issuer=issuer,
                series=series,
                charge=abs(charge or 0.0),
                deposit=abs(deposit or 0.0),
                balance=balance,
            )
        )
    return result


def _reconcile_amounts(
    parsed: Sequence[ParsedMovement],
    initial_balance: Optional[float],
) -> None:
    previous = initial_balance
    for item in parsed:
        if item.balance is None:
            continue
        if previous is not None:
            expected_delta = round(item.balance - previous, 2)
            observed_delta = round(item.deposit - item.charge, 2)
            if abs(expected_delta - observed_delta) > 0.011:
                if expected_delta > 0.0:
                    item.deposit = expected_delta
                    item.charge = 0.0
                elif expected_delta < 0.0:
                    item.charge = abs(expected_delta)
                    item.deposit = 0.0
                else:
                    item.charge = 0.0
                    item.deposit = 0.0
        previous = item.balance


def _concept(item: ParsedMovement) -> Tuple[str, str]:
    operation = OPERATION_NAMES.get(item.operation_code, item.operation_code)
    instrument = " ".join(
        value for value in (item.issuer, item.series) if value
    ).strip()
    concept = f"{operation} - {instrument}" if instrument else operation
    original = " ".join(
        value
        for value in (item.operation_code, item.issuer, item.series)
        if value
    ).strip()
    return concept, original


def _to_model(item: ParsedMovement) -> Movimiento:
    concept, original = _concept(item)
    operation_type: Optional[str] = None
    if item.charge:
        operation_type = "CARGO"
    elif item.deposit:
        operation_type = "ABONO"

    return Movimiento(
        fecha_operacion=item.operation_date,
        fecha_liquidacion=item.settlement_date,
        concepto=concept,
        tipo_operacion=operation_type,
        cargo=round(item.charge, 2),
        abono=round(item.deposit, 2),
        referencia=item.reference,
        autorizacion=None,
        beneficiario=None,
        cuenta_beneficiario=None,
        clabe_beneficiario=None,
        clave_rastreo=None,
        rfc=None,
        sucursal=None,
        caja=None,
        hora_operacion=None,
        saldo_operacion=round(item.balance or 0.0, 2),
        saldo_liquidacion=0.0,
        concepto_original=original,
    )


def extract_movimientos_words(words: List[SpatialWord]) -> List[Movimiento]:
    """Extrae los movimientos de efectivo CETESDIRECTO, digital u OCR."""

    if not words:
        return []
    lines = group_words_into_lines(words)
    section = _section_lines(lines)
    if not section:
        return []
    layout = build_column_layout(words)
    parsed = _parse_rows(section, layout)
    _reconcile_amounts(parsed, _initial_balance(section))
    return [_to_model(item) for item in parsed]


__all__ = [
    "SpatialLine",
    "build_column_layout",
    "compact_text",
    "dates_from_text",
    "extract_movimientos_words",
    "extract_statement_period",
    "format_statement_date",
    "group_words_into_lines",
    "is_money_text",
    "normalize_text",
    "normalize_upper",
    "parse_money",
    "safe_float",
    "safe_page",
    "word_center_x",
    "word_center_y",
]
