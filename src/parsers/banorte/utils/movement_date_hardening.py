from __future__ import annotations

import re
from typing import Any, Sequence


# pdfplumber puede entregar una fecha BANORTE y el inicio de una clave/folio
# numérico como una sola palabra espacial, por ejemplo:
#
#     22-JUN-2650114599TRANSBPI07617702
#
# El extractor principal de movimientos ya protege el año de dos dígitos, pero
# otras etapas históricas del recorte aceptan años de 2 a 4 dígitos. Sin una
# separación explícita, los dos primeros dígitos del folio pueden confundirse
# con parte del año ("22-JUN-2650").
#
# Esta normalización es deliberadamente mínima: sólo inserta un espacio cuando
# después del año de dos dígitos viene INMEDIATAMENTE otro dígito. No cambia
# coordenadas, páginas ni el diccionario original, y no toca los casos normales
# como "25-JUN-24COMPRA".
AMBIGUOUS_NUMERIC_SUFFIX_DATE_PATTERN = re.compile(
    r"^"
    r"(?P<date>"
    r"\d{1,2}"
    r"-"
    r"[A-ZÁÉÍÓÚÑ]{3}"
    r"-"
    r"\d{2}"
    r")"
    r"(?P<suffix>\d\S*)"
    r"$",
    re.IGNORECASE,
)


def normalize_ambiguous_movement_date_token(value: Any) -> str:
    """Hace inequívoca una fecha BANORTE pegada a un sufijo numérico.

    Ejemplo::

        22-JUN-2650114599TRANSBPI07617702
        ->
        22-JUN-26 50114599TRANSBPI07617702

    La función no intenta reescribir fechas normales ni conceptos pegados que
    comienzan con letras, ya soportados por el extractor existente.
    """

    text = "" if value is None else str(value)
    match = AMBIGUOUS_NUMERIC_SUFFIX_DATE_PATTERN.match(text)

    if match is None:
        return text

    return f"{match.group('date')} {match.group('suffix')}"


def normalize_ambiguous_movement_date_words(
    words: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normaliza sólo las palabras ambiguas antes del pipeline de movimientos.

    Las palabras no afectadas se reutilizan tal cual. Para una palabra afectada
    se crea una copia superficial y se reemplaza únicamente ``text``. Esto evita
    alterar ``DocumentData.spatial_words`` y mantiene intactos los extractores de
    datos de cuenta, resumen y productos.
    """

    normalized: list[dict[str, Any]] = []

    for word in words:
        original_text = word.get("text", "")
        normalized_text = normalize_ambiguous_movement_date_token(original_text)

        if normalized_text == original_text:
            normalized.append(word)
            continue

        normalized_word = dict(word)
        normalized_word["text"] = normalized_text
        normalized.append(normalized_word)

    return normalized
