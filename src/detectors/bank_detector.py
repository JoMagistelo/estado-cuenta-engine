from __future__ import annotations

from catalog.bank_signatures import BANK_SIGNATURES
from detectors.clabe_detector import detect_by_clabe
from utils.text_normalizer import normalize_text


def identify_bank_key(raw_text: str) -> str | None:
    """
    Identifica el banco y retorna la clave interna.

    Usa diferentes estrategias:
    - CLABE
    - RFC futuro
    - Keywords futuro
    """

    normalized_text = normalize_text(raw_text)

    return (
        detect_by_clabe(normalized_text)
    )


def identify_bank(raw_text: str) -> str:
    """
    Identifica el banco y retorna nombre visible.
    """

    bank_key = identify_bank_key(raw_text)

    if not bank_key:
        return "Desconocido"

    return BANK_SIGNATURES.get(
        bank_key,
        {}
    ).get(
        "display_name",
        "Desconocido"
    )