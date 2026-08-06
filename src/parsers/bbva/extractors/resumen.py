from __future__ import annotations


from models.resumen_financiero import ResumenFinanciero


from utils.parsers import (
    parse_entero,
    parse_monto,
)



def extract_resumen_financiero(
    normalized_text: str
) -> ResumenFinanciero:

    """
    Extrae el resumen financiero
    del estado de cuenta BBVA.
    """


    saldo_promedio = parse_monto(
        r"Saldo Promedio\s+([\d,]+\.\d{2})",
        normalized_text
    )


    dias_periodo = parse_entero(
        r"D[íi]as\s+del\s+Period[oó]\s+(\d+)",
        normalized_text,
        default=30
    )


    tasa_bruta_anual = parse_monto(
        r"Tasa Bruta Anual\s*%\s*([\d,]+\.\d{2,3})",
        normalized_text
    )


    saldo_promedio_gravable = parse_monto(
        r"Saldo Promedio Gravable\s+([\d,]+\.\d{2})",
        normalized_text
    )


    intereses_a_favor = parse_monto(
        r"Intereses a Favor\s*\(\+\)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    isr_retenido = parse_monto(
        r"ISR Retenido\s*\(-\)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    saldo_anterior = parse_monto(
        r"Saldo Anterior\s+([\d,]+\.\d{2})",
        normalized_text
    )


    depositos_abonos = parse_monto(
        r"Dep[óo]sitos\s*/\s*Abonos\s*\(\+\)\s+(?:\d+)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    retiros_cargos = parse_monto(
        r"Retiros\s*/\s*Cargos\s*\(-\)\s+(?:\d+)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    saldo_final = parse_monto(
        r"Saldo Final\s+([\d,]+\.\d{2})",
        normalized_text
    )


    saldo_promedio_minimo_mensual = parse_monto(
        r"Saldo Promedio M[íi]nimo Mensual:?\s+([\d,]+\.\d{2})",
        normalized_text
    )


    cheques_pagados = parse_entero(
        r"Cheques pagados\s+(\d+)",
        normalized_text
    )


    manejo_cuenta = parse_monto(
        r"Manejo de Cuenta\s+([\d,]+\.\d{2})",
        normalized_text
    )


    cargos_objetados = parse_monto(
        r"Cargos Objetados\s+(?:\d+)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    abonos_objetados = parse_monto(
        r"Abonos Objetados\s+(?:\d+)\s+([\d,]+\.\d{2})",
        normalized_text
    )


    saldo_global = parse_monto(
        r"Saldo Global\s*\$?\s*([\d,]+\.\d{2})",
        normalized_text
    )



    return ResumenFinanciero(

        saldo_promedio=saldo_promedio,

        dias_periodo=dias_periodo,

        tasa_bruta_anual=tasa_bruta_anual,

        saldo_promedio_gravable=saldo_promedio_gravable,

        intereses_a_favor=intereses_a_favor,

        isr_retenido=isr_retenido,

        cheques_pagados=cheques_pagados,

        manejo_cuenta=manejo_cuenta,

        cargos_objetados=cargos_objetados,

        abonos_objetados=abonos_objetados,

        saldo_anterior=saldo_anterior,

        depositos_abonos=depositos_abonos,

        retiros_cargos=retiros_cargos,

        saldo_final=saldo_final,

        saldo_promedio_minimo_mensual=saldo_promedio_minimo_mensual,

        saldo_global=saldo_global

    )