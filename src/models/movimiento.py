from dataclasses import dataclass
from typing import Optional


@dataclass
class Movimiento:
    """
    Representa una operación individual del estado de cuenta.
    Mantiene el concepto original y los datos estructurados
    obtenidos de su análisis.
    """

    # Fechas

    fecha_operacion: str
    fecha_liquidacion: Optional[str]


    # Descripción bancaria

    concepto: str
    tipo_operacion: Optional[str]


    # Importes

    cargo: float
    abono: float


    # Referencias bancarias

    referencia: str | None = None
    autorizacion: str | None = None


    # Datos extraídos del concepto

    beneficiario: str | None = None
    cuenta_beneficiario: str | None = None
    clabe_beneficiario: str | None = None

    rfc: str | None = None

    sucursal: str | None = None
    caja: str | None = None
    hora_operacion: str | None = None

    # Saldos BBVA
    saldo_operacion: float =0.0
    saldo_liquidacion: float =0.0

    # Conservamos el texto original siempre

    concepto_original: str | None = None