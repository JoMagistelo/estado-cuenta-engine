from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from models.processing_result import ProcessingResult

from mappers.estado_cuenta_tables import (
    estado_cuenta_to_tables
)

from exporters.excel.writer import (
    write_table_sheet
)



def export_batch_excel(
    results: list[ProcessingResult],
    output_path: str | Path
) -> Path:


    mappers = estado_cuenta_to_tables(results)


    wb = Workbook()

    wb.remove(
        wb.active
    )


    for table_name, rows in mappers.items():

        ws = wb.create_sheet(
            title=table_name[:31]
        )


        write_table_sheet(
            ws,
            rows
        )


    output_path = Path(
        output_path
    )


    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    wb.save(
        output_path
    )


    return output_path