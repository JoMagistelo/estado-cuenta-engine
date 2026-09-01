from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from models.datos_cuenta import DatosCuenta


SpatialWord = dict[str, Any]

_MONTHS = (
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE",
    "DICIEMBRE",
)

_DATE_RE = re.compile(
    r"(?<!\d)([0O]?\d|[12]\d|3[01])\s*/\s*"
    r"([A-ZÁÉÍÓÚÜÑa-záéíóúüñ0-9]{3,12})\s*/\s*(20\d{2})(?!\d)"
)
_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _page(word: SpatialWord) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _x0(word: SpatialWord) -> float:
    return _f(word.get("x0", 0.0))


def _x1(word: SpatialWord) -> float:
    return _f(word.get("x1", word.get("x0", 0.0)))


def _top(word: SpatialWord) -> float:
    return _f(word.get("top", 0.0))


def _bottom(word: SpatialWord) -> float:
    return _f(word.get("bottom", word.get("top", 0.0)))


def _cy(word: SpatialWord) -> float:
    return (_top(word) + _bottom(word)) / 2.0


def _strip_accents(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _norm(value: Any) -> str:
    text = _strip_accents(str(value or "")).upper()
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norm(value))


def _line_text(line: list[SpatialWord]) -> str:
    return " ".join(
        str(w.get("text", "")).strip()
        for w in sorted(line, key=_x0)
        if str(w.get("text", "")).strip()
    ).strip()


def _group_lines(words: list[SpatialWord]) -> list[list[SpatialWord]]:
    if not words:
        return []

    heights = sorted(
        max(0.0, _bottom(w) - _top(w))
        for w in words
        if _bottom(w) > _top(w)
    )
    typical = heights[len(heights) // 2] if heights else 6.0
    tolerance = max(3.6, min(6.5, typical * 0.62))

    ordered = sorted(words, key=lambda w: (_page(w), _cy(w), _x0(w)))
    result: list[list[SpatialWord]] = []
    current: list[SpatialWord] = []
    current_page: int | None = None
    current_y: float | None = None

    for word in ordered:
        page = _page(word)
        y = _cy(word)

        if current_y is None:
            current = [word]
            current_page = page
            current_y = y
            continue

        if page == current_page and abs(y - current_y) <= tolerance:
            current.append(word)
            current_y = sum(_cy(item) for item in current) / len(current)
        else:
            current.sort(key=_x0)
            result.append(current)
            current = [word]
            current_page = page
            current_y = y

    if current:
        current.sort(key=_x0)
        result.append(current)

    return result


def _line_score_for_data(line: list[SpatialWord]) -> int:
    text = _norm(_line_text(line))
    compact = _compact(text)
    score = 0

    if "PRODUCTO" in text and "CUENTA" in text and "CLABE" in text:
        score += 80
    if "PERIODO" in text:
        score += 35
    if "FECHA" in text and "CORTE" in text:
        score += 30
    if "CLIENTE" in text:
        score += 20
    if "DATOS" in text and "SUCURSAL" in text:
        score += 15
    if "SALDOINICIAL" in compact or _similar(compact, "SALDOINICIALDELPERIODO") >= 0.80:
        score += 25
    return score


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _find_data_page(lines: list[list[SpatialWord]]) -> int | None:
    scores: dict[int, int] = {}
    for line in lines:
        if not line:
            continue
        page = _page(line[0])
        scores[page] = scores.get(page, 0) + _line_score_for_data(line)

    if not scores:
        return None

    page, score = max(scores.items(), key=lambda item: (item[1], -item[0]))
    return page if score > 0 else None


def _canonical_month(raw: str, day: int | None = None) -> str | None:
    cleaned = _norm(raw).replace("0", "O").replace("1", "I")
    if not cleaned:
        return None

    # Common three-letter OCR forms.
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
    }
    if cleaned in aliases:
        return aliases[cleaned]

    if cleaned.startswith("D") and len(cleaned) <= 3:
        return "DICIEMBRE"

    ranked = sorted(
        _MONTHS,
        key=lambda month: _similar(cleaned, month),
        reverse=True,
    )
    month_days = {
        "ENERO": 31, "FEBRERO": 29, "MARZO": 31, "ABRIL": 30,
        "MAYO": 31, "JUNIO": 30, "JULIO": 31, "AGOSTO": 31,
        "SEPTIEMBRE": 30, "OCTUBRE": 31, "NOVIEMBRE": 30,
        "DICIEMBRE": 31,
    }
    for candidate in ranked:
        if _similar(cleaned, candidate) < 0.58:
            break
        if day is not None and day > month_days[candidate]:
            continue
        return candidate
    return None


def _extract_dates(value: str) -> list[str]:
    dates: list[str] = []

    # OCR often glues "Del01/..." to the previous token; search, don't fullmatch.
    for match in _DATE_RE.finditer(value):
        day_raw, month_raw, year = match.groups()
        day_digits = day_raw.upper().replace("O", "0")
        try:
            day = int(day_digits)
        except ValueError:
            continue
        if not 1 <= day <= 31:
            continue

        month = _canonical_month(month_raw, day)
        if month is None:
            continue

        month_title = month[0] + month[1:].lower()
        dates.append(f"{day:02d}/{month_title}/{year}")

    return dates


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _find_account_row(page_lines: list[list[SpatialWord]]) -> list[SpatialWord] | None:
    candidates: list[tuple[int, list[SpatialWord]]] = []
    for line in page_lines:
        text = _norm(_line_text(line))
        digits = [_digits(w.get("text")) for w in line]
        has_account = any(len(d) == 10 for d in digits)
        has_product = "SUMANOMINA" in text or ("NOMINA" in text and has_account)
        if has_product and has_account:
            candidates.append((3, line))
        elif has_account and any(len(d) >= 12 for d in digits):
            candidates.append((1, line))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _extract_table_values(account_row: list[SpatialWord] | None) -> tuple[
    str | None, str | None, str | None
]:
    if not account_row:
        return None, None, None

    ordered = sorted(account_row, key=_x0)

    numeric = [(w, _digits(w.get("text"))) for w in ordered]
    account_candidates = [
        (w, d)
        for w, d in numeric
        if len(d) == 10 and 120.0 <= _x0(w) <= 280.0
    ]
    account_word = account_candidates[0][0] if account_candidates else None
    account = account_candidates[0][1] if account_candidates else None

    # El producto es el texto situado antes del número de cuenta. No se fija a
    # SUMANOMINA para que el extractor pueda crecer a otros productos Banorte
    # que compartan el mismo layout.
    product = None
    if account_word is not None:
        product_parts: list[str] = []
        for word in ordered:
            if _x0(word) >= _x0(account_word):
                break
            raw = str(word.get("text", "")).strip()
            raw = re.sub(r"^[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", "", raw)
            raw = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9/ -]+$", "", raw)
            if raw and any(char.isalpha() for char in raw):
                product_parts.append(raw)
        if product_parts:
            product = re.sub(r"\s+", " ", " ".join(product_parts)).strip() or None

    # CLABE may be split into 2-4 OCR tokens. It is to the right of account
    # and to the left of the monetary columns.
    clabe_parts: list[str] = []
    for w, d in numeric:
        if not d:
            continue
        if 265.0 <= _x0(w) < 390.0:
            clabe_parts.append(d)

    clabe_digits = "".join(clabe_parts)
    clabe = clabe_digits if len(clabe_digits) == 18 else None

    return product, account, clabe


def _find_name(page_lines: list[list[SpatialWord]], account_row: list[SpatialWord] | None) -> str | None:
    account_y = min((_cy(w) for w in account_row), default=9999.0) if account_row else 9999.0
    blacklist = (
        "CALLE", "BENITO", "NARVARTE", "PERIODO", "ESTADO", "BANORTE",
        "DATOS", "PLAZA", "SUCURSAL", "MONEDA", "CLIENTE", "RFC",
    )
    candidates: list[tuple[float, str]] = []

    for line in page_lines:
        y = sum(_cy(w) for w in line) / len(line)
        if y >= account_y:
            continue
        if min(_x0(w) for w in line) > 120.0:
            continue

        text = re.sub(r"\s+", " ", _line_text(line)).strip()
        normalized = _norm(text)
        if any(word in normalized for word in blacklist):
            continue

        tokens = re.findall(r"[A-ZÁÉÍÓÚÜÑ]{2,}", text.upper())
        if not 3 <= len(tokens) <= 7:
            continue
        if any(ch.isdigit() for ch in text):
            continue

        # Names in this layout sit in the upper-left block.
        if 70.0 <= y <= 180.0:
            candidates.append((y, text))

    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _find_customer_number(page_lines: list[list[SpatialWord]]) -> str | None:
    for line in page_lines:
        text = _norm(_line_text(line))
        if "CLIENTE" not in text:
            continue
        for word in sorted(line, key=_x0, reverse=True):
            d = _digits(word.get("text"))
            if 6 <= len(d) <= 12:
                return d

    # OCR can lose "NO."/"NÚMERO" but keeps CLIENTE and the number near x~100.
    for line in page_lines:
        if not (50.0 <= min(_x0(w) for w in line) <= 90.0):
            continue
        for word in line:
            d = _digits(word.get("text"))
            if 7 <= len(d) <= 10 and 85.0 <= _x0(word) <= 150.0:
                return d
    return None


def _find_rfc(page_lines: list[list[SpatialWord]], customer_number: str | None) -> str | None:
    # Search the small band below/around the customer number. Never "repair"
    # missing characters: only return a value supported by OCR.
    candidate_tokens: list[tuple[float, str]] = []
    customer_y: float | None = None

    for line in page_lines:
        if customer_number and customer_number in _digits(_line_text(line)):
            customer_y = sum(_cy(w) for w in line) / len(line)
            break

    for line in page_lines:
        y = sum(_cy(w) for w in line) / len(line)
        if customer_y is not None and not (customer_y - 4.0 <= y <= customer_y + 24.0):
            continue
        if min(_x0(w) for w in line) > 150.0:
            continue

        # Combine neighboring OCR fragments on the RFC row, e.g. OOMM85 + 1003P53.
        fragments = []
        for word in sorted(line, key=_x0):
            if _x0(word) > 150.0:
                continue
            raw = re.sub(r"[^A-Za-zÑñ&0-9]", "", str(word.get("text", ""))).upper()
            if raw in {"RFC", "REC", "RFEC", "RR", "HE", "DE", "CLIENTE"}:
                continue
            if raw:
                fragments.append(raw)

        if fragments:
            combined = "".join(fragments)
            # Strip a customer number if Tesseract put both logical rows together.
            if customer_number:
                combined = combined.replace(customer_number, "")
            candidate_tokens.append((y, combined))

        for word in line:
            raw = re.sub(r"[^A-Za-zÑñ&0-9]", "", str(word.get("text", ""))).upper()
            if _RFC_RE.fullmatch(raw):
                return raw

    for _, raw in sorted(candidate_tokens):
        if _RFC_RE.fullmatch(raw):
            return raw

    # Last pass over individual text anywhere on the data page.
    for line in page_lines:
        for word in line:
            raw = re.sub(r"[^A-Za-zÑñ&0-9]", "", str(word.get("text", ""))).upper()
            if _RFC_RE.fullmatch(raw):
                return raw
    return None


def _find_period(page_lines: list[list[SpatialWord]]) -> tuple[str | None, str | None]:
    candidates: list[str] = []
    for line in page_lines:
        text = _line_text(line)
        normalized = _norm(text)
        if "PERIODO" not in normalized and "/" not in text:
            continue
        candidates.extend(_extract_dates(text))
        if len(candidates) >= 2:
            break

    if len(candidates) >= 2:
        return candidates[0], candidates[1]

    # Search across the page because OCR may split "Periodo" from its dates.
    page_text = " ".join(_line_text(line) for line in page_lines)
    dates = _extract_dates(page_text)
    return (
        dates[0] if dates else None,
        dates[1] if len(dates) > 1 else None,
    )


def _find_cut_date(page_lines: list[list[SpatialWord]]) -> str | None:
    for line in page_lines:
        text = _line_text(line)
        normalized = _norm(text)
        if "CORTE" not in normalized:
            continue
        dates = _extract_dates(text)
        if dates:
            return dates[-1]
    return None


def extract_datos_cuenta_words(words: list[SpatialWord]) -> DatosCuenta:
    if not words:
        return DatosCuenta(
            producto_principal=None,
            periodo_inicio=None,
            periodo_fin=None,
            fecha_corte=None,
            numero_cuenta=None,
            numero_cliente=None,
            clabe=None,
            nombre_cliente=None,
            rfc=None,
        )

    lines = _group_lines(words)
    data_page = _find_data_page(lines)
    if data_page is None:
        data_page = min((_page(w) for w in words), default=1)

    page_lines = [line for line in lines if line and _page(line[0]) == data_page]
    account_row = _find_account_row(page_lines)
    producto, numero_cuenta, clabe = _extract_table_values(account_row)

    periodo_inicio, periodo_fin = _find_period(page_lines)
    fecha_corte = _find_cut_date(page_lines)
    numero_cliente = _find_customer_number(page_lines)
    nombre_cliente = _find_name(page_lines, account_row)
    rfc = _find_rfc(page_lines, numero_cliente)

    return DatosCuenta(
        producto_principal=producto,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        fecha_corte=fecha_corte,
        numero_cuenta=numero_cuenta,
        numero_cliente=numero_cliente,
        clabe=clabe,
        nombre_cliente=nombre_cliente,
        rfc=rfc,
    )
