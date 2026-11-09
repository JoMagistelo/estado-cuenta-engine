"""Recover labelled/positioned SPEI fields only when explicitly normalizing.

Bank parsers and the shared legacy extractor are deliberately independent.
Rules describe formats, never actual payments. No network or workbook access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cep.catalog import ALIASES, account_identifier, bank_code, clabe_bank, identifier, valid_clabe
from cep.spei_classifier import Classification, RECEIVED, RECOVERY_TRACKING_LABEL, RETURNED, SENT
from exporters.excel.cells import get
from utils.spei_metadata import extract_spei_metadata, valid_tracking
from utils.statement_dates import text_key


RECOVERABLE_FIELDS = frozenset({
    "Clave de Rastreo", "Referencia", "Referencia SPEI", "Referencia Original",
    "Cuenta del Beneficiario", "CLABE del Beneficiario", "Cuenta del Ordenante",
    "CLABE del Ordenante", "Banco del Beneficiario", "Banco Emisor",
    "Código Banco Beneficiario", "Código Plaza/Producto CLABE",
})
TOKEN = re.compile(r"[A-Z0-9][A-Z0-9._/-]{2,39}(?![A-Z0-9._/-])", re.I)
NUMBER = (
    r"([0-9]+(?:[ -][0-9]+)*)(?![A-Z0-9]|[ -]+[0-9])"
    r"(?=\s*[-—_]*\s*(?:[,.;)\]]|CLAVE\b|CVE\b|CLV\b|RAST|REF\b|REFERENCIA\b|SPE[IL!1]\b|"
    r"AL\b|DEL?\b|CON\b|RFC\b|NOM(?:BRE)?\b|BENEF|BCO\b|HORA\b|BANCO\b|EMISOR|RECEPTOR|ORDENANTE|$))"
)


def recovery_bank(value) -> str:
    """Statement family aliases, independent of the official bank catalogue."""
    name = text_key(value)
    name = re.sub(r"\s+(?:2|OCR)$", "", name)
    return bank_code(name)


def participant_code(value) -> str:
    code = bank_code(value)
    number = str(value).strip()
    # Banorte's BCO:0002 means the three-digit institution 002. It is
    # neither a five-digit CEP code nor a branch number.
    return code or (bank_code(number[1:]) if re.fullmatch(r"0[0-9]{3}", number) else "")


def _bank_prefix(text):
    text = text.lstrip(" :.-")
    number = re.match(r"([0-9]{1,5})(?![A-Z0-9])", text)
    if number and participant_code(number[1]):
        return participant_code(number[1])
    for name in sorted(ALIASES, key=len, reverse=True):
        if re.match(re.escape(name) + r"(?![A-Z0-9])", text):
            return ALIASES[name]
    return ""


def _structured_text(text, bank):
    text = text_key(text)
    if bank == "40072":
        # Banorte places the bank-authored REFERENCIA/CVE RAST footer AFTER
        # the sender's memo. Keep that footer, without scanning the memo.
        start = re.search(r"\bCONCEPTO\s*:", text)
        if start:
            footer = re.search(
                r"\bREFERENCIA\s*:\s*[0-9]{1,20}\s+(?:CVE|CLAVE|CLV)\.?\s*(?:DE\s+)?RA", text[start.end():])
            return (text[:start.start()] + "\n" + text[start.end() + footer.start():]
                    if footer else text[:start.start()])
    return re.split(r"\bCONCEPTO(?:\s+DEL?\s+PAGO)?(?:\s*:|\s+)", text, maxsplit=1)[0]


@dataclass
class RecoveredMetadata:
    tracking: str = ""
    reference: str = ""
    destination: str = ""
    origin: str = ""
    bank: str = ""
    notes: list[str] = field(default_factory=list)


def _unique(values, label, notes):
    values = set(filter(None, values))
    if len(values) > 1:
        notes.append(f"{label}: varias candidatas; no se elige una automáticamente")
    return next(iter(values)) if len(values) == 1 else ""


def _tracking(text):
    values = set()
    for label in RECOVERY_TRACKING_LABEL.finditer(text):
        tail = text[label.end():]
        match = TOKEN.match(tail)
        if not match:
            continue
        value = match[0].rstrip("./-")
        # Whitespace in these printed channel prefixes is a field boundary
        # error. Do not replace I/1, O/0 or other characters in an identifier.
        split = re.match(r"((?:MBAN|BNET|BMOV))\s+([0-9]{8,32})(?![0-9])", tail)
        if split:
            value = split[1] + split[2]
        wrapped = re.match(r"([A-Z0-9]{3,16})\s+([0-9]{8,32})\s*(?=RFC\b|HORA\b|REF\b|$)", tail)
        if wrapped and any(c.isalpha() for c in wrapped[1]) and len(wrapped[1] + wrapped[2]) <= 40:
            value = wrapped[1] + wrapped[2]
        if valid_tracking(value):
            values.add(value)
    return values


def _bbva(text, result):
    """BBVA's printed block: heading, memo/reference, account, tracking, name."""
    lines = [s.strip() for s in text_key(text).splitlines()
             if s.strip() and not re.fullmatch(r"NO\.?\s+DE", s.strip())]
    heading = re.match(r"^SPE[IL!1]\s+(ENVIADO|RECIBIDO|DEVUELTO)\s*(.*)", lines[0]) if lines else None
    if not heading:
        return set(), set(), set()
    bank = _bank_prefix(re.sub(r"^(?:A|DE)\s+", "", heading[2]))
    if bank:
        result.bank = bank
    if heading[1] == "DEVUELTO":
        return set(), set(), set()
    accounts, tracking, references = set(), set(), set()
    if len(lines) >= 4:
        value = re.sub(r"[ -]", "", lines[2])
        key = re.sub(r"\s+", "", lines[3])
        # BBVA prints the account left-padded to 20 positions with 00.
        # Positional evidence also covers cards and imperfect CLABEs; their
        # checksum must not suppress an independently printed tracking key.
        if re.fullmatch(r"00[0-9]{18}|[0-9]{16,18}", value) and valid_tracking(key):
            account = value[2:] if len(value) == 20 else value
            if key != account:
                accounts.add(account)
                tracking.add(key)
                reference = re.match(r"([0-9]{7})(?![0-9])", lines[1])
                if reference:
                    references.add(reference[1])
    elif len(lines) == 1:
        # Flattened exports retain the 00-prefixed 20-digit account + key.
        pairs = set(re.findall(r"(?<![A-Z0-9])00([0-9]{18})\s+"
                               r"([A-Z0-9][A-Z0-9._/-]{3,39})(?![A-Z0-9._/-])", lines[0]))
        pairs = {(a, k.rstrip(".")) for a, k in pairs if valid_tracking(k) and a != k}
        if len(pairs) == 1:
            account, key = next(iter(pairs))
            accounts.add(account)
            tracking.add(key)
    return accounts, tracking, references


def extract_metadata(row: dict, classification: Classification) -> RecoveredMetadata:
    result = RecoveredMetadata()
    if not classification.spei:
        return result
    bank = recovery_bank(get(row, "Banco"))
    source = get(row, "Concepto") or get(row, "Concepto Original") or ""
    text = _structured_text(source, bank)
    flat = re.sub(r"\s+", " ", text)
    tracking = _tracking(text)
    references = set(re.findall(
        r"\b(?:REFERENCIA(?:\s+NUMERICA)?|REF\.?)\s*[:#=-]?\s*([0-9]{1,20})(?![0-9])", text))
    if bank == "40012":
        accounts, positioned_tracking, positioned_refs = _bbva(source, result)
        # The second line is the user's memo: only the positioned block can
        # provide BBVA metadata. Label-like text in that memo is not evidence.
        tracking, references = positioned_tracking, positioned_refs
        value = _unique(accounts, "Cuenta SPEI", result.notes)
        if classification.label == SENT:
            result.destination = value
        elif classification.label == RECEIVED:
            result.origin = value
        old = extract_spei_metadata(str(get(row, "Banco", "")), source)
        if not tracking and not accounts and "\n" not in str(source):
            tracking.update(_tracking(text))
            references.update(re.findall(
                r"\b(?:REFERENCIA(?:\s+NUMERICA)?|REF\.?)\s*[:#=-]?\s*([0-9]{1,20})(?![0-9])", text))
            if old.clabe:
                if classification.label == SENT:
                    result.destination = old.clabe
                elif classification.label == RECEIVED:
                    result.origin = old.clabe
    if bank == "40072":
        prefix = re.match(r"^\s*([A-Z0-9][A-Z0-9._/-]{3,39})\s+SPE[IL!1]\s+RECIBID[O0]", text)
        if prefix and valid_tracking(prefix[1]):
            if not tracking:
                tracking.add(prefix[1])
            elif prefix[1] not in tracking:
                result.notes.append("Rastreo del encabezado difiere del campo etiquetado; revisar concepto")
        reverse_ref = re.search(r"\bSPE[IL!1]\s+([0-9]{1,7})\s*=\s*REFERENCIA", flat)
        if reverse_ref:
            references.add(reverse_ref[1])
    result.tracking = _unique(tracking, "Clave de Rastreo", result.notes)
    result.reference = _unique(references, "Referencia SPEI", result.notes)
    if bank == "40012" and (accounts or "\n" in str(source)):
        return result

    role_dest = r"(?:DEL?\s+)?(?:BENEFICIARI[AO]|BENEF\.?|DESTINO|RECEPTOR[AO]?)"
    role_origin = r"(?:DEL?\s+)?(?:ORDENANTE|ORIGEN|EMISOR[AO]?)"
    account_label = r"(?:CTA[.,]?\s*/\s*CLABE|CLABE(?:\s+INTERBANCARIA)?|CUENTA|CTA[.,]?)"
    for role, attribute in ((role_dest, "destination"), (role_origin, "origin")):
        found = set()
        for pattern in (rf"\b{account_label}\s*{role}\s*[:#=.-]?\s*[\[(]?\s*{NUMBER}",
                        rf"\b{role}\s+{account_label}\s*[:#=.-]?\s*[\[(]?\s*{NUMBER}"):
            found.update(re.sub(r"[ -]", "", m[1]) for m in re.finditer(pattern, flat))
        value = _unique(found, "Cuenta SPEI " + attribute, result.notes)
        if value:
            setattr(result, attribute, value)
    # The bank-specific direction supplies the role of an unqualified account
    # (Santander: A/DE LA CUENTA; Azteca: CUENTA; Banorte: CTA/CLABE).
    unqualified = set()
    for match in re.finditer(rf"\b{account_label}\s*[:#=.-]?\s*[\[(]?\s*{NUMBER}", flat):
        value = re.sub(r"[ -]", "", match[1])
        if len(value) >= 5 and set(value) != {"0"}:
            unqualified.add(value)
    value = _unique(unqualified, "Cuenta SPEI sin rol", result.notes)
    if classification.label == SENT and not result.destination:
        result.destination = value
    elif classification.label == RECEIVED and not result.origin:
        result.origin = value

    patterns = [r"\bBCO\s*:\s*"]
    if classification.label == SENT:
        patterns += [r"\b(?:ENVIADO|PAGO\s+INTERBANCARIO)\s+A\s+",
                     r"\b(?:BANCO\s+(?:DEL?\s+)?)?RECEPTOR[AO]?\s*:\s*"]
    elif classification.label == RECEIVED:
        patterns += [r"\b(?:RECIBIDO|PAGO\s+RECIBIDO)\s+DE\s+",
                     r"\b(?:BANCO\s+(?:DEL?\s+)?)?EMISOR[AO]?\s*:\s*"]
    banks = {_bank_prefix(flat[m.end():]) for pattern in patterns for m in re.finditer(pattern, flat)} - {""}
    if result.bank:
        banks.add(result.bank)
    explicit = _unique(banks, "Banco SPEI", result.notes)
    inferred = clabe_bank(result.destination if classification.label == SENT else result.origin)
    if explicit and inferred and explicit != inferred:
        result.notes.append("Banco SPEI explícito contradice la CLABE; revisar ambos datos")
    result.bank = explicit or (inferred if not banks else "")
    return result


def _missing(value):
    return not identifier(value) or text_key(value) in {"-", "SIN DATOS", "SIN DATO", "NO IDENTIFICADO"}


def recover_missing(row: dict, classification: Classification) -> tuple[dict, list[str]]:
    """Fill missing fields, preserving all existing usable/manual identifiers."""
    found = extract_metadata(row, classification)
    changes, notes = {}, list(found.notes)

    def offer(column, value, *, equivalent=identifier):
        if not value:
            return
        previous = get(row, column)
        if _missing(previous):
            changes[column] = value
        elif equivalent(previous) != equivalent(value):
            notes.append(f"{column}: difiere del concepto; se conserva el dato existente")

    offer("Clave de Rastreo", found.tracking)
    if found.reference:
        offer("Referencia SPEI", found.reference)
        # Statement references and payment references are distinct in BBVA.
        if recovery_bank(get(row, "Banco")) != "40012":
            offer("Referencia", found.reference)
    for role, account in (("Beneficiario", found.destination), ("Ordenante", found.origin)):
        offer("Cuenta del " + role, account, equivalent=account_identifier)
        if valid_clabe(account):
            offer("CLABE del " + role, account, equivalent=account_identifier)
        elif len(account) == 18:
            notes.append(f"Cuenta del {role}: no valida como CLABE; se conserva para consulta/revisión")
    if classification.label == SENT:
        offer("Banco del Beneficiario", found.bank, equivalent=bank_code)
        offer("Código Banco Beneficiario", found.bank, equivalent=bank_code)
        if valid_clabe(found.destination):
            offer("Código Plaza/Producto CLABE", found.destination[3:6])
    elif classification.label == RECEIVED:
        offer("Banco Emisor", found.bank, equivalent=bank_code)
    if classification.label == RETURNED:
        notes.append("Devolución: no se presume que el abono sea un nuevo SPEI recibido")
    return changes, notes
