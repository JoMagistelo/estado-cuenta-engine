from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento


SpatialWord = Dict[str, Any]


# ============================================================
# MESES Y MARCADORES DEL DOCUMENTO
# ============================================================

MONTH_NUMBERS = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}

MONTH_NAMES = tuple(MONTH_NUMBERS)
MONTH_PATTERN = "|".join(MONTH_NAMES)

STATEMENT_DATE_RE = re.compile(
    rf"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*[-./]?\s*"
    rf"({MONTH_PATTERN})\s*[-./]?\s*(\d{{2}}|\d{{4}})(?!\d)",
    re.IGNORECASE,
)

MOVEMENT_DATE_RE = re.compile(
    rf"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*[-./]?\s*"
    rf"({MONTH_PATTERN})(?![A-Z])",
    re.IGNORECASE,
)

MOVEMENT_TITLE_MARKERS = (
    "DETALLEDETUSMOVIMIENTOS",
    "DETALLETUSMOVIMIENTOS",
    "DETALLEDEMOVIMIENTOS",
)

COLUMN_HEADER_MARKERS = (
    "FECHA",
    "CONCEPTO",
    "ORIGEN",
    "REFERENCIA",
    "DEPOSITO",
    "RETIRO",
    "SALDO",
)

TERMINAL_MARKERS = (
    "LASTASASDEINTERES",
    "ENELCASODEENVIODETRANSFERENCIAS",
    "CODIESUNAMARCAREGISTRADA",
    "LOSSIGUIENTESDATOSSONINFORMATIVOS",
    "TOTALDECOMISIONESCOBRADAS",
    "ADVERTENCIAS",
)

FOOTER_MARKERS = (
    "PARALOSEFECTOSDELART100",
    "MAGNETICOSYDIGITALESQUEOBRAN",
    "SCOTIABANKINVERLATSA",
)


# ============================================================
# MODELOS ESPACIALES INTERNOS
# ============================================================


@dataclass(slots=True)
class SpatialLine:
    page: int
    words: List[SpatialWord]

    @property
    def top(self) -> float:
        return min(safe_float(word.get("top")) for word in self.words)

    @property
    def bottom(self) -> float:
        return max(safe_float(word.get("bottom")) for word in self.words)

    @property
    def center_y(self) -> float:
        return sum(word_center_y(word) for word in self.words) / len(self.words)

    @property
    def text(self) -> str:
        return " ".join(
            text
            for text in (
                clean_word_text(word.get("text", ""))
                for word in self.words
            )
            if text
        ).strip()


@dataclass(slots=True)
class ColumnLayout:
    """Límites de columnas, calibrados con el encabezado observado."""

    page_width: float
    date_right: float
    reference_start: float
    deposit_start: float
    withdrawal_start: float
    balance_start: float


@dataclass(slots=True)
class MovementBlock:
    lines: List[SpatialLine]

    @property
    def first_line(self) -> SpatialLine:
        return self.lines[0]


# ============================================================
# NORMALIZACIÓN SEGURA
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
    return (
        safe_float(word.get("x0"))
        + safe_float(word.get("x1"))
    ) / 2.0


def word_center_y(word: SpatialWord) -> float:
    return (
        safe_float(word.get("top"))
        + safe_float(word.get("bottom"))
    ) / 2.0


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def normalize_upper(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_text(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return text.upper()


def compact_text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_upper(value))


def clean_word_text(value: Any) -> str:
    text = normalize_text(value)

    if not text:
        return ""

    # Tesseract suele convertir líneas de la tabla en estos símbolos.
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9$]", text):
        return ""

    return text.strip(" _—–|¦")


# ============================================================
# AGRUPACIÓN EN RENGLONES
# ============================================================


def _line_tolerance(page_words: Sequence[SpatialWord]) -> float:
    heights = [
        safe_float(word.get("bottom")) - safe_float(word.get("top"))
        for word in page_words
    ]
    heights = [height for height in heights if 0.05 <= height <= 20.0]

    if not heights:
        return 2.0

    # PDF digital de Scotiabank reporta alturas cercanas a 0.24,
    # mientras que Tesseract produce alturas de 5 a 10 puntos.
    return max(1.25, min(3.25, statistics.median(heights) * 0.48))


def group_words_into_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    """Agrupa words de PDF digital y OCR sin depender de un top exacto."""

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
            center = word_center_y(word)
            candidate: Optional[int] = None
            candidate_delta = float("inf")

            # Los centros están ordenados; normalmente sólo los últimos
            # renglones pueden recibir la palabra actual.
            for index in range(max(0, len(groups) - 4), len(groups)):
                delta = abs(center - centers[index])
                if delta <= tolerance and delta < candidate_delta:
                    candidate = index
                    candidate_delta = delta

            if candidate is None:
                groups.append([word])
                centers.append(center)
                continue

            groups[candidate].append(word)
            centers[candidate] = sum(
                word_center_y(item) for item in groups[candidate]
            ) / len(groups[candidate])

        ordered_groups = sorted(
            zip(centers, groups),
            key=lambda item: item[0],
        )

        for _, line_words in ordered_groups:
            line_words.sort(key=lambda item: safe_float(item.get("x0")))
            result.append(SpatialLine(page=page, words=line_words))

    return result


# ============================================================
# FECHAS DEL ESTADO DE CUENTA
# ============================================================


def _parse_full_dates(value: Any) -> List[date]:
    normalized = normalize_upper(value)
    result: List[date] = []

    for day_text, month_text, year_text in STATEMENT_DATE_RE.findall(normalized):
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


def extract_statement_period(
    words: Sequence[SpatialWord],
) -> Tuple[Optional[date], Optional[date]]:
    """Obtiene el periodo usando la etiqueta, no una coordenada absoluta."""

    page_one = [word for word in words if safe_page(word) == 1]

    for anchor in page_one:
        if "PERIODO" not in compact_text(anchor.get("text", "")):
            continue

        anchor_y = word_center_y(anchor)
        nearby = [
            word
            for word in page_one
            if abs(word_center_y(word) - anchor_y) <= 8.0
            and safe_float(word.get("x0")) >= safe_float(anchor.get("x0")) - 5.0
        ]
        nearby.sort(key=lambda item: (word_center_y(item), safe_float(item.get("x0"))))
        dates = _parse_full_dates(
            " ".join(normalize_text(word.get("text", "")) for word in nearby)
        )

        if len(dates) >= 2:
            return dates[0], dates[1]

    # Fallback para tokens compactos como 26-NOV-24/24-DIC-24.
    for word in page_one:
        dates = _parse_full_dates(word.get("text", ""))
        if len(dates) >= 2:
            return dates[0], dates[1]

    return None, None


def format_statement_date(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None

    month_name = next(
        name
        for name, month_number in MONTH_NUMBERS.items()
        if month_number == value.month and name != "SET"
    )
    return f"{value.day:02d}-{month_name}-{value.year % 100:02d}"


def _movement_date_parts(
    line: SpatialLine,
    layout: ColumnLayout,
) -> Optional[Tuple[int, int]]:
    date_words = [
        clean_word_text(word.get("text", ""))
        for word in line.words
        if word_center_x(word) <= layout.date_right
    ]
    date_text = " ".join(value for value in date_words if value)
    match = MOVEMENT_DATE_RE.search(normalize_upper(date_text))

    if match is None:
        match = MOVEMENT_DATE_RE.search(compact_text(date_text))

    if match is None:
        return None

    day = int(match.group(1))
    month = MONTH_NUMBERS[match.group(2).upper()]

    try:
        date(2000, month, day)
    except ValueError:
        return None

    return day, month


def _build_operation_date(
    parts: Optional[Tuple[int, int]],
    period_start: Optional[date],
    period_end: Optional[date],
) -> str:
    if parts is None:
        return ""

    day, month = parts

    if period_start is None and period_end is None:
        month_name = next(
            name
            for name, number in MONTH_NUMBERS.items()
            if number == month and name != "SET"
        )
        return f"{day:02d} {month_name}"

    reference = period_end or period_start
    assert reference is not None

    candidates: List[date] = []
    for year in range(reference.year - 1, reference.year + 2):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue

    if period_start is not None and period_end is not None:
        lower = period_start - timedelta(days=3)
        upper = period_end + timedelta(days=3)
        in_period = [candidate for candidate in candidates if lower <= candidate <= upper]
        if in_period:
            candidates = in_period

    chosen = min(candidates, key=lambda candidate: abs((candidate - reference).days))
    return chosen.strftime("%d/%m/%Y")


# ============================================================
# IMPORTES
# ============================================================


def parse_money(value: Any) -> Optional[float]:
    """Convierte importes mexicanos y repara errores OCR conservadores."""

    original = normalize_text(value)
    if not original or "%" in original:
        return None

    if not re.search(r"\d", original):
        return None

    # Sólo se corrigen caracteres OCR dentro de un token que ya contiene
    # evidencia numérica.
    normalized = original.translate(
        str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
    )
    negative = normalized.lstrip().startswith("-") or (
        "(" in normalized and ")" in normalized
    )
    currency_hint = "$" in normalized
    numeric = re.sub(r"[^0-9.,]", "", normalized)

    if not numeric or not re.search(r"\d", numeric):
        return None

    decimal_value: str

    if "," in numeric and "." in numeric:
        decimal_separator = "." if numeric.rfind(".") > numeric.rfind(",") else ","
        integer_part, fraction = numeric.rsplit(decimal_separator, 1)
        integer_part = re.sub(r"[.,]", "", integer_part)
        decimal_value = f"{integer_part}.{fraction}"
    elif "," in numeric:
        left, right = numeric.rsplit(",", 1)
        if len(right) == 2:
            decimal_value = f"{left.replace(',', '')}.{right}"
        elif len(right) > 3 and currency_hint:
            # Ejemplo OCR: $2,03218 -> 2032.18
            digits = numeric.replace(",", "")
            decimal_value = f"{digits[:-2]}.{digits[-2:]}"
        else:
            decimal_value = numeric.replace(",", "")
    elif "." in numeric:
        left, right = numeric.rsplit(".", 1)
        if len(right) == 2:
            decimal_value = f"{left.replace('.', '')}.{right}"
        else:
            decimal_value = numeric.replace(".", "")
    else:
        decimal_value = numeric

    try:
        amount = float(decimal_value)
    except ValueError:
        return None

    return round(-amount if negative else amount, 2)


def is_money_text(value: Any) -> bool:
    text = normalize_text(value)
    if not text or "%" in text:
        return False

    return bool(
        "$" in text
        or re.search(r"[-(]?\d[\d,]*\.\d{2}\)?", text)
        or re.search(r"[-(]?\d[\d.]*,\d{2}\)?", text)
    )


# ============================================================
# DETECCIÓN DE SECCIÓN Y COLUMNAS
# ============================================================


def _is_movement_title(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in MOVEMENT_TITLE_MARKERS)


def _is_column_header(line: SpatialLine) -> bool:
    normalized = normalize_upper(line.text)
    score = sum(marker in normalized for marker in COLUMN_HEADER_MARKERS)
    return score >= 3


def _is_page_identification(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return "PAGINA" in compact and "CUENTA" in compact


def _is_footer(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in FOOTER_MARKERS)


def _is_terminal(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in TERMINAL_MARKERS)


def _movement_pages(lines: Sequence[SpatialLine]) -> List[int]:
    by_page: Dict[int, List[SpatialLine]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)

    title_pages = {
        page
        for page, page_lines in by_page.items()
        if any(_is_movement_title(line) for line in page_lines)
    }
    header_pages = {
        page
        for page, page_lines in by_page.items()
        if any(_is_column_header(line) for line in page_lines)
    }

    # En páginas intermedias Tesseract puede omitir el título "Detalle",
    # pero conserva el encabezado completo de columnas.
    return sorted(title_pages | header_pages)


def _section_lines(lines: Sequence[SpatialLine]) -> List[SpatialLine]:
    by_page: Dict[int, List[SpatialLine]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)

    result: List[SpatialLine] = []
    stop_document = False

    for page in _movement_pages(lines):
        if stop_document:
            break

        page_lines = sorted(by_page[page], key=lambda line: line.center_y)
        title_indexes = [
            index for index, line in enumerate(page_lines) if _is_movement_title(line)
        ]
        header_indexes = [
            index for index, line in enumerate(page_lines) if _is_column_header(line)
        ]

        if title_indexes:
            start_index = title_indexes[0] + 1
        elif header_indexes:
            start_index = header_indexes[0]
        else:
            continue

        for line in page_lines[start_index:]:
            if _is_terminal(line):
                stop_document = True
                break

            if _is_footer(line):
                break

            if (
                _is_movement_title(line)
                or _is_column_header(line)
                or _is_page_identification(line)
            ):
                continue

            if line.text:
                result.append(line)

    return result


def _median_word_center(
    lines: Sequence[SpatialLine],
    markers: Iterable[str],
    max_width: float = 100.0,
) -> Optional[float]:
    marker_values = tuple(markers)
    candidates: List[float] = []

    for line in lines:
        if not _is_column_header(line):
            continue

        for word in line.words:
            compact = compact_text(word.get("text", ""))
            width = safe_float(word.get("x1")) - safe_float(word.get("x0"))
            if width <= max_width and any(marker in compact for marker in marker_values):
                candidates.append(word_center_x(word))

    return statistics.median(candidates) if candidates else None


def build_column_layout(
    all_words: Sequence[SpatialWord],
    section_lines: Sequence[SpatialLine],
) -> ColumnLayout:
    max_x = max((safe_float(word.get("x1")) for word in all_words), default=592.0)
    page_width = max(612.0, max_x + 18.0)

    concept_center = _median_word_center(section_lines, ("CONCEPTO",), 180.0)
    reference_center = _median_word_center(
        section_lines,
        ("ORIGENREFERENCIA", "REFERENCIA", "ORIGEN"),
        120.0,
    )
    deposit_center = _median_word_center(section_lines, ("DEPOSITO",), 80.0)
    withdrawal_center = _median_word_center(section_lines, ("RETIRO",), 80.0)
    balance_center = _median_word_center(section_lines, ("SALDO",), 80.0)

    reference_start = page_width * 0.395
    deposit_start = page_width * 0.59
    withdrawal_start = page_width * 0.725
    balance_start = page_width * 0.84

    if concept_center is not None and reference_center is not None:
        reference_start = (concept_center + reference_center) / 2.0
    if reference_center is not None and deposit_center is not None:
        deposit_start = (reference_center + deposit_center) / 2.0
    if deposit_center is not None and withdrawal_center is not None:
        withdrawal_start = (deposit_center + withdrawal_center) / 2.0
    if withdrawal_center is not None and balance_center is not None:
        balance_start = (withdrawal_center + balance_center) / 2.0

    # Un encabezado OCR defectuoso nunca debe invertir columnas.
    if not (
        page_width * 0.34 < reference_start < page_width * 0.47
        and reference_start < deposit_start < page_width * 0.68
        and deposit_start < withdrawal_start < page_width * 0.80
        and withdrawal_start < balance_start < page_width * 0.91
    ):
        reference_start = page_width * 0.395
        deposit_start = page_width * 0.59
        withdrawal_start = page_width * 0.725
        balance_start = page_width * 0.84

    return ColumnLayout(
        page_width=page_width,
        date_right=page_width * 0.145,
        reference_start=reference_start,
        deposit_start=deposit_start,
        withdrawal_start=withdrawal_start,
        balance_start=balance_start,
    )


# ============================================================
# RECONSTRUCCIÓN DE BLOQUES
# ============================================================


def _financial_values_from_line(
    line: SpatialLine,
    layout: ColumnLayout,
) -> Dict[str, float]:
    result: Dict[str, float] = {}

    for word in line.words:
        text = clean_word_text(word.get("text", ""))
        if not is_money_text(text):
            continue

        amount = parse_money(text)
        if amount is None:
            continue

        center_x = word_center_x(word)

        if center_x >= layout.balance_start:
            result.setdefault("balance", amount)
        elif center_x >= layout.withdrawal_start:
            result.setdefault("withdrawal", amount)
        elif center_x >= layout.deposit_start:
            result.setdefault("deposit", amount)

    return result


def _reference_text_from_line(
    line: SpatialLine,
    layout: ColumnLayout,
) -> Optional[str]:
    parts: List[str] = []

    for word in line.words:
        center_x = word_center_x(word)
        if not (layout.reference_start <= center_x < layout.deposit_start):
            continue

        value = re.sub(r"[^A-Za-z0-9]", "", normalize_text(word.get("text", "")))
        if value:
            parts.append(value)

    value = "".join(parts)
    return value or None


def _concept_line_text(
    line: SpatialLine,
    layout: ColumnLayout,
) -> str:
    parts = [
        clean_word_text(word.get("text", ""))
        for word in line.words
        if layout.date_right < word_center_x(word) < layout.reference_start
    ]
    return " ".join(part for part in parts if part).strip()


def _line_starts_movement(
    line: SpatialLine,
    layout: ColumnLayout,
) -> bool:
    if _movement_date_parts(line, layout) is None:
        return False

    financial = _financial_values_from_line(line, layout)
    if financial:
        return True

    # Recuperación parcial: fecha + concepto + referencia, aun cuando
    # Tesseract haya omitido los importes del renglón.
    return bool(
        _concept_line_text(line, layout)
        and _reference_text_from_line(line, layout)
    )


def build_movement_blocks(
    section_lines: Sequence[SpatialLine],
    layout: ColumnLayout,
) -> List[MovementBlock]:
    blocks: List[MovementBlock] = []
    current: List[SpatialLine] = []

    for line in section_lines:
        if _line_starts_movement(line, layout):
            if current:
                blocks.append(MovementBlock(lines=current))
            current = [line]
            continue

        if current and line.text:
            current.append(line)

    if current:
        blocks.append(MovementBlock(lines=current))

    return blocks


# ============================================================
# CAMPOS DERIVADOS DEL CONCEPTO
# ============================================================


def _concept_from_block(block: MovementBlock, layout: ColumnLayout) -> str:
    lines: List[str] = []

    for line in block.lines:
        value = _concept_line_text(line, layout)
        if value:
            lines.append(value)

    return "\n".join(lines).strip()


def _amounts_from_block(
    block: MovementBlock,
    layout: ColumnLayout,
) -> Tuple[float, float, float]:
    deposit: Optional[float] = None
    withdrawal: Optional[float] = None
    balance: Optional[float] = None

    for line in block.lines:
        values = _financial_values_from_line(line, layout)
        if deposit is None and "deposit" in values:
            deposit = values["deposit"]
        if withdrawal is None and "withdrawal" in values:
            withdrawal = values["withdrawal"]
        if balance is None and "balance" in values:
            balance = values["balance"]

    return deposit or 0.0, withdrawal or 0.0, balance or 0.0


def _extract_time(concept: str) -> Optional[str]:
    match = re.search(r"\b([01]\d|2[0-3]):[0-5]\d:[0-5]\d\b", concept)
    return match.group(0) if match else None


def _extract_authorization(concept: str) -> Optional[str]:
    match = re.search(
        r"(?:^|\s)[/|I]?([0-9O]{8,10})\s+(?=[0-2]\d:[0-5]\d:[0-5]\d)",
        concept,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None

    value = match.group(1).upper().replace("O", "0")
    return value[-8:]


def _extract_tracking_key(concept: str) -> Optional[str]:
    for line in concept.splitlines():
        compact = re.sub(r"[^A-Za-z0-9]", "", line).upper()
        match = re.search(r"20\d{2}[A-Z0-9]{18,}", compact)
        if match:
            return match.group(0)
    return None


def _extract_beneficiary(concept: str) -> Optional[str]:
    for line in concept.splitlines():
        normalized = normalize_upper(line)
        match = re.search(r"\bTRANSFERENCIA\s+A\s+(.+)$", normalized)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def _extract_account_identifiers(
    concept: str,
) -> Tuple[Optional[str], Optional[str]]:
    account: Optional[str] = None
    clabe: Optional[str] = None

    for line in concept.splitlines()[1:]:
        compact = re.sub(r"\s+", "", line)
        slash_match = re.search(r"/(\d{16,18})$", compact)
        plain_match = re.fullmatch(r"\d{16}|\d{18}", compact)

        if slash_match:
            value = slash_match.group(1)
        elif plain_match:
            value = plain_match.group(0)
        else:
            continue

        if len(value) == 18:
            clabe = value
        else:
            account = value

    return account, clabe


def _extract_caja(concept: str) -> Optional[str]:
    match = re.search(r"\bI\d{5}\b", normalize_upper(concept))
    return match.group(0) if match else None


def _movement_from_block(
    block: MovementBlock,
    layout: ColumnLayout,
    period_start: Optional[date],
    period_end: Optional[date],
) -> Movimiento:
    concept = _concept_from_block(block, layout)
    deposit, withdrawal, balance = _amounts_from_block(block, layout)
    reference = _reference_text_from_line(block.first_line, layout)
    account, clabe = _extract_account_identifiers(concept)

    operation_type: Optional[str]
    if withdrawal != 0.0:
        operation_type = "CARGO"
    elif deposit != 0.0:
        operation_type = "ABONO"
    else:
        operation_type = None

    return Movimiento(
        fecha_operacion=_build_operation_date(
            _movement_date_parts(block.first_line, layout),
            period_start,
            period_end,
        ),
        fecha_liquidacion=None,
        concepto=concept,
        tipo_operacion=operation_type,
        cargo=withdrawal,
        abono=deposit,
        referencia=reference,
        autorizacion=_extract_authorization(concept),
        beneficiario=_extract_beneficiary(concept),
        cuenta_beneficiario=account,
        clabe_beneficiario=clabe,
        clave_rastreo=_extract_tracking_key(concept),
        rfc=None,
        sucursal=None,
        caja=_extract_caja(concept),
        hora_operacion=_extract_time(concept),
        saldo_operacion=balance,
        saldo_liquidacion=0.0,
        concepto_original=concept,
    )


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================


def extract_movimientos_words(words: List[SpatialWord]) -> List[Movimiento]:
    """
    Extrae movimientos Scotiabank desde words digitales u OCR.

    La detección se basa en anclas semánticas y columnas calibradas.
    Conserva continuaciones entre páginas y se detiene antes de las
    leyendas y tablas informativas posteriores a los movimientos.
    """

    if not words:
        return []

    lines = group_words_into_lines(words)
    section = _section_lines(lines)

    if not section:
        return []

    layout = build_column_layout(words, section)
    blocks = build_movement_blocks(section, layout)
    period_start, period_end = extract_statement_period(words)

    movements: List[Movimiento] = []

    for block in blocks:
        movement = _movement_from_block(
            block,
            layout,
            period_start,
            period_end,
        )

        has_identity = bool(
            movement.fecha_operacion
            and (movement.concepto or movement.referencia)
        )
        has_financial_data = any(
            value != 0.0
            for value in (
                movement.cargo,
                movement.abono,
                movement.saldo_operacion,
            )
        )

        # Una fila parcial con identidad se conserva. Esto permite
        # recuperar movimientos cuando OCR pierde exclusivamente importes.
        if has_identity and (has_financial_data or movement.referencia):
            movements.append(movement)

    return movements


__all__ = [
    "ColumnLayout",
    "SpatialLine",
    "compact_text",
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
