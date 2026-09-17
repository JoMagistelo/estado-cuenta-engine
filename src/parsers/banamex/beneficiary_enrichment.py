from __future__ import annotations

import re
from typing import Iterable

from models.movimiento import Movimiento


_ORDERED_BY_RE = re.compile(
    r"\bPOR\s+ORDEN\s+DE\s+(.+?)"
    r"(?=\s+(?:"
    r"REF\.?\s*[:#-]?|"
    r"CTA\.?\s*ORDENANTE\b|"
    r"CUENTA\s+ORDENANTE\b|"
    r"RASTREO\b|"
    r"CAJA\b|AUT\b|HORA\b|SUC\b|"
    r"TRANSFERENCIA\b"
    r")|$)",
    re.IGNORECASE | re.DOTALL,
)


def _normalize_name(value: str) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip(" ,.;:-")
    if not cleaned or len(cleaned) > 120:
        return None
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", cleaned):
        return None
    return cleaned


def extract_ordering_party(concept: str | None) -> str | None:
    """Extrae el ordenante de pagos recibidos Banamex sin depender del banco origen."""

    if not concept:
        return None

    match = _ORDERED_BY_RE.search(str(concept))
    if not match:
        return None
    return _normalize_name(match.group(1))


def enrich_banamex_beneficiaries(movements: Iterable[Movimiento]) -> None:
    """Completa sólo beneficiarios vacíos usando ``POR ORDEN DE``.

    Es una segunda pasada deliberadamente acotada. No sustituye beneficiarios ya
    extraídos por la lógica histórica y no modifica importes, fechas ni conceptos.
    """

    for movement in movements:
        if getattr(movement, "beneficiario", None):
            continue

        for source in (
            getattr(movement, "concepto_original", None),
            getattr(movement, "concepto", None),
        ):
            beneficiary = extract_ordering_party(source)
            if beneficiary:
                movement.beneficiario = beneficiary
                break


__all__ = ["enrich_banamex_beneficiaries", "extract_ordering_party"]
