from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# CONFIGURACIÓN
# ============================================================

GRAFICO_TEXT_1 = "GRAFICO"
GRAFICO_TEXT_2 = "TRANSACCIONAL"


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalize_text(
    value: Any,
) -> str:
    """
    Normaliza mínimamente el texto de una palabra.
    """

    if value is None:
        return ""

    return (
        str(value)
        .replace("\xa0", " ")
        .strip()
        .upper()
    )


# ============================================================
# DETECCIÓN DE GRAFICO TRANSACCIONAL
# ============================================================

def is_grafico_transaccional_start(
    words: List[Dict[str, Any]],
    index: int,
) -> bool:
    """
    Determina si en `index` comienza la sección:

        GRAFICO TRANSACCIONAL

    Se exige que ambas palabras pertenezcan a la misma página
    y aparezcan consecutivamente en el orden esperado.
    """

    if index < 0:
        return False

    if index + 1 >= len(words):
        return False

    current = words[index]
    next_word = words[index + 1]

    text_current = normalize_text(
        current.get("text", "")
    )

    text_next = normalize_text(
        next_word.get("text", "")
    )

    if text_current != GRAFICO_TEXT_1:
        return False

    if text_next != GRAFICO_TEXT_2:
        return False

    page_current = int(
        current.get("page", 1) or 1
    )

    page_next = int(
        next_word.get("page", 1) or 1
    )

    if page_current != page_next:
        return False

    return True


# ============================================================
# ELIMINACIÓN
# ============================================================

def remove_after_grafico_transaccional(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Elimina absolutamente todo desde la sección
    'GRAFICO TRANSACCIONAL' hacia adelante.

    Se conserva la sección 'GRAFICO TRANSACCIONAL' fuera
    del resultado, junto con todo lo que aparece antes.

    Si no encuentra la sección, devuelve todas las palabras
    sin modificación.
    """

    if not words:
        return []

    for index in range(
        len(words) - 1
    ):

        if is_grafico_transaccional_start(
            words,
            index,
        ):

            return words[:index]

    return words