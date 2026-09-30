"""Conciliación exclusiva de Azteca sin modificar cifras impresas ni movimientos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion


def _money(value: float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and number >= 0 and number == number.quantize(Decimal("0.01")):
            return number
    except (InvalidOperation, ValueError):
        pass
    return None


@dataclass
class ResumenFinancieroAzteca(ResumenFinanciero):
    # Evidencia independiente del resumen: el pie de la tabla de retiros.
    total_retiros_tabla: float | None = None

    def validar_total_cargos(self, movimientos: list[Movimiento]) -> ResultadoValidacion | None:
        """Devuelve una conciliación con advertencia sólo para el patrón respaldado.

        Las muestras respaldan una omisión menor a un peso, no una tolerancia
        monetaria general ni una regla del banco para todos sus estados.
        """
        reported = _money(self.retiros_cargos)
        footer = _money(self.total_retiros_tabla)
        start = _money(self.saldo_anterior)
        deposits = _money(self.depositos_abonos)
        final = _money(self.saldo_final)
        if any(value is None for value in (reported, footer, start, deposits, final)):
            return None
        if footer != reported or reported != reported.to_integral_value():
            return None

        cargos = []
        abonos = []
        for movement in movimientos:
            cargo, abono = _money(movement.cargo), _money(movement.abono)
            # No aceptar el patrón si hay filas parciales, sin importe o con
            # cargo y abono a la vez: una extracción incompleta debe revisarse.
            if (
                cargo is None
                or abono is None
                or bool(cargo) == bool(abono)
                or not movement.fecha_operacion
                or not movement.concepto
            ):
                return None
            cargos.append(cargo)
            abonos.append(abono)

        detail = sum(cargos, Decimal("0.00"))
        difference = detail - reported
        if not Decimal("0.00") < difference < Decimal("1.00"):
            return None
        if reported != sum(
            (c.to_integral_value(rounding=ROUND_DOWN) for c in cargos), Decimal("0.00")
        ):
            return None
        # Los abonos y la ecuación impresa deben coincidir exactamente a centavos.
        # La suma del detalle NO reemplaza el resumen para hacer pasar esta prueba.
        if sum(abonos, Decimal("0.00")) != deposits or start + deposits - reported != final:
            return None

        return ResultadoValidacion(
            nombre="Total retiros / cargos",
            esperado=float(reported),
            obtenido=float(detail),
            diferencia=float(difference),
            correcto=True,
            mensaje=(
                "Azteca: posible omisión de centavos en el total. "
                f"Reportado ${reported:,.2f} · Detalle ${detail:,.2f} · "
                f"Diferencia ${difference:,.2f}."
            ),
            advertencia=True,
        )
