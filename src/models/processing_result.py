from __future__ import annotations

from dataclasses import dataclass, field

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
    - método utilizado para procesar el documento
    """

    file_name: str

    bank_key: str

    estado_cuenta: EstadoCuenta

    raw_text: str

    normalized_text: str

    validaciones: list[ResultadoValidacion] = field(
        default_factory=list
    )

    processing_method: str = "Digital"

    debug: object | None = None