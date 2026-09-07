from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.movement_date_hardening import (
    normalize_ambiguous_movement_date_words,
)


def parse_banorte(document: DocumentData) -> EstadoCuenta:
    """
    Parser principal de estados de cuenta BANORTE.

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
    # Banorte puede codificar físicamente una fecha de dos dígitos y una
    # clave numérica como una sola palabra, por ejemplo:
    #
    #     22-JUN-2650114599TRANSBPI07617702
    #
    # Se normaliza únicamente una COPIA de esas palabras ambiguas antes del
    # pipeline de movimientos. El resto de extractores conserva exactamente
    # ``spatial_words`` para no modificar el comportamiento ya validado.
    #

    movement_words = normalize_ambiguous_movement_date_words(
        spatial_words
    )

    movimientos = extract_movimientos_words(
        movement_words
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
