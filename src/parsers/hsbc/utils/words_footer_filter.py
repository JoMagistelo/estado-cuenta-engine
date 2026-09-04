from __future__ import annotations

import re
import unicodedata

from typing import Any, Dict, List, Sequence


# ============================================================
# CONFIGURACIÓN
# ============================================================

# HSBC imprime el footer aproximadamente al final de la página,
# pero el OCR puede desplazarlo algunos puntos. La coordenada sólo
# limita la zona de búsqueda: nunca se elimina contenido por Y sin
# evidencia textual de footer.
FOOTER_TOP_RATIO = 0.84
FOOTER_MIN_TOP = 650.0
FOOTER_LINE_Y_TOLERANCE = 5.0

# PSM 11 y algunos escaneos inclinados pueden interpretar líneas
# horizontales como cadenas muy largas de signos. Este filtro es
# deliberadamente estricto para no tocar referencias o conceptos.
GRAPHIC_NOISE_MIN_TOP = 500.0
GRAPHIC_NOISE_MAX_CONFIDENCE = 15.0
GRAPHIC_NOISE_MIN_LENGTH = 8
GRAPHIC_NOISE_MAX_ALNUM_RATIO = 0.30


# ============================================================
# UTILIDADES
# ============================================================

def safe_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1))
    except (TypeError, ValueError):
        return 1


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    text = text.upper()
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def page_words(
    words: Sequence[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    result: Dict[int, List[Dict[str, Any]]] = {}

    for word in words:
        result.setdefault(
            safe_page(word),
            [],
        ).append(word)

    return result


def word_center_y(word: Dict[str, Any]) -> float:
    top = safe_float(word.get("top", 0.0))
    bottom = safe_float(word.get("bottom", top))

    return (top + bottom) / 2.0


def group_page_lines(
    words: Sequence[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    ordered = sorted(
        words,
        key=lambda word: (
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []

    for word in ordered:
        center_y = word_center_y(word)
        best_line = None
        best_distance = float("inf")

        for line in reversed(lines):
            line_y = sum(
                word_center_y(item)
                for item in line
            ) / len(line)
            distance = abs(center_y - line_y)

            if (
                distance <= FOOTER_LINE_Y_TOLERANCE
                and distance < best_distance
            ):
                best_line = line
                best_distance = distance

            if line_y < center_y - FOOTER_LINE_Y_TOLERANCE:
                break

        if best_line is None:
            lines.append([word])
        else:
            best_line.append(word)

    for line in lines:
        line.sort(
            key=lambda word: safe_float(
                word.get("x0", 0.0)
            )
        )

    return lines


def line_top(line: Sequence[Dict[str, Any]]) -> float:
    if not line:
        return 0.0

    return min(
        safe_float(word.get("top", 0.0))
        for word in line
    )


def line_text(line: Sequence[Dict[str, Any]]) -> str:
    return " ".join(
        str(word.get("text", "")).strip()
        for word in line
        if str(word.get("text", "")).strip()
    ).strip()


# ============================================================
# RUIDO GRÁFICO OCR
# ============================================================

def is_graphic_noise_word(word: Dict[str, Any]) -> bool:
    """
    Detecta exclusivamente ruido gráfico extremo de OCR.

    Una referencia real como ``49671`` nunca cumple esta regla:
    contiene 100 % caracteres alfanuméricos. El objetivo son tokens
    como ``———];;——e€ci—;j——TTLT;——`` con confianza cercana a cero.
    """

    top = safe_float(word.get("top", 0.0))
    if top < GRAPHIC_NOISE_MIN_TOP:
        return False

    confidence = safe_float(
        word.get("confidence", 100.0),
        default=100.0,
    )
    if confidence > GRAPHIC_NOISE_MAX_CONFIDENCE:
        return False

    text = str(word.get("text", "")).strip()
    if len(text) < GRAPHIC_NOISE_MIN_LENGTH:
        return False

    alnum_count = sum(
        1
        for char in text
        if char.isalnum()
    )
    alnum_ratio = alnum_count / max(len(text), 1)

    return alnum_ratio <= GRAPHIC_NOISE_MAX_ALNUM_RATIO


def remove_graphic_noise(
    words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        word
        for word in words
        if not is_graphic_noise_word(word)
    ]


# ============================================================
# DETECCIÓN DEL FOOTER
# ============================================================

def find_footer_top(
    words: Sequence[Dict[str, Any]],
) -> float | None:
    """
    Devuelve la coordenada Y donde empieza el footer.

    La detección se hace sobre renglones completos para tolerar
    fragmentación OCR. Se exige además una marca inequívoca:

      - ``Emitido ... HSBC`` (incluye ``Emitid o``);
      - ``Paseo ... Reforma``;
      - marcador de página ``PAG``.
    """

    if not words:
        return None

    max_top = max(
        safe_float(word.get("top", 0.0))
        for word in words
    )
    dynamic_threshold = max(
        FOOTER_MIN_TOP,
        max_top * FOOTER_TOP_RATIO,
    )

    candidates = []

    for line in group_page_lines(words):
        top = line_top(line)
        if top < dynamic_threshold:
            continue

        normalized = normalize_text(line_text(line))
        tokens = re.findall(r"[A-Z0-9]+", normalized)
        token_set = set(tokens)

        has_emitido = (
            any(
                token.startswith("EMITID")
                for token in tokens
            )
            and "HSBC" in token_set
        )
        has_address = (
            "PASEO" in token_set
            and "REFORMA" in token_set
        )
        has_page_marker = "PAG" in token_set

        if has_emitido or has_address or has_page_marker:
            candidates.append(top)

    if not candidates:
        return None

    return min(candidates)


# ============================================================
# FILTRO POR PÁGINA
# ============================================================

def filter_page_footer(
    words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not words:
        return []

    cleaned = remove_graphic_noise(words)
    footer_top = find_footer_top(cleaned)

    if footer_top is None:
        return sorted(
            cleaned,
            key=lambda word: (
                safe_float(word.get("top", 0.0)),
                safe_float(word.get("x0", 0.0)),
            ),
        )

    return sorted(
        [
            word
            for word in cleaned
            if safe_float(word.get("top", 0.0))
            < footer_top - FOOTER_LINE_Y_TOLERANCE
        ],
        key=lambda word: (
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        ),
    )


# ============================================================
# FILTRO PÚBLICO
# ============================================================

def filter_hsbc_footer_words(
    words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Elimina footer y ruido gráfico extremo de cada página HSBC.

    La página se procesa de forma independiente. El filtro conserva
    movimientos y referencias cercanos al final de la página porque
    el corte requiere evidencia textual real del footer.
    """

    if not words:
        return []

    grouped = page_words(words)
    result: List[Dict[str, Any]] = []

    for page in sorted(grouped):
        result.extend(
            filter_page_footer(grouped[page])
        )

    result.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    return result
