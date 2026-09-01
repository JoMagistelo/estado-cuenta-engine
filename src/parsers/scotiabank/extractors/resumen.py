from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.resumen_financiero import ResumenFinanciero

from .movimientos import (
    SpatialLine,
    compact_text,
    extract_movimientos_words,
    extract_statement_period,
    group_words_into_lines,
    is_money_text,
    normalize_text,
    parse_money,
    safe_float,
    safe_page,
    word_center_x,
    word_center_y,
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


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def _page_words(
    words: Sequence[SpatialWord],
    page: int,
) -> List[SpatialWord]:
    return [word for word in words if safe_page(word) == page]


def _page_lines(
    words: Sequence[SpatialWord],
    page: int,
) -> List[SpatialLine]:
    return [line for line in group_words_into_lines(words) if line.page == page]


def _document_width(words: Sequence[SpatialWord]) -> float:
    max_x = max((safe_float(word.get("x1")) for word in words), default=592.0)
    return max(612.0, max_x + 18.0)


def _matches_markers(
    line: SpatialLine,
    markers: Sequence[str],
    excludes: Sequence[str] = (),
) -> bool:
    compact = compact_text(line.text)
    return (
        all(marker in compact for marker in markers)
        and not any(marker in compact for marker in excludes)
    )


def _money_candidates(
    words: Sequence[SpatialWord],
    anchor_y: float,
    x_min: float,
    x_max: float,
    y_tolerance: float,
) -> List[Tuple[float, float, float]]:
    result: List[Tuple[float, float, float]] = []

    for word in words:
        center_x = word_center_x(word)
        center_y = word_center_y(word)

        if not (x_min <= center_x <= x_max):
            continue
        if abs(center_y - anchor_y) > y_tolerance:
            continue

        text = normalize_text(word.get("text", ""))
        if not is_money_text(text):
            continue

        value = parse_money(text)
        if value is None:
            continue

        result.append((abs(center_y - anchor_y), center_x, value))

    result.sort(key=lambda item: (item[0], item[1]))
    return result


def _money_from_labeled_row(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
    markers: Sequence[str],
    excludes: Sequence[str] = (),
    y_tolerance: float = 10.0,
) -> Optional[float]:
    """
    Lee la columna de importes del Resumen de Saldos.

    En el layout observado esa columna ocupa aproximadamente 29%-41%
    del ancho. La restricción evita confundir los importes de la gráfica
    que Scotiabank imprime a la derecha del resumen.
    """

    width = _document_width(words)
    page_one = _page_words(words, 1)

    for line in lines:
        if not _matches_markers(line, markers, excludes):
            continue

        candidates = _money_candidates(
            page_one,
            line.center_y,
            width * 0.285,
            width * 0.405,
            y_tolerance,
        )
        if candidates:
            return candidates[0][2]

    return None


def _money_anywhere_on_labeled_line(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
    markers: Sequence[str],
) -> Optional[float]:
    for line in lines:
        if not _matches_markers(line, markers):
            continue

        page_words = _page_words(words, line.page)
        candidates = _money_candidates(
            page_words,
            line.center_y,
            0.0,
            _document_width(words),
            7.0,
        )
        if candidates:
            # Las etiquetas pueden contener porcentajes, pero esos tokens
            # no pasan is_money_text/parse_money como importes monetarios.
            return candidates[-1][2]

    return None


def _top_balance_pair(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
) -> Tuple[Optional[float], Optional[float]]:
    width = _document_width(words)
    page_one = _page_words(words, 1)

    for line in lines:
        compact = compact_text(line.text)
        if "SALDOINICIAL" not in compact or "SALDOFINAL" not in compact:
            continue

        candidates = _money_candidates(
            page_one,
            line.center_y,
            width * 0.62,
            width,
            8.0,
        )
        values = [candidate[2] for candidate in sorted(candidates, key=lambda item: item[1])]
        if len(values) >= 2:
            return values[0], values[-1]

    return None, None


def _period_days(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
) -> int:
    for line in lines:
        compact = compact_text(line.text)
        if "DIAS" not in compact or "PERIODO" not in compact:
            continue

        match = re.search(r"PERIODO(\d{1,3})$", compact)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 366:
                return value

    start, end = extract_statement_period(words)
    if start is not None and end is not None and end >= start:
        return (end - start).days + 1

    return 0


def _annual_rate(lines: Sequence[SpatialLine]) -> float:
    preferred_markers = (
        "INTERESESRECIBIDOS",
        "TASADEINTERESORDINARIA",
    )

    for marker in preferred_markers:
        for line in lines:
            if marker not in compact_text(line.text):
                continue

            for word in line.words:
                text = normalize_text(word.get("text", ""))
                if "%" not in text:
                    continue
                value = parse_money(text.replace("%", ""))
                if value is not None:
                    return value

    return 0.0


def _movement_totals(
    words: List[SpatialWord],
) -> Tuple[float, float, Optional[float]]:
    movements = extract_movimientos_words(words)

    if not movements:
        return 0.0, 0.0, None

    deposits = round(sum(movement.abono or 0.0 for movement in movements), 2)
    withdrawals = round(sum(movement.cargo or 0.0 for movement in movements), 2)
    last_balance = movements[-1].saldo_operacion or None
    return deposits, withdrawals, last_balance


def _non_negative(value: Optional[float], default: float = 0.0) -> float:
    return round(value if value is not None else default, 2)


# ============================================================
# CONSTRUCCIÓN Y RECONCILIACIÓN DEL RESUMEN
# ============================================================


def _build_summary_values(words: List[SpatialWord]) -> SummaryValues:
    lines_page_one = _page_lines(words, 1)
    all_lines = group_words_into_lines(words)

    primary_initial = _money_from_labeled_row(
        words,
        lines_page_one,
        ("SALDOINICIAL",),
        ("SALDOFINAL",),
    )
    primary_deposits = _money_from_labeled_row(
        words,
        lines_page_one,
        ("DEPOSITOS",),
    )
    primary_withdrawals = _money_from_labeled_row(
        words,
        lines_page_one,
        ("RETIROS",),
    )
    primary_final = _money_from_labeled_row(
        words,
        lines_page_one,
        ("SALDOFINAL", "CUENTA"),
        ("INVERSIONES",),
    )

    top_initial, top_final = _top_balance_pair(words, lines_page_one)
    movement_deposits, movement_withdrawals, last_movement_balance = (
        _movement_totals(words)
    )

    deposits = (
        primary_deposits
        if primary_deposits is not None
        else movement_deposits
    )
    withdrawals = (
        primary_withdrawals
        if primary_withdrawals is not None
        else movement_withdrawals
    )
    final_balance = (
        primary_final
        if primary_final is not None
        else top_final
        if top_final is not None
        else last_movement_balance
    )
    initial_balance = (
        primary_initial
        if primary_initial is not None
        else top_initial
    )

    deposits = _non_negative(deposits)
    withdrawals = _non_negative(withdrawals)
    final_balance = _non_negative(final_balance)

    calculated_initial = round(
        final_balance - deposits + withdrawals,
        2,
    )

    if initial_balance is None:
        initial_balance = calculated_initial
    else:
        equation_difference = abs(
            round(initial_balance + deposits - withdrawals - final_balance, 2)
        )
        if equation_difference > 0.01:
            # Corrige casos como $2,03218 o un dígito OCR equivocado usando
            # la ecuación financiera que sí se puede verificar.
            initial_balance = calculated_initial

    average_balance = _money_from_labeled_row(
        words,
        lines_page_one,
        ("SDOPROM", "CTA"),
        ("MIN", "REQUERIDO"),
        y_tolerance=12.0,
    )
    minimum_average = _money_from_labeled_row(
        words,
        lines_page_one,
        ("SDOPROM", "MIN", "REQUERIDO"),
        y_tolerance=9.0,
    )
    interest = _money_from_labeled_row(
        words,
        lines_page_one,
        ("INTERESESRECIBIDOS",),
        y_tolerance=9.0,
    )
    explicit_isr = _money_from_labeled_row(
        words,
        lines_page_one,
        ("ISR",),
        y_tolerance=9.0,
    )
    commissions = _money_from_labeled_row(
        words,
        lines_page_one,
        ("COMISIONESCOBRADAS",),
        y_tolerance=9.0,
    )

    if commissions is None:
        commissions = _money_anywhere_on_labeled_line(
            words,
            all_lines,
            ("TOTALDECOMISIONESCOBRADAS",),
        )

    global_balance = _money_from_labeled_row(
        words,
        lines_page_one,
        ("SALDOFINAL", "CUENTA", "INVERSIONES"),
        y_tolerance=9.0,
    )

    if global_balance is None:
        global_balance = final_balance

    return SummaryValues(
        saldo_promedio=_non_negative(average_balance),
        dias_periodo=_period_days(words, lines_page_one),
        tasa_bruta_anual=_annual_rate(lines_page_one),
        saldo_promedio_gravable=0.0,
        intereses_a_favor=_non_negative(interest),
        isr_retenido=_non_negative(explicit_isr),
        cheques_pagados=0,
        manejo_cuenta=_non_negative(commissions),
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=_non_negative(initial_balance),
        depositos_abonos=deposits,
        retiros_cargos=withdrawals,
        saldo_final=final_balance,
        saldo_promedio_minimo_mensual=_non_negative(minimum_average),
        saldo_global=_non_negative(global_balance, final_balance),
    )


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


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


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================


def extract_resumen_financiero_words(
    words: List[SpatialWord],
) -> ResumenFinanciero:
    """
    Extrae y reconcilia el resumen financiero Scotiabank.

    Primero utiliza las filas etiquetadas del Resumen de Saldos. Cuando
    Tesseract omite los importes de esas filas, recupera depósitos y retiros
    desde los movimientos y valida el saldo inicial con la ecuación:

        saldo inicial + depósitos - retiros = saldo final
    """

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
        saldo_promedio_minimo_mensual=(
            values.saldo_promedio_minimo_mensual
        ),
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
