from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.amount_sign_hardening import (
    ensure_signed_amount_operation_types,
    normalize_trailing_negative_amount_words,
)


def parse_bbva(document: DocumentData) -> EstadoCuenta:
    """
    Parser principal de estados de cuenta BBVA.

    Todos los extractores utilizan exclusivamente spatial_words.

    Flujo:

        DocumentData
             │
             ▼
        spatial_words
             │
        ┌────┼───────────────┐
        ▼    ▼               ▼
      Datos Resumen       Productos
        │    │               │
        └────┴───────────────┘
                 │
                 ▼
             Movimientos
                 │
                 ▼
            EstadoCuenta
    """

    # ============================================================
    # FUENTE ÚNICA DE EXTRACCIÓN
    # ============================================================
    #
    # Todos los extractores trabajan sobre las mismas palabras
    # espaciales obtenidas por PDFWordReader.
    #
    spatial_words = document.spatial_words

    # ============================================================
    # DATOS DE CUENTA
    # ============================================================

    datos_cuenta = extract_datos_cuenta_words(
        spatial_words
    )

    # ============================================================
    # RESUMEN FINANCIERO
    # ============================================================

    resumen_financiero = extract_resumen_financiero_words(
        spatial_words
    )

    # ============================================================
    # OTROS PRODUCTOS
    # ============================================================

    otros_productos = extract_otros_productos_words(
        spatial_words
    )

    # ============================================================
    # MOVIMIENTOS
    # ============================================================
    #
    # BBVA puede imprimir importes negativos con el signo al final (53.00-).
    # Se normaliza únicamente una COPIA de las palabras destinadas al extractor
    # de movimientos. Datos, resumen y productos siguen recibiendo exactamente
    # ``spatial_words`` para conservar el comportamiento ya validado.
    #

    movement_words = normalize_trailing_negative_amount_words(
        spatial_words
    )

    movimientos = extract_movimientos_words(
        movement_words
    )

    # El extractor histórico determina CARGO/ABONO con importes > 0. Para el
    # nuevo caso negativo, la columna monetaria sigue siendo la fuente de verdad
    # y sólo se completa el tipo cuando todavía no fue resuelto.
    movimientos = ensure_signed_amount_operation_types(
        movimientos
    )

    # ============================================================
    # CONSTRUCCIÓN DEL ESTADO DE CUENTA
    # ============================================================

    return EstadoCuenta(
        datos_cuenta=datos_cuenta,
        resumen_financiero=resumen_financiero,
        otros_productos=otros_productos,
        movimientos=movimientos,
    )