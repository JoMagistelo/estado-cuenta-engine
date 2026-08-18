from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# CONFIGURACIÓN DEL ENCABEZADO BANAMEX
# ============================================================
#
# El encabezado institucional de Banamex aparece repetido
# al inicio de cada página.
#
# En el PDF observado, sus palabras se encuentran
# aproximadamente entre:
#
#     top = 8.97
#     top = 58.65
#
# Por seguridad dejamos un margen hasta 65.0.
#
# Ejemplo observado:
#
#     ESTADO         top ≈ 8.98
#     DE             top ≈ 8.98
#     CUENTA         top ≈ 8.98
#     ...
#     CLIENTE:       top ≈ 20.68
#     Página:        top ≈ 32.08
#     PATRICIA       top ≈ 43.48
#     Resto          top ≈ 50.66
#
# ============================================================

BANAMEX_HEADER_TOP_MAX = 65.0


# ============================================================
# UTILIDADES
# ============================================================


def get_word_top(
    word: Dict[str, Any],
) -> float:
    """
    Obtiene la coordenada vertical superior de una palabra.

    Si no existe o no puede convertirse a float,
    devuelve 0.0.
    """

    try:
        return float(
            word.get(
                "top",
                0,
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


# ============================================================
# DETECCIÓN DEL ENCABEZADO
# ============================================================


def is_banamex_header_word(
    word: Dict[str, Any],
) -> bool:
    """
    Determina si una palabra pertenece a la región
    institucional superior del encabezado Banamex.

    El criterio principal es exclusivamente vertical.

    No dependemos del texto de la palabra ni de su coordenada X.
    """

    top = get_word_top(
        word
    )

    return (
        0.0
        <= top
        <= BANAMEX_HEADER_TOP_MAX
    )


# ============================================================
# ELIMINACIÓN
# ============================================================


def remove_banamex_header(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Elimina el encabezado institucional superior de Banamex.

    Se conserva todo lo que esté por debajo de la región
    definida por BANAMEX_HEADER_TOP_MAX.

    La función no modifica las palabras originales.
    Devuelve una nueva lista.
    """

    if not words:
        return []

    return [
        word
        for word in words
        if not is_banamex_header_word(
            word
        )
    ]