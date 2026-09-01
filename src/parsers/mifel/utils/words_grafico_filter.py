from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURACIÓN — FIN DE MOVIMIENTOS BANAMEX
# ============================================================
#
# El nombre público histórico se conserva, pero el filtro ya
# no depende únicamente de que GRAFICO y TRANSACCIONAL sean dos
# elementos consecutivos en la lista original.
#
# También reconoce el pie fiscal que puede aparecer antes del
# gráfico y que, de otro modo, se adjunta al último movimiento.
#
# ============================================================


GRAFICO_TEXT_1 = "GRAFICO"
GRAFICO_TEXT_2 = "TRANSACCIONAL"

LINE_Y_TOLERANCE = 3.5

STOP_LINE_MARKERS = (
    "GRAFICO TRANSACCIONAL",
    "ESTE DOCUMENTO ES UNA REPRESENTACION IMPRESA SIN VALIDEZ FISCAL",
    "INFORMACION IMPORTANTE",
)


# ============================================================
# NORMALIZACIÓN
# ============================================================


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparaciones semánticas."""

    if value is None:
        return ""

    normalized = unicodedata.normalize(
        "NFD",
        str(value).replace("\xa0", " "),
    )

    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )

    normalized = normalized.upper()
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)

    return " ".join(normalized.split())


# ============================================================
# COORDENADAS
# ============================================================


def _word_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _word_center_y(word: Dict[str, Any]) -> float:
    try:
        top = float(word.get("top", 0) or 0)
    except (TypeError, ValueError):
        top = 0.0

    try:
        bottom = float(word.get("bottom", top) or top)
    except (TypeError, ValueError):
        bottom = top

    return (top + bottom) / 2.0


def _word_x0(word: Dict[str, Any]) -> float:
    try:
        return float(word.get("x0", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# DETECCIÓN HISTÓRICA COMPATIBLE
# ============================================================


def is_grafico_transaccional_start(
    words: List[Dict[str, Any]],
    index: int,
) -> bool:
    """
    Conserva la comprobación pública histórica sobre dos
    palabras consecutivas de la misma página.
    """

    if index < 0 or index + 1 >= len(words):
        return False

    current = words[index]
    next_word = words[index + 1]

    return (
        normalize_text(current.get("text", ""))
        == GRAFICO_TEXT_1
        and normalize_text(next_word.get("text", ""))
        == GRAFICO_TEXT_2
        and _word_page(current) == _word_page(next_word)
    )


# ============================================================
# AGRUPACIÓN ESPACIAL
# ============================================================


def _group_words_into_lines(
    words: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Agrupa palabras sin depender del orden recibido."""

    ordered = sorted(
        words,
        key=lambda word: (
            _word_page(word),
            _word_center_y(word),
            _word_x0(word),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:
        page = _word_page(word)
        center_y = _word_center_y(word)

        if (
            current_y is None
            or page != current_page
            or abs(center_y - current_y) > LINE_Y_TOLERANCE
        ):
            if current:
                current.sort(key=_word_x0)
                lines.append(current)

            current = [word]
            current_page = page
            current_y = center_y
            continue

        current.append(word)
        current_y = sum(
            _word_center_y(item)
            for item in current
        ) / len(current)

    if current:
        current.sort(key=_word_x0)
        lines.append(current)

    return lines


def _line_text(line: List[Dict[str, Any]]) -> str:
    return normalize_text(
        " ".join(
            str(word.get("text", ""))
            for word in sorted(line, key=_word_x0)
        )
    )


def _is_stop_line(line: List[Dict[str, Any]]) -> bool:
    text = _line_text(line)

    return any(
        marker in text
        for marker in STOP_LINE_MARKERS
    )


def find_banamex_movements_cut(
    words: List[Dict[str, Any]],
) -> Optional[tuple[int, float]]:
    """Devuelve la posición del primer terminador reconocido."""

    candidates: List[tuple[int, float]] = []

    for line in _group_words_into_lines(words):
        if not line or not _is_stop_line(line):
            continue

        candidates.append(
            (
                _word_page(line[0]),
                min(_word_center_y(word) for word in line),
            )
        )

    if not candidates:
        return None

    return min(candidates)


# ============================================================
# ELIMINACIÓN
# ============================================================


def remove_after_banamex_movements(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Elimina el terminador y absolutamente todo lo posterior."""

    if not words:
        return []

    cut = find_banamex_movements_cut(words)

    if cut is None:
        return list(words)

    cut_page, cut_y = cut

    return [
        word
        for word in words
        if (
            _word_page(word) < cut_page
            or (
                _word_page(word) == cut_page
                and _word_center_y(word)
                < cut_y - LINE_Y_TOLERANCE
            )
        )
    ]


def remove_after_grafico_transaccional(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Alias compatible del filtro fortalecido de fin de tabla."""

    return remove_after_banamex_movements(words)
