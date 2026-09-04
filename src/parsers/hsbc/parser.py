from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta

from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .utils.movement_accounting_recovery import (
    strengthen_hsbc_scanned_movements,
)
from .utils.movement_supplemental_fill import (
    fill_existing_movements_from_supplemental,
)
from .utils.spei_received_party_repair import (
    repair_received_spei_parties_in_movements,
)
from .utils.summary_accounting_recovery import (
    strengthen_hsbc_summary_accounting,
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

    # Refuerzo del bloque contable: sólo sustituye saldo anterior,
    # depósitos, retiros y saldo final cuando al menos tres valores
    # están anclados de forma independiente y la identidad contable
    # cierra. Si faltan dos o más datos no fuerza ninguna inferencia.
    strengthen_hsbc_summary_accounting(
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
    #
    # El extractor localiza el inicio real de la tabla, reconstruye
    # filas OCR mediante continuidad contable y enriquece únicamente
    # los cruces SPEI confirmados.
    #

    movimientos = extract_movimientos_words(
        spatial_words
    )

    # Una segunda lectura de las mismas words se usa solamente como
    # evidencia para completar campos ausentes de una fila que ya fue
    # aceptada. La Referencia/Serial debe coincidir de forma única y
    # nunca se sustituye un importe o saldo ya publicado.
    fill_existing_movements_from_supplemental(
        spatial_words,
        movimientos,
    )

    # Refuerzo exclusivo para escaneados degradados. Reutiliza el
    # parser histórico y sólo agrega filas que formen una cadena
    # contable exacta entre saldos ya observados. También valida la
    # serie completa contra los saldos de apertura/cierre antes de
    # corregir balances OCR.
    movimientos = strengthen_hsbc_scanned_movements(
        spatial_words,
        movimientos,
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
