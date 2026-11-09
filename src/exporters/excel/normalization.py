"""Normalize a copy of an Engine workbook, retaining rows and user columns."""

from __future__ import annotations

import re
from copy import copy
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from cep.catalog import INSTITUTIONS, account_identifier, bank_code, clabe_bank, identifier, valid_clabe
from utils.statement_dates import MONTHS, resolve_date, statement_interval, text_key
from utils.spei_metadata import bbva_statement_reference, extract_spei_metadata, metadata_search_text, valid_tracking


def header_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", text_key(value))


def rows_from_sheet(ws) -> list[dict]:
    headers = [c.value for c in ws[1]]
    return [dict(zip(headers, values)) | {"_row": index}
            for index, values in enumerate(ws.iter_rows(min_row=2, values_only=True), 2)
            if any(v is not None for v in values)]


def get(row: dict, name: str, default=None):
    wanted = header_key(name)
    for key, value in row.items():
        if header_key(key) == wanted:
            return value if value is not None else default
    return default


def _display(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value or "")


def _present(value):
    return value is not None and text_key(value) not in {"", "N/A", "NA", "NONE", "NULL", "-"}


def filename_family(filename: str) -> str:
    s = text_key(Path(filename).stem).replace("_", " ")
    s = re.sub(r"\b\d{4}[-. /]\d{1,2}(?:[-. /]\d{1,2})?\b", " ", s)
    s = re.sub(r"\b\d{1,2}[-. /]\d{1,2}[-. /](?:20)?\d{2}\b", " ", s)
    s = re.sub(r"\b(?:0?[1-9]|1[0-2])[-. /]20\d{2}\b", " ", s)
    names = "|".join(sorted(MONTHS, key=len, reverse=True))
    s = re.sub(rf"\b(?:\d{{1,2}}[ .-]+)?(?:{names})[ .-]*(?:20)?\d{{2}}\b", " ", s)
    s = re.sub(rf"\b(?:{names})\b|\b20\d{{2}}\b", " ", s)
    s = re.sub(r"\b(?:ESTADO DE CUENTA|ESTADO CUENTA|CORTE|PERIODO)\b", " ", s)
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def _account(value):
    value = account_identifier(value)
    return value if re.fullmatch(r"[0-9]{5,17}", value) or valid_clabe(value) else ""


@dataclass
class Owner:
    row: dict
    bank: str
    account: str
    clabe: str
    family: str
    sources: list[str] = field(default_factory=list)


def _owner(row):
    account = _account(get(row, "Número de Cuenta"))
    clabe = account_identifier(get(row, "CLABE"))
    clabe = clabe if valid_clabe(clabe) else account if valid_clabe(account) else ""
    return Owner(row, bank_code(get(row, "Banco")) or clabe_bank(clabe), account,
                 clabe, filename_family(str(get(row, "Nombre del Archivo", ""))))


def _conflict(a: Owner, b: Owner):
    return (a.bank != b.bank or not a.bank
            or bool(a.account and b.account and a.account != b.account)
            or bool(a.clabe and b.clabe and a.clabe != b.clabe)
            or any(_present(get(a.row, k)) and _present(get(b.row, k))
                   and text_key(get(a.row, k)) != text_key(get(b.row, k))
                   for k in ("RFC", "Nombre del Cliente")))


def reconstruct_owners(accounts: list[dict]) -> list[Owner]:
    """Use immutable donor evidence; a name/RFC alone never merges accounts."""
    owners = [_owner(row) for row in accounts]
    parents = list(range(len(owners)))

    def root(i):
        while parents[i] != i:
            i = parents[i]
        return i

    for i, a in enumerate(owners):
        for j, b in enumerate(owners[:i]):
            if not _conflict(a, b) and ((a.account and a.account == b.account)
                                       or (a.clabe and a.clabe == b.clabe)):
                parents[root(i)] = root(j)
    groups: dict[int, list[Owner]] = {}
    for i, owner in enumerate(owners):
        if owner.account or owner.clabe:
            groups.setdefault(root(i), []).append(owner)
    resolved = []
    for target in owners:
        strong, by_name = [], []
        for donors in groups.values():
            if any(_conflict(target, d) for d in donors):
                continue
            if any((target.account and target.account == d.account)
                   or (target.clabe and target.clabe == d.clabe) for d in donors):
                strong.append(donors)
            elif target.family and any(target.family == d.family for d in donors):
                by_name.append(donors)
        candidates = strong or by_name
        updated = Owner(dict(target.row), target.bank, target.account, target.clabe, target.family)
        if len(candidates) == 1:
            donors = candidates[0]
            for field_name in ("Número de Cuenta", "CLABE", "Nombre del Cliente", "RFC", "Número de Cliente"):
                values = {}
                for donor in donors:
                    value = get(donor.row, field_name)
                    if field_name == "Número de Cuenta":
                        value = donor.account
                    elif field_name == "CLABE":
                        value = donor.clabe
                    if _present(value):
                        values[text_key(value)] = value
                current = get(updated.row, field_name)
                missing = not _present(current)
                if field_name == "Número de Cuenta":
                    missing = not updated.account
                elif field_name == "CLABE":
                    missing = not updated.clabe
                if missing and len(values) == 1:
                    updated.row[field_name] = next(iter(values.values()))
                    updated.sources = sorted({str(get(d.row, "Nombre del Archivo", "")) for d in donors})
            refreshed = _owner(updated.row)
            updated.account, updated.clabe = refreshed.account, refreshed.clabe
        resolved.append(updated)
    return resolved


_ID_CAPTURE = r"([0-9](?:[0-9 -]*[0-9])?)(?![0-9])"
_ROLE = r"(?:DEL?\s+)?(?:BENEFICIARI[AO]|DESTINO|RECEPTOR[AO]?)"


def recover_fields(row: dict) -> tuple[dict, list[str]]:
    """Repair labelled identifiers; never pick an arbitrary long concept number."""
    text = metadata_search_text(str(get(row, "Banco", "")), get(row, "Concepto"), get(row, "Concepto Original"))
    changes, notes = {}, []
    found = extract_spei_metadata(str(get(row, "Banco", "")), get(row, "Concepto"), get(row, "Concepto Original"))
    notes.extend(found.notes)
    existing = identifier(get(row, "Clave de Rastreo"))
    if found.tracking and not valid_tracking(existing):
        changes["Clave de Rastreo"] = found.tracking
    elif found.tracking and existing.upper() != found.tracking:
        notes.append("Clave de Rastreo: difiere del concepto; se conserva el dato extraído")
    if found.reference and not identifier(get(row, "Referencia")):
        changes["Referencia"] = found.reference
    if bank_code(get(row, "Banco")) == "40012":
        # BBVA has both a statement reference and a distinct 7-digit payment
        # reference. Keep their meanings separate and retain the source value.
        repaired = bbva_statement_reference(get(row, "Referencia"), found)
        if repaired:
            changes["Referencia"] = repaired
        if found.reference and not _present(get(row, "Referencia SPEI")):
            changes["Referencia SPEI"] = found.reference
    if "Referencia" in changes and get(row, "Referencia Original") is None:
        changes["Referencia Original"] = get(row, "Referencia")
    if found.clabe:
        column = "CLABE del Ordenante" if found.direction == "RECIBIDO" else "CLABE del Beneficiario"
        existing = account_identifier(get(row, column))
        # A 16-digit card or a 00-padded card may be a deliberate manual
        # correction. Never replace it with an older value found in CONCEPTO.
        protected = existing.isdigit() and len(existing) in (10, 16, 18)
        if not valid_clabe(existing) and not protected:
            changes[column] = found.clabe
        elif protected and existing != found.clabe:
            notes.append(f"{column}: difiere del concepto; se conserva la edición")
    if found.bank:
        column = "Banco Emisor" if found.direction == "RECIBIDO" else "Banco Receptor"
        if not _present(get(row, column)):
            changes[column] = found.bank
    for column, pattern in (
        ("Referencia", r"\b(?:REFERENCIA(?:\s+NUMERICA)?|REF\.?)\s*[:#=-]?\s*([0-9]{1,20})\b"),
    ):
        existing = identifier(get(row, column))
        matches = {m[1] for m in re.finditer(pattern, text)}
        valid = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,39}", existing))
        if (not valid) and len(matches) == 1:
            changes[column] = next(iter(matches))
        elif len(matches) > 1:
            notes.append(f"{column}: varias candidatas en el concepto")
        elif valid and matches and existing.upper() not in matches:
            notes.append(f"{column}: difiere del concepto; se conserva el dato extraído")
    for role, clabe_col, account_col in (
        (_ROLE, "CLABE del Beneficiario", "Cuenta del Beneficiario"),
        (r"(?:DEL?\s+)?(?:ORDENANTE|ORIGEN|EMISOR)", "CLABE del Ordenante", "Cuenta del Ordenante"),
    ):
        labelled = set()
        patterns = [
            rf"\b(?:CLABE|CTA\s*/\s*CLABE|CUENTA|CTA\.?)\s*{role}\s*[:#=-]?\s*{_ID_CAPTURE}",
            rf"\b{role}\s+(?:CLABE|CUENTA|CTA\.?)\s*[:#=-]?\s*{_ID_CAPTURE}",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = re.sub(r"[ -]", "", match[1])
                if 5 <= len(value) <= 18:
                    labelled.add(value)
        # An unqualified CLABE is usable only if the concept has no other role
        # label and exactly one valid CLABE. Preserve it as the parser's third party.
        if clabe_col == "CLABE del Beneficiario" and not labelled:
            if not re.search(r"\b(?:ORDENANTE|ORIGEN|EMISOR|TITULAR)\b", text):
                labelled = {re.sub(r"[ -]", "", m[1]) for m in re.finditer(
                    rf"\b(?:CLABE(?:\s+INTERBANCARIA)?|CTA\s*/\s*CLABE)\s*[:#=-]?\s*{_ID_CAPTURE}", text)}
        clabes = {v for v in labelled if valid_clabe(v)}
        accounts = {v for v in labelled if len(v) != 18 and v.isdigit()}
        existing_clabe = account_identifier(get(row, clabe_col))
        existing_account = account_identifier(get(row, account_col))
        if not valid_clabe(existing_clabe):
            protected = existing_clabe.isdigit() and len(existing_clabe) in (10, 16, 18)
            if not protected:
                if valid_clabe(existing_account):
                    changes[clabe_col] = existing_account
                elif len(clabes) == 1:
                    changes[clabe_col] = next(iter(clabes))
            elif clabes and existing_clabe not in clabes:
                notes.append(f"{clabe_col}: valor manual distinto; se conserva para revisión")
        elif clabes and existing_clabe not in clabes:
            notes.append(f"{clabe_col}: contradicción; se conserva el dato extraído")
        if not _account(existing_account) and len(accounts) == 1:
            changes[account_col] = next(iter(accounts))
        if len(clabes) > 1 or len(accounts) > 1:
            notes.append(f"{account_col}: varias candidatas")
    beneficiary_clabe = changes.get("CLABE del Beneficiario", account_identifier(get(row, "CLABE del Beneficiario")))
    code = clabe_bank(beneficiary_clabe)
    if code:
        changes["Banco del Beneficiario"] = INSTITUTIONS[code]
        changes["Código Banco Beneficiario"] = code
        changes["Código Plaza/Producto CLABE"] = beneficiary_clabe[3:6]
        # Historical UI uses Sucursal for the counterpart bank. Do not replace
        # an explicitly extracted value or claim a physical branch from CLABE.
        if not _present(get(row, "Sucursal")):
            changes["Sucursal"] = INSTITUTIONS[code]
    return changes, notes


def collapse_holder_account(ws, *, allow_column_removal=True) -> bool:
    """Keep Número de Cuenta as the only account column (CLABE Titular stays).

    Never discard competing manually entered values. Removing a column in a
    workbook containing formulas may invalidate external cell references;
    callers should opt out for those complex workbooks.
    """
    headers = {header_key(cell.value): cell.column for cell in ws[1] if cell.value is not None}
    redundant = headers.get("CUENTATITULAR")
    canonical = headers.get("NUMERODECUENTA")
    if not redundant:
        return False
    if not canonical:
        ws.cell(1, redundant).value = "Número de Cuenta"
        return True
    for index in range(2, ws.max_row + 1):
        current = account_identifier(ws.cell(index, canonical).value)
        previous = account_identifier(ws.cell(index, redundant).value)
        if current and previous and current != previous:
            raise ValueError(
                f"Fila {index}: Cuenta Titular y Número de Cuenta son distintos. "
                "Corrige Número de Cuenta en Movimientos antes de normalizar/cruzar."
            )
    if not allow_column_removal:
        return False
    for index in range(2, ws.max_row + 1):
        canonical_cell = ws.cell(index, canonical)
        old = account_identifier(ws.cell(index, redundant).value)
        if not account_identifier(canonical_cell.value) and old:
            canonical_cell.value = old
            canonical_cell.data_type = "s"
    ws.delete_cols(redundant)
    return True


def set_literal(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"
    if isinstance(value, (date, datetime)):
        cell.number_format = "dd/mm/yyyy"


def put_columns(ws, row_number: int, values: dict):
    columns = {header_key(c.value): c.column for c in ws[1] if c.value is not None}
    for header, value in values.items():
        key = header_key(header)
        if key not in columns:
            column = ws.max_column + 1
            cell = ws.cell(1, column)
            if column > 1:
                cell._style = copy(ws.cell(1, 1)._style)
            set_literal(cell, header)
            columns[key] = column
            ws.column_dimensions[get_column_letter(column)].width = min(36, max(18, len(header) + 2))
        column = columns[key]
        cell = ws.cell(row_number, column)
        if not cell.has_style and column > 1:
            cell._style = copy(ws.cell(row_number, 1)._style)
        set_literal(cell, value)
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


@dataclass
class NormalizationReport:
    movements: int = 0
    dates_resolved: int = 0
    dates_review: int = 0
    changes: list[dict] = field(default_factory=list)


def normalize_workbook(source: str | Path | bytes, destination: str | Path) -> NormalizationReport:
    """Do not mutate the original file, row order, amounts, or extra sheets."""
    workbook = load_workbook(BytesIO(source) if isinstance(source, bytes) else source)
    if "Movimientos" not in workbook.sheetnames:
        workbook.close()
        raise ValueError("El Excel debe contener la hoja Movimientos")
    report = NormalizationReport()

    ws = workbook["Movimientos"]
    # Generated Engine sheets have no formulas, tables, charts or defined
    # names. Place holder identifiers next to the cutoff in those sheets.
    # Keep coordinates in analyst workbooks that contain dependent formulas.
    headers = {header_key(c.value): c.column for c in ws[1]}
    movable = not workbook.defined_names and not any(
        sheet.tables or sheet._charts or any(c.data_type == "f" for cells in sheet.iter_rows() for c in cells)
        for sheet in workbook.worksheets)
    if "CUENTATITULAR" in headers and "NUMERODECUENTA" in headers and not movable:
        raise ValueError(
            "El Excel tiene fórmulas o tablas que impiden quitar con seguridad Cuenta Titular. "
            "Puedes generar el TXT directamente sin normalizar este archivo."
        )
    collapse_holder_account(ws, allow_column_removal=movable)
    headers = {header_key(c.value): c.column for c in ws[1] if c.value is not None}
    if movable and "FECHADECORTE" in headers and "CLABETITULAR" not in headers:
        position = headers["FECHADECORTE"] + 1
        ws.insert_cols(position, 1)
        ws.cell(1, position, "CLABE Titular")._style = copy(ws.cell(1, 1)._style)
        ws.column_dimensions[get_column_letter(position)].width = 24

    def record(row, field_name, old, new, detail):
        report.changes.append({
            "Nombre del Archivo": get(row, "Nombre del Archivo", ""),
            "Fila Excel": row.get("_row"), "Campo": field_name,
            "Original": _display(old), "Normalizado": _display(new), "Detalle": detail,
        })

    account_rows = rows_from_sheet(workbook["Datos de la Cuenta"]) if "Datos de la Cuenta" in workbook else []
    owners = reconstruct_owners(account_rows)
    owner_index: dict[tuple[str, str], list[Owner]] = {}
    for owner in owners:
        row = owner.row
        original = next(r for r in account_rows if r["_row"] == row["_row"])
        values = {}
        for field_name in ("Número de Cuenta", "CLABE", "Nombre del Cliente", "RFC", "Número de Cliente"):
            value, old = get(row, field_name), get(original, field_name)
            if value != old:
                values[field_name] = value
                record(row, field_name, old, value, "Reconstruido desde: " + "; ".join(owner.sources))
        first, last, cut = statement_interval(get(row, "Periodo de Inicio"), get(row, "Periodo de Fin"), get(row, "Fecha de Corte"))
        for field_name, parsed in (("Periodo de Inicio", first), ("Periodo de Fin", last), ("Fecha de Corte", cut)):
            if parsed:
                values[field_name] = parsed
        if owner.sources:
            values["Origen Datos Titular"] = "; ".join(owner.sources)
        put_columns(workbook["Datos de la Cuenta"], row["_row"], values)
        key = (identifier(get(row, "id_estado")), str(get(row, "Nombre del Archivo", "")))
        owner_index.setdefault(key, []).append(owner)
    ws = workbook["Movimientos"]
    for row in rows_from_sheet(ws):
        if get(row, "Sin información"):
            continue
        report.movements += 1
        key = (identifier(get(row, "id_estado")), str(get(row, "Nombre del Archivo", "")))
        matches = owner_index.get(key, [])
        owner = matches[0] if len(matches) == 1 else None
        metadata = owner.row if owner else row
        values, notes = recover_fields(row)
        # The analyst's movement columns take precedence over donor data.
        account = _account(get(row, "Número de Cuenta")) or (owner.account if owner else "")
        own_clabe = account_identifier(get(row, "CLABE Titular"))
        clabe = own_clabe if valid_clabe(own_clabe) else (owner.clabe if owner else "")
        if not _present(own_clabe):
            values["CLABE Titular"] = clabe if valid_clabe(clabe) else ""
        elif not valid_clabe(own_clabe):
            notes.append("CLABE Titular inválida; se conserva para corrección manual")
        if account and not _account(get(row, "Número de Cuenta")):
            values["Número de Cuenta"] = account
        if owner and owner.sources:
            values["Origen Datos Titular"] = "; ".join(owner.sources)
        for field_name in ("Fecha de Operación", "Fecha de Liquidación", "Fecha de Corte"):
            old = get(row, field_name)
            if not _present(old) and field_name == "Fecha de Corte":
                old = get(metadata, field_name)
            resolution = resolve_date(old, get(metadata, "Periodo de Inicio"), get(metadata, "Periodo de Fin"),
                                      get(metadata, "Fecha de Corte"), filename=key[1],
                                      settlement=field_name == "Fecha de Liquidación")
            original_column = field_name + " Original"
            if get(row, original_column) is None:
                values[original_column] = get(row, field_name)
            if resolution.value:
                values[field_name] = resolution.value
                if field_name == "Fecha de Operación":
                    report.dates_resolved += 1
            if field_name == "Fecha de Operación":
                values["Estado de Fecha"] = resolution.status
                if resolution.status == "VACIA":
                    report.dates_review += 1
                    notes.append("Fecha de Operación: no se extrajo fecha; requiere revisión")
            if resolution.status in {"REVISAR", "FUERA_DE_PERIODO", "POR_ARCHIVO"}:
                notes.append(f"{field_name}: {resolution.detail}")
                if field_name == "Fecha de Operación":
                    report.dates_review += 1
            if (resolution.value and not isinstance(old, (date, datetime))) or resolution.status == "REVISAR":
                record(row, field_name, old, resolution.value or old, resolution.status + ": " + resolution.detail)
        for field_name, value in list(values.items()):
            if field_name in {"Clave de Rastreo", "Referencia", "Referencia SPEI", "Cuenta del Beneficiario", "CLABE del Beneficiario", "Cuenta del Ordenante", "CLABE del Ordenante", "Sucursal", "Banco del Beneficiario", "Banco Emisor", "Banco Receptor", "Cuenta Titular", "CLABE Titular"}:
                if get(row, field_name) != value:
                    record(row, field_name, get(row, field_name), value, "Concepto, catálogo o datos del titular")
        # Excel identifiers stay strings, including leading zeros.
        for field_name in ("Referencia", "Clave de Rastreo", "Cuenta del Beneficiario", "CLABE del Beneficiario"):
            if field_name not in values and _present(get(row, field_name)):
                if (field_name == "Referencia" and bank_code(get(row, "Banco")) == "40012"
                        and re.fullmatch(r"\s*[0-9]{10}\s+[0-9]{3}\s*", str(get(row, field_name)))):
                    notes.append("Referencia: contiene código bancario no concordante; se conserva para revisión")
                    continue
                value = (account_identifier if field_name in {"Cuenta del Beneficiario", "CLABE del Beneficiario"} else identifier)(get(row, field_name))
                if value:
                    values[field_name] = value
                    if value != get(row, field_name):
                        record(row, field_name, get(row, field_name), value, "Identificador guardado como texto")
                else:
                    notes.append(f"{field_name}: identificador numérico con posible pérdida de precisión")
        values["Revisión Normalización"] = "; ".join(dict.fromkeys(notes))
        put_columns(ws, row["_row"], values)
    # Audit differences are retained in the in-memory report, not in a
    # separate Revisión Excel sheet. The final user's corrections live in
    # Movimientos, and the generated Control CEP reports query problems.
    # A previously crossed workbook may contain stale CEP status/results.
    # They are not evidence for this new run; rebuilding them requires
    # importing the official Banxico ZIP again. Never alter the source XLSX.
    previous_cep_columns = [
        cell.column for cell in ws[1]
        if cell.value and header_key(cell.value).startswith("CEP")
    ]
    if previous_cep_columns and not movable:
        raise ValueError(
            "El Excel tiene fórmulas que impiden retirar los resultados CEP anteriores. "
            "Genera TXT sin normalizar o trabaja sobre una copia sin dependencias."
        )
    for column in sorted(previous_cep_columns, reverse=True):
        ws.delete_cols(column)
    for old_sheet in ("Revisión Excel", "Revisión CEP", "Control CEP", "Datos CEP"):
        if old_sheet in workbook:
            del workbook[old_sheet]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return report
