"""
Compatibilidad temporal.

Será eliminado cuando la interfaz
use directamente exporters.excel
"""

from exporters.excel.batch_exporter import export_batch_excel


def export_processing_results_excel(
    results,
    output_path
):
    return export_batch_excel(
        results,
        output_path
    )