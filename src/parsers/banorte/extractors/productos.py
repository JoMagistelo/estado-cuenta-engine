from __future__ import annotations

from typing import List, Dict, Any, Optional


from models.otros_productos import OtrosProductos


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
#
# BANAMEX
#
# Actualmente no se dispone de un layout espacial definido
# para la sección de Otros Productos / Productos Financieros.
#
# Mientras no exista una definición espacial específica para
# Banamex, todos los campos se conservan como:
#
#     "N/A"
#
# IMPORTANTE:
#
# Se mantienen las funciones individuales de extracción
# preparadas para que posteriormente puedan sustituirse
# por extracción mediante coordenadas sin modificar la
# función pública ni el modelo de datos.
#
# ============================================================


NA_VALUE = "N/A"


# ============================================================
# TIPO DE DATOS DE ENTRADA
# ============================================================

SpatialWord = Dict[str, Any]


# ============================================================
# UTILIDAD GENERAL
# ============================================================


def na_value() -> str:
    """
    Devuelve el valor por defecto utilizado por Banamex.

    Actualmente todos los campos de Otros Productos se
    representan como "N/A".
    """

    return NA_VALUE


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_contrato(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el contrato del producto financiero.

    Actualmente Banamex no utiliza extracción espacial para
    esta sección, por lo que devuelve "N/A".

    La función queda preparada para reemplazarse posteriormente
    por una extracción basada en coordenadas.
    """

    return na_value()


def extract_producto(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el nombre del producto financiero.

    Actualmente devuelve "N/A".

    Posteriormente puede reemplazarse por extracción espacial
    sin modificar la interfaz pública del extractor.
    """

    return na_value()


def extract_tasa_interes_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae la tasa de interés anual.

    Actualmente devuelve "N/A".
    """

    return na_value()


def extract_gat_nominal_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el GAT nominal anual.

    Actualmente devuelve "N/A".
    """

    return na_value()


def extract_gat_real_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el GAT real anual.

    Actualmente devuelve "N/A".
    """

    return na_value()


def extract_total_comisiones(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el total de comisiones.

    Actualmente devuelve "N/A".
    """

    return na_value()


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Extractor de Otros Productos para Banamex.

    Actualmente Banamex no tiene implementada una extracción
    espacial específica para esta sección.

    Por ello todos los campos se devuelven literalmente como:

        "N/A"

    La estructura queda preparada para implementar
    posteriormente coordenadas específicas de Banamex.

    Campos:

        - contrato
        - producto
        - tasa_interes_anual
        - gat_nominal_anual
        - gat_real_anual
        - total_comisiones
    """

    contrato = extract_contrato(
        words
    )

    producto = extract_producto(
        words
    )

    tasa_interes_anual = (
        extract_tasa_interes_anual(
            words
        )
    )

    gat_nominal_anual = (
        extract_gat_nominal_anual(
            words
        )
    )

    gat_real_anual = (
        extract_gat_real_anual(
            words
        )
    )

    total_comisiones = (
        extract_total_comisiones(
            words
        )
    )

    return OtrosProductos(
        contrato=contrato,
        producto=producto,
        tasa_interes_anual=tasa_interes_anual,
        gat_nominal_anual=gat_nominal_anual,
        gat_real_anual=gat_real_anual,
        total_comisiones=total_comisiones,
    )