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
from exporters.excel.normalization import put_columns, set_literal
from exporters.excel.workbook_bundle import WorkbookBundle
from exporters.excel.writer import write_table_sheet


def append_cep(source: bytes, matches: dict[int, dict], queries: list[CepQuery], evidence: CepEvidence) -> bytes:
    workbook = load_workbook(BytesIO(source))
    ws = workbook["Movimientos"]
    for row_number, values in matches.items():
        put_columns(ws, row_number, values)
    for name in ("Control CEP", "Datos CEP", "Revisión CEP"):
        if name in workbook:
            del workbook[name]
    write_table_sheet(workbook.create_sheet("Control CEP"), [q.audit() | matches[q.row] for q in queries])
    write_table_sheet(workbook.create_sheet("Datos CEP"), [r.data | {
        "Archivo XML": r.xml_path, "Tiene PDF": "SÍ" if r.pdf else "NO", "Archivo PDF": r.pdf_path,
    } for r in evidence.records])
    write_table_sheet(workbook.create_sheet("Revisión CEP"), evidence.review)
    for name in ("Control CEP", "Datos CEP", "Revisión CEP"):
        for cells in workbook[name].iter_rows():
            for cell in cells:
                if isinstance(cell.value, str):
                    set_literal(cell, cell.value)
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
            for name in ("CEP Estado", "CEP Clave de Rastreo", "CEP Archivo XML", "CEP Archivo PDF"):
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
