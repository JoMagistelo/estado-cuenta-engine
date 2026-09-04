from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.spei_received_party_repair import (
    repair_received_spei_parties_in_movements,
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
    # El extractor localiza el inicio real de la tabla, reconstruye
    # filas OCR mediante continuidad contable y enriquece únicamente
    # los cruces SPEI confirmados.
    #

    movimientos = extract_movimientos_words(
        spatial_words
    )

    # Refuerzo conservador para SPEI recibidos. Sólo actúa cuando una
    # misma word invade geométricamente Participante Emisor y Nombre
    # del Ordenante y el fragmento izquierdo valida contra un
    # participante conocido. Los casos normales conservan la ruta
    # histórica sin cambios.
    repair_received_spei_parties_in_movements(
        spatial_words,
        movimientos,
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
