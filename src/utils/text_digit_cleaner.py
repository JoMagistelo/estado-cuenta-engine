"""
Limpiador de dígitos.

Responsabilidad:
----------------
Eliminar cualquier carácter que no sea numérico
de una cadena de texto.
"""
import re

def clean_digits(text: str) -> str:
    """
    Elimina todo excepto números.
    """
    return re.sub(
        r"\D",
        "",
        text
    )