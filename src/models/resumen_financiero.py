from dataclasses import dataclass
from typing import Optional


@dataclass
class ResumenFinanciero:
    """
    Información financiera resumida del estado de cuenta.
    Incluye rendimiento, comisiones y comportamiento del periodo.
    """
    # Rendimiento

    saldo_promedio: Optional[float]
    dias_periodo: int
    tasa_bruta_anual: float
    saldo_promedio_gravable: float
    intereses_a_favor: float
    isr_retenido: float


    # Comisiones

    cheques_pagados: int
    manejo_cuenta: float

    # Total Comisiones

    cargos_objetados: float
    abonos_objetados: float


    # Comportamiento

    saldo_anterior: float
    depositos_abonos: float
    retiros_cargos: float
    saldo_final: float

    saldo_promedio_minimo_mensual: float
    saldo_global: float    