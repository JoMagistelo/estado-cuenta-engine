"""Conservative SPEI metadata recovery, shared by parsing and Excel repair.

Only explicit field labels and documented bank block positions are evidence.
An account, reference, authorization or arbitrary long number is not a rastreo.
This module contains no statement data and performs no network or file access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cep.catalog import ALIASES, account_identifier, bank_code, identifier, valid_clabe
from utils.statement_dates import text_key


TRACKING_LABEL = re.compile(
    r"\b(?:(?:CLAVE|CVE|CLV)\.?\s*(?:DE\s+)?RAST(?:REO)?\.?|RASTREO)"
    r"\s*(?:SPEI\b\s*)?[:#=.-]?\s*", re.I,
)
TOKEN = re.compile(r"[A-Z0-9][A-Z0-9._/-]*", re.I)
PLACEHOLDERS = {"N/A", "NA", "NONE", "NULL", "SIN DATO", "SIN DATOS", "NO IDENTIFICADO"}


def valid_tracking(value: object) -> bool:
    value = identifier(value)
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{3,39}", value, re.I)
                and any(c.isdigit() for c in value) and text_key(value) not in PLACEHOLDERS)


@dataclass
class SpeiMetadata:
    tracking: str = ""
    reference: str = ""
    account: str = ""
    clabe: str = ""
    bank: str = ""
    direction: str = ""
    notes: list[str] = field(default_factory=list)


def _one(values: set[str], label: str, notes: list[str]) -> str:
    if len(values) > 1:
        notes.append(f"{label}: varias candidatas; requiere revisión")
    return next(iter(values)) if len(values) == 1 else ""


def _labelled_tracking(text: str) -> set[str]:
    values = set()
    for label in TRACKING_LABEL.finditer(text):
        tail = text[label.end():]
        token = TOKEN.match(tail)
        if not token:
            continue
        value = token[0].rstrip(".")
        # OCR sometimes separates a channel prefix from its numeric suffix.
        # Joining is allowed only on a labelled, otherwise numeric value.
        line = tail.splitlines()[0].strip()
        if re.fullmatch(r"(?:BNET|MBAN|BMOV)\s+[0-9 ]{8,36}", line):
            value = re.sub(r"\s+", "", line)
        if valid_tracking(value):
            values.add(value.upper())
    return values


def extract_spei_metadata(bank: str, concept: str | None, original: str | None = None) -> SpeiMetadata:
    result = SpeiMetadata()
    sources = list(dict.fromkeys(str(s) for s in (concept, original) if s))
    # Keep newlines: in BBVA their position identifies the field, not its shape.
    texts = [text_key(s) for s in sources]
    tracking = set().union(*(_labelled_tracking(t) for t in texts)) if texts else set()
    references = set()
    for text in texts:
        references.update(re.findall(r"\b(?:REFERENCIA(?:\s+NUMERICA)?|REF\.?)\s*[:#=-]?\s*([0-9]{1,20})(?![0-9])", text))
        if bank in {"banorte", "banorte_ocr"}:
            match = re.search(r"^\s*([A-Z0-9][A-Z0-9._/-]{3,39})\s+SPEI\s+RECIBIDO\b", text)
            if match and valid_tracking(match[1]):
                tracking.add(match[1])

    if bank_code(bank) == "40012":
        bbva_texts = texts[:1] if texts and re.match(r"^SPEI\s+(ENVIADO|RECIBIDO)", texts[0]) else texts
        for text in bbva_texts:
            lines = [s.strip() for s in text.splitlines() if s.strip()]
            header = re.match(r"^SPEI\s+(ENVIADO|RECIBIDO)\s*(.*)", lines[0]) if lines else None
            if not header:
                continue
            result.direction = header[1]
            for alias in sorted(ALIASES, key=len, reverse=True):
                if re.fullmatch(re.escape(alias) + r"[ .]*", header[2]):
                    result.bank = ALIASES[alias]
                    break
            if len(lines) >= 4:
                # BBVA prints 00 + 18 CLABE digits, then a complete tracking
                # key on the following line. A checksum anchors that position.
                padded = re.fullmatch(r"(?:00)?([0-9]{18})", re.sub(r"[ -]", "", lines[2]))
                value = re.sub(r"\s+", "", lines[3])
                if padded and valid_clabe(padded[1]):
                    result.clabe = padded[1]
                    if valid_tracking(value) and value != result.clabe and not valid_clabe(value):
                        tracking.add(value)
                    ref = re.match(r"([0-9]{7})(?![0-9])", lines[1])
                    if ref:
                        references.add(ref[1])
            elif len(lines) == 1:
                # Historical flattened exports still carry the same adjacent
                # CLABE/rastreo block. Never scan arbitrary numbers elsewhere.
                pairs = [(m[1], m[2]) for m in re.finditer(
                    r"(?<![A-Z0-9])(?:00)?([0-9]{18})\s+([A-Z0-9][A-Z0-9._/-]*)(?![A-Z0-9])", text)
                    if valid_clabe(m[1]) and valid_tracking(m[2]) and not valid_clabe(m[2])]
                if len(set(pairs)) == 1:
                    result.clabe, value = pairs[0]
                    tracking.add(value)
    result.tracking = _one(tracking, "Clave de Rastreo", result.notes)
    result.reference = _one(references, "Referencia", result.notes)
    return result


def enrich_missing_spei_fields(movements, bank: str):
    """Complete metadata only, preserving existing fields and all money/dates."""
    for movement in movements or []:
        found = extract_spei_metadata(bank, getattr(movement, "concepto", None),
                                      getattr(movement, "concepto_original", None))
        if found.tracking and not valid_tracking(getattr(movement, "clave_rastreo", None)):
            movement.clave_rastreo = found.tracking
        if found.reference and not identifier(getattr(movement, "referencia", None)):
            movement.referencia = found.reference
        if found.clabe and not valid_clabe(getattr(movement, "clabe_beneficiario", None)):
            movement.clabe_beneficiario = found.clabe
        if found.bank and not identifier(getattr(movement, "sucursal", None)):
            movement.sucursal = next(name for name, code in ALIASES.items() if code == found.bank)
    return movements
