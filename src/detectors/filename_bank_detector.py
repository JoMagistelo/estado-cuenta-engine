from __future__ import annotations

import re
import unicodedata

from catalog.bank_signatures import BANK_SIGNATURES


def _normalize_filename(filename: str) -> str:
    """
    Normaliza el nombre de archivo para facilitar la detección.

    Ejemplo:
        "12.1_Nómina_Banorte_dic_23_TO..." 
        ->
        "12 1 nomina banorte dic 23 tog..."

    Se eliminan acentos y caracteres no alfanuméricos,
    conservando únicamente separadores de palabras.
    """

    if not filename:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        filename,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.upper()

    text = re.sub(
        r"[^A-Z0-9]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _build_filename_signature_index() -> list[tuple[str, str]]:
    """
    Construye un índice de búsqueda a partir del catálogo.

    Cada elemento contiene:

        (
            keyword_normalized,
            bank_key,
        )

    Las palabras clave más largas se colocan primero para evitar
    que una coincidencia corta opaque a una más específica.

    Ejemplo:

        "BANCO MERCANTIL DEL NORTE"
        debe evaluarse antes que
        "BANORTE"
    """

    signatures: list[tuple[str, str]] = []

    for bank_key, bank_data in BANK_SIGNATURES.items():

        keywords = bank_data.get(
            "filename_keywords",
            [],
        )

        for keyword in keywords:

            normalized_keyword = _normalize_filename(
                keyword
            )

            if not normalized_keyword:
                continue

            signatures.append(
                (
                    normalized_keyword,
                    bank_key,
                )
            )

    signatures.sort(
        key=lambda item: len(item[0]),
        reverse=True,
    )

    return signatures


FILENAME_SIGNATURE_INDEX = (
    _build_filename_signature_index()
)


def detect_by_filename(
    filename: str,
) -> str | None:
    """
    Detecta el banco a partir del nombre del archivo.

    La búsqueda se realiza contra las firmas declaradas
    en BANK_SIGNATURES["<bank>"]["filename_keywords"].

    Ejemplos válidos:

        "12.1_Nómina_Banorte_dic_23.pdf"
            -> "banorte"

        "estado_cuenta_BBVA_enero.pdf"
            -> "bbva"

        "2025_CITIBANAMEX_cuenta.pdf"
            -> "banamex"

    Si no encuentra una firma conocida, devuelve None.
    """

    normalized_filename = _normalize_filename(
        filename
    )

    if not normalized_filename:
        return None

    for keyword, bank_key in FILENAME_SIGNATURE_INDEX:

        pattern = rf"(?<![A-Z0-9]){re.escape(keyword)}(?![A-Z0-9])"

        if re.search(
            pattern,
            normalized_filename,
        ):
            return bank_key

    return None