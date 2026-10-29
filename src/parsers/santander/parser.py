from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from models.otros_productos import OtrosProductos
from readers.models.document_data import DocumentData
from parsers.periods import combine_periods, split_word_periods

from .extractors.common import group_lines, normalized
from .extractors.datos import extract_datos_cuenta_lines
from .extractors.movimientos import extract_movimientos_lines
from .extractors.resumen import extract_resumen_financiero_lines


def _is_cover(words: list[dict]) -> bool:
    text = " ".join(normalized(l.text) for l in group_lines(words))
    return all(marker in text for marker in ("RESUMEN INFORMATIVO", "CUENTA DE CHEQUES", "SALDO INICIAL"))


def _parse_santander_words(words: list[dict]) -> EstadoCuenta:
    """Una ruta semántica para words digitales, PaddleOCR y PDF OCR releído."""
    lines = group_lines(words)
    datos = extract_datos_cuenta_lines(lines)
    return EstadoCuenta(
        datos_cuenta=datos,
        resumen_financiero=extract_resumen_financiero_lines(lines),
        movimientos=extract_movimientos_lines(lines, datos.numero_cuenta),
        otros_productos=OtrosProductos("N/A", "N/A", "N/A", "N/A", "N/A", "N/A"),
    )


def parse_santander(document: DocumentData) -> EstadoCuenta:
    sections = split_word_periods(document.spatial_words, _is_cover)
    return combine_periods([_parse_santander_words(words) for words in sections])
