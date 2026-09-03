from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
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
CHARGE_OPERATIONS = {"COMPRA", "COMPSI", "EGREFVO", "ISR"}

OPERATION_NAMES = {
    "AMORTIZACION": "AMORTIZACION DE TITULOS",
    "COMPRA": "COMPRA DE TITULOS",
    "COMPSI": "COMPRA DE BONDDIA",
    "EGREFVO": "EGRESO DE EFECTIVO",
    "INGEFVO": "INGRESO DE EFECTIVO",
    "ISR": "RETENCION DE ISR",
    "PAGINTCU": "PAGO DE INTERESES CUPON",
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
            for value in (clean_word_text(word.get("text", "")) for word in self.words)
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
    rotated: bool


@dataclass(slots=True)
class MovementRow:
    """Renglon reconstruido antes de convertirlo al modelo publico."""

    page: int
    center_y: float
    words: List[SpatialWord]
    operation_code: str
    rotated: bool
    registration_text: str
    settlement_text: str


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
    return (safe_float(word.get("top")) + safe_float(word.get("bottom"))) / 2.0


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

    # En los PDFs historicos Tesseract suele agregar un cero al final de
    # importes cortos (por ejemplo ``14.680`` en vez de ``14.68``). El formato
    # de CETESDIRECTO usa coma para miles y punto para centavos, por lo que el
    # caso de tres decimales sin coma se puede corregir sin confundir 1,000.
    three_decimals = re.fullmatch(r"\d{1,6}\.\d{3}", text)
    if three_decimals:
        integer, decimal = text.split(".")
        text = f"{integer}.{decimal[:2]}"

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
# NORMALIZACION DE OCR Y ORIENTACION
# ============================================================


def _canonical_operation(value: Any) -> Optional[str]:
    """Normaliza codigos CETES aun con ruido OCR o una pagina a 180 grados."""

    compact = compact_text(value)
    for operation in OPERATION_NAMES:
        if operation in compact:
            return operation

    # Tesseract sobre texto invertido no solo invierte los caracteres: tambien
    # confunde glifos. Estos patrones describen la forma del codigo, no una
    # coordenada ni un folio particular, y por eso siguen siendo escalables.
    if "LIZ" in compact and compact.endswith("ION"):
        return "AMORTIZACION"
    if compact in {"IS", "ISY", "1S"}:
        return "ISR"
    if compact.endswith(("LYSI", "IVSI")) or compact == "VTSI":
        return "VTASI"
    if any(marker in compact for marker in ("NDSI", "NISI", "NASI")):
        return "COMPSI"
    if compact.endswith(("DAV", "DEV", "DASI")):
        return "COMPRA"
    if compact.startswith("IN") and compact.endswith(("JAO", "JNO", "JSAO")):
        return "INGEFVO"
    return None


def _page_orientation_scores(
    page_words: Sequence[SpatialWord],
    width: float,
) -> Tuple[int, int]:
    normal = 0
    inverted = 0
    if any(
        compact_text(word.get("text", "")) in {"PERIODO", "CONTRATO"}
        for word in page_words
    ):
        return 1_000, 0
    for word in page_words:
        center = word_center_x(word)
        text = word.get("text", "")
        if width * 0.13 <= center <= width * 0.35:
            compact = compact_text(text)
            if any(operation in compact for operation in OPERATION_NAMES):
                normal += 1
            elif _canonical_operation(text) is not None:
                normal += 1
        if width * 0.65 <= center <= width * 0.87:
            if _canonical_operation(normalize_text(text)[::-1]) is not None:
                inverted += 1
    return normal, inverted


def normalize_movement_orientation(
    words: Sequence[SpatialWord],
) -> List[SpatialWord]:
    """Devuelve words logicos y rota solo las paginas de tabla invertidas.

    Algunos PDFs historicos contienen las paginas intermedias a 180 grados.
    PDFium conserva esa orientacion y Tesseract entrega tanto el orden de los
    words como sus caracteres al reves. La deteccion se basa en la posicion y
    forma de varios codigos de operacion para no alterar paginas sanas.
    """

    width = _document_width(words)
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        pages.setdefault(safe_page(word), []).append(word)

    result: List[SpatialWord] = []
    for page in sorted(pages):
        page_words = pages[page]
        normal, inverted = _page_orientation_scores(page_words, width)
        rotate = inverted >= 2 and inverted > normal
        if not rotate:
            result.extend(dict(word) for word in page_words)
            continue

        height = max(
            600.0,
            max((safe_float(word.get("bottom")) for word in page_words), default=0.0)
            + 12.0,
        )
        for word in page_words:
            normalized = dict(word)
            normalized["x0"] = width - safe_float(word.get("x1"))
            normalized["x1"] = width - safe_float(word.get("x0"))
            normalized["top"] = height - safe_float(word.get("bottom"))
            normalized["bottom"] = height - safe_float(word.get("top"))
            normalized["text"] = normalize_text(word.get("text", ""))[::-1]
            normalized["_cetes_rotated"] = True
            result.append(normalized)
    return result


_ROTATED_MONEY_OPTIONS: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "O": (("0", 0.0),),
    "o": (("0", 0.0),),
    "D": (("0", 0.2),),
    "Q": (("0", 0.2),),
    "L": (("1", 0.0), ("7", 0.5)),
    "l": (("1", 0.0), ("7", 0.5)),
    "I": (("1", 0.0),),
    "i": (("1", 0.0),),
    "|": (("1", 0.0),),
    "Z": (("2", 0.0),),
    "z": (("2", 0.0),),
    "E": (("3", 0.0), ("2", 0.5)),
    "e": (("3", 0.0), ("2", 0.5)),
    "C": (("3", 0.2), ("2", 0.3)),
    "c": (("3", 0.2), ("2", 0.3)),
    "€": (("3", 0.0),),
    "£": (("3", 0.0),),
    "v": (("4", 0.0),),
    "V": (("4", 0.0),),
    "A": (("4", 0.2),),
    "Y": (("4", 0.2),),
    "y": (("4", 0.2),),
    "S": (("5", 0.0), ("2", 0.7)),
    "s": (("5", 0.0),),
    "9": (("6", 0.0), ("9", 0.5)),
    "G": (("6", 0.0),),
    "g": (("6", 0.0),),
    "b": (("6", 0.2),),
    "7": ((".", 0.0), ("7", 0.25), ("4", 0.4)),
    "B": (("8", 0.0),),
    "8": (("8", 0.0),),
    "6": (("9", 0.0), ("6", 0.5)),
    "q": (("9", 0.0),),
    "T": ((".", 0.0), ("1", 0.2), ("2", 0.4)),
    "t": ((".", 0.0), ("1", 0.2), ("2", 0.4)),
    ".": ((".", 0.0),),
    ",": ((".", 0.0),),
    "'": ((".", 0.0),),
    ":": ((".", 0.1),),
    '"': ((".", 0.1),),
    "-": (("-", 0.0),),
}


def _rotated_money_candidates(value: Any) -> List[Tuple[float, float]]:
    """Genera (costo OCR, importe) sin escoger silenciosamente un glifo."""

    states: List[Tuple[str, float]] = [("", 0.0)]
    compact_value = normalize_text(value).replace(" ", "")
    for position, character in enumerate(compact_value):
        if character.isdigit() and character not in "679":
            options = ((character, 0.0),)
        elif character == "7" and position == len(compact_value) - 1:
            # Al final del token suele ser el digito 7 (99.17); en medio de
            # ``100700`` representa el punto que OCR perdio (100.00).
            options = (("7", 0.0), (".", 0.4), ("4", 0.4))
        else:
            options = _ROTATED_MONEY_OPTIONS.get(character, (("", 0.35),))
        if character.isalnum() and len(compact_value) >= 4:
            options = (*options, ("", 10.0))
        states = sorted(
            (
                (prefix + replacement, cost + replacement_cost)
                for prefix, cost in states
                for replacement, replacement_cost in options
            ),
            key=lambda candidate: candidate[1],
        )[:300]

    values: Dict[float, float] = {}
    for candidate, cost in states:
        negative = candidate.startswith("-")
        unsigned = candidate.lstrip("-")
        normalized_values: List[Tuple[str, float]] = []
        if unsigned.count(".") == 1:
            integer, decimal = unsigned.split(".")
            if integer and 1 <= len(decimal) <= 2:
                normalized_values.append((f"{integer}.{decimal}", cost))

        digits = re.sub(r"\D", "", unsigned)
        if digits:
            if len(digits) == 1:
                normalized_values.append((f"0.0{digits}", cost + 1.0))
            elif len(digits) == 2:
                normalized_values.append((f"0.{digits}", cost + 0.4))
            else:
                normalized_values.append((f"{digits[:-2]}.{digits[-2:]}", cost + 0.25))

        for normalized, candidate_cost in normalized_values:
            try:
                amount = round(float(normalized), 2)
            except ValueError:
                continue
            if negative:
                amount = -amount
            if abs(amount) > 100_000_000:
                continue
            values[amount] = min(values.get(amount, float("inf")), candidate_cost)
    return sorted((cost, amount) for amount, cost in values.items())[:30]


_ROTATED_DATE_GLYPHS: Dict[str, set[str]] = {
    "/": set("/\\IiNn|!"),
    "0": set("0OoDQ"),
    "1": set("1LlIi|!"),
    "2": set("2Zz7CcTtSs"),
    "3": set("3Ee€£"),
    "4": set("4vVAYy79"),
    "5": set("5Ss"),
    "6": set("69Ggb"),
    "7": set("7Ll1T"),
    "8": set("8B&"),
    "9": set("96Ggq"),
}


def _ocr_date_distance(value: str, expected: str) -> float:
    """Distancia Levenshtein con equivalencias visuales de texto invertido."""

    observed = "".join(
        character
        for character in normalize_text(value)
        if character not in " ,._'\"():"
    )
    previous = [float(index) for index in range(len(expected) + 1)]
    for row, observed_character in enumerate(observed, start=1):
        current = [float(row)] + [0.0] * len(expected)
        for column, expected_character in enumerate(expected, start=1):
            equivalent = observed_character in _ROTATED_DATE_GLYPHS[expected_character]
            substitution = 0.0 if equivalent else 1.0
            current[column] = min(
                previous[column] + 1.0,
                current[column - 1] + 1.0,
                previous[column - 1] + substitution,
            )
        previous = current
    return previous[-1]


def _statement_days(start: date, end: date) -> List[date]:
    if end < start or (end - start).days > 400:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _best_registration_for_settlement(
    row: MovementRow,
    settlement: date,
    start: date,
) -> Tuple[float, date]:
    if row.operation_code != "COMPRA":
        candidates = (settlement,)
    else:
        candidates = tuple(
            settlement - timedelta(days=lag)
            for lag in range(8)
            if settlement - timedelta(days=lag) >= start
        )
    return min(
        (
            _ocr_date_distance(
                row.registration_text,
                candidate.strftime("%d/%m/%y"),
            ),
            candidate,
        )
        for candidate in candidates
    )


def _row_date_candidates(
    row: MovementRow,
    days: Sequence[date],
) -> Dict[int, Tuple[float, date, date]]:
    registration = _parse_row_date(row.registration_text)
    settlement = _parse_row_date(row.settlement_text)
    day_index = {value: index for index, value in enumerate(days)}

    if registration is not None and settlement is not None:
        parsed_registration = dates_from_text(registration)[0]
        parsed_settlement = dates_from_text(settlement)[0]
        index = day_index.get(parsed_settlement)
        if index is not None:
            return {index: (0.0, parsed_registration, parsed_settlement)}

    if not row.rotated:
        # En OCR derecho una fecha puede traer un caracter espurio. Si la otra
        # columna sobrevivio, usarla es mas seguro que inventar otro dia.
        parsed = settlement or registration
        if parsed is None:
            return {}
        parsed_date = dates_from_text(parsed)[0]
        index = day_index.get(parsed_date)
        if index is None:
            return {}
        return {index: (1.0, parsed_date, parsed_date)}

    result: Dict[int, Tuple[float, date, date]] = {}
    start = days[0]
    for index, candidate_settlement in enumerate(days):
        registration_cost, candidate_registration = _best_registration_for_settlement(
            row, candidate_settlement, start
        )
        cost = registration_cost + _ocr_date_distance(
            row.settlement_text,
            candidate_settlement.strftime("%d/%m/%y"),
        )
        if candidate_settlement.weekday() >= 5:
            cost += 1.5
        if candidate_registration.weekday() >= 5:
            cost += 1.5
        result[index] = (
            cost,
            candidate_registration,
            candidate_settlement,
        )
    return result


def _assign_row_dates(
    rows: Sequence[MovementRow],
    start: Optional[date],
    end: Optional[date],
) -> List[Tuple[str, str]]:
    """Escoge fechas globalmente; la liquidacion nunca retrocede entre filas."""

    if start is None or end is None:
        return []
    days = _statement_days(start, end)
    if not days:
        return []

    candidates = [_row_date_candidates(row, days) for row in rows]
    if any(not values for values in candidates):
        return []

    infinity = float("inf")
    state = [infinity] * len(days)
    for index, (cost, _, _) in candidates[0].items():
        state[index] = cost

    back_references: List[List[Optional[int]]] = []
    linked_operations = {
        ("INGEFVO", "COMPSI"),
        ("COMPRA", "AMORTIZACION"),
        ("COMPRA", "VTASI"),
        ("AMORTIZACION", "ISR"),
        ("ISR", "VTASI"),
        ("VTASI", "COMPSI"),
        ("COMPSI", "COMPSI"),
    }
    for row_number, row_candidates in enumerate(candidates[1:], start=1):
        transition_weight = (
            0.4
            if (
                rows[row_number - 1].operation_code,
                rows[row_number].operation_code,
            )
            in linked_operations
            else 0.0
        )
        prefix: List[Tuple[float, Optional[int]]] = []
        best: Tuple[float, Optional[int]] = (infinity, None)
        for index, cost in enumerate(state):
            adjusted = cost - transition_weight * index
            if adjusted < best[0]:
                best = (adjusted, index)
            prefix.append(best)

        new_state = [infinity] * len(days)
        row_back: List[Optional[int]] = [None] * len(days)
        for index, (cost, _, _) in row_candidates.items():
            previous_cost, previous_index = prefix[index]
            if previous_index is None:
                continue
            new_state[index] = previous_cost + transition_weight * index + cost
            row_back[index] = previous_index
        if all(cost == infinity for cost in new_state):
            return []
        state = new_state
        back_references.append(row_back)

    index = min(range(len(state)), key=state.__getitem__)
    selected = [index]
    for row_back in reversed(back_references):
        previous_index = row_back[index]
        if previous_index is None:
            return []
        index = previous_index
        selected.append(index)
    selected.reverse()

    result: List[Tuple[str, str]] = []
    for row_candidates, selected_index in zip(candidates, selected):
        _, registration, settlement = row_candidates[selected_index]
        result.append(
            (
                registration.strftime("%d/%m/%Y"),
                settlement.strftime("%d/%m/%Y"),
            )
        )
    return result


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
        normalize_text(word.get("text", ""))
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


def _movement_row_tolerance(page_words: Sequence[SpatialWord]) -> float:
    heights = [
        safe_float(word.get("bottom")) - safe_float(word.get("top"))
        for word in page_words
    ]
    heights = [height for height in heights if 1.0 <= height <= 20.0]
    if not heights:
        return 5.5
    return max(4.0, min(6.25, statistics.median(heights) * 0.95))


def _movement_rows(
    words: Sequence[SpatialWord],
    layout: ColumnLayout,
) -> List[MovementRow]:
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        pages.setdefault(safe_page(word), []).append(word)

    rows: List[MovementRow] = []
    for page in sorted(pages):
        page_words = pages[page]
        tolerance = _movement_row_tolerance(page_words)
        anchors = [
            word
            for word in page_words
            if layout.registration_right * 1.55
            <= word_center_x(word)
            <= layout.issuer_right
            and _canonical_operation(word.get("text", "")) is not None
        ]
        anchors.sort(key=word_center_y)

        unique_anchors: List[SpatialWord] = []
        for anchor in anchors:
            if (
                unique_anchors
                and abs(word_center_y(anchor) - word_center_y(unique_anchors[-1]))
                <= tolerance * 0.45
            ):
                continue
            unique_anchors.append(anchor)

        for anchor in unique_anchors:
            center_y = word_center_y(anchor)
            row_words = [
                word
                for word in page_words
                if abs(word_center_y(word) - center_y) <= tolerance
            ]
            row_words.sort(key=lambda word: safe_float(word.get("x0")))
            line = SpatialLine(page=page, words=row_words)
            operation = _canonical_operation(anchor.get("text", ""))
            if operation is None:
                continue
            rotated = any(word.get("_cetes_rotated") for word in row_words)
            registration_text = _text_in_range(
                line,
                0.0,
                layout.registration_right,
            )
            settlement_text = _text_in_range(
                line,
                layout.registration_right,
                layout.liquidation_right,
            )
            if (
                not rotated
                and _parse_row_date(registration_text) is None
                and _parse_row_date(settlement_text) is None
            ):
                continue
            rows.append(
                MovementRow(
                    page=page,
                    center_y=center_y,
                    words=row_words,
                    operation_code=operation,
                    rotated=rotated,
                    registration_text=registration_text,
                    settlement_text=settlement_text,
                )
            )
    rows.sort(key=lambda row: (row.page, row.center_y))
    return rows


def _cheapest_rotated_digits(value: str) -> str:
    result: List[str] = []
    for character in value:
        if character.isdigit() and character not in "679":
            result.append(character)
            continue
        options = _ROTATED_MONEY_OPTIONS.get(character, ())
        digit_options = [
            (replacement_cost, replacement)
            for replacement, replacement_cost in options
            if replacement.isdigit()
        ]
        if digit_options:
            result.append(min(digit_options)[1])
    return "".join(result)


def _reference(value: str, rotated: bool) -> Optional[str]:
    compact = compact_text(value)
    match = re.search(r"S?V+D(\d{6,14})", compact)
    if match:
        return f"SVD{match.group(1)}"

    if not rotated:
        return None
    for token in normalize_text(value).split():
        candidate = compact_text(token)
        if len(candidate) < 7 or not candidate.startswith(("SN", "SA", "SG")):
            continue
        digits = _cheapest_rotated_digits(candidate[3:])
        if 6 <= len(digits) <= 14:
            return f"SVD{digits}"
    return None


def _issuer(value: str, rotated: bool) -> str:
    compact = compact_text(value)
    if "CETES" in compact:
        return "CETES"
    if "BONDDIA" in compact:
        return "BONDDIA"
    if "PESOS" in compact:
        return "PESOS"
    if rotated:
        if any(marker in compact for marker in ("93LAS", "9313S", "9HLAS")) or (
            compact.startswith(("93", "9H")) and compact.endswith("S")
        ):
            return "CETES"
        if compact.startswith(("SONA", "9ONA", "OONA", "8ONG")):
            return "BONDDIA"
        if "SOS" in compact:
            return "PESOS"
    return normalize_upper(value)


def _series(
    value: str,
    issuer: str,
    rotated: bool,
    operation_code: str,
    settlement_date: str,
) -> str:
    normalized = normalize_upper(value)
    compact = compact_text(normalized)
    if issuer == "PESOS":
        return "PESOS"
    if issuer == "BONDDIA":
        if "PF2" in compact or rotated:
            return "PF2"
    if issuer == "CETES":
        match = re.search(r"\d{6}", compact)
        if match:
            return match.group(0)
        if rotated:
            settlement = dates_from_text(settlement_date)[0]
            if operation_code in {"AMORTIZACION", "ISR"}:
                return settlement.strftime("%y%m%d")
            candidates = [settlement + timedelta(days=offset) for offset in range(731)]
            return min(
                candidates,
                key=lambda candidate: (
                    _ocr_date_distance(normalized, candidate.strftime("%y%m%d"))
                    + (0.25 if candidate.weekday() != 3 else 0.0),
                    candidate,
                ),
            ).strftime("%y%m%d")
    return normalized


def _money_candidates_from_row(
    row: MovementRow,
    left: float,
    right: float,
) -> List[Tuple[float, float]]:
    line = SpatialLine(page=row.page, words=row.words)
    if not row.rotated:
        value = _money_in_range(line, left, right)
        return [(0.0, value)] if value is not None else []

    values = [
        normalize_text(word.get("text", ""))
        for word in row.words
        if left <= word_center_x(word) < right
    ]
    text = "".join(value for value in values if value)
    return _rotated_money_candidates(text)


def _initial_balance(
    words: Sequence[SpatialWord],
    parsed: Sequence[ParsedMovement],
) -> Optional[float]:
    lines = group_words_into_lines(words)
    for index, line in enumerate(lines):
        if "SALDOINICIAL" not in compact_text(line.text):
            continue
        direct = [
            parse_money(word.get("text", ""))
            for word in line.words
            if word_center_x(word) > _document_width(words) * 0.88
        ]
        direct_amounts = [value for value in direct if value is not None]
        if direct_amounts:
            return direct_amounts[-1]

        nearby = [
            candidate
            for candidate in lines[max(0, index - 2) : index + 3]
            if candidate.page == line.page
            and abs(candidate.center_y - line.center_y) <= 14.0
            and candidate.center_y <= line.center_y + 1.0
        ]
        values = [
            parse_money(word.get("text", ""))
            for candidate in nearby
            for word in candidate.words
            if word_center_x(word) > _document_width(words) * 0.88
        ]
        amounts = [value for value in values if value is not None]
        if amounts:
            return amounts[-1]

    if parsed:
        first = parsed[0]
        delta = first.deposit - first.charge
        if first.balance is not None and abs(first.balance - delta) <= 0.011:
            return 0.0
    return None


def _parse_rows(
    rows: Sequence[MovementRow],
    dates: Sequence[Tuple[str, str]],
    layout: ColumnLayout,
) -> List[ParsedMovement]:
    result: List[ParsedMovement] = []
    rotated_previous: Optional[float] = None
    for row, (registration, settlement) in zip(rows, dates):
        line = SpatialLine(page=row.page, words=row.words)
        folio_text = _text_in_range(
            line,
            layout.liquidation_right,
            layout.folio_right,
        )
        issuer = _issuer(
            _text_in_range(line, layout.folio_right, layout.issuer_right),
            row.rotated,
        )
        series = _series(
            _text_in_range(line, layout.issuer_right, layout.series_right),
            issuer,
            row.rotated,
            row.operation_code,
            settlement,
        )
        charge_candidates = _money_candidates_from_row(
            row, layout.rate_right, layout.charge_right
        )
        deposit_candidates = _money_candidates_from_row(
            row, layout.charge_right, layout.deposit_right
        )
        balance_candidates = _money_candidates_from_row(
            row, layout.deposit_right, float("inf")
        )
        charge = charge_candidates[0][1] if charge_candidates else 0.0
        deposit = deposit_candidates[0][1] if deposit_candidates else 0.0
        balance = balance_candidates[0][1] if balance_candidates else None

        if row.rotated and balance_candidates:
            direction = -1.0 if row.operation_code in CHARGE_OPERATIONS else 1.0
            amount_candidates = (
                charge_candidates if direction < 0 else deposit_candidates
            ) or [(3.0, 0.0)]
            if rotated_previous is None:
                _, amount = amount_candidates[0]
                _, balance = balance_candidates[0]
            else:
                _, amount, balance = min(
                    (
                        (
                            amount_cost
                            + balance_cost
                            + abs(
                                rotated_previous
                                + direction * abs(candidate_amount)
                                - candidate_balance
                            )
                            * 3.0
                            + (
                                20.0
                                if (candidate_balance - rotated_previous) * direction
                                < -0.011
                                else 0.0
                            ),
                            abs(candidate_amount),
                            candidate_balance,
                        )
                        for amount_cost, candidate_amount in amount_candidates
                        for balance_cost, candidate_balance in balance_candidates
                    ),
                    key=lambda candidate: candidate[0],
                )
            charge = amount if direction < 0 else 0.0
            deposit = amount if direction > 0 else 0.0
            rotated_previous = balance
        result.append(
            ParsedMovement(
                operation_date=registration,
                settlement_date=settlement,
                reference=_reference(folio_text, row.rotated),
                operation_code=row.operation_code,
                issuer=issuer,
                series=series,
                charge=abs(charge or 0.0),
                deposit=abs(deposit or 0.0),
                balance=balance,
                rotated=row.rotated,
            )
        )
    return result


def _statement_final_balance(words: Sequence[SpatialWord]) -> Optional[float]:
    for line in group_words_into_lines(words):
        if line.page != 1 or "TOTALDEEFECTIVO" not in compact_text(line.text):
            continue
        values = [parse_money(word.get("text", "")) for word in line.words]
        amounts = [value for value in values if value is not None]
        if amounts:
            return amounts[-1]
    return None


def _optimize_rotated_financials(
    rows: Sequence[MovementRow],
    parsed: Sequence[ParsedMovement],
    layout: ColumnLayout,
    initial_balance: Optional[float],
    final_balance: Optional[float],
) -> None:
    """Selecciona importes/saldos como una secuencia financiera completa."""

    if not rows or not all(row.rotated for row in rows):
        return
    if initial_balance is None:
        initial_balance = 0.0

    layers: List[List[Tuple[float, float, Optional[int], float]]] = []
    previous_layer: List[Tuple[float, float, Optional[int], float]] = [
        (0.0, initial_balance, None, 0.0)
    ]
    for row in rows:
        direction = -1.0 if row.operation_code in CHARGE_OPERATIONS else 1.0
        amount_candidates = _money_candidates_from_row(
            row,
            layout.rate_right if direction < 0 else layout.charge_right,
            layout.charge_right if direction < 0 else layout.deposit_right,
        ) or [(4.0, 0.0)]
        balance_candidates = _money_candidates_from_row(
            row,
            layout.deposit_right,
            float("inf"),
        ) or [(4.0, previous_layer[0][1])]

        layer: List[Tuple[float, float, Optional[int], float]] = []
        for balance_cost, balance in balance_candidates:
            best: Optional[Tuple[float, float, Optional[int], float]] = None
            for previous_index, previous in enumerate(previous_layer):
                previous_cost, previous_balance, _, _ = previous
                for amount_cost, amount in amount_candidates:
                    amount = abs(amount)
                    delta = balance - previous_balance
                    error = abs(previous_balance + direction * amount - balance)
                    score = previous_cost + balance_cost + amount_cost + error * 3.0
                    if delta * direction < -0.011:
                        score += 35.0
                    candidate = (score, balance, previous_index, amount)
                    if best is None or score < best[0]:
                        best = candidate
            if best is not None:
                layer.append(best)
        if not layer:
            return
        layers.append(layer)
        previous_layer = layer

    last_layer = layers[-1]
    last_index = min(
        range(len(last_layer)),
        key=lambda index: (
            last_layer[index][0]
            + (
                abs(last_layer[index][1] - final_balance) * 200.0
                if final_balance is not None
                else 0.0
            )
        ),
    )
    selected: List[Tuple[float, float, Optional[int], float]] = []
    for layer in reversed(layers):
        item = layer[last_index]
        selected.append(item)
        if item[2] is None:
            break
        last_index = item[2]
    selected.reverse()
    if len(selected) != len(parsed):
        return

    previous_balance = initial_balance
    for item, (_, balance, _, amount) in zip(parsed, selected):
        direction = -1.0 if item.operation_code in CHARGE_OPERATIONS else 1.0
        delta = round(balance - previous_balance, 2)
        if delta * direction >= -0.011:
            amount = abs(delta)
        else:
            balance = round(previous_balance + direction * amount, 2)
        item.balance = balance
        if item.operation_code in CHARGE_OPERATIONS:
            item.charge = amount
            item.deposit = 0.0
        else:
            item.charge = 0.0
            item.deposit = amount
        previous_balance = balance


def _reconcile_amounts(
    parsed: Sequence[ParsedMovement],
    initial_balance: Optional[float],
) -> None:
    previous = initial_balance
    for item in parsed:
        if item.balance is None and previous is not None:
            item.balance = round(previous + item.deposit - item.charge, 2)
        if item.balance is None:
            continue
        if previous is not None:
            expected_delta = round(item.balance - previous, 2)
            observed_delta = round(item.deposit - item.charge, 2)
            if abs(expected_delta - observed_delta) > 0.011:
                if item.rotated:
                    direction = (
                        -1.0 if item.operation_code in CHARGE_OPERATIONS else 1.0
                    )
                    # Usar el saldo impreso cuando confirma sentido e importe
                    # dentro de la tolerancia OCR. Si no, conservar la columna
                    # del importe y recalcular el saldo para no propagar ruido.
                    if expected_delta * direction >= 0.0 and (
                        abs(expected_delta - observed_delta) <= 2.5
                        or abs(observed_delta) > max(10.0, abs(expected_delta) * 3.0)
                    ):
                        item.charge = abs(expected_delta) if expected_delta < 0 else 0.0
                        item.deposit = expected_delta if expected_delta > 0 else 0.0
                    else:
                        item.balance = round(previous + observed_delta, 2)
                elif expected_delta > 0.0:
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
        value for value in (item.operation_code, item.issuer, item.series) if value
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
    """Extrae movimientos CETESDIRECTO digitales, OCR y a 180 grados."""

    if not words:
        return []
    start, end = extract_statement_period(words)
    normalized_words = normalize_movement_orientation(words)
    layout = build_column_layout(normalized_words)
    rows = _movement_rows(normalized_words, layout)
    if not rows:
        return []
    dates = _assign_row_dates(rows, start, end)
    if len(dates) != len(rows):
        return []
    parsed = _parse_rows(rows, dates, layout)
    initial = _initial_balance(normalized_words, parsed)
    _optimize_rotated_financials(
        rows,
        parsed,
        layout,
        initial,
        _statement_final_balance(words),
    )
    _reconcile_amounts(parsed, initial)
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
    "normalize_movement_orientation",
    "normalize_upper",
    "parse_money",
    "safe_float",
    "safe_page",
    "word_center_x",
    "word_center_y",
]
