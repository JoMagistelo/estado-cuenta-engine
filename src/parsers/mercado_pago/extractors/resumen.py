from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from models.resumen_financiero import ResumenFinanciero

from .datos import extract_period
from .movimientos import (
    SpatialLine,
    extract_movimientos_words,
    group_words_into_lines,
    normalize_upper,
    parse_money,
)


SpatialWord = Dict[str, Any]


@dataclass(slots=True)
class SummaryValues:
    saldo_promedio: float
    dias_periodo: int
    tasa_bruta_anual: float
    saldo_promedio_gravable: float
    intereses_a_favor: float
    isr_retenido: float
    cheques_pagados: int
    manejo_cuenta: float
    cargos_objetados: float
    abonos_objetados: float
    saldo_anterior: float
    depositos_abonos: float
    retiros_cargos: float
    saldo_final: float
    saldo_promedio_minimo_mensual: float
    saldo_global: float


def _summary_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return [
        line
        for line in group_words_into_lines(words)
        if line.page == 1 and line.center_y < 175.0
    ]


def _labeled_amount(
    lines: Sequence[SpatialLine],
    label: str,
) -> Optional[float]:
    pattern = re.compile(
        rf"\b{label}\s*:\s*\$?\s*"
        r"(-?\s*[\d,]+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.search(normalize_upper(line.text))
        if not match:
            continue
        value = parse_money(match.group(1))
        if value is not None:
            return value
    return None


def _period_days(words: Sequence[SpatialWord]) -> int:
    start, end = extract_period(words)
    if start is not None and end is not None and end >= start:
        return (end - start).days + 1
    return 0


def _build_summary_values(words: List[SpatialWord]) -> SummaryValues:
    lines = _summary_lines(words)
    movements = extract_movimientos_words(words)

    movement_deposits = round(sum(item.abono or 0.0 for item in movements), 2)
    movement_withdrawals = round(sum(item.cargo or 0.0 for item in movements), 2)
    movement_final = movements[-1].saldo_operacion if movements else None

    initial = _labeled_amount(lines, r"SALDO\s+INICIAL")
    deposits = _labeled_amount(lines, r"ENTRADAS")
    withdrawals = _labeled_amount(lines, r"SALIDAS")
    final = _labeled_amount(lines, r"SALDO\s+FINAL")

    deposits = abs(deposits) if deposits is not None else movement_deposits
    withdrawals = (
        abs(withdrawals) if withdrawals is not None else movement_withdrawals
    )
    final = final if final is not None else (movement_final or 0.0)

    if initial is None:
        initial = round(final - deposits + withdrawals, 2)

    return SummaryValues(
        saldo_promedio=0.0,
        dias_periodo=_period_days(words),
        tasa_bruta_anual=0.0,
        saldo_promedio_gravable=0.0,
        intereses_a_favor=0.0,
        isr_retenido=0.0,
        cheques_pagados=0,
        manejo_cuenta=0.0,
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=initial,
        depositos_abonos=deposits,
        retiros_cargos=withdrawals,
        saldo_final=final,
        saldo_promedio_minimo_mensual=0.0,
        saldo_global=final,
    )


def extract_saldo_promedio(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_promedio


def extract_dias_periodo(words: List[SpatialWord]) -> int:
    return _build_summary_values(words).dias_periodo


def extract_tasa_bruta_anual(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).tasa_bruta_anual


def extract_saldo_promedio_gravable(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_promedio_gravable


def extract_intereses_a_favor(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).intereses_a_favor


def extract_isr_retenido(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).isr_retenido


def extract_cheques_pagados(words: List[SpatialWord]) -> int:
    return _build_summary_values(words).cheques_pagados


def extract_manejo_cuenta(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).manejo_cuenta


def extract_cargos_objetados(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).cargos_objetados


def extract_abonos_objetados(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).abonos_objetados


def extract_saldo_anterior(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_anterior


def extract_depositos_abonos(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).depositos_abonos


def extract_retiros_cargos(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).retiros_cargos


def extract_saldo_final(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_final


def extract_saldo_promedio_minimo_mensual(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_promedio_minimo_mensual


def extract_saldo_global(words: List[SpatialWord]) -> float:
    return _build_summary_values(words).saldo_global


def extract_resumen_financiero_words(
    words: List[SpatialWord],
) -> ResumenFinanciero:
    values = _build_summary_values(words)
    return ResumenFinanciero(
        saldo_promedio=values.saldo_promedio,
        dias_periodo=values.dias_periodo,
        tasa_bruta_anual=values.tasa_bruta_anual,
        saldo_promedio_gravable=values.saldo_promedio_gravable,
        intereses_a_favor=values.intereses_a_favor,
        isr_retenido=values.isr_retenido,
        cheques_pagados=values.cheques_pagados,
        manejo_cuenta=values.manejo_cuenta,
        cargos_objetados=values.cargos_objetados,
        abonos_objetados=values.abonos_objetados,
        saldo_anterior=values.saldo_anterior,
        depositos_abonos=values.depositos_abonos,
        retiros_cargos=values.retiros_cargos,
        saldo_final=values.saldo_final,
        saldo_promedio_minimo_mensual=values.saldo_promedio_minimo_mensual,
        saldo_global=values.saldo_global,
    )


__all__ = [
    "extract_abonos_objetados",
    "extract_cargos_objetados",
    "extract_cheques_pagados",
    "extract_depositos_abonos",
    "extract_dias_periodo",
    "extract_intereses_a_favor",
    "extract_isr_retenido",
    "extract_manejo_cuenta",
    "extract_resumen_financiero_words",
    "extract_retiros_cargos",
    "extract_saldo_anterior",
    "extract_saldo_final",
    "extract_saldo_global",
    "extract_saldo_promedio",
    "extract_saldo_promedio_gravable",
    "extract_saldo_promedio_minimo_mensual",
    "extract_tasa_bruta_anual",
]
