from __future__ import annotations

from typing import List

from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from .resultado_validacion import ResultadoValidacion


TOLERANCIA = 0.01


def validar_movimientos(
    movimientos: List[Movimiento],
    resumen: ResumenFinanciero,
):
    """
    Ejecuta las validaciones financieras que sean posibles.

    Una validación solamente se genera cuando existen todos los
    datos necesarios para realizarla.

    Esto evita que la ausencia de un campo opcional del resumen
    provoque un error de ejecución y detenga el procesamiento
    completo de los estados de cuenta.
    """

    resultados = []

    # =====================================================
    # TOTAL ABONOS
    # =====================================================

    if resumen.depositos_abonos is not None:

        total_abonos = sum(
            m.abono or 0
            for m in movimientos
        )

        diferencia = (
            total_abonos
            - resumen.depositos_abonos
        )

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

    # =====================================================
    # TOTAL CARGOS
    # =====================================================

    if resumen.retiros_cargos is not None:

        total_cargos = sum(
            m.cargo or 0
            for m in movimientos
        )

        diferencia = (
            total_cargos
            - resumen.retiros_cargos
        )

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

    # =====================================================
    # SALDO FINAL
    # =====================================================

    if movimientos and resumen.saldo_final is not None:

        ultimo = movimientos[-1]

        saldo_movimiento = (
            ultimo.saldo_liquidacion
            or ultimo.saldo_operacion
            or None
        )

        # -------------------------------------------------
        # Solo podemos validar si tenemos un saldo real
        # en el último movimiento.
        # -------------------------------------------------

        if saldo_movimiento is not None:

            diferencia = (
                saldo_movimiento
                - resumen.saldo_final
            )

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

    # =====================================================
    # ECUACIÓN FINANCIERA
    # =====================================================

    if all(
        x is not None
        for x in [
            resumen.saldo_anterior,
            resumen.depositos_abonos,
            resumen.retiros_cargos,
            resumen.saldo_final,
        ]
    ):

        saldo_calculado = (
            resumen.saldo_anterior
            + resumen.depositos_abonos
            - resumen.retiros_cargos
        )

        diferencia = (
            saldo_calculado
            - resumen.saldo_final
        )

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