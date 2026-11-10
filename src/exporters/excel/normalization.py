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

from cep.catalog import account_identifier, bank_code, clabe_bank, identifier, valid_clabe
from cep.catalog import statement_account as _account
from cep.columns import (
    CEP_COLUMNS, RETIRED_KEYS, TXT_COLUMNS, add_bank_catalog, arrange_movement_blocks,
    has_txt_inputs, install_txt_inputs, query_values, safe_to_reorder,
)
from cep.queries import queries_from_rows
from cep.spei_classifier import CLASSIFICATION_COLUMN, classify_spei, operation_type, stored_classification
from cep.spei_recovery import SOURCE_RECOVERY_FIELDS, recover_missing
from exporters.excel.cells import (
    delete_column, ensure_columns, get, header_key, insert_column, put_columns, rows_from_sheet, set_literal, updated_row,
)
from utils.statement_dates import MONTHS, resolve_date, statement_interval, text_key
from utils.spei_metadata import bbva_statement_reference, extract_spei_metadata, metadata_search_text, valid_tracking


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
        # Do not add Banco Receptor beside Banco del Beneficiario:
        # the latter is the receiver for outgoing SPEI.
        column = "Banco Emisor" if found.direction == "RECIBIDO" else "Banco del Beneficiario"
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
    delete_column(ws, redundant)
    return True


@dataclass
class NormalizationReport:
    movements: int = 0
    dates_resolved: int = 0
    dates_review: int = 0
    classifications: dict[str, int] = field(default_factory=dict)
    metadata_recovered: int = 0
    changes: list[dict] = field(default_factory=list)


def normalize_workbook(source: str | Path | bytes, destination: str | Path) -> NormalizationReport:
    """Normalize dates, classify SPEI and recover missing data on a copy only."""
    workbook = load_workbook(BytesIO(source) if isinstance(source, bytes) else source)
    try:
        if "Movimientos" not in workbook:
            raise ValueError("El Excel debe contener la hoja Movimientos")
        ws = workbook["Movimientos"]
        report = NormalizationReport()
        existing_txt = has_txt_inputs(ws[1])
        movable = safe_to_reorder(workbook)
        headers = {header_key(c.value): c.column for c in ws[1]}
        legacy_schema = bool(RETIRED_KEYS & headers.keys())
        if not existing_txt and "CUENTATITULAR" in headers and "NUMERODECUENTA" in headers and not movable:
            raise ValueError(
                "El Excel tiene fórmulas o tablas que impiden quitar con seguridad Cuenta Titular. "
                "Puedes generar el TXT directamente sin normalizar este archivo."
            )
        if not existing_txt:
            collapse_holder_account(ws, allow_column_removal=movable)
        headers = {header_key(c.value): c.column for c in ws[1]}
        if movable and "FECHADECORTE" in headers and "CLABETITULAR" not in headers:
            position = headers["FECHADECORTE"] + 1
            insert_column(ws, position)
            ws.cell(1, position, "CLABE Titular")._style = copy(ws.cell(1, 1)._style)
            ws.column_dimensions[get_column_letter(position)].width = 24
        # Legacy workbooks occasionally omitted the type. Add it before the
        # trace columns so formula-bearing files keep their existing positions.
        ensure_columns(ws, (CLASSIFICATION_COLUMN,))

        def record(row, label, old, new, detail):
            report.changes.append({
                "Nombre del Archivo": get(row, "Nombre del Archivo", ""),
                "Fila Excel": row.get("_row"), "Campo": label,
                "Original": _display(old), "Normalizado": _display(new), "Detalle": detail,
            })

        accounts = rows_from_sheet(workbook["Datos de la Cuenta"]) if "Datos de la Cuenta" in workbook else []
        owners = reconstruct_owners(accounts)
        owner_index = {}
        for owner in owners:
            row = owner.row
            original = next(r for r in accounts if r["_row"] == row["_row"])
            values = {}
            for label in ("Número de Cuenta", "CLABE", "Nombre del Cliente", "RFC", "Número de Cliente"):
                value, old = get(row, label), get(original, label)
                if value != old:
                    values[label] = value
                    record(row, label, old, value, "Reconstruido desde: " + "; ".join(owner.sources))
            first, last, cut = statement_interval(
                get(row, "Periodo de Inicio"), get(row, "Periodo de Fin"), get(row, "Fecha de Corte"))
            for label, parsed in (("Periodo de Inicio", first), ("Periodo de Fin", last), ("Fecha de Corte", cut)):
                if parsed:
                    values[label] = parsed
            if owner.sources:
                values["Origen Datos Titular"] = "; ".join(owner.sources)
            put_columns(workbook["Datos de la Cuenta"], row["_row"], values)
            key = (identifier(get(row, "id_estado")), str(get(row, "Nombre del Archivo", "")))
            owner_index.setdefault(key, []).append(owner)

        baseline_rows = []
        query_rows = []
        authoritative_txt_rows = set()
        ambiguous_tracking = set()
        for row in rows_from_sheet(ws):
            if get(row, "Sin información"):
                continue
            report.movements += 1
            if existing_txt and not legacy_schema and stored_classification(row):
                authoritative_txt_rows.add(row["_row"])
            key = (identifier(get(row, "id_estado")), str(get(row, "Nombre del Archivo", "")))
            matches = owner_index.get(key, [])
            owner = matches[0] if len(matches) == 1 else None
            metadata = owner.row if owner else row
            classification = classify_spei(row)
            if classification.label:
                report.classifications[classification.label] = report.classifications.get(classification.label, 0) + 1
            recovered, recovery_notes = recover_missing(row, classification)
            if (any(note.startswith("Clave de Rastreo: varias candidatas") for note in recovery_notes)
                    and not valid_tracking(get(row, "Clave de Rastreo"))):
                ambiguous_tracking.add(row["_row"])
            values = {}
            account = _account(get(row, "Número de Cuenta")) or (owner.account if owner else "")
            own_clabe = account_identifier(get(row, "CLABE Titular"))
            agrees = not (owner and owner.account and account and owner.account != account)
            if not _present(own_clabe):
                values["CLABE Titular"] = owner.clabe if owner and agrees else ""
            if account and not _account(get(row, "Número de Cuenta")):
                values["Número de Cuenta"] = account
            for label in ("Fecha de Operación", "Fecha de Liquidación", "Fecha de Corte"):
                old = get(row, label)
                if not _present(old) and label == "Fecha de Corte":
                    old = get(metadata, label)
                resolution = resolve_date(
                    old, get(metadata, "Periodo de Inicio"), get(metadata, "Periodo de Fin"),
                    get(metadata, "Fecha de Corte"), filename=key[1],
                    settlement=label == "Fecha de Liquidación",
                )
                original_column = label + " Original"
                if not any(header_key(k) == header_key(original_column) for k in row):
                    values[original_column] = get(row, label)
                if resolution.value:
                    values[label] = resolution.value
                    if label == "Fecha de Operación":
                        report.dates_resolved += 1
                if label == "Fecha de Operación":
                    values["Estado de Fecha"] = resolution.status
                    if resolution.status in {"VACIA", "REVISAR", "FUERA_DE_PERIODO", "POR_ARCHIVO"}:
                        report.dates_review += 1
                if (resolution.value and not isinstance(old, (date, datetime))) or resolution.status == "REVISAR":
                    record(row, label, old, resolution.value or old, resolution.status + ": " + resolution.detail)
            if existing_txt and row["_row"] not in authoritative_txt_rows:
                # Reproduce what the previous normalizer could infer. A blank
                # blue cell whose old source was usable is an intentional edit;
                # only genuinely newly recovered evidence may fill old gaps.
                old_recovered, _ = recover_fields(row)
                baseline_rows.append(updated_row(updated_row(row, values), old_recovered))
            for label, value in recovered.items():
                # Only already-existing parser fields can be completed in
                # green. Bank/ordenante/reference intermediates stay in memory.
                if label in SOURCE_RECOVERY_FIELDS and any(header_key(k) == header_key(label) for k in row):
                    values[label] = value
                    record(row, label, get(row, label), value, "Recuperado del concepto SPEI")
            report.metadata_recovered += len(recovered)
            values[CLASSIFICATION_COLUMN] = operation_type(row, classification)
            query_rows.append(updated_row(updated_row(row, values), recovered))
            put_columns(ws, row["_row"], values)

        current_accounts = rows_from_sheet(workbook["Datos de la Cuenta"]) if "Datos de la Cuenta" in workbook else []
        queries = queries_from_rows(query_rows, current_accounts)
        rows_index = {row["_row"]: row for row in query_rows}
        for query in queries:
            if not query.candidate:
                continue
            if query.row in ambiguous_tracking:
                query.tracking = ""
                query.issues.append("Varias claves de rastreo: completa TXT Clave de Rastreo")
            # A contradictory automatic route must not become a ready query
            # simply by copying it into the authoritative blue block. Existing
            # blue values still win; newly inferred conflicting banks stay blank.
            if any("contradice banco receptor" in issue for issue in query.issues):
                query.receiver = ""
            if any("contradice banco emisor" in issue or "Banco emisor contradice" in issue
                   for issue in query.issues):
                query.issuer = ""
            if any("Banco receptor contradice" in issue for issue in query.issues):
                query.receiver = ""
        install_txt_inputs(ws, queries)
        if existing_txt:
            baseline_queries = {q.row: q for q in queries_from_rows(baseline_rows, current_accounts)}
            for query in queries:
                baseline = baseline_queries.get(query.row)
                if query.row in authoritative_txt_rows or not baseline or not query.candidate:
                    continue
                row = rows_index[query.row]
                old_values = query_values(baseline)
                new_candidate = not baseline.candidate and all(
                    get(row, label) is None or str(get(row, label)).strip() == "" for label in TXT_COLUMNS)
                for label, value in query_values(query).items():
                    previous = get(row, label)
                    blank = previous is None or str(previous).strip() == ""
                    if blank and _present(value) and (new_candidate or not _present(old_values[label])):
                        put_columns(ws, query.row, {label: value})
                        record(row, label, previous, value, "Nuevo metadato recuperado; se conservan las demás celdas TXT")
        stale = [c.column for c in ws[1] if c.value in CEP_COLUMNS]
        if stale and not movable:
            raise ValueError(
                "El Excel tiene fórmulas que impiden retirar los resultados CEP anteriores. "
                "Genera TXT sin normalizar o trabaja sobre una copia sin dependencias."
            )
        for column in sorted(stale, reverse=True):
            delete_column(ws, column)
        for old_sheet in ("Revisión Excel", "Revisión CEP", "Control CEP", "Datos CEP"):
            if old_sheet in workbook:
                del workbook[old_sheet]
        arrange_movement_blocks(workbook, queries=queries)
        add_bank_catalog(workbook)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(destination)
        return report
    finally:
        workbook.close()
