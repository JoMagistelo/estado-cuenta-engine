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
from exporters.excel.normalization import collapse_holder_account, header_key, put_columns, set_literal
from exporters.excel.workbook_bundle import WorkbookBundle
from exporters.excel.writer import write_table_sheet


# The only CEP columns added to Movimientos. The bank's original data
# remains the source of truth for manual TXT corrections.
MOVEMENT_CEP_COLUMNS = (
    "CEP Estado", "CEP Detalle", "CEP Tiene PDF", "CEP Archivo PDF", "CEP Archivo XML",
)


def _safe_to_remove_columns(workbook) -> bool:
    return not workbook.defined_names and not any(
        sheet.tables or sheet._charts or any(
            cell.data_type == "f" for row in sheet.iter_rows() for cell in row
        ) for sheet in workbook.worksheets
    )


def _compact_existing_movements(workbook):
    ws = workbook["Movimientos"]
    removable = [
        cell.column for cell in ws[1]
        if cell.value and header_key(cell.value).startswith("CEP")
        and cell.value not in MOVEMENT_CEP_COLUMNS
    ]
    duplicate_holder = any(header_key(cell.value) == "CUENTATITULAR" for cell in ws[1])
    safe = _safe_to_remove_columns(workbook)
    if not safe and (removable or duplicate_holder):
        raise ValueError(
            "El Excel tiene fórmulas/tablas que impiden quitar columnas CEP o "
            "Cuenta Titular sin riesgo. Genera TXT directamente o prepara "
            "una copia de Movimientos sin fórmulas."
        )
    for column in sorted(removable, reverse=True):
        ws.delete_cols(column)
    collapse_holder_account(ws)
    return ws


def _control_row(q: CepQuery, result: dict) -> dict:
    """Show precisely the six Banxico query values, not duplicated XML details."""
    state = result["CEP Estado"]
    detail = result["CEP Detalle"]
    if state == "NO_APARECE_EN_ZIP" and not detail:
        detail = "No aparece en los ZIP cargados; verifica lote/token o consulta pendiente"
    return {
        "Fila Movimientos": q.row,
        "Nombre del Archivo": q.filename,
        "No. de Movimiento": q.movement,
        "Sentido": q.direction,
        "Fecha TXT": q.operation_date,
        "Clave de Rastreo TXT": q.tracking,
        "Banco Emisor TXT": q.issuer,
        "Banco Receptor TXT": q.receiver,
        "Cuenta Beneficiaria TXT": q.destination,
        "Formato Cuenta TXT": q.destination_format,
        "Monto TXT": float(q.value) if q.value is not None else None,
        "Línea TXT (fecha base)": q.line() if q.ready else "",
        "Estado de datos": "LISTO" if q.ready else "CORREGIR",
        "Datos por corregir": "; ".join(q.issues),
        "Resultado CEP": state,
        "Motivo resultado": detail,
        "PDF disponible": result["CEP Tiene PDF"],
        "Archivo PDF": result["CEP Archivo PDF"],
        "Archivo XML": result["CEP Archivo XML"],
    }


def append_cep(source: bytes, matches: dict[int, dict], queries: list[CepQuery], evidence: CepEvidence) -> bytes:
    workbook = load_workbook(BytesIO(source))
    ws = _compact_existing_movements(workbook)
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
    write_table_sheet(
        workbook.create_sheet("Control CEP"),
        [_control_row(q, matches[q.row]) for q in queries if q.candidate],
    )
    write_table_sheet(workbook.create_sheet("Datos CEP"), [r.data | {
        "Archivo XML": r.xml_path, "Tiene PDF": "SÍ" if r.pdf else "NO", "Archivo PDF": r.pdf_path,
    } for r in evidence.records])
    for name in ("Control CEP", "Datos CEP"):
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
