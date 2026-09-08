from __future__ import annotations

import re
from typing import Any, Dict, List

from models.movimiento import Movimiento


# Banorte puede imprimir el signo negativo DESPUÉS del importe, por ejemplo:
#
#     53.00-
#     $1,253.40-
#
# Los extractores existentes ya entienden correctamente el signo cuando va al
# inicio (``-53.00``). Esta utilidad sólo normaliza el formato bancario de signo
# final sobre una COPIA de las palabras de movimientos, sin alterar los words
# originales usados por datos de cuenta, resumen u otros productos.
#
# Se exige una parte decimal para no confundir identificadores/conceptos que
# casualmente terminen en guion (por ejemplo ``123-``) con importes monetarios.
_TRAILING_NEGATIVE_AMOUNT_PATTERN = re.compile(
    r"""
    ^
    (?P<body>
        \$?
        (?:
            (?:\d{1,3}(?:,\d{3})*|\d+)\.\d{1,2}
            |
            \d+,\d{1,2}
        )
    )
    -
    $
    """,
    re.VERBOSE,
)


def normalize_trailing_negative_amount_token(value: Any) -> str:
    """Convierte ``53.00-`` a ``-53.00`` sin tocar otros tokens."""
    if value is None:
        return ""

    original = str(value)
    candidate = (
        original
        .replace("\xa0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .strip()
        .replace(" ", "")
    )

    match = _TRAILING_NEGATIVE_AMOUNT_PATTERN.fullmatch(candidate)
    if match is None:
        return original

    return f"-{match.group('body')}"


def normalize_trailing_negative_amount_words(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normaliza sólo words monetarios afectados, preservando coordenadas."""
    normalized: List[Dict[str, Any]] = []

    for word in words:
        original_text = word.get("text", "")
        normalized_text = normalize_trailing_negative_amount_token(original_text)

        if normalized_text == str(original_text):
            normalized.append(word)
            continue

        cloned = dict(word)
        cloned["text"] = normalized_text
        normalized.append(cloned)

    return normalized


def ensure_signed_amount_operation_types(
    movements: List[Movimiento],
) -> List[Movimiento]:
    """
    Conserva CARGO/ABONO cuando el importe válido es negativo.

    El extractor digital histórico clasificaba el tipo sólo con ``> 0``. No se
    sobrescribe ningún tipo ya resuelto; únicamente se completa el caso nuevo en
    el que existe un cargo/abono distinto de cero pero negativo.
    """
    for movement in movements:
        if movement.tipo_operacion:
            continue

        cargo = movement.cargo or 0.0
        abono = movement.abono or 0.0

        if cargo != 0.0:
            movement.tipo_operacion = "CARGO"
        elif abono != 0.0:
            movement.tipo_operacion = "ABONO"

    return movements
