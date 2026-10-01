from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from models.otros_productos import OtrosProductos
from readers.models.document_data import DocumentData

from .extractors.common import group_lines
from .extractors.datos import extract_datos_cuenta_lines
from .extractors.movimientos import extract_movimientos_lines
from .extractors.resumen import extract_resumen_financiero_lines


def parse_azteca(document: DocumentData) -> EstadoCuenta:
    """Lee variantes breves y SPEI detalladas desde palabras espaciales OCR."""
    lines = group_lines(document.spatial_words)
    datos = extract_datos_cuenta_lines(lines)
    return EstadoCuenta(
        datos_cuenta=datos,
        resumen_financiero=extract_resumen_financiero_lines(lines),
        movimientos=extract_movimientos_lines(lines),
        # El modelo requiere esta sección. Las ofertas informativas no son
        # productos contratados; no se implementa extracción de otros productos.
        otros_productos=OtrosProductos("N/A", "N/A", "N/A", "N/A", "N/A", "N/A"),
    )
