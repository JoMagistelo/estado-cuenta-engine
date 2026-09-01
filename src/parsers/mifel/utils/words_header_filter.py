from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURACIÓN — ENCABEZADO BANAMEX
# ============================================================
#
# BANAMEX_HEADER_TOP_MAX se conserva como fallback compatible
# con el filtro histórico.
#
# El criterio principal ya no es un corte vertical fijo. Si la
# página contiene la cabecera de movimientos, su coordenada Y
# se usa como frontera dinámica y se elimina todo lo anterior.
# La propia cabecera FECHA/CONCEPTO/... se conserva para que el
# parser pueda calcular las columnas de esa página.
#
# ============================================================


BANAMEX_HEADER_TOP_MAX = 65.0
LINE_Y_TOLERANCE = 3.5

HEADER_ALIASES = {
    "FECHA": {"FECHA"},
    "CONCEPTO": {"CONCEPTO", "DESCRIPCION"},
    "RETIROS": {"RETIROS", "CARGOS"},
    "DEPOSITOS": {"DEPOSITOS", "ABONOS"},
    "SALDO": {"SALDO"},
}


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


def get_word_top(word: Dict[str, Any]) -> float:
    """Obtiene `top` de forma segura."""

    try:
        return float(word.get("top", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def get_word_center_y(word: Dict[str, Any]) -> float:
    """Obtiene el centro vertical de una palabra."""

    top = get_word_top(word)

    try:
        bottom = float(word.get("bottom", top) or top)
    except (TypeError, ValueError):
        bottom = top

    return (top + bottom) / 2.0


def get_word_page(word: Dict[str, Any]) -> int:
    """Obtiene la página de forma segura."""

    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


# ============================================================
# AGRUPACIÓN DE LÍNEAS
# ============================================================


def _group_words_into_lines(
    words: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Agrupa palabras por página y cercanía vertical."""

    ordered = sorted(
        words,
        key=lambda word: (
            get_word_page(word),
            get_word_center_y(word),
            float(word.get("x0", 0) or 0),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:
        page = get_word_page(word)
        center_y = get_word_center_y(word)

        if (
            current_y is None
            or page != current_page
            or abs(center_y - current_y) > LINE_Y_TOLERANCE
        ):
            if current:
                current.sort(
                    key=lambda item: float(
                        item.get("x0", 0) or 0
                    )
                )
                lines.append(current)

            current = [word]
            current_page = page
            current_y = center_y
            continue

        current.append(word)
        current_y = sum(
            get_word_center_y(item)
            for item in current
        ) / len(current)

    if current:
        current.sort(
            key=lambda item: float(item.get("x0", 0) or 0)
        )
        lines.append(current)

    return lines


def _line_tokens(line: List[Dict[str, Any]]) -> set[str]:
    return {
        normalize_text(word.get("text", ""))
        for word in line
        if normalize_text(word.get("text", ""))
    }


def _is_movements_header(line: List[Dict[str, Any]]) -> bool:
    tokens = _line_tokens(line)

    found = sum(
        1
        for aliases in HEADER_ALIASES.values()
        if tokens.intersection(aliases)
    )

    return found >= 4


def find_movements_header_y_by_page(
    words: List[Dict[str, Any]],
) -> Dict[int, float]:
    """Localiza la primera cabecera de movimientos por página."""

    result: Dict[int, float] = {}

    for line in _group_words_into_lines(words):
        if not line or not _is_movements_header(line):
            continue

        page = get_word_page(line[0])
        center_y = sum(
            get_word_center_y(word)
            for word in line
        ) / len(line)

        previous = result.get(page)

        if previous is None or center_y < previous:
            result[page] = center_y

    return result


# ============================================================
# DETECCIÓN DEL ENCABEZADO HISTÓRICO
# ============================================================


def is_banamex_header_word(word: Dict[str, Any]) -> bool:
    """
    Criterio histórico conservado para páginas sin cabecera de
    movimientos detectable.
    """

    top = get_word_top(word)

    return 0.0 <= top <= BANAMEX_HEADER_TOP_MAX


# ============================================================
# ELIMINACIÓN
# ============================================================


def remove_banamex_header(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Elimina contenido previo a la tabla de movimientos.

    Estrategia:

        1. Si la página contiene FECHA/CONCEPTO/... se usa esa
           cabecera como frontera vertical dinámica.
        2. Si no existe esa evidencia, se conserva el fallback
           histórico `top <= 65.0`.

    La línea de cabecera de la tabla nunca se elimina.
    """

    if not words:
        return []

    header_y_by_page = find_movements_header_y_by_page(words)
    result: List[Dict[str, Any]] = []

    for word in words:
        page = get_word_page(word)
        header_y = header_y_by_page.get(page)

        if header_y is not None:
            if (
                get_word_center_y(word)
                < header_y - LINE_Y_TOLERANCE
            ):
                continue

            result.append(word)
            continue

        if not is_banamex_header_word(word):
            result.append(word)

    return result
