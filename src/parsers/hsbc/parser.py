from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.robust_recovery import (
    normalize_hsbc_ocr_words,
    repair_datos_cuenta,
    repair_resumen_financiero,
    repair_movimientos,
)


def parse_hsbc(document: DocumentData) -> EstadoCuenta:
    """
    Parser principal de estados de cuenta HSBC.

    Todos los extractores utilizan exclusivamente spatial_words.

    Antes de ejecutar los extractores se aplica una normalización OCR
    extremadamente acotada. Las rutas históricas de Datos, Resumen,
    Productos y Movimientos permanecen intactas; las reparaciones se
    aplican únicamente después de la extracción y sólo cuando existe
    evidencia estructural suficiente.
    """

    # ============================================================
    # FUENTE ÚNICA DE EXTRACCIÓN
    # ============================================================
    #
    # Se conserva una copia normalizada para no modificar el
    # DocumentData original. Actualmente la normalización sólo
    # recupera encabezados inequívocos como:
    #
    #     ETALLE MOVIMIENTOS -> DETALLE MOVIMIENTOS
    #
    # cuando ambas palabras pertenecen al mismo renglón OCR.
    #
    spatial_words = normalize_hsbc_ocr_words(
        document.spatial_words
    )

    # ============================================================
    # DATOS DE CUENTA
    # ============================================================

    datos_cuenta = extract_datos_cuenta_words(
        spatial_words
    )

    repair_datos_cuenta(
        spatial_words,
        datos_cuenta,
    )

    # ============================================================
    # RESUMEN FINANCIERO
    # ============================================================

    resumen_financiero = extract_resumen_financiero_words(
        spatial_words
    )

    repair_resumen_financiero(
        spatial_words,
        resumen_financiero,
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

    movimientos = extract_movimientos_words(
        spatial_words
    )

    # Si el OCR conservó la identidad del primer movimiento pero
    # omitió exclusivamente su importe/saldo, se permite una
    # reconstrucción sólo cuando la contabilidad del segundo
    # movimiento y los totales del resumen lo demuestran.
    repair_movimientos(
        movimientos,
        resumen_financiero,
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
