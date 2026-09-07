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
# Esta normalización es deliberadamente mínima: sólo actúa cuando después del
# año corto hay más dígitos y esos primeros cuatro dígitos NO forman un año de
# cuatro cifras razonable. Así se preservan fechas ya soportadas como
# "22-JUN-2026" y "22-JUN-2026COMPRA", además de "25-JUN-24COMPRA".
DATE_AND_NUMERIC_BODY_PATTERN = re.compile(
    r"^"
    r"(?P<prefix>"
    r"\d{1,2}"
    r"-"
    r"[A-ZÁÉÍÓÚÑ]{3}"
    r"-"
    r")"
    r"(?P<body>\d{3,}\S*)"
    r"$",
    re.IGNORECASE,
)


def _starts_with_plausible_four_digit_year(body: str) -> bool:
    if len(body) < 4 or not body[:4].isdigit():
        return False

    year = int(body[:4])
    return 1900 <= year <= 2099


def normalize_ambiguous_movement_date_token(value: Any) -> str:
    """Hace inequívoca una fecha BANORTE pegada a un sufijo numérico.

    Ejemplo::

        22-JUN-2650114599TRANSBPI07617702
        ->
        22-JUN-26 50114599TRANSBPI07617702

    La función no reescribe fechas normales de cuatro dígitos ni conceptos
    alfanuméricos pegados que ya son soportados por el extractor existente.
    """

    text = "" if value is None else str(value)
    match = DATE_AND_NUMERIC_BODY_PATTERN.match(text)

    if match is None:
        return text

    body = match.group("body")

    # Si los primeros cuatro dígitos ya representan un año razonable, no se
    # modifica el token. Esto evita convertir 22-JUN-2026 en 22-JUN-20 26.
    if _starts_with_plausible_four_digit_year(body):
        return text

    date = f"{match.group('prefix')}{body[:2]}"
    suffix = body[2:]

    return f"{date} {suffix}"


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
