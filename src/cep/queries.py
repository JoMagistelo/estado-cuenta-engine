"""Prepare the six Banxico fields from original or normalized Engine Excel."""

from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone

from openpyxl import load_workbook

from cep.catalog import account_identifier, bank_code, bank_mentions, clabe_bank, identifier, valid_clabe
from cep.catalog import labelled_bank as _label_bank
from exporters.excel.normalization import _account, get, rows_from_sheet
from utils.spei_metadata import extract_spei_metadata
from utils.statement_dates import full_date, resolve_date, text_key


BANXICO_BATCH_URL = "https://www.banxico.org.mx/cep-scl/inicio.do"


def mexico_today():
    # Mexico City's current civil time is UTC-6. The portable Windows bundle
    # must not require a system IANA database (or a new tzdata dependency).
    return datetime.now(timezone(timedelta(hours=-6))).date()


def amount(value) -> Decimal | None:
    try:
        v = Decimal(str(value or 0).replace("$", "").replace(",", "").strip())
        if not v.is_finite() or v < 0 or v != v.quantize(Decimal("0.01")):
            return None
        return v
    except (ValueError, InvalidOperation):
        return None


def _valid_card16(value: str) -> bool:
    """Check a 16-digit card identifier without treating it as an 18-digit CLABE."""
    if not re.fullmatch(r"[0-9]{16}", value) or len(set(value)) < 2:
        return False
    total = 0
    for index, char in enumerate(value):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _destination(value):
    """Select only a supported Banxico account identifier, without modifying Excel.

    Some bank statements print a debit-card number as 00 + its 16 digits.
    Strip 00 only when the 18-digit value is NOT a valid CLABE and the
    remaining 16 digits pass the Luhn checksum. Do not guess any other digits.
    """
    s = account_identifier(value)
    if len(s) == 18:
        # All-zero placeholders can satisfy the CLABE checksum by accident.
        if len(set(s)) == 1:
            return ""
        if valid_clabe(s):
            return s
        if s.startswith("00") and _valid_card16(s[2:]):
            return s[2:]
        return ""
    return s if re.fullmatch(r"[0-9]{10}|[0-9]{16}", s) else ""


@dataclass
class CepQuery:
    row: int
    statement: str
    filename: str
    movement: str
    candidate: bool
    direction: str = ""
    operation_date: date | None = None
    tracking: str = ""
    reference: str = ""
    issuer: str = ""
    receiver: str = ""
    destination: str = ""
    destination_format: str = ""
    destination_aliases: tuple[str, ...] = ()
    owner_aliases: tuple[str, ...] = ()
    origin_aliases: tuple[str, ...] = ()
    value: Decimal | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def ready(self):
        return self.candidate and not self.issues

    def line(self, operation_date: date | None = None):
        if not self.ready:
            return ""
        return ",".join(((operation_date or self.operation_date).isoformat(), self.tracking,
                         self.issuer, self.receiver, self.destination, f"{self.value:.2f}"))

    def audit(self):
        return {
            "Fila Excel": self.row, "id_estado": self.statement,
            "Nombre del Archivo": self.filename, "No. de Movimiento": self.movement,
            "Sentido": self.direction, "Fecha": self.operation_date,
            "Clave de Rastreo": self.tracking, "Referencia": self.reference,
            "Banco Emisor": self.issuer, "Banco Receptor": self.receiver,
            "Cuenta Beneficiaria Consulta": self.destination,
            "Formato Cuenta Consulta": self.destination_format,
            "Monto": float(self.value) if self.value is not None else None,
            "Estado": "LISTO" if self.ready else "NO_CONSULTABLE" if self.candidate else "SIN_INDICIOS_SPEI",
            "Detalle": "; ".join(self.issues),
        }


def queries_from_workbook(source: bytes | str | Path, *, today: date | None = None) -> list[CepQuery]:
    today = today or mexico_today()
    workbook = load_workbook(BytesIO(source) if isinstance(source, bytes) else source, data_only=True)
    if "Movimientos" not in workbook:
        workbook.close()
        raise ValueError("El Excel no contiene la hoja Movimientos")
    # Legacy exports kept the holder CLABE only in Datos de la Cuenta. Link
    # donors by BOTH statement id and original filename, never by account name
    # alone. An ambiguous donor is not silently selected.
    account_index: dict[tuple[str, str], list[dict]] = {}
    account_rows = rows_from_sheet(workbook["Datos de la Cuenta"]) if "Datos de la Cuenta" in workbook else []
    for account in account_rows:
        key = (identifier(get(account, "id_estado")),
               str(get(account, "Nombre del Archivo", "")))
        account_index.setdefault(key, []).append(account)
    queries = []
    for row in rows_from_sheet(workbook["Movimientos"]):
        key = (identifier(get(row, "id_estado")),
               str(get(row, "Nombre del Archivo", "")))
        donors = account_index.get(key, [])
        donor = donors[0] if len(donors) == 1 else {}
        if not donor:
            # Some older versions renamed exported PDFs or used different
            # internal ids. Fall back ONLY on an exact, unique bank + account
            # match. Never use a person's name or an approximate number.
            movement_account = _account(get(row, "Número de Cuenta") or get(row, "Cuenta Titular"))
            movement_bank = bank_code(get(row, "Banco"))
            if movement_account and movement_bank:
                matches = [
                    candidate for candidate in account_rows
                    if _account(get(candidate, "Número de Cuenta")) == movement_account
                    and bank_code(get(candidate, "Banco")) == movement_bank
                ]
                if len(matches) == 1:
                    donor = matches[0]
        text = text_key(str(get(row, "Concepto", "")) + " " + str(get(row, "Concepto Original", "")))
        tracking = identifier(get(row, "Clave de Rastreo")).upper()
        if not tracking:
            # Extraction from an existing CONCEPTO is read-only. Parsed or
            # manually corrected tracking always wins over this fallback.
            tracking = extract_spei_metadata(
                str(get(row, "Banco", "")),
                get(row, "Concepto"), get(row, "Concepto Original")
            ).tracking
        classified_spei = text_key(get(row, "Tipo de Operación")) == "SPEI"
        candidate = bool(classified_spei or tracking or re.search(r"\bSPEI\b|INTERBANCARI|\bRASTREO\b", text))
        q = CepQuery(row["_row"], identifier(get(row, "id_estado")), str(get(row, "Nombre del Archivo", "")),
                     identifier(get(row, "No. de Movimiento")), candidate, tracking=tracking,
                     reference=identifier(get(row, "Referencia SPEI") or get(row, "Referencia")))
        date_input = get(row, "Fecha de Operación")
        explicit_date = full_date(date_input)
        q.operation_date = explicit_date
        if q.operation_date is None:
            context = donor if donor else row
            resolved = resolve_date(
                date_input, get(context, "Periodo de Inicio"),
                get(context, "Periodo de Fin"),
                get(context, "Fecha de Corte") or get(row, "Fecha de Corte"),
                filename=key[1],
            )
            if resolved.status in {"POR_ARCHIVO", "FUERA_DE_PERIODO", "REVISAR"}:
                q.issues.append("Fecha sin evidencia suficiente; corrige Fecha de Operación")
            else:
                q.operation_date = resolved.value
        debit, credit = amount(get(row, "Cargo")), amount(get(row, "Abono"))
        if debit is not None and credit is not None and bool(debit) != bool(credit):
            q.direction = "ENVIADO" if debit else "RECIBIDO"
            q.value = debit or credit
        else:
            q.issues.append("Cargo/abono ambiguos o importe inválido")
        owner_bank = bank_code(get(row, "Banco")) or bank_code(get(donor, "Banco"))
        holder_clabe = account_identifier(get(row, "CLABE Titular"))
        movement_account = _account(get(row, "Número de Cuenta"))
        legacy_account = _account(get(row, "Cuenta Titular"))
        if movement_account and legacy_account and movement_account != legacy_account:
            q.issues.append(
                "Cuenta Titular difiere de Número de Cuenta: corrige Número de Cuenta en Movimientos"
            )
        donor_account = _account(get(donor, "Número de Cuenta"))
        donor_agrees = not (donor_account and movement_account and donor_account != movement_account)
        donor_clabe = account_identifier(get(donor, "CLABE")) if donor_agrees else ""
        if not donor_agrees and not valid_clabe(holder_clabe) and q.direction == "RECIBIDO":
            q.issues.append(
                "Número de Cuenta corregido difiere de Datos de la Cuenta: completa CLABE Titular"
            )
        own = tuple(dict.fromkeys(v for v in (
            holder_clabe if valid_clabe(holder_clabe) else "",
            donor_clabe if valid_clabe(donor_clabe) else "",
            movement_account,
            legacy_account,  # previous improved layouts
            donor_account if donor_agrees else "",
        ) if v))
        q.owner_aliases = own
        if not owner_bank:
            owner_bank = next((clabe_bank(v) for v in own if clabe_bank(v)), "")
        q.issuer = bank_code(get(row, "Banco Emisor")) or _label_bank(text, "emisor")
        q.receiver = bank_code(get(row, "Banco Receptor")) or _label_bank(text, "receptor")
        if q.direction == "ENVIADO":
            q.origin_aliases = own
            if q.issuer and owner_bank and q.issuer != owner_bank:
                q.issues.append("Banco emisor contradice banco del estado")
            q.issuer = q.issuer or owner_bank
            destinations = tuple(dict.fromkeys(v for v in (
                _destination(get(row, "CLABE del Beneficiario")),
                _destination(get(row, "Cuenta del Beneficiario")),
            ) if v))
            q.destination_aliases = destinations
            q.destination = destinations[0] if destinations else ""
            raw_beneficiary = account_identifier(get(row, "CLABE del Beneficiario"))
            raw_account = account_identifier(get(row, "Cuenta del Beneficiario"))
            if q.destination and any(
                raw.startswith("00") and len(raw) == 18 and q.destination == raw[2:]
                for raw in (raw_beneficiary, raw_account)
            ):
                q.destination_format = "TARJETA_16_DESDE_00"
            elif len(q.destination) == 18:
                q.destination_format = "CLABE_18"
            elif len(q.destination) == 16:
                q.destination_format = "TARJETA_16"
            elif len(q.destination) == 10:
                q.destination_format = "CELULAR_10"
            inferred = clabe_bank(q.destination)
            explicit = q.receiver or bank_code(get(row, "Banco del Beneficiario")) or bank_code(get(row, "Sucursal"))
            if inferred and explicit and inferred != explicit:
                q.issues.append("CLABE beneficiaria contradice banco receptor")
            q.receiver = explicit or inferred
        elif q.direction == "RECIBIDO":
            if q.receiver and owner_bank and q.receiver != owner_bank:
                q.issues.append("Banco receptor contradice banco del estado")
            q.receiver = q.receiver or owner_bank
            q.destination_aliases = own
            # For a received SPEI the beneficiary is the HOLDER, never the
            # transfer sender. Prefer the movement's corrected CLABE; otherwise
            # use the same statement's legacy Datos de la Cuenta.
            if holder_clabe and not valid_clabe(holder_clabe):
                q.issues.append("CLABE Titular inválida; corrígela en Movimientos")
                q.destination = ""
            else:
                q.destination = next((v for v in own if _destination(v)), "")
            q.destination_format = ("CLABE_18" if len(q.destination) == 18
                                    else "TARJETA_16" if len(q.destination) == 16
                                    else "CELULAR_10" if len(q.destination) == 10 else "")
            inferred = clabe_bank(identifier(get(row, "CLABE del Ordenante")))
            if inferred and q.issuer and inferred != q.issuer:
                q.issues.append("CLABE ordenante contradice banco emisor")
            q.issuer = q.issuer or inferred
            source_accounts = [_account(get(row, "CLABE del Ordenante")),
                               _account(get(row, "Cuenta del Ordenante"))]
            # HSBC and BBVA map Ordenante -> legacy Beneficiario and
            # Participante Emisor -> Sucursal in received-SPEI enrichment.
            # The destination for Banxico remains the HOLDER's account.
            if owner_bank in {"40021", "40012"}:
                source_accounts.extend((_account(get(row, "CLABE del Beneficiario")),
                                        _account(get(row, "Cuenta del Beneficiario"))))
            q.origin_aliases = tuple(dict.fromkeys(v for v in source_accounts if v and v not in own))
            participant = bank_code(get(row, "Sucursal")) or bank_code(get(row, "Banco del Beneficiario"))
            if not q.issuer and participant and participant != owner_bank:
                q.issuer = participant
            if not q.issuer:
                inferred_sources = {clabe_bank(v) for v in q.origin_aliases if clabe_bank(v)}
                if len(inferred_sources) == 1:
                    q.issuer = next(iter(inferred_sources))
        other = bank_mentions(text) - {owner_bank}
        if len(other) == 1:
            if q.direction == "ENVIADO" and not q.receiver:
                q.receiver = next(iter(other))
            elif q.direction == "RECIBIDO" and not q.issuer:
                q.issuer = next(iter(other))
        for label, value in (("Fecha", q.operation_date), ("Clave de rastreo", q.tracking),
                             ("Banco emisor", q.issuer), ("Banco receptor", q.receiver),
                             ("Cuenta beneficiaria", q.destination)):
            if not value:
                q.issues.append(f"Falta {label.lower()}")
        if q.tracking and not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,39}", q.tracking):
            q.issues.append("Formato de rastreo no admitido")
        if q.operation_date and not date(2018, 3, 16) <= q.operation_date <= today:
            q.issues.append("Fecha fuera del intervalo de consulta CEP por lotes")
        # Estado de Fecha is a previous, potentially stale audit value.
        # A manually corrected explicit date takes precedence over it.
        if not explicit_date and text_key(get(row, "Estado de Fecha")) in {"REVISAR", "FUERA_DE_PERIODO"} and not q.operation_date:
            q.issues.append("Fecha requiere revisión del periodo")
        if q.destination and valid_clabe(q.destination) and clabe_bank(q.destination) not in ("", q.receiver):
            q.issues.append("CLABE de destino contradice banco receptor")
        queries.append(q)
    workbook.close()
    return queries


def batch_texts(queries: list[CepQuery], *, adjacent_days: bool = True, today: date | None = None) -> dict[str, bytes]:
    """One enriched series: original, previous and following day, 2–500/file."""
    today = today or mexico_today()
    lines = []
    for q in queries:
        if not q.ready:
            continue
        for offset in ((0, -1, 1) if adjacent_days else (0,)):
            value = q.operation_date + timedelta(days=offset)
            if date(2018, 3, 16) <= value <= today:
                lines.append(q.line(value))
    lines = list(dict.fromkeys(lines))
    if len(lines) < 2:
        raise ValueError("Banxico requiere al menos dos consultas. Revisa los datos o activa fechas ±1 día.")
    result, offset = {}, 0
    while offset < len(lines):
        remaining = len(lines) - offset
        size = 499 if remaining == 501 else min(500, remaining)
        result[f"lote_{len(result) + 1:03d}.txt"] = ("\n".join(lines[offset:offset + size]) + "\n").encode("utf-8")
        offset += size
    return result


def txt_zip(queries: list[CepQuery], *, adjacent_days: bool = True) -> bytes:
    files = batch_texts(queries, adjacent_days=adjacent_days)
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()
