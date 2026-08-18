from __future__ import annotations

from readers.models import DocumentData

from utils.text_normalizer import normalize_text

from parsers.bbva import parse_bbva
from parsers.banamex import parse_banamex

# ============================================================
# REGISTRO DE PARSERS
# ============================================================


PARSER_REGISTRY = {

    "bbva": parse_bbva,
    "banamex": parse_banamex,

}


# ============================================================
# PROCESAMIENTO DE DOCUMENTO
# ============================================================


def process_single_statement(
    document: DocumentData,
    bank_key: str
):

    """
    Procesa un documento leído por ReaderManager.

    Flujo

    ReaderManager
            ↓
    DocumentData
            ↓
    Normalización
            ↓
    Parser
            ↓
    EstadoCuenta
    """

    document.normalized_text = normalize_text(
        document.raw_text
    )

    parser_fn = PARSER_REGISTRY.get(
        bank_key
    )

    if parser_fn is None:

        raise NotImplementedError(
            f"No existe parser para '{bank_key}'."
        )

    # ========================================================
    # PARSER
    # ========================================================
    #
    # El parser recibe el DocumentData completo.
    #
    # Esto permite que los parsers actuales utilicen:
    #
    #   document.raw_text
    #   document.normalized_text
    #   document.tables
    #   document.spatial_words
    #
    # ========================================================

    estado = parser_fn(
        document
    )

    return estado, document