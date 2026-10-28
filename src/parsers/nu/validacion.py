"""Conciliación Nu: importes impresos, rendimientos y traspasos internos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import ClassVar

from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion
from .extractors.common import normalize_upper


# Reglas semánticas del concepto completo; no dependen de coordenadas ni del
# nombre de la Cajita. Operaciones desconocidas permanecen como externas.
FLOW_RULES = (
    (
        "interno",
        re.compile(
            r"^(?:RETIRO (?:DE |EN )?CAJITA|DEPOSITO (?:EN |A )CAJITA|CONGELASTE SALDO|DESCONGELAMOS SALDO)\b"
        ),
    ),
    ("comision", re.compile(r"^(?:COMISION|COMISIONES)\b")),
    ("rendimiento", re.compile(r"^(?:RENDIMIENTO|INTERESES?|DINERO GENERADO)\b")),
)


def flow_kind(movement: Movimiento) -> str:
    text = normalize_upper(movement.concepto_original or movement.concepto)
    # Un memo que mencione una Cajita no convierte un SPEI en traspaso interno.
    if re.search(r"\b(?:TRANSFERENCIA|DEPOSITO)\s+SPEI\b", text):
        return "externo"
    return next((kind for kind, pattern in FLOW_RULES if pattern.search(text)), "externo")


def _decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _total(movements: list[Movimiento], field: str, kind: str | None = None) -> Decimal | None:
    total = Decimal("0.00")
    for movement in movements:
        if kind is not None and flow_kind(movement) != kind:
            continue
        value = _decimal(getattr(movement, field) or 0)
        if value is None:
            return None
        total += value
    return total


def _label(value: Decimal | None) -> str:
    return f"${value:,.2f}" if value is not None else "no disponible"


def _result(
    name: str, expected: float | None, actual: Decimal | None, message: str
) -> ResultadoValidacion:
    target = _decimal(expected)
    difference = actual - target if target is not None and actual is not None else None
    return ResultadoValidacion(
        nombre=name,
        esperado=expected,
        obtenido=float(actual) if actual is not None else None,
        diferencia=float(difference) if difference is not None else None,
        correcto=difference is not None and abs(difference) <= Decimal("0.01"),
        mensaje=message,
    )


@dataclass
class ResumenFinancieroNu(ResumenFinanciero):
    rendimiento_neto: float | None = None
    # El resumen cero sigue siendo comprobable cuando no existen operaciones.
    validar_sin_movimientos: ClassVar[bool] = True

    def validar_total_abonos(self, movimientos: list[Movimiento]) -> ResultadoValidacion:
        gross = _total(movimientos, "abono")
        external = _total(movimientos, "abono", "externo")
        return _result(
            "Total depósitos / abonos",
            self.depositos_abonos,
            external,
            f"Nu: abonos del detalle {_label(gross)}; externos {_label(external)}. "
            "El resumen compara depósitos externos; Cajitas y rendimientos se concilian por separado.",
        )

    def validar_total_cargos(self, movimientos: list[Movimiento]) -> ResultadoValidacion:
        gross = _total(movimientos, "cargo")
        external = _total(movimientos, "cargo", "externo")
        return _result(
            "Total retiros / cargos",
            self.retiros_cargos,
            external,
            f"Nu: cargos del detalle {_label(gross)}; externos {_label(external)}. "
            "El resumen compara gastos externos; Cajitas y comisiones se concilian por separado.",
        )

    def validar_ecuacion_financiera(self) -> ResultadoValidacion:
        values = [
            _decimal(value)
            for value in (
                self.saldo_anterior,
                self.depositos_abonos,
                self.retiros_cargos,
                self.manejo_cuenta,
                self.rendimiento_neto,
            )
        ]
        if all(value is not None for value in values):
            start, deposits, expenses, fees, earnings = values
            actual = start + deposits - expenses - fees + earnings
            message = "Nu: saldo inicial + depósitos - gastos - comisiones + rendimiento neto."
        else:
            actual = None
            message = (
                "Nu: faltan importes impresos para comprobar saldo, comisiones o rendimiento neto."
            )
        return _result("Ecuación financiera", self.saldo_final, actual, message)

    def validar_componentes(self, movimientos: list[Movimiento]) -> list[ResultadoValidacion]:
        """Comprobar las partidas separadas cuando existe evidencia independiente."""
        results = []
        gross, tax, net = map(
            _decimal, (self.intereses_a_favor, self.isr_retenido, self.rendimiento_neto)
        )
        if gross is not None and tax is not None and net is not None:
            results.append(
                _result(
                    "Rendimiento neto Nu",
                    self.rendimiento_neto,
                    gross - tax,
                    "Nu: interés bruto - ISR vs dinero generado neto impreso.",
                )
            )
        for kind, expected, name, positive, negative in (
            ("comision", self.manejo_cuenta, "Comisiones Nu", "cargo", "abono"),
            ("rendimiento", self.rendimiento_neto, "Rendimientos Nu", "abono", "cargo"),
        ):
            if not any(flow_kind(m) == kind for m in movimientos):
                continue
            debit, credit = _total(movimientos, positive, kind), _total(movimientos, negative, kind)
            actual = debit - credit if debit is not None and credit is not None else None
            results.append(
                _result(
                    name,
                    expected,
                    actual,
                    "Nu: partidas explícitas del detalle vs resumen impreso.",
                )
            )
        return results
