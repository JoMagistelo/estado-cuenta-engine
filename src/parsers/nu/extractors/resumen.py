from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from models.resumen_financiero import ResumenFinanciero

from .common import SpatialLine, group_words_into_lines, normalize_upper, parse_money
from .datos import extract_period
from .movimientos import extract_movimientos_words

SpatialWord = Dict[str, Any]

TRAILING_AMOUNT_RE = re.compile(r"([+-]?\s*\$?\s*[\d,]+(?:\.\d{1,2})?)\s*$")
PERCENT_RE = re.compile(r"INTERES\s+BRUTO\s+ANUAL\s+DE\s+([\d.,]+)\s*%", re.IGNORECASE)


def _lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return group_words_into_lines(words)


def _amount_for_label(lines: Sequence[SpatialLine], *labels: str) -> Optional[float]:
    normalized_labels = tuple(normalize_upper(label) for label in labels)
    for line in lines:
        normalized = normalize_upper(line.text)
        if not all(label in normalized for label in normalized_labels):
            continue
        match = TRAILING_AMOUNT_RE.search(line.text)
        if match:
            value = parse_money(match.group(1))
            if value is not None:
                return value
    return None


def _period_days(words: Sequence[SpatialWord]) -> int:
    start, end = extract_period(words)
    if start is None or end is None or end < start:
        return 0
    return (end - start).days + 1


def _tasa_bruta_anual(lines: Sequence[SpatialLine]) -> float:
    for line in lines:
        match = PERCENT_RE.search(normalize_upper(line.text))
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return 0.0


def extract_resumen_financiero_words(words: List[SpatialWord]) -> ResumenFinanciero:
    lines = _lines(words)
    movimientos = extract_movimientos_words(words)

    saldo_anterior = _amount_for_label(lines, "SALDO INICIAL")
    depositos = _amount_for_label(lines, "DEPOSITOS")
    retiros = _amount_for_label(lines, "GASTOS")
    saldo_final = _amount_for_label(lines, "SALDO AL GENERAR ESTE ESTADO DE CUENTA")
    saldo_promedio = _amount_for_label(lines, "SALDO PROMEDIO DEL PERIODO")
    intereses = _amount_for_label(lines, "DINERO GENERADO ANTES DE IMPUESTOS")
    isr = _amount_for_label(lines, "IMPUESTOS SOBRE EL DINERO GENERADO")
    comisiones = _amount_for_label(lines, "COMISIONES COBRADAS POR NU")

    if depositos is None:
        depositos = round(sum(item.abono or 0.0 for item in movimientos), 2)
    else:
        depositos = abs(depositos)

    if retiros is None:
        retiros = round(sum(item.cargo or 0.0 for item in movimientos), 2)
    else:
        retiros = abs(retiros)

    if saldo_final is None and saldo_anterior is not None:
        saldo_final = round(saldo_anterior + depositos - retiros, 2)
    if saldo_anterior is None and saldo_final is not None:
        saldo_anterior = round(saldo_final - depositos + retiros, 2)

    final_value = saldo_final if saldo_final is not None else 0.0
    return ResumenFinanciero(
        saldo_promedio=saldo_promedio if saldo_promedio is not None else 0.0,
        dias_periodo=_period_days(words),
        tasa_bruta_anual=_tasa_bruta_anual(lines),
        saldo_promedio_gravable=0.0,
        intereses_a_favor=abs(intereses) if intereses is not None else 0.0,
        isr_retenido=abs(isr) if isr is not None else 0.0,
        cheques_pagados=0,
        manejo_cuenta=abs(comisiones) if comisiones is not None else 0.0,
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=saldo_anterior if saldo_anterior is not None else 0.0,
        depositos_abonos=depositos,
        retiros_cargos=retiros,
        saldo_final=final_value,
        saldo_promedio_minimo_mensual=0.0,
        saldo_global=final_value,
    )


__all__ = ["extract_resumen_financiero_words"]
