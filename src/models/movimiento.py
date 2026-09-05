"""Modelo de dominio para movimientos bancarios normalizados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Movimiento:
    """Representa una operación individual extraída de un estado de cuenta.

    El modelo conserva tanto campos normalizados como el concepto original para
    permitir trazabilidad técnica durante validación y exportación.
    """

    fecha_operacion: str
    fecha_liquidacion: str | None
    concepto: str
    tipo_operacion: str | None
    cargo: float
    abono: float

    referencia: str | None = None
    autorizacion: str | None = None
    beneficiario: str | None = None
    cuenta_beneficiario: str | None = None
    clabe_beneficiario: str | None = None
    clave_rastreo: str | None = None
    rfc: str | None = None
    sucursal: str | None = None
    caja: str | None = None
    hora_operacion: str | None = None

    # Algunos formatos exponen uno o ambos saldos asociados al movimiento.
    saldo_operacion: float = 0.0
    saldo_liquidacion: float = 0.0

    concepto_original: str | None = None
