"""Offline, generic SPEI vocabulary. Contains no statement examples or identities.

Only Normalizar invokes this classifier. Amounts resolve ambiguous vocabulary;
an ordinary credit by itself is never evidence of a SPEI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cep.catalog import bank_code, identifier
from exporters.excel.cells import get
from utils.spei_metadata import valid_tracking
from utils.statement_dates import text_key


CLASSIFICATION_COLUMN = "Clasificación SPEI"
SENT, RECEIVED, RETURNED = "SPEI Enviado", "SPEI Recibido", "SPEI Devuelto"
INTERNAL, TRANSFER = "Transferencia cuentas del mismo banco", "Traspaso"
RECOVERY_TRACKING_LABEL = re.compile(
    r"\b(?:(?:CLAVE|CVE|CLV)\.?\s*(?:DE\s+)?"
    r"(?:RA[S5][T7](?:RE[O0Q]|R)?|RAS\s+R)\.?|RA[S5][T7]RE[O0Q])"
    r"\s*(?:SPE[IL!1]\b\s*)?[:#=.,-]?\s*[\[(]?\s*", re.I,
)

# The supplied classifier's 57 rows: generic keywords only, including its OCR
# variants and duplicate/ambiguous entries. Never bundle payment examples.
CLASSIFIER_RULES = (
    ("ABONO TRANSFERENCIA SPEI", "ABONO TRANSFERENCIA SPE!", RECEIVED),
    ("ABONO TRANSFERENCIA SPEI", "ABONO TRANSFERENCIA SPEI", RECEIVED),
    ("ABONO X DEV DE OP", "ABONO X DEV DE OP", RETURNED),
    ("PAGO INTERBANCARIO", "AGO PAGO INTERBANC", SENT),
    ("PAGO RECIBIDO", "AGO PAGO RECI", RECEIVED),
    ("TRASPASO REF", "AGO TRASPASO", TRANSFER),
    ("CARGO TRANSF RAPID", "CARGO TRANSF RAPID", INTERNAL),
    ("CGO", "CGO", SENT),
    ("COMPENSACION DESFASE SPEI", "COMPENSACION DESFASE SPEI", RECEIVED),
    ("COMPRA ORDEN DE PAGO SPEI", "COMPR.A ORDEN DE PAGO SPE", SENT),
    ("COMPRA ORDEN DE PAGO SPEI", "COMPRA 0RDEN DE PAG0 SPEI", SENT),
    ("COMPRA ORDEN DE PAGO SPEI", "COMPRA 0RDEN DE PAG0 SPEl", SENT),
    ("COMPRA ORDEN DE PAGO SPEI", "COMPRA ORDEN DE PAG0 SPEI", SENT),
    ("COMPRA ORDEN DE PAGO SPEI", "COMPRA ORDEN DE PAGO SPEI", SENT),
    ("DEP TERCERO HOST T", "DEP TERCERO HOST T", INTERNAL),
    ("DEV.SPE:", "DEV.SPE:", RETURNED),
    ("DEV.SPEI", "DEV.SPEI", RETURNED),
    ("PAGO RECIBIDO", "ENE PAGO RECI", RECEIVED),
    ("ENVIO SPEI", "ENVIO SPEI", SENT),
    ("ENVIO TRANSFERENCIA SPEI", "ENVIO TRANSFERENCIA SPEI", SENT),
    ("PAGO INTERBANCARIO", "JUL PAGO INTERBANC", SENT),
    ("PAGO INTERBANCARIO", "JUN PAGO INTERBANC", SENT),
    ("PAGO RECIBIDO", "JUN PAGO RECI", RECEIVED),
    ("PAGO RECIBIDO", "MAR PAGO RECI", RECEIVED),
    ("PAGO INTERBANCARIO", "NOV PAGO INTERBANC", SENT),
    ("PAGO RECIBIDO", "NOV PAGO RECI", RECEIVED),
    ("PAGO RECIBIDO", "OCT PAGO RECI", RECEIVED),
    ("ORDEN DE TRANSFERENCIA SPEI RECEPTOR", "ORDEN DE TRANSFERENCIA SPEI RECEPTOR", SENT),
    ("PAGO A TERCEROS", "PAGO A TERCEROS", INTERNAL),
    ("PAGO CUENTA DE TERCERO", "PAGO CUENTA DE TERCERO", INTERNAL),
    ("PAGO INTERBANCARIO", "PAGO INTERBANCARIO", SENT),
    ("PAGO INTERBANCARIO", "PAGO INTERBANCARIO", RECEIVED),
    ("PAGO INTERBANCARIO", "PAGO INTERBANÇARIO", SENT),
    ("PAGO RECIBIDO", "PAGO RECIBIDO", RECEIVED),
    ("PAGO RECIBIDO DE", "PAGO RECIBIDO DE", INTERNAL),
    ("PAGO TRANSF RAPIDA SPEI", "PAGO TRANSF RAPIDA SPEI", SENT),
    ("PAGO TRANSFERENCIA SPEI", "PAGO TRANSFERENCIA SPE ", SENT),
    ("PAGO TRANSFERENCIA SPEI", "PAGO TRANSFERENCIA SPE!", SENT),
    ("PAGO TRANSFERENCIA SPEI", "PAGO TRANSFERENCIA SPEI", SENT),
    ("PAGO TRANSFERENCIA SPEI", "PAGO TRANSFERENCIA SPEl", SENT),
    ("SPEI DEVUELTO", "SPEI DEVUELTO", RETURNED),
    ("SPEI ENVIADO", "SPEI ENVIADO", SENT),
    ("SPEI RECIBIDO", "SPEI RECIBIDO", RECEIVED),
    ("TRANSFERENCIA BPI ", "TRANSFERENCIA BPI ", INTERNAL),
    ("Transferencia recibida", "Transferencia recibida", INTERNAL),
    ("TRANSFERENCIA SPEI", "TRANSFERENCIA SPEI", SENT),
    ("TRANSFERENCIA SPEI", "TRANSFERENCIA SPEI", RECEIVED),
    ("TRANSFERENCIA SPEI A SU FAVOR", "TRANSFERENCIA SPEI A SU FAVOR", RECEIVED),
    ("TRANSFERENCIA SPEI", "TRANSFEREÑCIA SPEI", RECEIVED),
    ("TRASP FONDOS", "TRASP FOND0S", TRANSFER),
    ("TRASP FONDOS", "TRASP FONDOS", TRANSFER),
    ("TRASPASO", "TRASPASO", TRANSFER),
    ("TRASPASO CUENTAS PROPIAS", "TRASPASO CUENTAS PROPIAS", TRANSFER),
    ("TRASPASO DE INVERSION", "TRASPASO DE INVERSION", TRANSFER),
    ("TRASPASO ENTRE CUENTAS", "TRASPASO ENTRE CUENTAS", TRANSFER),
    ("TRASPASO REF", "TRASPASO REE", TRANSFER),
    ("TRASPASO REF", "TRASPASO REF", TRANSFER),
)


def keyword_text(value) -> str:
    """Search-only cleanup; never apply OCR substitutions to identifiers."""
    text = text_key(value)
    text = re.sub(r"\bSPE[!1L](?=\W|$)", "SPEI", text)
    return re.sub(r"\s+", " ", text).strip()


def amount_direction(row) -> str:
    # Import lazily: queries also consult classification on normalized files.
    from cep.queries import amount
    debit, credit = amount(get(row, "Cargo")), amount(get(row, "Abono"))
    return ("ENVIADO" if debit else "RECIBIDO") if (
        debit is not None and credit is not None and bool(debit) != bool(credit)) else ""


@dataclass(frozen=True)
class Classification:
    label: str = ""
    rule: str = ""
    notes: tuple[str, ...] = ()

    @property
    def spei(self):
        return self.label in {SENT, RECEIVED, RETURNED, "SPEI por revisar"}

    @property
    def direction(self):
        return "ENVIADO" if self.label == SENT else "RECIBIDO" if self.label == RECEIVED else ""


def _pattern(phrase):
    phrase = keyword_text(phrase)
    # Some headings concatenate RECIBIDO/DEVUELTO with the institution, and
    # several catalogue variants deliberately end in a truncated word.
    end = r"(?![A-Z0-9])" if phrase == "CGO" else ""
    return re.compile(r"(?<![A-Z0-9])" + re.escape(phrase) + end)


_RULE_PATTERNS = tuple((phrase, label, _pattern(phrase))
                       for canonical, variant, label in CLASSIFIER_RULES
                       for phrase in dict.fromkeys((canonical, variant)))


def classify_spei(row: dict) -> Classification:
    text = keyword_text(get(row, "Concepto") or get(row, "Concepto Original"))
    # User-authored payment memos must not reclassify the bank's heading.
    text = re.split(r"\bCONCEPTO(?:\s+DEL?\s+PAGO)?\s*:", text, maxsplit=1)[0]
    hits = [(m.start(), -len(keyword_text(phrase)), phrase, label)
            for phrase, label, pattern in _RULE_PATTERNS if (m := pattern.search(text))]
    direction = amount_direction(row)
    raw_key = get(row, "Clave de Rastreo")
    has_cell = bool(identifier(raw_key)) or (isinstance(raw_key, (int, float)) and not isinstance(raw_key, bool))
    has_labelled_key = any(
        valid_tracking(match[0])
        for label in RECOVERY_TRACKING_LABEL.finditer(text)
        if (match := re.match(r"[A-Z0-9][A-Z0-9._/-]{2,39}(?![A-Z0-9._/-])", text[label.end():])))
    has_key = has_cell or has_labelled_key
    if not hits:
        if has_key or re.search(r"\bSPEI\b", text):
            label = SENT if direction == "ENVIADO" else RECEIVED if direction == "RECIBIDO" else "SPEI por revisar"
            return Classification(label, "Clave de rastreo / SPEI explícito",
                                  () if direction else ("SPEI: cargo/abono ambiguos",))
        return Classification()
    hits.sort()
    first = hits[0][0]
    # A return marker in the operation heading wins over the original SPEI's
    # direction. Later occurrences in a memo are not return evidence.
    heading = [hit for hit in hits if hit[0] <= first + 8]
    returned = next((h for h in heading if h[3] == RETURNED), None)
    if returned:
        return Classification(RETURNED, returned[2], ("Devolución SPEI: revisar datos de la operación original",))
    labels = {h[3] for h in heading}
    # Banamex uses PAGO RECIBIDO DE both for internal transfers and incoming
    # interbank payments. A named external bank or explicit rastreo disambiguates.
    if INTERNAL in labels and RECEIVED in labels:
        match = re.search(r"PAGO RECIBIDO DE (.+?)(?: POR ORDEN| SU REF| CTA| REF[ .:]|$)", text)
        other_bank = bank_code(match[1].strip()) if match else ""
        if has_key or (other_bank and other_bank != bank_code(get(row, "Banco"))):
            labels.discard(INTERNAL)
        else:
            labels = {INTERNAL}
    if SENT in labels and RECEIVED in labels:
        chosen = SENT if direction == "ENVIADO" else RECEIVED if direction == "RECIBIDO" else "SPEI por revisar"
    else:
        chosen = next(h[3] for h in heading if h[3] in labels)
    notes = []
    if chosen in {INTERNAL, TRANSFER} and has_key:
        chosen = SENT if direction == "ENVIADO" else RECEIVED if direction == "RECIBIDO" else "SPEI por revisar"
        notes.append("Clasificación interna con clave de rastreo: se conserva como SPEI para revisión")
    expected = "ENVIADO" if chosen == SENT else "RECIBIDO" if chosen == RECEIVED else ""
    if expected and direction != expected:
        notes.append("Clasificación SPEI contradice cargo/abono; revisar sentido e importe")
    if chosen == "SPEI por revisar":
        notes.append("SPEI: cargo/abono ambiguos")
    if heading[0][2] == "CGO":
        notes.append("CGO: clasificado por catálogo; el concepto puede no contener datos de rastreo")
    previous = text_key(get(row, "Tipo de Operación"))
    if previous in {text_key(SENT), text_key(RECEIVED), text_key(RETURNED)} and previous != text_key(chosen):
        notes.append("Clasificación del catálogo difiere de Tipo de Operación; revisar movimiento")
    return Classification(chosen, heading[0][2], tuple(notes))


def add_classifier_catalog(workbook):
    """Expose the bundled generic vocabulary, never the training concepts."""
    from exporters.excel.writer import write_table_sheet
    name = "Clasificador SPEI"
    columns = ("Palabra sin errores", "Palabra con errores", "Clasificación")
    if name in workbook:
        ws = workbook[name]
        if tuple(c.value for c in ws[1]) != columns:
            return
        workbook.remove(ws)
    ws = workbook.create_sheet(name)
    write_table_sheet(ws, [dict(zip(columns, rule)) for rule in CLASSIFIER_RULES])
