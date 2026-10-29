from __future__ import annotations

from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta
from parsers.periods import combine_periods, split_word_periods

from .beneficiary_enrichment import enrich_banamex_beneficiaries
from .extractors.datos import extract_datos_cuenta_words
from .extractors.resumen import extract_resumen_financiero_words
from .extractors.productos import extract_otros_productos_words
from .extractors.movimientos import extract_movimientos_words
from .extractors.anchored_header import is_cover_page
from .utils.cover_words import align_table_words


def _parse_banamex_words(spatial_words: list[dict]) -> EstadoCuenta:
    """
    Parser principal de estados de cuenta Banamex.

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
    cover_layout = is_cover_page([w for w in spatial_words if int(w.get("page") or 1) == 1])
    if cover_layout:
        spatial_words = align_table_words(spatial_words)

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
    # El extractor histórico permanece intacto. La segunda pasada completa
    # metadatos del tipo «PAGO RECIBIDO DE [BANCO] POR ORDEN DE [ORDENANTE]».
    #

    movimientos = (extract_movimientos_words(spatial_words, recover_missing_dates=True)
                   if cover_layout else extract_movimientos_words(spatial_words))
    enrich_banamex_beneficiaries(movimientos)

    # ============================================================
    # CONSTRUCCIÓN DEL ESTADO DE CUENTA
    # ============================================================

    return EstadoCuenta(
        datos_cuenta=datos_cuenta,
        resumen_financiero=resumen_financiero,
        otros_productos=otros_productos,
        movimientos=movimientos,
    )


def parse_banamex(document: DocumentData) -> EstadoCuenta:
    sections = split_word_periods(document.spatial_words, is_cover_page)
    return combine_periods([_parse_banamex_words(words) for words in sections])
