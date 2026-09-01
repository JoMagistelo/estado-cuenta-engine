from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from models.movimiento import Movimiento

from .datos import (
    SpatialWord,
    _canonical_month,
    _compact,
    _group_lines,
    _line_text,
    _norm,
    _page,
    _x0,
    _x1,
)


# ============================================================
# MOVIMIENTOS BANORTE OCR
# ============================================================
#
# Diferencias frente al parser espacial digital:
#
# - No presupone que los movimientos empiezan en page == 2.
# - Detecta las páginas de movimientos por evidencia real.
# - Tolera meses OCR como N0V, DK, DiC, etc.
# - Las columnas monetarias se resuelven dinámicamente desde el
#   encabezado cuando es legible y usan límites seguros cuando no.
# - La descripción se reconstruye por bloque hasta la siguiente
#   fecha, sin depender de una coordenada Y exacta.
# - Nunca reescribe el texto original almacenado en `concepto`.
#   Las reparaciones OCR se hacen únicamente sobre una copia de
#   búsqueda para extraer referencia/SPEI/RFC/hora/etc.
#
# ============================================================


_DATE_RE = re.compile(
    r"^\s*(?P<day>[0O]?\d|[12]\d|3[01])\s*-\s*"
    r"(?P<month>[A-ZÁÉÍÓÚÜÑ0-9?\]\[!|]{2,5})\s*-\s*"
    r"(?P<year>\d{2}|20\d{2})(?!\d)",
    re.IGNORECASE,
)

_MONEY_RE = re.compile(
    r"^[+-]?\(?\$?\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{1,2})?\)?$"
)

_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\s*\d{6}\s*[A-Z0-9]{3}\b", re.IGNORECASE)
_CLABE_RE = re.compile(r"(?<!\d)(\d(?:[\s-]*\d){15,17})(?!\d)")

_MONTH_ABBR = {
    "ENERO": "ENE",
    "FEBRERO": "FEB",
    "MARZO": "MAR",
    "ABRIL": "ABR",
    "MAYO": "MAY",
    "JUNIO": "JUN",
    "JULIO": "JUL",
    "AGOSTO": "AGO",
    "SEPTIEMBRE": "SEP",
    "OCTUBRE": "OCT",
    "NOVIEMBRE": "NOV",
    "DICIEMBRE": "DIC",
}


# Límite horizontal conservador del bloque descriptivo observado en
# el layout Banorte. Los importes comienzan mucho más a la derecha.
DESCRIPTION_X_MAX = 335.0
DEFAULT_DEPOSIT_END = 414.0
DEFAULT_WITHDRAW_END = 492.0
DEFAULT_BALANCE_START = 492.0


# Marcadores que indican que la tabla principal ya terminó.
_STOP_MARKERS = (
    "FOLIO FECHA TIPO DE CARGO",
    "FOLIO FECHA TIPE DE CARGO",
    "GRAFICO TRANSACCIONAL",
    "GRÁFICO TRANSACCIONAL",
    "INFORME DE DEPOSITOS",
    "INFORME DE DEPÓSITOS",
    "IMPUESTO A LOS DEPOSITOS",
    "IMPUESTO A LOS DEPÓSITOS",
)


def _cy(word: SpatialWord) -> float:
    try:
        top = float(word.get("top", 0.0) or 0.0)
        bottom = float(word.get("bottom", top) or top)
    except (TypeError, ValueError):
        return 0.0
    return (top + bottom) / 2.0


def _line_y(line: list[SpatialWord]) -> float:
    if not line:
        return 0.0
    return sum(_cy(word) for word in line) / len(line)


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _parse_date_token(value: str) -> str | None:
    """Devuelve la fecha Banorte en DD-MMM-YY/YYYY, reparando solo el mes OCR."""
    match = _DATE_RE.match(str(value or ""))
    if not match:
        return None

    try:
        day = int(match.group("day").upper().replace("O", "0"))
    except ValueError:
        return None

    raw_month = _norm(match.group("month"))
    raw_month = (
        raw_month
        .replace("0", "O")
        .replace("1", "I")
        .replace("?", "")
        .replace("]", "")
        .replace("[", "")
        .replace("!", "I")
        .replace("|", "I")
    )

    # Casos breves observados por Tesseract: DK -> DIC.
    compact_month = _compact(raw_month)
    aliases = {
        "ENE": "ENERO",
        "FEB": "FEBRERO",
        "MAR": "MARZO",
        "ABR": "ABRIL",
        "MAY": "MAYO",
        "JUN": "JUNIO",
        "JUL": "JULIO",
        "AGO": "AGOSTO",
        "SEP": "SEPTIEMBRE",
        "OCT": "OCTUBRE",
        "NOV": "NOVIEMBRE",
        "DIC": "DICIEMBRE",
        "DK": "DICIEMBRE",
        "DIK": "DICIEMBRE",
    }

    month = aliases.get(compact_month)
    if month is None:
        month = _canonical_month(compact_month, day=day)
    if month is None:
        return None

    year = match.group("year")
    return f"{day:02d}-{_MONTH_ABBR[month]}-{year}"


def _date_from_line(line: list[SpatialWord]) -> str | None:
    """Busca una fecha sólo en la zona izquierda esperada de la tabla."""
    for word in sorted(line, key=_x0):
        if _x0(word) > 100.0:
            break
        date = _parse_date_token(str(word.get("text", "")))
        if date:
            return date
    return None


def _normalize_amount_token(value: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    candidate = raw.replace("$", "").replace(" ", "")
    candidate = candidate.strip("[]|:")

    negative = False
    if candidate.startswith("(") and candidate.endswith(")"):
        negative = True
        candidate = candidate[1:-1]
    if candidate.startswith("-"):
        negative = True
        candidate = candidate[1:]
    candidate = candidate.lstrip("+")

    if not _MONEY_RE.fullmatch(("-" if negative else "") + candidate):
        return None

    # Tesseract puede producir 6,000,00. La última coma se toma como decimal
    # sólo cuando no existe punto y deja 1-2 dígitos a la derecha.
    if "." not in candidate and candidate.count(",") >= 2:
        left, right = candidate.rsplit(",", 1)
        if len(right) in {1, 2}:
            candidate = left.replace(",", "") + "." + right
        else:
            candidate = candidate.replace(",", "")
    elif "," in candidate and "." in candidate:
        candidate = candidate.replace(",", "")
    elif candidate.count(",") == 1 and "." not in candidate:
        left, right = candidate.split(",", 1)
        if len(right) == 3:
            candidate = left + right
        elif len(right) in {1, 2}:
            candidate = left + "." + right
        else:
            candidate = left + right

    try:
        amount = float(candidate)
    except ValueError:
        return None
    return -amount if negative else amount


def _money_words(line: list[SpatialWord], *, min_x: float = 330.0) -> list[tuple[float, float, SpatialWord]]:
    result: list[tuple[float, float, SpatialWord]] = []
    for word in sorted(line, key=_x0):
        if _x0(word) < min_x:
            continue
        amount = _normalize_amount_token(str(word.get("text", "")))
        if amount is None:
            continue
        result.append((_x0(word), amount, word))
    return result


def _is_header(line: list[SpatialWord]) -> bool:
    text = _norm(_line_text(line))
    compact = _compact(text)
    if "FECHA" in text and "SALDO" in text and ("MONTO" in text or "DEPOSITO" in text):
        return True
    # El encabezado de Dic-23 está muy dañado, pero conserva los nombres de columnas.
    return (
        "DEPOSITO" in compact
        and "RETIRO" in compact
        and "SALDO" in compact
        and _line_y(line) < 180.0
    )


def _is_stop_line(line: list[SpatialWord]) -> bool:
    text = _norm(_line_text(line))
    compact = _compact(text)
    for marker in _STOP_MARKERS:
        if _compact(marker) in compact:
            return True
    return False


def _strong_movement_line(line: list[SpatialWord]) -> bool:
    """Evidencia fuerte: fecha en margen izquierdo + importe en columnas derechas."""
    return _date_from_line(line) is not None and bool(_money_words(line))


def _movement_pages(lines: list[list[SpatialWord]]) -> set[int]:
    """
    Detecta páginas de la tabla sin depender del número físico de página.

    Una página entra si tiene encabezado reconocible o al menos dos filas fuertes.
    Una sola fila fuerte también se acepta cuando es adyacente a otra página ya
    clasificada, para soportar continuación de una tabla al salto de página.
    """
    strong_by_page: dict[int, int] = {}
    header_pages: set[int] = set()

    for line in lines:
        if not line:
            continue
        page = _page(line[0])
        if _is_header(line):
            header_pages.add(page)
        if _strong_movement_line(line):
            strong_by_page[page] = strong_by_page.get(page, 0) + 1

    pages = set(header_pages)
    pages.update(page for page, count in strong_by_page.items() if count >= 2)

    for page, count in strong_by_page.items():
        if count == 1 and (page - 1 in pages or page + 1 in pages):
            pages.add(page)

    return pages


def _column_limits(lines: list[list[SpatialWord]], pages: set[int]) -> tuple[float, float, float]:
    """
    Devuelve (fin_deposito, fin_retiro, inicio_saldo).

    Se intenta inferir desde el encabezado. Si OCR no lo permite, se usan límites
    seguros que corresponden al layout Banorte en puntos PDF.
    """
    for line in lines:
        if not line or _page(line[0]) not in pages or not _is_header(line):
            continue

        deposit_word = None
        withdrawal_word = None
        balance_word = None
        for word in line:
            token = _compact(word.get("text", ""))
            if "DEPOSITO" in token:
                deposit_word = word
            elif "RETIRO" in token:
                withdrawal_word = word
            elif token == "SALDO":
                balance_word = word

        if deposit_word and withdrawal_word and balance_word:
            deposit_end = (_x1(deposit_word) + _x0(withdrawal_word)) / 2.0
            withdrawal_end = (_x1(withdrawal_word) + _x0(balance_word)) / 2.0
            balance_start = withdrawal_end
            return deposit_end, withdrawal_end, balance_start

    return DEFAULT_DEPOSIT_END, DEFAULT_WITHDRAW_END, DEFAULT_BALANCE_START


def _description_from_line(line: list[SpatialWord], *, first: bool) -> str:
    values: list[str] = []
    date_removed = False

    for word in sorted(line, key=_x0):
        if _x0(word) >= DESCRIPTION_X_MAX:
            continue

        text = str(word.get("text", "")).strip()
        if not text:
            continue

        if first and not date_removed:
            match = _DATE_RE.match(text)
            if match:
                text = text[match.end():].strip()
                date_removed = True
                if not text:
                    continue

        values.append(text)

    return " ".join(values).strip()


def _block_concept(block: list[list[SpatialWord]]) -> str:
    parts: list[str] = []
    for index, line in enumerate(block):
        if _is_header(line) or _is_stop_line(line):
            continue
        text = _description_from_line(line, first=(index == 0))
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _build_blocks(lines: list[list[SpatialWord]], pages: set[int]) -> list[list[list[SpatialWord]]]:
    blocks: list[list[list[SpatialWord]]] = []
    current: list[list[SpatialWord]] = []
    last_line_y: float | None = None
    current_page: int | None = None

    for line in lines:
        if not line:
            continue
        page = _page(line[0])
        if page not in pages:
            continue

        if _is_header(line):
            continue

        if _is_stop_line(line):
            if current:
                blocks.append(current)
                current = []
            # A stop marker belongs to a section after the movement table on
            # this page. We still allow a later movement page independently.
            last_line_y = None
            current_page = page
            continue

        date = _date_from_line(line)
        if date:
            if current:
                blocks.append(current)
            current = [line]
            last_line_y = _line_y(line)
            current_page = page
            continue

        if not current:
            continue

        # On a page change, header/noise before the first next movement must not
        # be appended to the previous operation.
        if current_page is not None and page != current_page:
            continue

        line_y = _line_y(line)
        if last_line_y is not None and line_y - last_line_y > 55.0:
            blocks.append(current)
            current = []
            last_line_y = None
            continue

        current.append(line)
        last_line_y = line_y

    if current:
        blocks.append(current)

    return blocks


def _block_amounts(
    block: list[list[SpatialWord]],
    deposit_end: float,
    withdrawal_end: float,
    balance_start: float,
) -> tuple[float, float, float]:
    """Extrae depósito, retiro y saldo conservando la lectura OCR disponible."""
    candidates: list[tuple[float, float]] = []
    for line in block:
        for x, amount, _ in _money_words(line):
            candidates.append((x, amount))

    if not candidates:
        return 0.0, 0.0, 0.0

    # Valores monetarios de la tabla están ordenados por columna. Usamos la
    # posición X, no el orden textual, para no confundir importes del concepto.
    deposit_values = [amount for x, amount in candidates if x < deposit_end]
    withdrawal_values = [
        amount for x, amount in candidates
        if deposit_end <= x < withdrawal_end
    ]
    balance_values = [amount for x, amount in candidates if x >= balance_start]

    deposit = deposit_values[-1] if deposit_values else 0.0
    withdrawal = withdrawal_values[-1] if withdrawal_values else 0.0
    balance = balance_values[-1] if balance_values else 0.0

    return deposit, withdrawal, balance


def _semantic_text(concept: str) -> str:
    """Copia reparada sólo para regex; no modifica `concepto`/`concepto_original`."""
    text = _norm(concept.replace("\n", " "))

    # Tesseract confunde I/L/]/!/t dentro de SPEI de manera repetitiva.
    text = re.sub(r"\bSPE[IL1T\]!]?\b", "SPEI", text)
    text = re.sub(r"\bSPEL\b", "SPEI", text)
    text = re.sub(r"\bSPE\]\b", "SPEI", text)
    text = re.sub(r"\bSPE!\b", "SPEI", text)
    text = re.sub(r"\bSPE\?PEI\b", "SPEI", text)
    text = text.replace("S?PEI", "SPEI")

    # LIQ aparece como L1Q / 11Q / £10 / EIO en las muestras.
    text = text.replace("£10", "LIQ")
    text = re.sub(r"\b(?:L1Q|11Q|LI0|LIO|EIO|ELO)\b", "LIQ", text)
    text = re.sub(r"\bHORA\s+L1Q\b", "HORA LIQ", text)
    return text


def _digits_joined(value: str) -> str:
    return re.sub(r"\D", "", value)


def _extract_reference(search: str) -> str | None:
    patterns = (
        r"\bREFERENCIA\s*[:=]?\s*([A-Z0-9_-]+)",
        r"\bORDEN\s+DE\s+PAGO\s+SPEI\s*([A-Z0-9]+)\s*=*\s*REFERENCIA\b",
    )
    for pattern in patterns:
        match = re.search(pattern, search, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ,;:-")
            if value:
                return value
    return None


def _extract_tracking(search: str) -> str | None:
    match = re.search(
        r"\bCVE\s+RAST(?:REO)?\s*[:=]?\s*([A-Z0-9][A-Z0-9 _-]{4,})",
        search,
        re.IGNORECASE,
    )
    if match:
        raw = match.group(1)
        raw = re.split(r"\b(?:RFC|REC|IVA|HORA|HR|BANCO|BCO)\b", raw, maxsplit=1, flags=re.IGNORECASE)[0]
        value = re.sub(r"\s+", "", raw).strip(" ,;:-").upper()
        return value or None

    match = re.search(r"^\s*(.+?)\s+SPEI\s+RECIBIDO\b", search, re.IGNORECASE)
    if match:
        value = re.sub(r"\s+", "", match.group(1)).strip(" ,;:-").upper()
        return value or None
    return None


def _extract_clabe(search: str) -> str | None:
    # First prefer an explicitly labelled account/CLABE.
    for pattern in (
        r"\bCTA\s*/\s*CLABE\s*:\s*([\d\s]{16,25})",
        r"\bDE\s+LA\s+CLABE\s+([\d\s]{18,26})",
        r"\bDELA\s+CLABE\s+([\d\s]{18,26})",
        r"\bCLABE\s+([\d\s]{18,26})",
    ):
        match = re.search(pattern, search, re.IGNORECASE)
        if not match:
            continue
        digits = _digits_joined(match.group(1))
        if len(digits) >= 18:
            return digits[:18]
    return None


def _extract_beneficiary(search: str) -> str | None:
    # Outgoing SPEI.
    match = re.search(
        r"\bBENEF\s*:\s*(.*?)\s*\(?\s*DATO\s+(?:NO|TO|t0)\s+VERIF",
        search,
        re.IGNORECASE,
    )
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:-")
        return value or None

    # Incoming SPEI: DEL CLIENTE <name> DE/DE LA CLABE.  Avoid Treasury labels
    # when OCR shows "DEL CLIENTE TESORERIA ... DE LA CLABE"? That text is the
    # sender and therefore remains a valid beneficiary/counterparty value.
    match = re.search(
        r"\bDEL\s+CLIENTE\s+(.*?)\s+(?:DE\s+LA|DELA)\s+CLABE\b",
        search,
        re.IGNORECASE,
    )
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:-")
        return value or None

    return None


def _extract_rfc(search: str) -> str | None:
    match = re.search(r"\b(?:CON\s+RFC|RFC|AL\s+RFC)\s*[:=]?\s*([A-ZÑ&0-9 ]{10,18})", search, re.IGNORECASE)
    if not match:
        return None
    candidate = re.sub(r"\s+", "", match.group(1)).upper()
    candidate = re.split(r"(?:CONCEPTO|IVA|HORA|HR)", candidate, maxsplit=1)[0]
    if candidate in {"ND", "NOCAPTURADO", "HOCAPTURADO"}:
        return None
    strict = _RFC_RE.search(candidate)
    if strict:
        return re.sub(r"\s+", "", strict.group(0)).upper()
    return None


def _extract_time(search: str) -> str | None:
    match = re.search(
        r"\b(?:HR|HORA)\s+LIQ\s*:\s*"
        r"((?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?|\d{6})\b",
        search,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1)
    if ":" in value:
        return value
    h, m, s = int(value[:2]), int(value[2:4]), int(value[4:6])
    if h <= 23 and m <= 59 and s <= 59:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return None


def _extract_original_concept(search: str) -> str | None:
    # Incoming SPEI.
    match = re.search(
        r"\bCONCEPTO\s*[:;]\s*(.*?)\s+REFERENCIA\s*[:=]",
        search,
        re.IGNORECASE,
    )
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:-")
        return value or None

    # Outgoing SPEI: text after the verifier parenthesis and before tracking.
    match = re.search(
        r"\)\s*,?\s*(.*?)\s+CVE\s+RAST(?:REO)?\s*:",
        search,
        re.IGNORECASE,
    )
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:-")
        return value or None
    return None


def _operation_type(deposit: float, withdrawal: float) -> str | None:
    if withdrawal != 0.0:
        return "CARGO"
    if deposit != 0.0:
        return "ABONO"
    return None


def _build_movement(
    block: list[list[SpatialWord]],
    deposit_end: float,
    withdrawal_end: float,
    balance_start: float,
) -> Movimiento | None:
    if not block:
        return None

    date = _date_from_line(block[0])
    if not date:
        return None

    concept = _block_concept(block)
    search = _semantic_text(concept)

    if "SALDO ANTERIOR" in search:
        return None

    deposit, withdrawal, balance = _block_amounts(
        block,
        deposit_end=deposit_end,
        withdrawal_end=withdrawal_end,
        balance_start=balance_start,
    )

    if not concept and deposit == 0.0 and withdrawal == 0.0 and balance == 0.0:
        return None

    reference = _extract_reference(search)
    tracking = _extract_tracking(search)
    beneficiary = _extract_beneficiary(search)
    clabe = _extract_clabe(search)
    rfc = _extract_rfc(search)
    time = _extract_time(search)
    original = _extract_original_concept(search)

    return Movimiento(
        fecha_operacion=date,
        fecha_liquidacion=None,
        concepto=concept,
        tipo_operacion=_operation_type(deposit, withdrawal),
        cargo=withdrawal,
        abono=deposit,
        referencia=reference,
        autorizacion=None,
        beneficiario=beneficiary,
        cuenta_beneficiario=None,
        clabe_beneficiario=clabe,
        clave_rastreo=tracking,
        rfc=rfc,
        sucursal=None,
        caja=None,
        hora_operacion=time,
        saldo_operacion=balance,
        saldo_liquidacion=0.0,
        concepto_original=original,
    )


def extract_movimientos_words(words: list[SpatialWord]) -> list[Movimiento]:
    """
    Extrae movimientos Banorte a partir de words de Tesseract.

    El método es deliberadamente semántico-espacial: usa texto para localizar la
    tabla y fechas, y coordenadas X solamente para separar depósito/retiro/saldo.
    Por eso tolera desplazamientos verticales y páginas preliminares.
    """
    if not words:
        return []

    lines = _group_lines(words)
    if not lines:
        return []

    pages = _movement_pages(lines)
    if not pages:
        return []

    deposit_end, withdrawal_end, balance_start = _column_limits(lines, pages)
    blocks = _build_blocks(lines, pages)

    movements: list[Movimiento] = []
    previous_balance: float | None = None

    for block in blocks:
        # La fila SALDO ANTERIOR no es un movimiento, pero su saldo sirve para
        # recuperar un importe que Tesseract haya perdido por completo.
        concept = _semantic_text(_block_concept(block))
        _, _, block_balance = _block_amounts(
            block,
            deposit_end=deposit_end,
            withdrawal_end=withdrawal_end,
            balance_start=balance_start,
        )
        if "SALDO ANTERIOR" in concept:
            if block_balance != 0.0 or _money_words(block[0]):
                previous_balance = block_balance
            continue

        movement = _build_movement(
            block,
            deposit_end=deposit_end,
            withdrawal_end=withdrawal_end,
            balance_start=balance_start,
        )
        if movement is None:
            continue

        # Fallback matemático estrictamente acotado: sólo cuando OCR no produjo
        # ningún importe de depósito/retiro, sí produjo saldo y conocemos el saldo
        # inmediatamente anterior. No corrige importes ya leídos por Tesseract.
        if (
            movement.abono == 0.0
            and movement.cargo == 0.0
            and movement.saldo_operacion != 0.0
            and previous_balance is not None
        ):
            delta = round(movement.saldo_operacion - previous_balance, 2)
            if delta > 0.0:
                movement.abono = delta
                movement.tipo_operacion = "ABONO"
            elif delta < 0.0:
                movement.cargo = abs(delta)
                movement.tipo_operacion = "CARGO"

        movements.append(movement)
        previous_balance = movement.saldo_operacion

    return movements
