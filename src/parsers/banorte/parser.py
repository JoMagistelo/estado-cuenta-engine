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
    # También puede imprimir importes negativos con el signo al final:
    #
    #     53.00-
    #
    # Ambas normalizaciones se aplican únicamente a una COPIA de las palabras
    # destinadas al extractor de movimientos. El resto de extractores conserva
    # exactamente ``spatial_words`` para no modificar comportamiento validado.
    #

    movement_words = normalize_ambiguous_movement_date_words(
        spatial_words
    )

    movement_words = normalize_trailing_negative_amount_words(
        movement_words
    )

    movimientos = extract_movimientos_words(
        movement_words
    )

    # El extractor digital histórico determina CARGO/ABONO con importes > 0.
    # Para el caso nuevo de un importe negativo válido conservamos la columna
    # como fuente de verdad y completamos el tipo sin alterar tipos ya resueltos.
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
