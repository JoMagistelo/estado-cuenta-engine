from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.spei_received_counterparty_repair import (
    repair_received_spei_counterparties,
)


def parse_hsbc(document: DocumentData) -> EstadoCuenta:
    """
    Parser principal de estados de cuenta HSBC.

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
    # espaciales contenidas en DocumentData.
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
    # Este extractor ya funciona correctamente y se conserva
    # exactamente con el mismo mecanismo.
    #

    movimientos = extract_movimientos_words(
        spatial_words
    )

    # Reparación posterior, deliberadamente acotada a SPEI recibidos
    # donde una misma word OCR cruza la frontera Participante Emisor /
    # Nombre del Ordenante. Si no existe esa evidencia geométrica y un
    # participante bancario validable, los movimientos quedan intactos.
    repair_received_spei_counterparties(
        movimientos,
        spatial_words,
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