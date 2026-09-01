from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from models.resumen_financiero import ResumenFinanciero

from .movimientos import (
    SpatialLine,
    compact_text,
    extract_movimientos_words,
    extract_statement_period,
    group_words_into_lines,
    normalize_text,
    parse_money,
    word_center_x,
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


def _lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    return group_words_into_lines(words)


def _matches(
    line: SpatialLine,
    markers: Sequence[str],
    excludes: Sequence[str] = (),
) -> bool:
    compact = compact_text(line.text)
    return all(marker in compact for marker in markers) and not any(
        marker in compact for marker in excludes
    )


def _money_values(
    line: SpatialLine,
    x_min: float = 0.0,
    x_max: float = float("inf"),
) -> List[float]:
    values = []
    for word in sorted(line.words, key=word_center_x):
        center = word_center_x(word)
        if not (x_min <= center < x_max):
            continue
        amount = parse_money(word.get("text", ""))
        if amount is not None:
            values.append(amount)
    return values


def _percentage_values(line: SpatialLine) -> List[float]:
    values: List[float] = []
    for word in sorted(line.words, key=word_center_x):
        text = normalize_text(word.get("text", ""))
        if "%" not in text:
            continue
        amount = parse_money(text.replace("%", ""))
        if amount is not None:
            values.append(amount)
    return values


def _labeled_money(
    lines: Sequence[SpatialLine],
    markers: Sequence[str],
    *,
    page: Optional[int] = None,
    excludes: Sequence[str] = (),
    x_min: float = 0.0,
    x_max: float = float("inf"),
    take_last: bool = True,
) -> Optional[float]:
    for line in lines:
        if page is not None and line.page != page:
            continue
        if not _matches(line, markers, excludes):
            continue
        values = _money_values(line, x_min, x_max)
        if values:
            return values[-1] if take_last else values[0]
    return None


def _labeled_percentage(
    lines: Sequence[SpatialLine],
    markers: Sequence[str],
    *,
    page: Optional[int] = None,
) -> Optional[float]:
    for line in lines:
        if page is not None and line.page != page:
            continue
        if not _matches(line, markers):
            continue
        values = _percentage_values(line)
        if values:
            return values[-1]
    return None


def _period_days(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
) -> int:
    for line in lines:
        if line.page != 1 or not _matches(line, ("DIAS", "PERIODO")):
            continue
        match = re.search(r"(?:PERIODO)?(\d{1,3})$", compact_text(line.text))
        if match and 1 <= int(match.group(1)) <= 366:
            return int(match.group(1))

    start, end = extract_statement_period(words)
    if start is not None and end is not None and end >= start:
        return (end - start).days + 1
    return 0


def _isr_from_yield_table(lines: Sequence[SpatialLine]) -> Optional[float]:
    for line in lines:
        if line.page != 2 or "CUENTAALAVISTA" not in compact_text(line.text):
            continue
        values = _money_values(line)
        if len(values) >= 2:
            return values[-1]
    return None


def _interest_from_yield_table(lines: Sequence[SpatialLine]) -> Optional[float]:
    for line in lines:
        if line.page != 2 or "CUENTAALAVISTA" not in compact_text(line.text):
            continue
        values = _money_values(line)
        if len(values) >= 2:
            return values[0]
    return None


def _objected_amount(lines: Sequence[SpatialLine]) -> float:
    for index, line in enumerate(lines):
        if "CARGOSOBJETADOS" not in compact_text(line.text):
            continue
        for candidate in lines[index + 1 : index + 5]:
            if candidate.page != line.page:
                break
            values = _money_values(candidate)
            if values:
                return abs(values[-1])
    return 0.0


def _build_summary_values(words: List[SpatialWord]) -> SummaryValues:
    lines = _lines(words)
    movements = extract_movimientos_words(words)

    movement_deposits = round(sum(item.abono or 0.0 for item in movements), 2)
    movement_withdrawals = round(sum(item.cargo or 0.0 for item in movements), 2)
    movement_final = movements[-1].saldo_operacion if movements else None

    initial = _labeled_money(
        lines,
        ("SALDOINICIAL",),
        page=2,
    )
    if initial is None:
        initial = _labeled_money(
            lines,
            ("POSICIONTOTALALINICIO",),
            page=1,
        )

    statement_deposits = _labeled_money(
        lines,
        ("SUMADERETIROSYDEPOSITOS",),
        x_min=410.0,
    )
    statement_withdrawals = _labeled_money(
        lines,
        ("SUMADERETIROSYDEPOSITOS",),
        x_min=330.0,
        x_max=410.0,
    )
    statement_final = _labeled_money(lines, ("SALDOAFECHADECORTE",))

    deposits = movement_deposits if movements else (statement_deposits or 0.0)
    withdrawals = (
        movement_withdrawals if movements else (statement_withdrawals or 0.0)
    )
    final = (
        movement_final
        if movement_final is not None
        else (statement_final or 0.0)
    )

    # Si OCR perdiera el saldo inicial pero conservara movimientos y saldo
    # final, la ecuacion financiera permite recuperarlo sin una coordenada fija.
    if initial is None and movements:
        initial = round(final - deposits + withdrawals, 2)

    interest = _labeled_money(
        lines,
        ("INTERESAPLICABLE", "RENDIMIENTO"),
        page=1,
    )
    if interest is None:
        interest = _interest_from_yield_table(lines)

    average = _labeled_money(
        lines,
        ("SALDOPROMEDIODIARIO",),
        page=1,
        x_min=450.0,
    )
    minimum = _labeled_money(
        lines,
        ("SALDOPROMEDIOMINIMOREQUERIDO",),
        page=1,
        x_min=450.0,
    )
    commissions = _labeled_money(
        lines,
        ("COMISIONESEFECTIVAMENTECOBRADAS",),
        page=1,
        x_min=450.0,
    )
    global_balance = _labeled_money(
        lines,
        ("POSICIONTOTALALCIERRE",),
        page=1,
    )

    return SummaryValues(
        saldo_promedio=average or 0.0,
        dias_periodo=_period_days(words, lines),
        tasa_bruta_anual=(
            _labeled_percentage(lines, ("TASAANUAL",), page=1) or 0.0
        ),
        saldo_promedio_gravable=0.0,
        intereses_a_favor=interest or 0.0,
        isr_retenido=_isr_from_yield_table(lines) or 0.0,
        cheques_pagados=0,
        manejo_cuenta=commissions or 0.0,
        cargos_objetados=_objected_amount(lines),
        abonos_objetados=0.0,
        saldo_anterior=initial or 0.0,
        depositos_abonos=deposits,
        retiros_cargos=withdrawals,
        saldo_final=final,
        saldo_promedio_minimo_mensual=minimum or 0.0,
        saldo_global=(global_balance if global_balance is not None else final),
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
    """Extrae el resumen Mifel y lo reconcilia contra los movimientos."""

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
