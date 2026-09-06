"""Exportación por lote de resultados normalizados a un libro Excel."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from exporters.excel.writer import write_table_sheet
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from models.processing_result import ProcessingResult


def pending_ocr_selection_files(results: list[ProcessingResult]) -> list[str]:
    """Devuelve los archivos OCR duales que aún no tienen elección manual."""
    pending: list[str] = []
    for result in results:
        review = getattr(result, "ocr_review", None)
        if review is None:
            continue
        if review.requires_user_selection and not review.selection_confirmed:
            pending.append(result.file_name)
    return pending


def _restore_confirmed_ocr_results(results: list[ProcessingResult]) -> None:
    pending = pending_ocr_selection_files(results)
    if pending:
        names = ", ".join(pending[:4])
        if len(pending) > 4:
            names += f" y {len(pending) - 4} más"
        raise ValueError(
            "Antes de exportar, elige explícitamente Tesseract o PaddleOCR "
            f"para: {names}."
        )

    for result in results:
        review = getattr(result, "ocr_review", None)
        if review is not None and review.requires_user_selection:
            result.restore_confirmed_ocr_engine()


def export_batch_excel(
    results: list[ProcessingResult],
    output_path: str | Path,
) -> Path:
    """Genera un libro Excel con una hoja por tabla normalizada.

    El directorio de salida se crea cuando no existe. Los nombres de hoja se
    limitan a 31 caracteres para cumplir la restricción de Excel. Si un PDF
    cuenta con dos resultados OCR, la exportación exige la elección explícita
    del usuario y nunca conserva automáticamente el motor recomendado.
    """
    _restore_confirmed_ocr_results(results)
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
