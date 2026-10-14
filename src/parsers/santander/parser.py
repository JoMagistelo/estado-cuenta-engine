from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from models.otros_productos import OtrosProductos
from readers.models.document_data import DocumentData

from .extractors.common import group_lines
from .extractors.datos import extract_datos_cuenta_lines
from .extractors.movimientos import extract_movimientos_lines
from .extractors.resumen import extract_resumen_financiero_lines


def parse_santander(document: DocumentData) -> EstadoCuenta:
    """Una ruta semántica para words digitales, PaddleOCR y PDF OCR releído."""
    lines = group_lines(document.spatial_words)
    datos = extract_datos_cuenta_lines(lines)
    return EstadoCuenta(
        datos_cuenta=datos,
        resumen_financiero=extract_resumen_financiero_lines(lines),
        movimientos=extract_movimientos_lines(lines, datos.numero_cuenta),
        otros_productos=OtrosProductos("N/A", "N/A", "N/A", "N/A", "N/A", "N/A"),
    )
