from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from parsers.banorte.utils.amount_sign_hardening import (
    normalize_trailing_negative_amount_words,
)
from readers.models.document_data import DocumentData

from .extractors.datos import extract_datos_cuenta_words
from .extractors.movimientos import extract_movimientos_words
from .extractors.productos import extract_otros_productos_words
from .extractors.resumen import extract_resumen_financiero_words


def parse_banorte_ocr(document: DocumentData) -> EstadoCuenta:
    """Parser especializado para estados de cuenta Banorte leídos por Tesseract."""
    words = document.spatial_words

    # Banorte también puede representar un importe negativo con el signo al
    # final (por ejemplo ``53.00-``). El extractor OCR ya entiende ``-53.00``;
    # normalizamos sólo una copia destinada a movimientos para preservar sin
    # cambios datos de cuenta, resumen y otros productos.
    movement_words = normalize_trailing_negative_amount_words(words)

    return EstadoCuenta(
        datos_cuenta=extract_datos_cuenta_words(words),
        resumen_financiero=extract_resumen_financiero_words(words),
        otros_productos=extract_otros_productos_words(words),
        movimientos=extract_movimientos_words(movement_words),
    )
