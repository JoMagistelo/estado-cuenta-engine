"""API de compatibilidad para consumidores del exportador Excel legado.

El punto de entrada preferido para código nuevo es
``exporters.excel.export_batch_excel``. Esta fachada conserva el contrato
existente sin establecer una fecha de retiro no gobernada.
"""

from __future__ import annotations

from pathlib import Path

from exporters.excel.batch_exporter import export_batch_excel
from models.processing_result import ProcessingResult


def export_processing_results_excel(
    results: list[ProcessingResult],
    output_path: str | Path,
) -> Path:
    """Exporta resultados manteniendo el nombre histórico de la API."""
    return export_batch_excel(results, output_path)
