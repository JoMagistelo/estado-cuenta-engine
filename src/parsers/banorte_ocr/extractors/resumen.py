from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from models.resumen_financiero import ResumenFinanciero

from .datos import (
    SpatialWord,
    _compact,
    _extract_dates,
    _group_lines,
    _line_text,
    _norm,
    _page,
    _x0,
)


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_contains(value: str, target: str, cutoff: float = 0.78) -> bool:
    value_c = _compact(value)
    target_c = _compact(target)
    if target_c in value_c:
        return True
    # Compare only a prefix/window when OCR joined neighboring labels.
    if len(value_c) >= len(target_c):
        best = max(
            (
                _similar(value_c[i : i + len(target_c)], target_c)
                for i in range(0, len(value_c) - len(target_c) + 1)
            ),
            default=0.0,
        )
        return best >= cutoff
    return _similar(value_c, target_c) >= cutoff


def _line_y(line: list[SpatialWord]) -> float:
    if not line:
        return 0.0
    return sum(
        (float(w.get("top", 0.0)) + float(w.get("bottom", w.get("top", 0.0)))) / 2.0
        for w in line
    ) / len(line)


def _find_summary_page(lines: list[list[SpatialWord]]) -> int | None:
    scores: dict[int, int] = {}

    for line in lines:
        if not line:
            continue
        page = _page(line[0])
        text = _norm(_line_text(line))
        compact = _compact(text)
        score = 0

        if "PRODUCTO" in text and "CUENTA" in text and "CLABE" in text:
            score += 80
        if _fuzzy_contains(compact, "SALDO INICIAL DEL PERIODO"):
            score += 65
        if _fuzzy_contains(compact, "TOTAL DE DEPOSITOS"):
            score += 55
        if _fuzzy_contains(compact, "TOTAL DE RETIROS"):
            score += 55
        if "DIAS" in text and "PERIODO" in text:
            score += 20
        if "SALDOFINAL" in compact:
            score += 15

        scores[page] = scores.get(page, 0) + score

    if not scores:
        return None

    page, score = max(scores.items(), key=lambda item: (item[1], -item[0]))
    return page if score > 0 else None


def _normalize_number_token(token: str) -> str | None:
    value = str(token or "").strip()
    if not value:
        return None

    value = value.replace("$", "").replace(" ", "")
    value = value.replace("(", "-").replace(")", "")
    value = value.strip("[]|")

    # Keep only a numeric-looking core.
    match = re.search(r"-?\d[\d.,]*", value)
    if not match:
        return None

    value = match.group(0)

    # OCR sometimes produces 103,578,58 instead of 103,578.58.
    if "." not in value and value.count(",") >= 2:
        head, tail = value.rsplit(",", 1)
        if len(tail) in {1, 2}:
            value = head.replace(",", "") + "." + tail
        else:
            value = value.replace(",", "")
    elif "," in value and "." in value:
        value = value.replace(",", "")
    elif value.count(",") == 1 and "." not in value:
        left, right = value.split(",", 1)
        # A single comma followed by exactly 3 digits is thousands; 1-2 is decimal.
        if len(right) == 3:
            value = left + right
        elif len(right) in {1, 2}:
            value = left + "." + right
        else:
            value = left + right

    try:
        float(value)
    except ValueError:
        return None
    return value


def _amounts_from_line(line: list[SpatialWord]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for word in sorted(line, key=_x0):
        normalized = _normalize_number_token(str(word.get("text", "")))
        if normalized is None:
            continue

        # Avoid dates, customer/account numbers and years. Monetary values in the
        # summary normally contain punctuation or a currency marker.
        raw = str(word.get("text", "")).strip()
        if not any(ch in raw for ch in "$.,"):
            continue

        try:
            amount = float(normalized)
        except ValueError:
            continue
        result.append((_x0(word), amount))
    return result


def _amount_from_line(line: list[SpatialWord], *, prefer: str = "last") -> float | None:
    amounts = _amounts_from_line(line)
    if not amounts:
        return None
    if prefer == "first":
        return amounts[0][1]
    return amounts[-1][1]


def _find_line(
    lines: list[list[SpatialWord]],
    target: str,
    *,
    start: int = 0,
    cutoff: float = 0.78,
    exclude: tuple[str, ...] = (),
) -> int | None:
    for index in range(start, len(lines)):
        text = _line_text(lines[index])
        normalized = _norm(text)
        if any(_compact(item) in _compact(normalized) for item in exclude):
            continue
        if _fuzzy_contains(normalized, target, cutoff=cutoff):
            return index
    return None


def _field_amount(
    lines: list[list[SpatialWord]],
    target: str,
    *,
    prefer: str = "last",
    cutoff: float = 0.78,
    exclude: tuple[str, ...] = (),
) -> float | None:
    index = _find_line(lines, target, cutoff=cutoff, exclude=exclude)
    if index is None:
        return None
    return _amount_from_line(lines[index], prefer=prefer)


def _line_sign(line: list[SpatialWord]) -> int:
    for word in sorted(line, key=_x0):
        text = str(word.get("text", "")).strip()
        if text.startswith("+"):
            return 1
        if text.startswith("-") or text in {"—", "–"}:
            return -1
    return 0


def _signed_field(
    lines: list[list[SpatialWord]],
    target: str,
    *,
    cutoff: float = 0.78,
) -> tuple[float | None, int]:
    index = _find_line(lines, target, cutoff=cutoff)
    if index is None:
        return None, 0
    return _amount_from_line(lines[index]), _line_sign(lines[index])


def _extract_days(lines: list[list[SpatialWord]]) -> int | None:
    index = _find_line(lines, "DIAS QUE COMPRENDE EL PERIODO", cutoff=0.72)
    if index is not None:
        text = _line_text(lines[index])
        for raw in re.findall(r"\b\d{1,3}\b", text):
            value = int(raw)
            if 1 <= value <= 366:
                return value

    # Source-grounded fallback: derive inclusive day count from period dates
    # present on the same statement page.
    page_text = " ".join(_line_text(line) for line in lines)
    dates = _extract_dates(page_text)
    if len(dates) >= 2:
        month_map = {
            "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
            "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
            "Septiembre": 9, "Octubre": 10, "Noviembre": 11,
            "Diciembre": 12,
        }
        try:
            d1, m1, y1 = dates[0].split("/")
            d2, m2, y2 = dates[1].split("/")
            start = datetime(int(y1), month_map[m1], int(d1))
            end = datetime(int(y2), month_map[m2], int(d2))
            if end >= start:
                return (end - start).days + 1
        except (ValueError, KeyError):
            pass
    return None


def _extract_percent(lines: list[list[SpatialWord]], target: str) -> float | None:
    index = _find_line(lines, target, cutoff=0.72)
    if index is None:
        return None
    text = _line_text(lines[index])
    match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_saldo_promedio(lines: list[list[SpatialWord]]) -> float | None:
    # Banorte presents the actual period average as "En el Periodo ...: $X",
    # immediately below "Saldo promedio mínimo".
    for index, line in enumerate(lines):
        text = _norm(_line_text(line))
        if "EN EL PERIODO" not in text:
            continue
        amount = _amount_from_line(line, prefer="last")
        if amount is not None:
            return amount
        # Tesseract may split the amount into the next line.
        if index + 1 < len(lines) and _line_y(lines[index + 1]) - _line_y(line) < 16.0:
            amount = _amount_from_line(lines[index + 1], prefer="first")
            if amount is not None:
                return amount
    return None


def _empty() -> ResumenFinanciero:
    return ResumenFinanciero(
        saldo_promedio=None,
        dias_periodo=None,
        tasa_bruta_anual=None,
        saldo_promedio_gravable=None,
        intereses_a_favor=None,
        isr_retenido=None,
        cheques_pagados=None,
        manejo_cuenta=None,
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=None,
        depositos_abonos=None,
        retiros_cargos=None,
        saldo_final=None,
        saldo_promedio_minimo_mensual=None,
        saldo_global=None,
    )


def extract_resumen_financiero_words(words: list[SpatialWord]) -> ResumenFinanciero:
    if not words:
        return _empty()

    all_lines = _group_lines(words)
    summary_page = _find_summary_page(all_lines)
    if summary_page is None:
        return _empty()

    lines = [line for line in all_lines if line and _page(line[0]) == summary_page]

    saldo_anterior = _field_amount(lines, "SALDO INICIAL DEL PERIODO", prefer="first", cutoff=0.74)
    total_depositos = _field_amount(lines, "TOTAL DE DEPOSITOS", cutoff=0.75)
    total_retiros = _field_amount(lines, "TOTAL DE RETIROS", cutoff=0.75)
    intereses_a_favor = _field_amount(lines, "INTERESES NETOS GANADOS", cutoff=0.74)

    comisiones, sign_comisiones = _signed_field(lines, "TOTAL DE COMISIONES COBRADAS PAGADAS", cutoff=0.70)
    iva = _field_amount(lines, "IVA SOBRE COMISIONES", cutoff=0.70)
    intereses_cobrados, sign_intereses = _signed_field(
        lines, "INTERESES COBRADOS PAGADOS", cutoff=0.72
    )

    depositos_abonos = total_depositos
    if depositos_abonos is not None:
        depositos_abonos += intereses_a_favor or 0.0
        if comisiones is not None and sign_comisiones > 0:
            depositos_abonos += comisiones
        if intereses_cobrados is not None and sign_intereses > 0:
            depositos_abonos += intereses_cobrados

    retiros_cargos = total_retiros
    if retiros_cargos is not None:
        retiros_cargos += iva or 0.0
        if comisiones is not None and sign_comisiones < 0:
            retiros_cargos += comisiones
        if intereses_cobrados is not None and sign_intereses < 0:
            retiros_cargos += intereses_cobrados

    saldo_promedio = _extract_saldo_promedio(lines)
    saldo_promedio_minimo = _field_amount(lines, "SALDO PROMEDIO MINIMO", cutoff=0.72)

    # Prefer the accounting summary ("Saldo actual"). If OCR loses the amount,
    # use the graph's explicit "SALDO FINAL" value from the same page.
    saldo_final = _field_amount(lines, "SALDO ACTUAL", cutoff=0.72)
    if saldo_final is None:
        saldo_final = _field_amount(lines, "SALDO FINAL", cutoff=0.72)

    isr = _field_amount(lines, "RETENCION DE ISR", cutoff=0.72)
    tasa = _extract_percent(lines, "TASA BRUTA ANUAL")
    dias = _extract_days(lines)

    # Preserve the semantics of the current Banorte digital extractor.
    manejo_cuenta = comisiones

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,
        dias_periodo=dias,
        tasa_bruta_anual=tasa,
        saldo_promedio_gravable=None,
        intereses_a_favor=intereses_a_favor,
        isr_retenido=isr,
        cheques_pagados=None,
        manejo_cuenta=manejo_cuenta,
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos_abonos,
        retiros_cargos=retiros_cargos,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=saldo_promedio_minimo,
        saldo_global=None,
    )
