from __future__ import annotations

import re
from typing import Iterable

from models.movimiento import Movimiento


# El banco y el ordenante se identifican por etiquetas, nunca por nombres fijos.
# Las líneas OCR pueden separar «POR» de «ORDEN DE» o unir REF/CTA al nombre.
_RECEIVED_PAYMENT_RE = re.compile(
    r"\bPAGO\s+RECIBIDO\s+DE\s+(?P<bank>.+?)\s+POR\s+ORDEN\s+DE\s+"
    r"(?P<party>.+?)"
    r"(?=\s*(?:"
    r"REF\.?\s*[:#-]?\s*[A-Z0-9]|"
    r"CTA\.?\s*ORDENANTE\b|CUENTA\s+ORDENANTE\b|"
    r"CLABE\b|(?:TRANSFERENCIA\s+)?RASTREO\b|"
    r"CAJA\b|AUT(?:ORIZACION)?\b|HORA\b|SUC(?:URSAL)?\b"
    r")|$)",
    re.IGNORECASE | re.DOTALL,
)
_ORDERING_ACCOUNT_RE = re.compile(
    r"\b(?:CTA\.?\s*ORDENANTE|CUENTA\s+ORDENANTE)\s*[:#-]?\s*"
    r"(\d{8,20})(?!\d)",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(r"\bREF\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)
_TRACKING_RE = re.compile(
    r"\b(?:CLAVE\s+(?:DE\s+)?)?RASTREO\s*[:#.-]?\s*"
    r"([A-Z0-9][A-Z0-9_-]{3,})\b",
    re.IGNORECASE,
)
_CASH_DESK_RE = re.compile(r"\bCAJA\.?\s*[:#-]?\s*(\d+)\b", re.IGNORECASE)
_AUTH_RE = re.compile(r"\bAUT(?:ORIZACION)?\.?\s*[:#-]?\s*(\d+)\b", re.IGNORECASE)


def _clean_label_value(value: str, *, max_length: int) -> str | None:
    cleaned = " ".join(value.split()).strip(" ,.;:-")
    if not cleaned or len(cleaned) > max_length:
        return None
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", cleaned):
        return None
    return cleaned


def _received_payment(concept: str | None) -> tuple[str, str] | None:
    if not concept:
        return None
    match = _RECEIVED_PAYMENT_RE.search(concept)
    if not match:
        return None
    bank = _clean_label_value(match.group("bank"), max_length=90)
    party = _clean_label_value(match.group("party"), max_length=120)
    return (bank, party) if bank and party else None


def extract_ordering_party(concept: str | None) -> str | None:
    """Obtiene el ordenante de cualquier «PAGO RECIBIDO DE [banco]» válido."""
    payment = _received_payment(concept)
    return payment[1] if payment else None


def _preferred_numeric(text: str, pattern: re.Pattern[str]) -> str | None:
    """Ignora marcadores OCR de cero y elige un identificador legible."""
    values = pattern.findall(text)
    return next((value for value in reversed(values) if int(value) != 0), None)


def enrich_banamex_beneficiaries(movements: Iterable[Movimiento]) -> None:
    """Completa los metadatos de pagos recibidos sin alterar el movimiento.

    En el modelo actual «beneficiario» representa la contraparte y «sucursal»
    contiene el banco de origen cuando está explícito. El código SUC impreso no
    sustituye al banco; el resto de campos previamente confirmados se conserva.
    """
    for movement in movements:
        for source in (
            getattr(movement, "concepto_original", None),
            getattr(movement, "concepto", None),
        ):
            payment = _received_payment(source)
            if payment is None:
                continue
            bank, party = payment
            movement.beneficiario = movement.beneficiario or party
            # Para este tipo de operación, «SUC 0859» es un código y no el banco.
            movement.sucursal = bank

            account_match = _ORDERING_ACCOUNT_RE.search(source)
            if account_match:
                account = account_match.group(1)
                movement.cuenta_beneficiario = movement.cuenta_beneficiario or account
                if len(account) == 18:
                    movement.clabe_beneficiario = movement.clabe_beneficiario or account

            if not movement.referencia:
                reference = _REFERENCE_RE.search(source)
                if reference:
                    movement.referencia = reference.group(1)
            if not movement.clave_rastreo:
                tracking = _TRACKING_RE.search(source)
                if tracking:
                    movement.clave_rastreo = tracking.group(1)

            # A veces OCR imprime «CAJA O AUT O» antes de los valores reales.
            # Se repara únicamente ese marcador ilegible y no un dato válido.
            if not movement.caja or str(movement.caja).upper() in {"O", "0"}:
                movement.caja = _preferred_numeric(source, _CASH_DESK_RE) or movement.caja
            if not movement.autorizacion or str(movement.autorizacion).upper() in {"O", "0"}:
                movement.autorizacion = _preferred_numeric(source, _AUTH_RE) or movement.autorizacion
            break


__all__ = ["enrich_banamex_beneficiaries", "extract_ordering_party"]
