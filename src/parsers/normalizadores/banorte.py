from __future__ import annotations

import re
import unicodedata
from typing import Any


SpatialWord = dict[str, Any]

# Coordenadas Y objetivo tomadas del layout espacial Banorte que ya consume el
# parser digital. El normalizador NO toca texto ni páginas; sólo aproxima la Y
# del bloque principal a estas bandas canónicas.
TARGET_NAME_Y = 64.0
TARGET_PERIOD_Y = 110.0
TARGET_CUT_Y = 122.0
TARGET_CUSTOMER_Y = 138.5
TARGET_ACCOUNT_ROW_Y = 225.0


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


def _top(word: SpatialWord) -> float:
    return _f(word.get("top", 0.0))


def _bottom(word: SpatialWord) -> float:
    return _f(word.get("bottom", word.get("top", 0.0)))


def _cy(word: SpatialWord) -> float:
    return (_top(word) + _bottom(word)) / 2.0


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norm(value))


def _line_text(line: list[SpatialWord]) -> str:
    return " ".join(
        str(word.get("text", "")).strip()
        for word in sorted(line, key=_x0)
        if str(word.get("text", "")).strip()
    ).strip()


def _line_y(line: list[SpatialWord]) -> float:
    return sum(_cy(word) for word in line) / len(line) if line else 0.0


def _group_lines(words: list[SpatialWord]) -> list[list[SpatialWord]]:
    if not words:
        return []

    heights = sorted(
        _bottom(word) - _top(word)
        for word in words
        if _bottom(word) > _top(word)
    )
    typical = heights[len(heights) // 2] if heights else 6.0
    tolerance = max(3.6, min(6.5, typical * 0.62))

    ordered = sorted(words, key=lambda word: (_page(word), _cy(word), _x0(word)))
    lines: list[list[SpatialWord]] = []
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
            lines.append(current)
            current = [word]
            current_page = page
            current_y = y

    if current:
        current.sort(key=_x0)
        lines.append(current)

    return lines


def _score_data_page(page_lines: list[list[SpatialWord]]) -> int:
    score = 0
    for line in page_lines:
        text = _norm(_line_text(line))
        compact = _compact(text)
        if "PERIODO" in text:
            score += 25
        if "FECHA" in text and "CORTE" in text:
            score += 30
        if "CLIENTE" in text:
            score += 20
        if "PRODUCTO" in text and "CUENTA" in text and "CLABE" in text:
            score += 70
        if "SALDOINICIALDELPERIODO" in compact or "TOTALDEDEPOSITOS" in compact:
            score += 45
    return score


def _find_data_page(lines: list[list[SpatialWord]]) -> int | None:
    pages = sorted({_page(line[0]) for line in lines if line})
    best_page: int | None = None
    best_score = 0
    for page in pages:
        page_lines = [line for line in lines if line and _page(line[0]) == page]
        score = _score_data_page(page_lines)
        if score > best_score:
            best_score = score
            best_page = page
    return best_page


def _find_account_row(page_lines: list[list[SpatialWord]]) -> list[SpatialWord] | None:
    header_index: int | None = None
    for index, line in enumerate(page_lines):
        text = _norm(_line_text(line))
        if "PRODUCTO" in text and "CUENTA" in text and "CLABE" in text:
            header_index = index
            break

    if header_index is not None:
        for line in page_lines[header_index + 1 : header_index + 5]:
            text = _line_text(line)
            digits = re.sub(r"\D", "", text)
            # Cuenta + CLABE + saldos suelen proporcionar una firma numérica muy
            # fuerte sin depender del nombre del producto.
            if len(digits) >= 24:
                return line

    # Fallback: una línea con un número de cuenta de 8-12 dígitos y suficiente
    # contenido numérico para contener también CLABE/saldos.
    for line in page_lines:
        text = _line_text(line)
        if re.search(r"(?<!\d)\d{8,12}(?!\d)", text) and len(re.sub(r"\D", "", text)) >= 24:
            return line
    return None


def _find_period_line(page_lines: list[list[SpatialWord]]) -> list[SpatialWord] | None:
    for line in page_lines:
        text = _norm(_line_text(line))
        if "PERIODO" in text and re.search(r"\d{1,2}\s*/.*?20\d{2}", text):
            return line
    return None


def _find_cut_line(page_lines: list[list[SpatialWord]]) -> list[SpatialWord] | None:
    for line in page_lines:
        text = _norm(_line_text(line))
        if "FECHA" in text and "CORTE" in text:
            return line
    return None


def _find_customer_line(page_lines: list[list[SpatialWord]]) -> list[SpatialWord] | None:
    for line in page_lines:
        text = _norm(_line_text(line))
        if "CLIENTE" in text and re.search(r"\d{6,12}", text):
            return line
    return None


def _find_name_line(
    page_lines: list[list[SpatialWord]],
    period_line: list[SpatialWord] | None,
) -> list[SpatialWord] | None:
    if period_line is None:
        return None

    period_y = _line_y(period_line)
    candidates: list[tuple[float, list[SpatialWord]]] = []
    banned = {
        "CALLE", "AV", "AV.", "PISO", "DEPTO", "COLONIA", "C.P.",
        "INFORMACION", "PERIODO", "SUCURSAL", "PLAZA", "TELEFONO",
    }

    for line in page_lines:
        y = _line_y(line)
        if not (40.0 <= period_y - y <= 80.0):
            continue
        text = _line_text(line)
        normalized = _norm(text)
        tokens = [token for token in re.split(r"\s+", normalized) if token]
        if not 2 <= len(tokens) <= 8:
            continue
        if any(char.isdigit() for char in normalized):
            continue
        if any(token in banned for token in tokens):
            continue
        if sum(token.isalpha() for token in tokens) < 2:
            continue
        if min((_x0(word) for word in line), default=999.0) > 100.0:
            continue
        candidates.append((period_y - y, line))

    if not candidates:
        return None

    # El nombre suele ser la línea alfabética más alejada inmediatamente antes
    # del bloque de dirección/periodo.
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _anchors(page_lines: list[list[SpatialWord]]) -> list[tuple[float, float]]:
    period = _find_period_line(page_lines)
    cut = _find_cut_line(page_lines)
    customer = _find_customer_line(page_lines)
    account = _find_account_row(page_lines)
    name = _find_name_line(page_lines, period)

    pairs: list[tuple[float, float]] = []
    for line, target in (
        (name, TARGET_NAME_Y),
        (period, TARGET_PERIOD_Y),
        (cut, TARGET_CUT_Y),
        (customer, TARGET_CUSTOMER_Y),
        (account, TARGET_ACCOUNT_ROW_Y),
    ):
        if line:
            pairs.append((_line_y(line), target))

    pairs.sort(key=lambda pair: pair[0])

    # Deduplicar anclas OCR que terminaron físicamente en la misma línea.
    deduped: list[tuple[float, float]] = []
    for observed, target in pairs:
        if deduped and abs(observed - deduped[-1][0]) < 1.0:
            continue
        deduped.append((observed, target))
    return deduped


def _map_y(value: float, anchors: list[tuple[float, float]]) -> float:
    if len(anchors) < 2:
        return value

    # Elegir el segmento de interpolación o el extremo para extrapolación.
    if value <= anchors[0][0]:
        left, right = anchors[0], anchors[1]
    elif value >= anchors[-1][0]:
        left, right = anchors[-2], anchors[-1]
    else:
        left, right = anchors[0], anchors[1]
        for index in range(len(anchors) - 1):
            a, b = anchors[index], anchors[index + 1]
            if a[0] <= value <= b[0]:
                left, right = a, b
                break

    observed_span = right[0] - left[0]
    if abs(observed_span) < 0.01:
        return value

    slope = (right[1] - left[1]) / observed_span
    # Evitar transformaciones destructivas ante una ancla OCR falsa.
    if not 0.60 <= slope <= 1.40:
        shifts = [target - observed for observed, target in anchors]
        shifts.sort()
        return value + shifts[len(shifts) // 2]

    return left[1] + (value - left[0]) * slope


def normalize_banorte_words(words: list[SpatialWord]) -> list[SpatialWord]:
    """
    Normaliza de forma conservadora las coordenadas Y del bloque principal
    Banorte obtenido por Tesseract.

    Reglas de seguridad:
    - no muta la lista/objetos originales;
    - no cambia texto, `page`, X ni confianza;
    - no elimina páginas publicitarias;
    - sólo modifica la página que tiene evidencia de datos/resumen Banorte;
    - si no existen al menos dos anclas fiables, devuelve una copia sin cambios.

    Los movimientos quedan intactos porque su parser digital separa columnas por X
    y no necesita una Y absoluta. Así se minimiza el riesgo de romper continuidad
    entre páginas.
    """
    copied = [dict(word) for word in words]
    if not copied:
        return copied

    lines = _group_lines(copied)
    data_page = _find_data_page(lines)
    if data_page is None:
        return copied

    page_lines = [line for line in lines if line and _page(line[0]) == data_page]
    anchors = _anchors(page_lines)
    if len(anchors) < 2:
        return copied

    for word in copied:
        if _page(word) != data_page:
            continue

        old_top = _top(word)
        old_bottom = _bottom(word)
        new_top = _map_y(old_top, anchors)
        new_bottom = _map_y(old_bottom, anchors)

        if new_bottom < new_top:
            new_top, new_bottom = new_bottom, new_top

        word["top"] = new_top
        word["bottom"] = new_bottom
        word["height"] = max(0.0, new_bottom - new_top)

        # Tesseract genera doctop = page_offset + top. Mantener la misma base de
        # página y sólo aplicar la corrección local evita alterar el orden global.
        if "doctop" in word:
            old_doctop = _f(word.get("doctop", old_top), old_top)
            page_offset = old_doctop - old_top
            word["doctop"] = page_offset + new_top

    return copied


# Alias opcional para normalizadores genéricos.
normalize_words = normalize_banorte_words
