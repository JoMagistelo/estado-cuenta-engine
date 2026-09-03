from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from readers.models.document_data import DocumentData

from .extractors.datos import extract_datos_cuenta_words
from .extractors.movimientos import extract_movimientos_words
from .extractors.productos import extract_otros_productos_words
from .extractors.resumen import extract_resumen_financiero_words


def parse_mercado_pago(document: DocumentData) -> EstadoCuenta:
    """Construye un estado de cuenta Mercado Pago desde ``spatial_words``."""
    words = document.spatial_words
    return EstadoCuenta(
        datos_cuenta=extract_datos_cuenta_words(words),
        resumen_financiero=extract_resumen_financiero_words(words),
        otros_productos=extract_otros_productos_words(words),
        movimientos=extract_movimientos_words(words),
    )
