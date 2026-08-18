from __future__ import annotations

from catalog.bank_signatures import BANK_SIGNATURES
from extractors.clabe_extractor import extract_clabe_prefixes


# Índice invertido:
# "012" -> "bbva"
CLABE_PREFIX_TO_BANK: dict[str, str] = {
    prefix: bank_key
    for bank_key, bank_data in BANK_SIGNATURES.items()
    for prefix in bank_data.get("clabe_prefixes", [])
}


def detect_by_clabe(text: str) -> str | None:
    """
    Detecta banco utilizando prefijos CLABE.

    Ejemplo:
        012 -> bbva
        044 -> scotiabank
    """

    prefixes = extract_clabe_prefixes(text)

    for prefix in prefixes:

        bank_key = CLABE_PREFIX_TO_BANK.get(prefix)

        if bank_key:
            return bank_key

    return None