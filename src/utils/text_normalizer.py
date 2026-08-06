"""
Utilidades para normalizar texto.

Todos los detectores y parsers trabajan sobre texto normalizado
para evitar diferencias entre:

México
MEXICO
méxico
MéXiCo
"""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Convierte el texto a una representación estándar.

    - Mayúsculas
    - Sin acentos
    - Espacios repetidos eliminados

    Parameters
    ----------
    text : str

    Returns
    -------
    str
    """

    text = text.upper()

    text = unicodedata.normalize(
        "NFD",
        text
    )

    text = "".join(

        c

        for c in text

        if unicodedata.category(c) != "Mn"

    )

    text = re.sub(

        r"\s+",

        " ",

        text

    )

    return text.strip()