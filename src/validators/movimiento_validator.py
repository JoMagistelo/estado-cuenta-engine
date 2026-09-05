"""Validaciones de consistencia entre movimientos y resumen financiero."""

from __future__ import annotations

from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion


# Tolerancia monetaria del contrato actual basado en float. Una migración a
# Decimal debe abordarse de forma transversal en modelos, parsers y exportadores.
TOLERANCIA = 0.01


def validar_movimientos(
    movimientos: list[Movimiento],
    resumen: ResumenFinanciero,
) -> list[ResultadoValidacion]:
    """Ejecuta únicamente las validaciones cuyos datos están disponibles."""
    resultados: list[ResultadoValidacion] = []

    if resumen.depositos_abonos is not None:
        total_abonos = sum(m.abono or 0 for m in movimientos)
        diferencia = total_abonos - resumen.depositos_abonos
        resultados.append(
            ResultadoValidacion(
                nombre="Total depósitos / abonos",
                esperado=resumen.depositos_abonos,
                obtenido=total_abonos,
                diferencia=diferencia,
                correcto=abs(diferencia) <= TOLERANCIA,
                mensaje="Suma de movimientos vs resumen financiero",
            )
        )

    if resumen.retiros_cargos is not None:
        total_cargos = sum(m.cargo or 0 for m in movimientos)
        diferencia = total_cargos - resumen.retiros_cargos
        resultados.append(
            ResultadoValidacion(
                nombre="Total retiros / cargos",
                esperado=resumen.retiros_cargos,
                obtenido=total_cargos,
                diferencia=diferencia,
                correcto=abs(diferencia) <= TOLERANCIA,
                mensaje="Suma de movimientos vs resumen financiero",
            )
        )

    if movimientos and resumen.saldo_final is not None:
        ultimo = movimientos[-1]
        # No convertir 0.0 a ausencia: cero es un saldo válido.
        saldo_movimiento = ultimo.saldo_liquidacion or ultimo.saldo_operacion

        if saldo_movimiento is not None:
            diferencia = saldo_movimiento - resumen.saldo_final
            resultados.append(
                ResultadoValidacion(
                    nombre="Saldo final",
                    esperado=resumen.saldo_final,
                    obtenido=saldo_movimiento,
                    diferencia=diferencia,
                    correcto=abs(diferencia) <= TOLERANCIA,
                    mensaje="Último movimiento vs saldo final",
                )
            )

    if all(
        value is not None
        for value in (
            resumen.saldo_anterior,
            resumen.depositos_abonos,
            resumen.retiros_cargos,
            resumen.saldo_final,
        )
    ):
        saldo_calculado = (
            resumen.saldo_anterior
            + resumen.depositos_abonos
            - resumen.retiros_cargos
        )
        diferencia = saldo_calculado - resumen.saldo_final
        resultados.append(
            ResultadoValidacion(
                nombre="Ecuación financiera",
                esperado=resumen.saldo_final,
                obtenido=saldo_calculado,
                diferencia=diferencia,
                correcto=abs(diferencia) <= TOLERANCIA,
                mensaje="Saldo anterior + abonos - cargos",
            )
        )

    return resultados
