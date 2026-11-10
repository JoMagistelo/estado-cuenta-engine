"""Append CEP evidence after existing movement columns and package both Excel."""

from __future__ import annotations

import tempfile
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from cep.evidence import CepEvidence, match_evidence
from cep.queries import CepQuery
from cep.columns import (
    CEP_COLUMNS, add_bank_catalog, arrange_movement_blocks, has_txt_inputs,
    install_txt_inputs, safe_to_reorder,
)
from exporters.excel.cells import delete_column, header_key, put_columns, set_literal
from exporters.excel.normalization import collapse_holder_account
from exporters.excel.workbook_bundle import WorkbookBundle
from exporters.excel.writer import write_table_sheet


# Official XML fields and status sit after the six editable TXT columns.
MOVEMENT_CEP_COLUMNS = CEP_COLUMNS


def _compact_existing_movements(workbook):
    ws = workbook["Movimientos"]
    removable = [
        cell.column for cell in ws[1]
        if cell.value and header_key(cell.value).startswith("CEP")
        and cell.value not in MOVEMENT_CEP_COLUMNS
    ]
    prepared = has_txt_inputs(ws[1])
    duplicate_holder = not prepared and any(header_key(cell.value) == "CUENTATITULAR" for cell in ws[1])
    safe = safe_to_reorder(workbook)
    if not safe and (removable or duplicate_holder):
        raise ValueError(
            "El Excel tiene fórmulas/tablas que impiden quitar columnas CEP o "
            "Cuenta Titular sin riesgo. Genera TXT directamente o prepara "
            "una copia de Movimientos sin fórmulas."
        )
    for column in sorted(removable, reverse=True):
        delete_column(ws, column)
    if not prepared:
        collapse_holder_account(ws)
    return ws


def append_cep(source: bytes, matches: dict[int, dict], queries: list[CepQuery], evidence: CepEvidence) -> bytes:
    workbook = load_workbook(BytesIO(source))
    ws = _compact_existing_movements(workbook)
    install_txt_inputs(ws, queries)
    # Old review sheets are intentionally discarded in the new CEP output.
    for name in ("Control CEP", "Datos CEP", "Revisión CEP", "Revisión Excel"):
        if name in workbook:
            del workbook[name]
    for row_number, values in matches.items():
        put_columns(ws, row_number, {key: values[key] for key in MOVEMENT_CEP_COLUMNS})
    columns = {cell.value: cell.column for cell in ws[1]}
    for row_number, values in matches.items():
        for field in ("CEP Archivo PDF", "CEP Archivo XML"):
            cell = ws.cell(row_number, columns[field])
            if values[field]:
                # Relative to either XLSX at the root of the final ZIP.
                cell.hyperlink = values[field]
                cell.style = "Hyperlink"
            else:
                cell.hyperlink = None
    write_table_sheet(workbook.create_sheet("Datos CEP"), [r.data | {
        "Archivo XML": r.xml_path, "Tiene PDF": "SÍ" if r.pdf else "NO", "Archivo PDF": r.pdf_path,
    } for r in evidence.records])
    for name in ("Datos CEP",):
        for cells in workbook[name].iter_rows():
            for cell in cells:
                if isinstance(cell.value, str):
                    set_literal(cell, cell.value)
    arrange_movement_blocks(workbook, MOVEMENT_CEP_COLUMNS, queries=queries)
    add_bank_catalog(workbook)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    # Verify after serialization, including the actual appended row identity.
    check = load_workbook(BytesIO(output.getvalue()), read_only=True)
    try:
        headers = {c.value: c.column - 1 for c in check["Movimientos"][1]}
        for row, cells in enumerate(check["Movimientos"].iter_rows(min_row=2, values_only=True), 2):
            values = matches.get(row)
            if values is None:
                continue
            for name in ("CEP Estado", "CEP Tiene PDF", "CEP Archivo XML", "CEP Archivo PDF"):
                if (cells[headers[name]] or "") != values[name]:
                    raise ValueError(f"La comprobación CEP falló en fila {row}")
    finally:
        check.close()
    return output.getvalue()


def export_cep_zip(bundle: WorkbookBundle, queries: list[CepQuery], evidence: CepEvidence,
                   destination: str | Path) -> dict[str, int]:
    matches = match_evidence(queries, evidence)
    original = append_cep(bundle.original, matches, queries, evidence)
    improved = append_cep(bundle.improved, matches, queries, evidence)
    for values in matches.values():
        if values["CEP Estado"].startswith("EXITO"):
            if not any(r.xml_path == values["CEP Archivo XML"] for r in evidence.records):
                raise ValueError("Falta la evidencia XML de un movimiento coincidente")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement keeps a failed export from leaving a broken ZIP.
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".zip", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("excel_original_con_CEP.xlsx", original)
            archive.writestr("excel_mejorado_con_CEP.xlsx", improved)
            for record in evidence.records:
                archive.writestr(record.xml_path, record.xml)
                if record.pdf:
                    archive.writestr(record.pdf_path, record.pdf)
            for name, data in evidence.preserved.items():
                archive.writestr(name, data)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise ValueError("La comprobación detectó un archivo corrupto en el ZIP")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(Counter(value["CEP Estado"] for value in matches.values()))
