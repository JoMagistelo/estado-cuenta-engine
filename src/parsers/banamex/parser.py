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
from .extractors.tabular_cover import TabularCover
from .extractors.tabular_movements import extract_tabular_movements
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
    first_page = [w for w in spatial_words if int(w.get("page") or 1) == 1]
    grids = {int(w["page"]): w["_tabular_grid"] for w in spatial_words if "_tabular_grid" in w}
    tabular_cover = TabularCover.detect(first_page) if grids else None
    if tabular_cover is not None:
        data, summary, products = tabular_cover.extract(spatial_words)
        movements = extract_tabular_movements(spatial_words, grids)
        enrich_banamex_beneficiaries(movements, require_valid_clabe=True)
        return EstadoCuenta(data, products, summary, movements)

    cover_layout = is_cover_page(first_page)
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
    words = document.spatial_words
    raw_grids = document.metadata.get("banamex_tabular_pages") or {}
    if not raw_grids:
        return combine_periods([_parse_banamex_words(part)
                                for part in split_word_periods(words, is_cover_page)])
    grids = {int(page): grid for page, grid in raw_grids.items()}
    if grids:
        # split_word_periods rebasa las páginas. La geometría viaja con una
        # palabra de cada página sin modificar las palabras del lector.
        words = [{**w, "_tabular_grid": grids.pop(int(w["page"]))}
                 if int(w.get("page") or 1) in grids else w for w in words]
    sections = split_word_periods(words, lambda page: is_cover_page(page) or
                                  TabularCover.detect(page) is not None)
    return combine_periods([_parse_banamex_words(part) for part in sections])
