from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# UTILIDAD — ELIMINAR FOOTER BANORTE
# ============================================================
#
# REGLA
# ------------------------------------------------------------
#
# El footer de Banorte comienza aproximadamente en:
#
#     top = 743.x
#
# Ejemplos observados:
#
#     743.5125
#     743.6998125
#
# La posición es prácticamente constante entre layouts.
#
# Por lo tanto NO necesitamos detectar:
#
#     - palabras concretas
#     - texto del footer
#     - líneas
#     - número de página
#     - patrones regex
#
# Solamente utilizamos la coordenada vertical local:
#
#     word["top"]
#
# Todo lo que comienza desde FOOTER_TOP_REFERENCE hacia abajo
# se elimina.
#
# IMPORTANTE:
#
# Se utiliza "top" y NO "doctop".
#
# "top" es relativo a la página y el footer se repite en cada
# página.
#
# ============================================================


# ============================================================
# ALTURA DE REFERENCIA DEL FOOTER
# ============================================================
#
# Valores observados:
#
#     Layout 1:
#         top = 743.5125
#
#     Layout 2:
#         top = 743.6998125
#
# Se utiliza una referencia ligeramente anterior para cubrir
# ambos layouts sin depender de una coordenada exacta.
#
# ============================================================

FOOTER_TOP_REFERENCE = 743.0


# ============================================================
# CONVERSIÓN SEGURA
# ============================================================

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


# ============================================================
# COORDENADA VERTICAL
# ============================================================

def word_top(
    word: Dict[str, Any],
) -> float:
    """
    Obtiene la coordenada vertical superior de una palabra.

    Se utiliza "top" porque la referencia del footer es relativa
    a cada página.
    """

    return safe_float(
        word.get(
            "top",
            0.0,
        )
    )


# ============================================================
# ELIMINAR FOOTER
# ============================================================

def remove_banorte_footer(
    words: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Elimina todo el contenido del footer BANORTE.

    Regla:

        top < FOOTER_TOP_REFERENCE
            ↓
        conservar

        top >= FOOTER_TOP_REFERENCE
            ↓
        eliminar

    La misma regla se aplica independientemente de la página.

    No analiza:
        - texto
        - palabras
        - líneas
        - número de página
        - doctop

    Solamente utiliza la altura física "top" de cada palabra.
    """

    if not words:

        return []

    return [
        word
        for word in words
        if word_top(word)
        < FOOTER_TOP_REFERENCE
    ]