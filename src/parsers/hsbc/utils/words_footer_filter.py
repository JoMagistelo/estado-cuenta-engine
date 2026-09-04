from __future__ import annotations

import re
import unicodedata

from typing import Any, Dict, List, Sequence


# ============================================================
# CONFIGURACIÓN
# ============================================================

FOOTER_TOP_RATIO = 0.88

FOOTER_MIN_TOP = 700.0

FOOTER_MARKERS = (
    "EMITIDO POR",
    "GRUPO FINANCIERO HSBC",
    "HMI-950125KG8",
    "PASEO DE LA REFORMA",
)

FOOTER_LINE_Y_TOLERANCE = 5.0


# ============================================================
# UTILIDADES
# ============================================================


def safe_page(
    word: Dict[str, Any],
) -> int:
    """
    Devuelve la página de una word.
    """

    try:
        return int(
            word.get(
                "page",
                1,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte un valor a float de forma segura.
    """

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


def normalize_text(
    value: Any,
) -> str:
    """
    Normalización básica para detectar marcadores.
    """

    if value is None:
        return ""

    text = str(value).strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"\s+", " ", text.upper())

    return text.strip()


def page_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Dict[
    int,
    List[
        Dict[str, Any]
    ]
]:
    """
    Agrupa words por página.
    """

    result: Dict[
        int,
        List[
            Dict[str, Any]
        ]
    ] = {}

    for word in words:

        page = safe_page(
            word
        )

        result.setdefault(
            page,
            []
        ).append(
            word
        )

    return result


# ============================================================
# DETECCIÓN DE FOOTER
# ============================================================

def footer_lines(
    words: Sequence[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Agrupa sólo para reconocer marcadores partidos por OCR."""

    lines: List[List[Dict[str, Any]]] = []

    for word in sorted(
        words,
        key=lambda item: (
            safe_float(item.get("top", 0.0)),
            safe_float(item.get("x0", 0.0)),
        ),
    ):
        top = safe_float(word.get("top", 0.0))
        target = next(
            (
                line
                for line in reversed(lines)
                if abs(
                    safe_float(line[0].get("top", 0.0)) - top
                )
                <= FOOTER_LINE_Y_TOLERANCE
            ),
            None,
        )

        if target is None:
            lines.append([word])
        else:
            target.append(word)

    for line in lines:
        line.sort(key=lambda item: safe_float(item.get("x0", 0.0)))

    return lines


def is_footer_marker_text(value: str) -> bool:
    normalized = normalize_text(value)

    if any(marker in normalized for marker in FOOTER_MARKERS):
        return True

    return bool(
        re.search(r"\bPAG\.?\s*\d+\s*/\s*\d+\b", normalized)
    )


def find_footer_start_y(
    words: Sequence[Dict[str, Any]],
) -> float | None:
    """
    Localiza la frontera Y del pie mediante posición y frase fuerte.

    Una palabra aislada como RFC o HSBC no basta. Esto evita cortar
    tablas válidas cuando el último movimiento queda cerca del borde.
    """

    if not words:
        return None

    max_bottom = max(
        safe_float(word.get("bottom", word.get("top", 0.0)))
        for word in words
    )
    # La referencia absoluta funciona para la escala histórica y el
    # ratio permite que la misma utilidad opere sobre coordenadas
    # reescaladas (por ejemplo, otro motor OCR).
    dynamic_threshold = min(
        FOOTER_MIN_TOP,
        max_bottom * FOOTER_TOP_RATIO,
    )
    candidates = []

    for line in footer_lines(words):
        line_top = min(
            safe_float(word.get("top", 0.0))
            for word in line
        )
        if line_top < dynamic_threshold:
            continue

        text = " ".join(
            str(word.get("text", ""))
            for word in line
        )
        if is_footer_marker_text(text):
            candidates.append(line_top)

    return min(candidates) if candidates else None


def find_footer_start_index(
    words: Sequence[
        Dict[str, Any]
    ],
) -> int | None:
    """
    Localiza el inicio del footer de una página.

    La detección combina:

        - posición vertical inferior;
        - marcadores textuales conocidos.

    No depende de una coordenada Y exacta.
    """

    footer_y = find_footer_start_y(words)
    if footer_y is None:
        return None

    candidates = [
        index
        for index, word in enumerate(words)
        if safe_float(word.get("top", 0.0)) >= footer_y
    ]

    return min(candidates) if candidates else None


# ============================================================
# FILTRO POR PÁGINA
# ============================================================


def filter_page_footer(
    words: Sequence[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Elimina el footer de una página.
    """

    if not words:
        return []

    ordered = sorted(
        words,
        key=lambda word: (
            safe_float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    footer_start_y = find_footer_start_y(
        ordered
    )

    if footer_start_y is None:
        return ordered

    return [
        word
        for word in ordered
        if safe_float(word.get("top", 0.0)) < footer_start_y
    ]


# ============================================================
# FILTRO PÚBLICO
# ============================================================


def filter_hsbc_footer_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Elimina los footers de todas las páginas HSBC.

    Conserva intacta la información de encabezados y
    movimientos.

    La página se procesa individualmente para evitar que
    las coordenadas de una página afecten a otra.
    """

    if not words:
        return []

    grouped = page_words(
        words
    )

    result = []

    for page in sorted(
        grouped
    ):

        result.extend(
            filter_page_footer(
                grouped[page]
            )
        )

    result.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    return result
