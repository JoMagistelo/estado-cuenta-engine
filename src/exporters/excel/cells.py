"""Workbook primitives shared by normalization, TXT preparation and CEP output."""

import re
from copy import copy
from datetime import date, datetime

from openpyxl.utils import column_index_from_string, get_column_letter, range_boundaries

from utils.statement_dates import text_key


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


def updated_row(row: dict, values: dict) -> dict:
    """Overlay canonical fields without retaining a conflicting header alias."""
    result = dict(row)
    for label, value in values.items():
        key = next((k for k in result if header_key(k) == header_key(label)), label)
        result[key] = value
    return result


def set_literal(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"
    if isinstance(value, (date, datetime)):
        cell.number_format = "dd/mm/yyyy"


def ensure_columns(ws, headers):
    columns = {header_key(c.value): c.column for c in ws[1] if c.value is not None}
    for label in headers:
        key = header_key(label)
        if key not in columns:
            column = ws.max_column + 1
            cell = ws.cell(1, column)
            cell._style = copy(ws.cell(1, 1)._style)
            set_literal(cell, label)
            columns[key] = column
            ws.column_dimensions[get_column_letter(column)].width = min(36, max(18, len(label) + 2))
    return columns


def put_columns(ws, row_number: int, values: dict):
    columns = ensure_columns(ws, values)
    for header, value in values.items():
        column = columns[header_key(header)]
        cell = ws.cell(row_number, column)
        if not cell.has_style and column > 1:
            cell._style = copy(ws.cell(row_number, 1)._style)
        set_literal(cell, value)
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


def _shift_dimensions(ws, column, delta):
    dimensions = [(key, copy(value)) for key, value in ws.column_dimensions.items()]
    ws.column_dimensions.clear()
    for key, dimension in dimensions:
        first = dimension.min or column_index_from_string(key)
        last = dimension.max or first
        if delta < 0 and first == last == column:
            continue
        if first > column or (delta > 0 and first == column):
            first += delta
        if last >= column:
            last += delta
        dimension.index = get_column_letter(first)
        dimension.min, dimension.max = first, max(first, last)
        ws.column_dimensions[dimension.index] = dimension


def insert_column(ws, column):
    mapping = {i: i + (i >= column) for i in range(1, ws.max_column + 1)}
    ws.insert_cols(column)
    _shift_dimensions(ws, column, 1)
    remap_filter_columns(ws, mapping)


def delete_column(ws, column):
    mapping = {i: i - (i > column) for i in range(1, ws.max_column + 1) if i != column}
    ws.delete_cols(column)
    _shift_dimensions(ws, column, -1)
    remap_filter_columns(ws, mapping)


def remap_filter_columns(ws, mapping):
    """Keep existing filter/sort criteria attached to their original headers."""
    if not ws.auto_filter.ref:
        return
    first, _, _, _ = range_boundaries(ws.auto_filter.ref)
    filters = []
    for condition in ws.auto_filter.filterColumn:
        target = mapping.get(first + condition.colId)
        if target is not None:
            condition.colId = target - 1
            filters.append(condition)
    ws.auto_filter.filterColumn = filters
    state = ws.auto_filter.sortState
    if state:
        kept = []
        for condition in state.sortCondition:
            left, top, right, bottom = range_boundaries(condition.ref)
            if left == right and left in mapping:
                letter = get_column_letter(mapping[left])
                condition.ref = f"{letter}{top}:{letter}{bottom}"
                kept.append(condition)
        state.sortCondition = kept
        state.ref = ws.dimensions
    ws.auto_filter.ref = ws.dimensions
