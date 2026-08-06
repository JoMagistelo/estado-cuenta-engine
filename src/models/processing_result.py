from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.estado_cuenta import EstadoCuenta

from validators.resultado_validacion import ResultadoValidacion


@dataclass
class ProcessingResult:
    """
    Resultado completo del procesamiento
    de un estado de cuenta.

    Contiene:

    - información extraída
    - textos originales
    - tablas detectadas
    - validaciones
    """

    file_name: str

    bank_key: str

    estado_cuenta: EstadoCuenta

    raw_text: str

    normalized_text: str

    tables: list[list[list[Any]]] = field(
        default_factory=list
    )

    validaciones: list[ResultadoValidacion] = field(
        default_factory=list
    )

    debug: object | None = None