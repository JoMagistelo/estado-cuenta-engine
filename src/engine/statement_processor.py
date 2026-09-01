from __future__ import annotations

from readers.models import DocumentData

from utils.text_normalizer import normalize_text

from parsers.bbva import parse_bbva
from parsers.banamex import parse_banamex
from parsers.banorte import parse_banorte
from parsers.hsbc import parse_hsbc
from parsers.scotiabank import parse_scotiabank
from parsers.cetes import parse_cetes
from parsers.mifel import parse_mifel


# ============================================================
# REGISTRO DE PARSERS
# ============================================================


PARSER_REGISTRY = {

    "bbva": parse_bbva,
    "banamex": parse_banamex,
    "banorte": parse_banorte,
    "hsbc": parse_hsbc,
    "scotiabank": parse_scotiabank,
    "cetes": parse_cetes,
    "mifel": parse_mifel


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
    # PARSER: El parser recibe el DocumentData completo.
    # ========================================================

    estado = parser_fn(
        document
    )

    return estado, document