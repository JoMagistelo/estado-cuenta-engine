from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento


SpatialWord = Dict[str, Any]


# ============================================================
# PATRONES Y MARCADORES DEL DOCUMENTO
# ============================================================

FULL_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*"
    r"(0?[1-9]|1[0-2])\s*\2\s*(\d{2}|\d{4})(?!\d)"
)

MOVEMENT_DATE_RE = re.compile(
    r"^\s*(0?[1-9]|[12]\d|3[01])\s*[/.-]\s*"
    r"(0?[1-9]|1[0-2])\s*[/.-]\s*(\d{4})\s*$"
)

MONEY_RE = re.compile(
    r"^\s*[-(]?\s*\$?\s*\d[\d\s,.'’]*"
    r"(?:[.,]\d{1,2})?\s*\)?\s*$"
)

MOVEMENT_TITLE_MARKERS = (
    "DETALLESDELACUENTAALAVISTA",
    "DETALLEDELACUENTAALAVISTA",
    "DETALLESDECUENTAALAVISTA",
)

TERMINAL_MARKERS = (
    "SUMADERETIROSYDEPOSITOS",
    "SALDOAFECHADECORTE",
    "CARGOSOBJETADOS",
    "SPEIENVIADOS",
    "SPEIRECIBIDOS",
)

FOOTER_MARKERS = (
    "BANCAMIFELSA",
    "PRESIDENTEMASARYK",
    "REGIMENFISCAL",
    "WWW MIFEL",
)


# ============================================================
# MODELOS ESPACIALES INTERNOS
# ============================================================


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
            text
            for text in (
                clean_word_text(word.get("text", "")) for word in self.words
            )
            if text
        ).strip()


@dataclass(slots=True)
class ColumnLayout:
    date_right: float = 88.0
    reference_left: float = 88.0
    reference_right: float = 190.0
    concept_left: float = 190.0
    withdrawal_left: float = 335.0
    deposit_left: float = 415.0
    balance_left: float = 490.0


@dataclass(slots=True)
class ParsedMovement:
    operation_date: str
    reference: Optional[str]
    concept: str
    withdrawal: float
    deposit: float
    balance: Optional[float]


@dataclass(slots=True)
class SpeiDetailLayout:
    """Limites de las columnas de las tablas informativas SPEI de Mifel."""

    bank_right: float = 104.0
    date_right: float = 145.0
    amount_right: float = 212.0
    account_right: float = 325.0
    beneficiary_right: float = 410.0
    tracking_right: float = 460.0
    reference_right: float = 500.0


@dataclass(slots=True)
class SpeiDetail:
    """Contraparte y metadatos publicados fuera de la tabla de movimientos."""

    direction: str
    operation_date: str
    amount: Optional[float]
    bank: Optional[str]
    beneficiary: Optional[str]
    account: Optional[str]
    clabe: Optional[str]
    tracking_key: Optional[str]
    reference: Optional[str]
    concept: Optional[str]
    operation_time: Optional[str]


# ============================================================
# NORMALIZACION Y AGRUPACION DE WORDS
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
    if not text:
        return ""
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9$]", text):
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
    """Agrupa words digitales y OCR sin depender de coordenadas exactas."""

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


def _four_digit_year(value: str) -> int:
    year = int(value)
    return year + 2000 if year < 100 else year


def dates_from_text(value: Any) -> List[date]:
    result: List[date] = []
    for day, _, month, year in FULL_DATE_RE.findall(normalize_text(value)):
        try:
            result.append(date(_four_digit_year(year), int(month), int(day)))
        except ValueError:
            continue
    return result


def extract_statement_period(
    words: Sequence[SpatialWord],
) -> Tuple[Optional[date], Optional[date]]:
    lines = group_words_into_lines(words)

    for line in lines:
        if line.page != 1:
            continue
        compact = compact_text(line.text)
        if "PERIODO" not in compact:
            continue
        dates = dates_from_text(line.text)
        if len(dates) >= 2:
            return dates[0], dates[1]

    page_one_dates: List[date] = []
    for line in lines:
        if line.page == 1:
            page_one_dates.extend(dates_from_text(line.text))
    if len(page_one_dates) >= 2:
        return min(page_one_dates), max(page_one_dates)
    return None, None


def format_statement_date(value: Optional[date]) -> Optional[str]:
    return value.strftime("%d/%m/%Y") if value is not None else None


def parse_money(value: Any) -> Optional[float]:
    """Convierte importes mexicanos y tolera separadores comunes de OCR."""

    original = normalize_text(value)
    if not original or not MONEY_RE.match(original):
        return None

    negative = original.lstrip().startswith("-") or (
        "(" in original and ")" in original
    )
    text = re.sub(r"[^0-9,.'’]", "", original).replace("’", "'")
    if not text or not re.search(r"\d", text):
        return None

    # El ultimo separador con uno o dos digitos a la derecha es decimal.
    decimal_index = -1
    for separator in (".", ","):
        index = text.rfind(separator)
        if index >= 0 and 1 <= len(re.sub(r"\D", "", text[index + 1 :])) <= 2:
            if index > decimal_index:
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
# DETECCION DE LA TABLA Y SUS COLUMNAS
# ============================================================


def _is_title(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in MOVEMENT_TITLE_MARKERS)


def _is_header(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    score = sum(
        marker in compact
        for marker in ("FECHA", "REFERENCIA", "DESCRIPCION", "RETIROS", "DEPOSITOS", "SALDO")
    )
    return score >= 4


def _is_terminal(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in TERMINAL_MARKERS)


def _is_footer_or_page_header(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    if any(marker.replace(" ", "") in compact for marker in FOOTER_MARKERS):
        return True
    return (
        compact in {"ESTADODECUENTA", "CUENTAALAVISTA"}
        or compact.startswith("PAGINA")
    )


def _section_lines(lines: Sequence[SpatialLine]) -> List[SpatialLine]:
    title_index: Optional[int] = None
    for index, line in enumerate(lines):
        if _is_title(line):
            title_index = index
            break
    if title_index is None:
        return []

    start_index = title_index + 1
    for index in range(title_index + 1, min(len(lines), title_index + 12)):
        if _is_header(lines[index]):
            start_index = index + 1
            break

    result: List[SpatialLine] = []
    for line in lines[start_index:]:
        if _is_terminal(line):
            break
        if _is_header(line) or _is_footer_or_page_header(line):
            continue
        result.append(line)
    return result


def _header_layout(lines: Sequence[SpatialLine]) -> ColumnLayout:
    header = next((line for line in lines if _is_header(line)), None)
    if header is None:
        return ColumnLayout()

    centers: Dict[str, float] = {}
    for key, marker in (
        ("date", "FECHA"),
        ("reference", "REFERENCIA"),
        ("concept", "DESCRIPCION"),
        ("withdrawal", "RETIROS"),
        ("deposit", "DEPOSITOS"),
        ("balance", "SALDO"),
    ):
        matches = [
            word_center_x(word)
            for word in header.words
            if marker in compact_text(word.get("text", ""))
        ]
        if matches:
            centers[key] = sum(matches) / len(matches)

    if len(centers) < 5:
        return ColumnLayout()

    return ColumnLayout(
        date_right=(centers["date"] + centers["reference"]) / 2.0,
        reference_left=(centers["date"] + centers["reference"]) / 2.0,
        reference_right=(centers["reference"] + centers["concept"]) / 2.0,
        concept_left=(centers["reference"] + centers["concept"]) / 2.0,
        withdrawal_left=(centers["concept"] + centers["withdrawal"]) / 2.0,
        deposit_left=(centers["withdrawal"] + centers["deposit"]) / 2.0,
        balance_left=(centers["deposit"] + centers["balance"]) / 2.0,
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


def _movement_date(line: SpatialLine, layout: ColumnLayout) -> Optional[str]:
    date_text = _text_in_range(line, 0.0, layout.date_right)
    match = MOVEMENT_DATE_RE.match(date_text)
    if not match:
        return None
    day, month, year = (int(group) for group in match.groups())
    try:
        return date(year, month, day).strftime("%d/%m/%Y")
    except ValueError:
        return None


def _reference(line: SpatialLine, layout: ColumnLayout) -> Optional[str]:
    tokens = [
        clean_word_text(word.get("text", ""))
        for word in line.words
        if layout.reference_left <= word_center_x(word) < layout.reference_right
    ]
    value = "".join(token for token in tokens if token)
    value = re.sub(r"\s+", "", value)
    return value or None


def _concept_line(line: SpatialLine, layout: ColumnLayout) -> str:
    return _text_in_range(
        line,
        layout.concept_left,
        layout.withdrawal_left,
    )


def _initial_balance(lines: Sequence[SpatialLine]) -> Optional[float]:
    title = next((line for line in lines if _is_title(line)), None)

    for line in lines:
        if "SALDOINICIAL" not in compact_text(line.text):
            continue
        if title is not None and (
            line.page != title.page
            or not (title.center_y < line.center_y <= title.center_y + 45.0)
        ):
            continue
        candidates = [
            parse_money(word.get("text", "")) for word in line.words
        ]
        values = [value for value in candidates if value is not None]
        if values:
            return values[-1]
    return None


# ============================================================
# CONSTRUCCION Y CONCILIACION DE MOVIMIENTOS
# ============================================================


def _parse_blocks(
    section: Sequence[SpatialLine],
    layout: ColumnLayout,
) -> List[ParsedMovement]:
    blocks: List[List[SpatialLine]] = []

    for line in section:
        if _movement_date(line, layout):
            blocks.append([line])
        elif blocks and _concept_line(line, layout):
            blocks[-1].append(line)

    result: List[ParsedMovement] = []
    for block in blocks:
        first = block[0]
        operation_date = _movement_date(first, layout)
        if operation_date is None:
            continue

        concepts = [_concept_line(line, layout) for line in block]
        concept = " ".join(value for value in concepts if value).strip()

        withdrawal = _money_in_range(
            first,
            layout.withdrawal_left,
            layout.deposit_left,
        )
        deposit = _money_in_range(
            first,
            layout.deposit_left,
            layout.balance_left,
        )
        balance = _money_in_range(first, layout.balance_left, float("inf"))

        result.append(
            ParsedMovement(
                operation_date=operation_date,
                reference=_reference(first, layout),
                concept=concept,
                withdrawal=abs(withdrawal or 0.0),
                deposit=abs(deposit or 0.0),
                balance=balance,
            )
        )
    return result


def _reconcile_amounts(
    parsed: Sequence[ParsedMovement],
    initial_balance: Optional[float],
) -> None:
    """
    Reconstruye importes perdidos por OCR a partir de saldos consecutivos.

    Mifel imprime saldo en cada movimiento. Si el importe observado no
    explica el cambio de saldo, el delta es la fuente contable autoritativa.
    Esto recupera, entre otros casos, retenciones ISR pequeñas omitidas por
    Tesseract sin introducir reglas ligadas a una fecha o referencia.
    """

    previous = initial_balance
    for item in parsed:
        if item.balance is None:
            continue
        if previous is not None:
            expected_delta = round(item.balance - previous, 2)
            observed_delta = round(item.deposit - item.withdrawal, 2)
            if abs(expected_delta - observed_delta) > 0.011:
                if expected_delta > 0.0:
                    item.deposit = expected_delta
                    item.withdrawal = 0.0
                elif expected_delta < 0.0:
                    item.withdrawal = abs(expected_delta)
                    item.deposit = 0.0
                else:
                    item.withdrawal = 0.0
                    item.deposit = 0.0
        previous = item.balance


# ============================================================
# TABLAS INFORMATIVAS SPEI Y ENRIQUECIMIENTO
# ============================================================


SPEI_DETAIL_TERMINAL_MARKERS = (
    "FONDOSDEINVERSION",
    "INVERSIONESAPLAZO",
    "MESADEDINERO",
    "ACLARACIONES",
    "REFERENCIADEABREVIATURAS",
    "INFORMACIONIMPORTANTE",
    "COMPROBANTEFISCAL",
)


_BANK_ALIASES: Tuple[Tuple[str, str], ...] = (
    ("BBVABANCOMER", "BBVA MEXICO"),
    ("BBVAMEXICO", "BBVA MEXICO"),
    ("SANTANDER", "SANTANDER"),
    ("CITIBANAMEX", "BANAMEX"),
    ("BANCONACIONALDEMEXICO", "BANAMEX"),
    ("BANAMEX", "BANAMEX"),
    ("BANCOAZTECA", "AZTECA"),
    ("SCOTIABANK", "SCOTIABANK"),
    ("BANORTE", "BANORTE"),
    ("HSBC", "HSBC"),
    ("INBURSA", "INBURSA"),
    ("BANBAJIO", "BANBAJIO"),
    ("BANCODELBAJIO", "BANBAJIO"),
    ("AFIRME", "AFIRME"),
    ("FONDEADORA", "FONDEADORA"),
    ("MONEX", "MONEX"),
    ("STP", "STP"),
    ("NUBANCO", "NU MEXICO"),
    ("NUMEXICO", "NU MEXICO"),
    ("MIFEL", "MIFEL"),
)


def _detail_layout(
    words: Sequence[SpatialWord],
    direction: str,
) -> SpeiDetailLayout:
    """Escala limites conservadores para PDFs carta digitales u OCR."""

    max_x = max((safe_float(word.get("x1")) for word in words), default=594.0)
    page_width = max(594.0, min(673.0, max_x + 18.0))
    scale = page_width / 612.0

    # La tabla de recibidos usa menos columnas opcionales (sin tarjeta ni
    # telefono), por lo que banco, contraparte y claves empiezan mas a la
    # izquierda que en la tabla de enviados.
    if direction == "received":
        return SpeiDetailLayout(
            bank_right=90.0 * scale,
            date_right=140.0 * scale,
            amount_right=195.0 * scale,
            account_right=275.0 * scale,
            beneficiary_right=350.0 * scale,
            tracking_right=410.0 * scale,
            reference_right=465.0 * scale,
        )

    return SpeiDetailLayout(
        bank_right=104.0 * scale,
        date_right=145.0 * scale,
        amount_right=212.0 * scale,
        account_right=325.0 * scale,
        beneficiary_right=410.0 * scale,
        tracking_right=460.0 * scale,
        reference_right=500.0 * scale,
    )


def _spei_section_kind(line: SpatialLine) -> Optional[str]:
    compact = compact_text(line.text)
    if compact in {"SPEIENVIADO", "SPEIENVIADOS"}:
        return "sent"
    if compact in {"SPEIRECIBIDO", "SPEIRECIBIDOS"}:
        return "received"
    return None


def _is_spei_detail_terminal(line: SpatialLine) -> bool:
    compact = compact_text(line.text)
    return any(marker in compact for marker in SPEI_DETAIL_TERMINAL_MARKERS)


def _detail_operation_date(
    line: SpatialLine,
    layout: SpeiDetailLayout,
) -> Optional[str]:
    value = _text_in_range(line, layout.bank_right, layout.date_right)
    dates = dates_from_text(value)
    return dates[0].strftime("%d/%m/%Y") if dates else None


def _block_text(
    block: Sequence[SpatialLine],
    left: float,
    right: float,
) -> str:
    values = [_text_in_range(line, left, right) for line in block]
    return " ".join(value for value in values if value).strip()


def _block_amount(
    block: Sequence[SpatialLine],
    layout: SpeiDetailLayout,
) -> Optional[float]:
    for line in block:
        amount = _money_in_range(line, layout.date_right, layout.amount_right)
        if amount is not None:
            return abs(amount)
    return None


def _canonical_bank(value: str) -> Optional[str]:
    normalized = normalize_upper(value).strip(" /,.-")
    compact = compact_text(normalized)
    if not compact:
        return None

    for alias, canonical in _BANK_ALIASES:
        if alias in compact:
            return canonical
    return normalized or None


def _clean_counterparty(value: str) -> Optional[str]:
    normalized = normalize_upper(value)
    if not normalized:
        return None

    # Mifel agrega esta leyenda al nombre, dentro de la misma celda.
    marker = re.search(
        r"/?\s*DATO\s+NO\s+VERIFICADO\s+POR\s+ESTA\s+INSTITUCION\b",
        normalized,
    )
    if marker:
        normalized = normalized[: marker.start()]
    normalized = normalized.strip(" /,.-")
    return normalize_text(normalized) or None


def _account_identifiers(value: str) -> Tuple[Optional[str], Optional[str]]:
    contiguous = re.findall(r"(?<!\d)\d{10,18}(?!\d)", value)
    if contiguous:
        identifier = max(contiguous, key=len)
        if len(identifier) == 18:
            return None, identifier
        return identifier, None

    digits = re.sub(r"\D", "", value)
    if len(digits) == 18:
        return None, digits
    if 10 <= len(digits) <= 17:
        return digits, None
    return None, None


def _counterparty_from_cells(
    account_text: str,
    beneficiary_text: str,
) -> Optional[str]:
    """Recupera el nombre cuando PDFium pega su inicio a la CLABE."""

    suffix = ""
    match = re.search(r"(?<!\d)\d{10,18}(?!\d)", account_text)
    if match:
        suffix = account_text[match.end() :]
    return _clean_counterparty(
        " ".join(value for value in (suffix, beneficiary_text) if value)
    )


def _compact_identifier(value: str, minimum: int = 1) -> Optional[str]:
    compact = re.sub(r"[^A-Z0-9]", "", normalize_upper(value))
    if len(compact) < minimum or not re.search(r"\d", compact):
        return None
    return compact


def _extract_time(value: str) -> Optional[str]:
    match = re.search(r"\b(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\b", value)
    return match.group(0) if match else None


def _detail_from_block(
    direction: str,
    block: Sequence[SpatialLine],
    layout: SpeiDetailLayout,
) -> Optional[SpeiDetail]:
    if not block:
        return None

    operation_date = _detail_operation_date(block[0], layout)
    if operation_date is None:
        return None

    bank_text = _block_text(block, 0.0, layout.bank_right)
    date_text = _block_text(block, layout.bank_right, layout.date_right)
    account_text = _block_text(
        block,
        layout.amount_right,
        layout.account_right,
    )
    beneficiary_text = _block_text(
        block,
        layout.account_right,
        layout.beneficiary_right,
    )
    tracking_text = _block_text(
        block,
        layout.beneficiary_right,
        layout.tracking_right,
    )
    reference_text = _block_text(
        block,
        layout.tracking_right,
        layout.reference_right,
    )
    concept = _block_text(block, layout.reference_right, float("inf"))
    account, clabe = _account_identifiers(account_text)

    return SpeiDetail(
        direction=direction,
        operation_date=operation_date,
        amount=_block_amount(block, layout),
        bank=_canonical_bank(bank_text),
        beneficiary=_counterparty_from_cells(account_text, beneficiary_text),
        account=account,
        clabe=clabe,
        tracking_key=_compact_identifier(tracking_text, minimum=8),
        reference=_compact_identifier(reference_text),
        concept=normalize_text(concept) or None,
        operation_time=_extract_time(date_text),
    )


def _extract_spei_details(
    lines: Sequence[SpatialLine],
    words: Sequence[SpatialWord],
) -> List[SpeiDetail]:
    """Lee las tablas `SPEI enviados/recibidos`, incluso entre paginas."""

    layouts = {
        direction: _detail_layout(words, direction)
        for direction in ("sent", "received")
    }
    result: List[SpeiDetail] = []
    direction: Optional[str] = None
    block: List[SpatialLine] = []

    def flush() -> None:
        nonlocal block
        if direction is not None and block:
            detail = _detail_from_block(direction, block, layouts[direction])
            if detail is not None:
                result.append(detail)
        block = []

    for line in lines:
        section_kind = _spei_section_kind(line)
        if section_kind is not None:
            flush()
            direction = section_kind
            continue

        if direction is None:
            continue

        if _is_spei_detail_terminal(line):
            flush()
            direction = None
            continue

        if _is_footer_or_page_header(line):
            continue

        layout = layouts[direction]
        if _detail_operation_date(line, layout) is not None:
            flush()
            block = [line]
        elif block and line.text:
            block.append(line)

    flush()
    return result


def _extract_tracking_key(value: str) -> Optional[str]:
    compact = re.sub(r"[^A-Z0-9]", "", normalize_upper(value))
    match = re.search(r"20\d{2}[A-Z0-9]{18,}", compact)
    return match.group(0) if match else None


_MATCH_NOISE = {
    "A",
    "AL",
    "DE",
    "DEL",
    "EL",
    "EN",
    "LA",
    "PAGO",
    "R",
    "RT",
    "RTG",
    "RTGS",
    "SPEI",
    "TRANSFERENCIA",
    "Y",
}


def _match_tokens(value: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[A-Z0-9]+", normalize_upper(value))
        if len(token) >= 2 and token not in _MATCH_NOISE
    ]


def _detail_similarity(movement: Movimiento, detail: SpeiDetail) -> int:
    movement_tokens = set(_match_tokens(movement.concepto or ""))
    detail_tokens = set(_match_tokens(detail.concept or ""))
    overlap = len(movement_tokens & detail_tokens)

    movement_compact = "".join(_match_tokens(movement.concepto or ""))
    detail_compact = "".join(_match_tokens(detail.concept or ""))
    substring_bonus = 0
    if movement_compact and detail_compact:
        if movement_compact in detail_compact or detail_compact in movement_compact:
            substring_bonus = 20
    return overlap * 10 + substring_bonus


def _movement_direction(movement: Movimiento) -> Optional[str]:
    if movement.cargo:
        return "sent"
    if movement.abono:
        return "received"
    return None


def _movement_amount(movement: Movimiento) -> float:
    return abs(movement.cargo or movement.abono or 0.0)


def _apply_spei_detail(movement: Movimiento, detail: SpeiDetail) -> None:
    movement.beneficiario = movement.beneficiario or detail.beneficiary
    movement.cuenta_beneficiario = (
        movement.cuenta_beneficiario or detail.account
    )
    movement.clabe_beneficiario = movement.clabe_beneficiario or detail.clabe

    # La tabla informativa es la fuente autoritativa. El concepto de la tabla
    # principal puede contener otra clave como texto o una version truncada.
    if detail.tracking_key:
        movement.clave_rastreo = detail.tracking_key

    movement.sucursal = movement.sucursal or detail.bank
    movement.hora_operacion = movement.hora_operacion or detail.operation_time
    movement.rfc = movement.rfc or _extract_rfc(
        " ".join(
            value
            for value in (detail.beneficiary, detail.concept)
            if value
        )
    )

    if detail.concept and compact_text(detail.concept) != compact_text(
        detail.reference
    ):
        movement.concepto_original = detail.concept

    # `referencia` ya contiene el folio SMF que el parser historicamente
    # entrega. Se conserva para no romper consumidores; la referencia SPEI
    # secundaria se guarda en `autorizacion`, campo antes vacio en Mifel.
    if detail.reference:
        if not movement.referencia:
            movement.referencia = detail.reference
        elif not movement.autorizacion:
            movement.autorizacion = detail.reference


def _enrich_spei_movements(
    movements: Sequence[Movimiento],
    details: Sequence[SpeiDetail],
) -> None:
    """Concilia por sentido, fecha e importe y consume cada detalle una vez."""

    used: set[int] = set()

    for movement in movements:
        if "SPEI" not in compact_text(movement.concepto):
            continue

        direction = _movement_direction(movement)
        if direction is None:
            continue

        amount = _movement_amount(movement)
        candidates = [
            index
            for index, detail in enumerate(details)
            if index not in used
            and detail.direction == direction
            and detail.operation_date == movement.fecha_operacion
            and detail.amount is not None
            and abs(detail.amount - amount) <= 0.02
        ]

        # Si OCR perdio exclusivamente el importe de la tabla informativa,
        # conciliamos solo cuando la fecha/sentido dejan un candidato claro.
        if not candidates:
            partial = [
                index
                for index, detail in enumerate(details)
                if index not in used
                and detail.direction == direction
                and detail.operation_date == movement.fecha_operacion
                and detail.amount is None
                and _detail_similarity(movement, detail) >= 10
            ]
            if len(partial) == 1:
                candidates = partial

        if not candidates:
            continue

        best = max(
            candidates,
            key=lambda index: (_detail_similarity(movement, details[index]), -index),
        )
        _apply_spei_detail(movement, details[best])
        used.add(best)


def _extract_rfc(concept: str) -> Optional[str]:
    match = re.search(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", normalize_upper(concept))
    return match.group(0) if match else None


def _to_model(item: ParsedMovement) -> Movimiento:
    operation_type: Optional[str] = None
    if item.withdrawal:
        operation_type = "CARGO"
    elif item.deposit:
        operation_type = "ABONO"

    return Movimiento(
        fecha_operacion=item.operation_date,
        fecha_liquidacion=None,
        concepto=item.concept,
        tipo_operacion=operation_type,
        cargo=round(item.withdrawal, 2),
        abono=round(item.deposit, 2),
        referencia=item.reference,
        autorizacion=None,
        beneficiario=None,
        cuenta_beneficiario=None,
        clabe_beneficiario=None,
        clave_rastreo=_extract_tracking_key(item.concept),
        rfc=_extract_rfc(item.concept),
        sucursal=None,
        caja=None,
        hora_operacion=_extract_time(item.concept),
        saldo_operacion=round(item.balance or 0.0, 2),
        saldo_liquidacion=0.0,
        concepto_original=item.concept,
    )


def extract_movimientos_words(words: List[SpatialWord]) -> List[Movimiento]:
    """Extrae y concilia movimientos Mifel desde PDF digital u OCR."""

    if not words:
        return []

    lines = group_words_into_lines(words)
    section = _section_lines(lines)
    if not section:
        return []

    layout = _header_layout(lines)
    parsed = _parse_blocks(section, layout)
    _reconcile_amounts(parsed, _initial_balance(lines))
    movements = [_to_model(item) for item in parsed]
    _enrich_spei_movements(
        movements,
        _extract_spei_details(lines, words),
    )
    return movements


__all__ = [
    "SpatialLine",
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
