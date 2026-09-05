"""Exportación por lote de resultados normalizados a un libro Excel."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from exporters.excel.writer import write_table_sheet
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from models.processing_result import ProcessingResult


def export_batch_excel(
    results: list[ProcessingResult],
    output_path: str | Path,
) -> Path:
    """Genera un libro Excel con una hoja por tabla normalizada.

    El directorio de salida se crea cuando no existe. Los nombres de hoja se
    limitan a 31 caracteres para cumplir la restricción de Excel.
    """
    tables = estado_cuenta_to_tables(results)

    workbook = Workbook()
    workbook.remove(workbook.active)

    for table_name, rows in tables.items():
        worksheet = workbook.create_sheet(title=table_name[:31])
        write_table_sheet(worksheet, rows)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    return destination
