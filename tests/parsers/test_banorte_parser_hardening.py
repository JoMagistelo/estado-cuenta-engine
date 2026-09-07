from __future__ import annotations

from typing import Any

from parsers.banorte.extractors.movimientos import DATE_PREFIX_PATTERN
from parsers.banorte.utils.movement_date_hardening import (
    normalize_ambiguous_movement_date_token,
    normalize_ambiguous_movement_date_words,
)
from parsers.banorte.utils.words_after_last_movement import (
    extract_date_prefix as extract_cutoff_date_prefix,
)


def _word(text: str) -> dict[str, Any]:
    return {
        "text": text,
        "x0": 50.4,
        "x1": 224.0,
        "top": 390.0,
        "bottom": 399.0,
        "doctop": 3758.0,
        "page": 5,
    }


def test_numeric_trace_glued_to_banorte_date_becomes_unambiguous() -> None:
    original = "22-JUN-2650114599TRANSBPI07617702"

    normalized = normalize_ambiguous_movement_date_token(original)

    assert normalized == "22-JUN-26 50114599TRANSBPI07617702"

    movement_match = DATE_PREFIX_PATTERN.match(normalized)
    assert movement_match is not None
    assert movement_match.group("date").upper() == "22-JUN-26"

    # La utilidad de recorte histórica aceptaba \d{2,4}; el espacio evita que
    # los primeros dígitos del folio puedan convertirse en un falso año 2650.
    assert extract_cutoff_date_prefix(normalized) == "22-JUN-26"


def test_normalization_does_not_mutate_original_spatial_word() -> None:
    original_word = _word("22-JUN-2650114599TRANSBPI08143682")

    normalized_words = normalize_ambiguous_movement_date_words([original_word])

    assert original_word["text"] == "22-JUN-2650114599TRANSBPI08143682"
    assert normalized_words[0] is not original_word
    assert normalized_words[0]["text"] == "22-JUN-26 50114599TRANSBPI08143682"

    for key in ("x0", "x1", "top", "bottom", "doctop", "page"):
        assert normalized_words[0][key] == original_word[key]


def test_existing_alphanumeric_glued_date_behavior_is_preserved() -> None:
    # Este formato ya es soportado por el parser Banorte y no debe reescribirse.
    original_word = _word("25-JUN-24COMPRA")

    normalized_words = normalize_ambiguous_movement_date_words([original_word])

    assert normalized_words[0] is original_word
    assert normalized_words[0]["text"] == "25-JUN-24COMPRA"


def test_existing_four_digit_year_behavior_is_preserved() -> None:
    assert normalize_ambiguous_movement_date_token("22-JUN-2026") == "22-JUN-2026"
    assert normalize_ambiguous_movement_date_token("22-JUN-2026COMPRA") == (
        "22-JUN-2026COMPRA"
    )
    # Ante un caso numérico verdaderamente ambiguo que ya empieza por un año
    # plausible de cuatro cifras, se prefiere no modificar datos existentes.
    assert normalize_ambiguous_movement_date_token("22-JUN-20265011TRACE") == (
        "22-JUN-20265011TRACE"
    )


def test_regular_date_and_unrelated_numeric_text_are_untouched() -> None:
    assert normalize_ambiguous_movement_date_token("22-JUN-26") == "22-JUN-26"
    assert normalize_ambiguous_movement_date_token("50114599TRANSBPI07617702") == (
        "50114599TRANSBPI07617702"
    )
    assert normalize_ambiguous_movement_date_token("DETALLE DE MOVIMIENTOS") == (
        "DETALLE DE MOVIMIENTOS"
    )
