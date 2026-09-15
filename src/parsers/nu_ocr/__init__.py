from __future__ import annotations

from models.estado_cuenta import EstadoCuenta
from parsers.nu import parse_nu
from readers.models.document_data import DocumentData


def parse_nu_ocr(document: DocumentData) -> EstadoCuenta:
    """Ruta OCR de Nu; comparte reglas semánticas con el layout digital."""
    return parse_nu(document)


__all__ = ["parse_nu_ocr"]
