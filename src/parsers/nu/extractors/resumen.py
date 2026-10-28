from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from ..validacion import ResumenFinancieroNu

from .common import SpatialLine, group_words_into_lines, normalize_upper, parse_money
from .datos import extract_period

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


def extract_resumen_financiero_words(words: List[SpatialWord]) -> ResumenFinancieroNu:
    lines = _lines(words)

    saldo_anterior = _amount_for_label(lines, "SALDO INICIAL")
    depositos = _amount_for_label(lines, "DEPOSITOS")
    retiros = _amount_for_label(lines, "GASTOS")
    saldo_final = _amount_for_label(lines, "SALDO AL GENERAR ESTE ESTADO DE CUENTA")
    saldo_promedio = _amount_for_label(lines, "SALDO PROMEDIO DEL PERIODO")
    intereses = _amount_for_label(lines, "DINERO GENERADO ANTES DE IMPUESTOS")
    isr = _amount_for_label(lines, "IMPUESTOS SOBRE EL DINERO GENERADO")
    comisiones = _amount_for_label(lines, "COMISIONES COBRADAS POR NU")

    # No sustituir el resumen impreso con las sumas que se pretenden validar.
    if depositos is not None:
        depositos = abs(depositos)
    if retiros is not None:
        retiros = abs(retiros)
    neto = _amount_for_label(lines, "DINERO GENERADO ESTE MES")
    if neto is None and intereses is not None and isr is not None:
        neto = round(intereses - abs(isr), 2)

    return ResumenFinancieroNu(
        saldo_promedio=saldo_promedio if saldo_promedio is not None else 0.0,
        dias_periodo=_period_days(words),
        tasa_bruta_anual=_tasa_bruta_anual(lines),
        saldo_promedio_gravable=0.0,
        intereses_a_favor=abs(intereses) if intereses is not None else None,
        isr_retenido=abs(isr) if isr is not None else None,
        cheques_pagados=0,
        manejo_cuenta=abs(comisiones) if comisiones is not None else None,
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos,
        retiros_cargos=retiros,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=0.0,
        saldo_global=saldo_final,
        rendimiento_neto=neto,
    )


__all__ = ["extract_resumen_financiero_words"]
