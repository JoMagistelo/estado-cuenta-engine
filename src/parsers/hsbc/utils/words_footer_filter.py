from __future__ import annotations

from typing import Any, Dict, List, Sequence


# ============================================================
# CONFIGURACIÓN
# ============================================================

FOOTER_TOP_RATIO = 0.88

FOOTER_MIN_TOP = 700.0

FOOTER_MARKERS = (
    "EMITIDO",
    "HSBC MEXICO",
    "HSBC.",
    "RFC:",
    "PAG.",
    "PASEO DE LA REFORMA",
)


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

    return str(
        value
    ).strip().upper()


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

    if not words:
        return None

    max_top = max(
        safe_float(
            word.get(
                "top",
                0.0,
            )
        )
        for word in words
    )

    dynamic_threshold = max(
        FOOTER_MIN_TOP,
        max_top * FOOTER_TOP_RATIO,
    )

    candidates = []

    for index, word in enumerate(
        words
    ):

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        top = safe_float(
            word.get(
                "top",
                0.0,
            )
        )

        if top < dynamic_threshold:
            continue

        if any(
            marker in text
            for marker in FOOTER_MARKERS
        ):
            candidates.append(
                index
            )

    if not candidates:
        return None

    return min(
        candidates
    )


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

    footer_start = find_footer_start_index(
        ordered
    )

    if footer_start is None:
        return ordered

    return ordered[
        :footer_start
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