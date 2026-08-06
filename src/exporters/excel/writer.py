from __future__ import annotations

from typing import Any, Dict, List

from openpyxl.styles import Alignment

from exporters.excel.styles import (
    HEADER_FILL,
    HEADER_FONT,
)


_CENTER = Alignment(
    vertical="center"
)


def write_table_sheet(
    ws,
    rows: List[Dict[str, Any]]
):

    """
    Escribe una colección de diccionarios como una hoja de Excel.

    Cada diccionario representa una fila y la unión de todas las llaves
    define las columnas de la tabla.
    """

    if not rows:

        ws.append(
            ["Sin información"]
        )

        return



    headers = []

    for row in rows:

        for key in row:

            if key not in headers:

                headers.append(key)


    ws.append(
        headers
    )

    for row in rows:

        ws.append(
            [
                row.get(header)
                for header in headers
            ]
        )

    for cell in ws[1]:

        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = _CENTER

    ws.freeze_panes = "A2"

    ws.auto_filter.ref = ws.dimensions

    for column_cells in ws.columns:

        length = max(
            len(str(cell.value))
            if cell.value is not None
            else 0
            for cell in column_cells
        )

        ws.column_dimensions[
            column_cells[0].column_letter
        ].width = min(
            length + 2,
            40
        )

    for row in ws.iter_rows():

        for cell in row:

            if isinstance(cell.value, float):

                cell.number_format = "#,##0.00"