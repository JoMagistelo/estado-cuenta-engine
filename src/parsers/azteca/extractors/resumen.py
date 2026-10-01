from __future__ import annotations

import re

from ..validacion import ResumenFinancieroAzteca

from .common import Line, amount_for_label, group_lines, normalized


def _total_retiros_tabla(lines: list[Line]) -> float | None:
    inside = False
    for line in lines:
        text = normalized(line.text)
        if re.match(r"^TOTAL (?:DE )?RETIROS DEL MES", text):
            inside = True
        elif inside and re.match(r"^TOTAL\s*\$", text):
            return amount_for_label([line], r"^TOTAL\s*\$")
        elif re.match(
            r"^(?:CUANTO RECIBI|COMISIONES QUE|PARA FINES|IMPUESTOS RETENIDOS|"
            r"CARGOS OBJETADOS|TUS MOVIMIENTOS|GLOSARIO|TOTAL (?:DE )?DEPOSITOS DEL MES)",
            text,
        ):
            inside = False
    return None


def extract_resumen_financiero_lines(lines: list[Line]) -> ResumenFinancieroAzteca:
    def value(pattern: str) -> float | None:
        return amount_for_label(lines, pattern)

    # Preferir cifras impresas: las fórmulas de interés/ISR y la gráfica no son
    # importes del resumen. Ausencias financieras se conservan como None.
    days = 0
    rate = 0.0
    for line in lines:
        text = normalized(line.text)
        match = re.search(r"^#\s*DE DIAS DEL MES\s*=?\s*(\d+)(?:\.00)?\s*$", text)
        if match and not days:
            days = int(match[1])
        match = re.search(r"^TASA DE INTERES ANUALIZADA\s+([\d.]+)%", text)
        if match:
            rate = float(match[1])
    commission = value(r"^TOTAL COMISIONES COBRADAS\s*=")
    if commission is None:
        commission = value(r"^COMISIONES\s*\(")
    final = value(r"^SALDO FINAL AL\b")
    return ResumenFinancieroAzteca(
        saldo_promedio=value(r"^SALDO PROMEDIO DEL MES\*?\s+\$"),
        dias_periodo=days,
        tasa_bruta_anual=rate,
        saldo_promedio_gravable=0.0,
        intereses_a_favor=value(r"^INTERES RECIBIDO\s+\$[\d,.]+\s*$"),
        isr_retenido=value(r"^IMPUESTO RETENIDO\s*=\s*\$[\d,.]+\s*$"),
        cheques_pagados=0,
        manejo_cuenta=commission,
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=value(r"^SALDO INICIAL AL\b"),
        depositos_abonos=value(r"DEPOSITOS DEL PERIODO\b"),
        retiros_cargos=value(r"RETIROS DEL PERIODO\b"),
        saldo_final=final,
        saldo_promedio_minimo_mensual=0.0,
        saldo_global=final,
        total_retiros_tabla=_total_retiros_tabla(lines),
    )


def extract_resumen_financiero_words(words: list[dict]) -> ResumenFinancieroAzteca:
    return extract_resumen_financiero_lines(group_lines(words))
