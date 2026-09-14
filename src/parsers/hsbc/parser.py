from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.resumen_saldos import extract_resumen_saldos_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .ocr_summary_rescue import recover_resumen_saldos_words


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
    #
    # El layout "Resumen de Saldos" vive en el bloque izquierdo del
    # estado y no comparte la columna X del resumen HSBC moderno. En
    # Tesseract, además, los bordes de la tabla pueden hacer que PSM 3
    # conserve las etiquetas pero omita varios importes. El rescate es
    # local a HSBC y sólo relee ese rectángulo cuando hace falta.
    #

    summary_words = recover_resumen_saldos_words(
        document
    )

    resumen_saldos = extract_resumen_saldos_words(
        summary_words
    )

    if resumen_saldos is None:

        resumen_financiero = extract_resumen_financiero_words(
            spatial_words
        )

    else:

        # Se conserva el extractor existente únicamente para campos que
        # no pertenecen al bloque "Resumen de Saldos". Los importes del
        # bloque nuevo nunca se reemplazan por la tabla/gráfica contigua
        # ni se reconstruyen mediante sumas.
        resumen_legacy = extract_resumen_financiero_words(
            spatial_words
        )

        resumen_saldos.dias_periodo = resumen_legacy.dias_periodo
        if resumen_saldos.tasa_bruta_anual is None:
            resumen_saldos.tasa_bruta_anual = resumen_legacy.tasa_bruta_anual
        resumen_saldos.saldo_promedio_gravable = (
            resumen_legacy.saldo_promedio_gravable
        )
        resumen_saldos.cheques_pagados = resumen_legacy.cheques_pagados
        resumen_saldos.cargos_objetados = resumen_legacy.cargos_objetados
        resumen_saldos.abonos_objetados = resumen_legacy.abonos_objetados

        resumen_financiero = resumen_saldos

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

    # ============================================================
    # CONSTRUCCIÓN DEL ESTADO DE CUENTA
    # ============================================================

    return EstadoCuenta(
        datos_cuenta=datos_cuenta,
        resumen_financiero=resumen_financiero,
        otros_productos=otros_productos,
        movimientos=movimientos,
    )
