"""Visible, editable six-field TXT contract and movement workbook layout."""

from copy import copy
from datetime import date, datetime

from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from cep.catalog import CATALOG_SOURCE_URL, CATALOG_VERIFIED_ON, INSTITUTIONS
from exporters.excel.cells import (
    ensure_columns, header_key, put_columns, remap_filter_columns, set_literal,
)
from exporters.excel.styles import GOB_GREEN, HEADER_FONT
from exporters.excel.writer import write_table_sheet


TXT_COLUMNS = (
    "TXT Fecha de Operación", "TXT Clave de Rastreo", "TXT Banco Emisor",
    "TXT Banco Receptor", "TXT Cuenta Beneficiaria", "TXT Monto",
)
TXT_KEYS = frozenset(map(header_key, TXT_COLUMNS))
TRACE_COLUMNS = (
    "Fecha de Operación Original", "Estado de Fecha",
    "Fecha de Liquidación Original", "Fecha de Corte Original",
)
REVIEW_COLUMN = "Revisión Normalización"
CEP_COLUMNS = (
    "CEP Estado", "CEP Detalle", "CEP Fecha", "CEP Diferencia Días", "CEP Monto",
    "CEP Clave de Rastreo", "CEP Referencia", "CEP Banco Emisor", "CEP Banco Receptor",
    "CEP Nombre Ordenante", "CEP RFC Ordenante", "CEP Cuenta Ordenante",
    "CEP Nombre Beneficiario", "CEP RFC Beneficiario", "CEP Cuenta Beneficiaria",
    "CEP Concepto", "CEP Tiene PDF", "CEP Archivo PDF", "CEP Archivo XML",
)
GREEN_FILL = PatternFill("solid", fgColor=GOB_GREEN)
BLUE_FILL = PatternFill("solid", fgColor="156082")
ORANGE_FILL = PatternFill("solid", fgColor="F4B183")


def has_txt_inputs(headers) -> bool:
    keys = [header_key(h.value if hasattr(h, "value") else h) for h in headers]
    if any(keys.count(key) > 1 for key in TXT_KEYS):
        raise ValueError("Hay columnas TXT duplicadas; conserva una sola columna para cada dato de consulta")
    return any(key in TXT_KEYS for key in keys)


def install_txt_inputs(ws, queries) -> None:
    """Initialize once. Even a blank or partial existing block is authoritative."""
    existing = has_txt_inputs(ws[1])
    ensure_columns(ws, (REVIEW_COLUMN,) + TXT_COLUMNS)
    if existing:
        return
    for q in queries:
        if q.candidate:
            put_columns(ws, q.row, dict(zip(TXT_COLUMNS, (
                q.operation_date, q.tracking, q.issuer, q.receiver, q.destination,
                float(q.value) if q.value is not None else None,
            ))))


def safe_to_reorder(workbook) -> bool:
    return not workbook.defined_names and not any(
        sheet.tables or sheet._charts or sheet.merged_cells.ranges
        or sheet.data_validations.count or len(sheet.conditional_formatting)
        or any(c.data_type == "f" for cells in sheet.iter_rows() for c in cells)
        for sheet in workbook.worksheets
    )


def arrange_movement_blocks(workbook, cep_columns=()) -> None:
    """Original columns, review, six TXT inputs, then official CEP results."""
    ws = workbook["Movimientos"]
    columns = ensure_columns(ws, (REVIEW_COLUMN,) + TXT_COLUMNS + tuple(cep_columns))
    generated = {header_key(REVIEW_COLUMN)} | TXT_KEYS | {header_key(h) for h in cep_columns}
    base = [c.column for c in ws[1] if header_key(c.value) not in generated]
    order = base + [columns[header_key(h)] for h in (REVIEW_COLUMN,) + TXT_COLUMNS + tuple(cep_columns)]
    if order != list(range(1, ws.max_column + 1)):
        if not safe_to_reorder(workbook):
            raise ValueError(
                "No se pueden ordenar los bloques TXT/CEP sin mover referencias del libro. "
                "Puedes generar el TXT directamente; para reorganizar, usa una copia sin fórmulas/tablas."
            )
        cells = {(c.row, c.column): copy(c) for row in ws.iter_rows() for c in row}
        dimensions = {i: copy(ws.column_dimensions[get_column_letter(i)]) for i in order}
        remap_filter_columns(ws, {old: column for column, old in enumerate(order, 1)})
        ws.column_dimensions.clear()
        for column, old in enumerate(order, 1):
            dimension = dimensions[old]
            dimension.index = get_column_letter(column)
            dimension.min = dimension.max = column
            ws.column_dimensions[dimension.index] = dimension
            for row in range(1, ws.max_row + 1):
                source = cells[row, old]
                target = ws.cell(row, column)
                target.value, target.data_type = source.value, source.data_type
                target._style = copy(source._style)
                target.hyperlink = copy(source.hyperlink)
                target.comment = copy(source.comment)
    style_movement_blocks(ws, cep_columns)
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


def style_movement_blocks(ws, cep_columns=()) -> None:
    official = {header_key(h) for h in cep_columns}
    trace = {header_key(h) for h in TRACE_COLUMNS}
    for cell in ws[1]:
        key = header_key(cell.value)
        cell.fill = copy(BLUE_FILL if key in TXT_KEYS else ORANGE_FILL if key in official else GREEN_FILL)
        font = copy(cell.font if cell.has_style else HEADER_FONT)
        font.bold = True
        font.color = "202124" if key in official else "FFFFFF"
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if key in trace:
            ws.column_dimensions[get_column_letter(cell.column)].hidden = True
        if key in TXT_KEYS:
            ws.column_dimensions[get_column_letter(cell.column)].width = (
                19 if key == header_key("TXT Monto") else 28 if key == header_key("TXT Cuenta Beneficiaria") else 29
            )
            for cells in ws.iter_cols(min_col=cell.column, max_col=cell.column, min_row=2):
                for value in cells:
                    value.number_format = (
                        "yyyy-mm-dd" if key == header_key(TXT_COLUMNS[0]) and isinstance(value.value, (date, datetime))
                        else "0.00" if key == header_key(TXT_COLUMNS[-1]) else "@"
                    )
        elif key in official:
            for cells in ws.iter_cols(min_col=cell.column, max_col=cell.column, min_row=2):
                for value in cells:
                    if cell.value == "CEP Fecha":
                        value.number_format = "yyyy-mm-dd"
                    elif cell.value == "CEP Monto":
                        value.number_format = "0.00"
                    elif isinstance(value.value, str):
                        value.number_format = "@"
    ws.row_dimensions[1].height = max(ws.row_dimensions[1].height or 0, 45)


def add_bank_catalog(workbook) -> None:
    name = "Catálogo Bancos"
    if name in workbook:
        # A user-created sheet with this name is never overwritten.
        ws = workbook[name]
        if [c.value for c in ws[1]][:2] != ["Código Banxico", "Institución"]:
            return
        workbook.remove(ws)
    ws = workbook.create_sheet(name)
    write_table_sheet(ws, [
        {"Código Banxico": code, "Institución": institution}
        for code, institution in sorted(INSTITUTIONS.items(), key=lambda item: item[1])
    ])
    set_literal(ws["D1"], "Fuente oficial")
    set_literal(ws["D2"], CATALOG_SOURCE_URL)
    ws["D2"].hyperlink = CATALOG_SOURCE_URL
    set_literal(ws["D3"], "Verificado: " + CATALOG_VERIFIED_ON)
    ws.column_dimensions["A"].width = 19
    ws.column_dimensions["D"].width = 64
    for cell in ws["A"][1:]:
        cell.number_format = "@"
