from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional, Sequence

from models.resumen_financiero import ResumenFinanciero


LINE_Y_TOLERANCE = 5.0
VALUE_Y_TOLERANCE = 10.0

# Desplazamientos observados respecto al encabezado "Resumen de Saldos".
# Sólo se usan como respaldo cuando Tesseract pierde parte de una etiqueta.
ROW_OFFSETS = {
    "saldo_anterior": 18.0,
    "depositos_abonos": 35.0,
    "intereses_a_favor": 53.0,
    "retiros_cargos": 69.0,
    "manejo_cuenta": 87.0,
    "isr_retenido": 104.0,
    "saldo_final": 122.0,
    "saldo_inversiones": 143.0,
    "saldo_global": 161.0,
    "saldo_promedio_minimo_mensual": 178.0,
    "saldo_promedio": 193.0,
}


def _normalize(value: Any) -> str:
    text = str(value or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"\s+", " ", text.upper())
    return text.strip()


def _page(word: dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _float(word: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(word.get(key, default))
    except (TypeError, ValueError):
        return default


def _center_x(word: dict[str, Any]) -> float:
    x0 = _float(word, "x0")
    return (x0 + _float(word, "x1", x0)) / 2.0


def _center_y(word: dict[str, Any]) -> float:
    top = _float(word, "top")
    return (top + _float(word, "bottom", top)) / 2.0


def _group_lines(words: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    ordered = sorted(words, key=lambda word: (_page(word), _center_y(word), _float(word, "x0")))
    lines: list[list[dict[str, Any]]] = []

    for word in ordered:
        if not str(word.get("text", "")).strip():
            continue
        if not lines:
            lines.append([word])
            continue

        previous = lines[-1]
        if (
            _page(previous[0]) == _page(word)
            and abs(_center_y(previous[0]) - _center_y(word)) <= LINE_Y_TOLERANCE
        ):
            previous.append(word)
            previous.sort(key=lambda item: _float(item, "x0"))
        else:
            lines.append([word])

    return lines


def _line_text(line: Sequence[dict[str, Any]]) -> str:
    return _normalize(" ".join(str(word.get("text", "")).strip() for word in line))


def _find_header(words: Sequence[dict[str, Any]]) -> Optional[dict[str, float]]:
    resumen_words = [word for word in words if "RESUMEN" in _normalize(word.get("text"))]
    saldos_words = [word for word in words if "SALDOS" in _normalize(word.get("text"))]

    candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for resumen in resumen_words:
        for saldos in saldos_words:
            if _page(resumen) != _page(saldos):
                continue
            vertical = abs(_center_y(resumen) - _center_y(saldos))
            gap = _float(saldos, "x0") - _float(resumen, "x1")
            if vertical > 9.0 or not (-5.0 <= gap <= 80.0):
                continue
            # El Resumen de Saldos de este layout está en el bloque izquierdo.
            if _center_x(resumen) > 320.0:
                continue
            candidates.append((vertical + abs(gap) * 0.05, resumen, saldos))

    if not candidates:
        return None

    _, resumen, saldos = min(candidates, key=lambda item: item[0])
    header_y = (_center_y(resumen) + _center_y(saldos)) / 2.0
    left = min(_float(resumen, "x0"), _float(saldos, "x0"))
    right = max(_float(resumen, "x1"), _float(saldos, "x1"))

    return {
        "page": float(_page(resumen)),
        "y": header_y,
        "left": left,
        "right": right,
    }


def is_resumen_saldos_layout(words: Sequence[dict[str, Any]]) -> bool:
    return _find_header(words) is not None


def _table_words(
    words: Sequence[dict[str, Any]],
    header: dict[str, float],
) -> list[dict[str, Any]]:
    page = int(header["page"])
    xmin = max(0.0, header["left"] - 80.0)
    xmax = header["right"] + 85.0
    ymin = header["y"] + 7.0
    ymax = header["y"] + 205.0

    return [
        word
        for word in words
        if _page(word) == page
        and xmin <= _center_x(word) <= xmax
        and ymin <= _center_y(word) <= ymax
    ]


def _anchor_y(
    lines: Sequence[Sequence[dict[str, Any]]],
    tokens: Sequence[str],
    expected_y: float,
    *,
    exclude: Sequence[str] = (),
) -> float:
    normalized_tokens = tuple(_normalize(token) for token in tokens)
    normalized_exclude = tuple(_normalize(token) for token in exclude)
    candidates: list[Sequence[dict[str, Any]]] = []

    for line in lines:
        text = _line_text(line)
        if not all(token in text for token in normalized_tokens):
            continue
        if any(token in text for token in normalized_exclude):
            continue
        candidates.append(line)

    if not candidates:
        return expected_y

    best = min(
        candidates,
        key=lambda line: abs(
            sum(_center_y(word) for word in line) / max(1, len(line)) - expected_y
        ),
    )
    return sum(_center_y(word) for word in best) / max(1, len(best))


def _money_fragment(word: dict[str, Any]) -> bool:
    text = str(word.get("text", "")).strip()
    if not text or "%" in text:
        return False
    if text == "$":
        return True
    return any(char.isdigit() for char in text)


def _parse_ocr_money(value: str) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw or "%" in raw:
        return None

    negative = raw.startswith("-") or ("(" in raw and ")" in raw)
    cleaned = re.sub(r"[^0-9.,]", "", raw)
    if not cleaned or not any(char.isdigit() for char in cleaned):
        return None

    separators = [index for index, char in enumerate(cleaned) if char in ".,"]
    digits = re.sub(r"[^0-9]", "", cleaned)
    if not digits:
        return None

    amount: float
    if not separators:
        amount = float(digits)
    else:
        last = separators[-1]
        decimal_digits = sum(char.isdigit() for char in cleaned[last + 1 :])

        if decimal_digits == 2:
            integer_digits = re.sub(r"[^0-9]", "", cleaned[:last]) or "0"
            cents = re.sub(r"[^0-9]", "", cleaned[last + 1 :])
            amount = float(f"{integer_digits}.{cents}")
        elif decimal_digits == 3 and len(separators) == 1:
            # Separador de miles sin decimales.
            amount = float(digits)
        elif decimal_digits == 5 and len(separators) == 1:
            # Error OCR observado: 123,97067 -> 123970.67.
            amount = float(digits) / 100.0
        else:
            return None

    return -amount if negative else amount


def _extract_amount(
    table_words: Sequence[dict[str, Any]],
    header: dict[str, float],
    target_y: float,
) -> Optional[float]:
    xmin = header["right"] + 1.0
    xmax = header["right"] + 65.0

    candidates = [
        word
        for word in table_words
        if _money_fragment(word)
        and xmin <= _center_x(word) <= xmax
        and abs(_center_y(word) - target_y) <= VALUE_Y_TOLERANCE
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda word: (abs(_center_y(word) - target_y), _center_y(word), _float(word, "x0")))
    row_y = _center_y(candidates[0])
    row = [word for word in candidates if abs(_center_y(word) - row_y) <= LINE_Y_TOLERANCE]
    row.sort(key=lambda word: _float(word, "x0"))

    text = "".join(str(word.get("text", "")).strip() for word in row)
    return _parse_ocr_money(text)


def _extract_percentage(
    table_words: Sequence[dict[str, Any]],
    target_y: float,
) -> Optional[float]:
    for word in sorted(table_words, key=lambda item: abs(_center_y(item) - target_y)):
        if abs(_center_y(word) - target_y) > VALUE_Y_TOLERANCE:
            break
        text = str(word.get("text", "")).strip()
        if "%" not in text:
            continue
        cleaned = re.sub(r"[^0-9.,]", "", text).replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            continue
    return None


def extract_resumen_saldos_words(
    words: Sequence[dict[str, Any]],
) -> Optional[ResumenFinanciero]:
    """Extrae el layout HSBC cuyo bloque se titula ``Resumen de Saldos``.

    Este formato no comparte la columna X del resumen HSBC moderno. La tabla
    vive en el bloque izquierdo y a su derecha existe otra tabla/gráfica con
    importes que Tesseract suele confundir con el resumen. Por ello se delimita
    el bloque a partir del encabezado y cada importe se asocia a su renglón.

    Los importes se devuelven tal como están impresos. No se suman intereses,
    impuestos ni comisiones a depósitos/retiros y tampoco se inventa un saldo
    mediante una ecuación contable si una celda no fue reconocida.
    """

    header = _find_header(words)
    if header is None:
        return None

    table = _table_words(words, header)
    lines = _group_lines(table)
    base_y = header["y"]

    expected = {
        name: base_y + offset
        for name, offset in ROW_OFFSETS.items()
    }

    y_saldo_anterior = _anchor_y(lines, ("SALDO", "INICIAL"), expected["saldo_anterior"])
    y_depositos = _anchor_y(lines, ("DEPOSITOS",), expected["depositos_abonos"])
    y_intereses = _anchor_y(lines, ("INTERESES", "RECIBIDOS"), expected["intereses_a_favor"])
    y_retiros = _anchor_y(lines, ("RETIROS",), expected["retiros_cargos"])
    y_comisiones = _anchor_y(lines, ("COMISIONES", "COBRADAS"), expected["manejo_cuenta"])
    y_impuestos = _anchor_y(lines, ("IMPUESTOS",), expected["isr_retenido"])
    y_saldo_final = _anchor_y(
        lines,
        ("SALDO", "FINAL", "CUENTA"),
        expected["saldo_final"],
        exclude=("INVERSIONES",),
    )
    y_saldo_global = _anchor_y(
        lines,
        ("SALDO", "FINAL", "CUENTA", "INVERSIONES"),
        expected["saldo_global"],
    )
    y_minimo = _anchor_y(
        lines,
        ("PROM", "MIN"),
        expected["saldo_promedio_minimo_mensual"],
    )
    y_promedio = _anchor_y(
        lines,
        ("PROM", "CTA"),
        expected["saldo_promedio"],
        exclude=("MIN", "REQUERIDO"),
    )

    saldo_anterior = _extract_amount(table, header, y_saldo_anterior)
    depositos_abonos = _extract_amount(table, header, y_depositos)
    intereses_a_favor = _extract_amount(table, header, y_intereses)
    retiros_cargos = _extract_amount(table, header, y_retiros)
    manejo_cuenta = _extract_amount(table, header, y_comisiones)
    isr_retenido = _extract_amount(table, header, y_impuestos)
    saldo_final = _extract_amount(table, header, y_saldo_final)
    saldo_global = _extract_amount(table, header, y_saldo_global)
    saldo_promedio_minimo_mensual = _extract_amount(table, header, y_minimo)
    saldo_promedio = _extract_amount(table, header, y_promedio)
    tasa_bruta_anual = _extract_percentage(table, y_intereses)

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,
        dias_periodo=None,
        tasa_bruta_anual=tasa_bruta_anual,
        saldo_promedio_gravable=None,
        intereses_a_favor=intereses_a_favor,
        isr_retenido=isr_retenido,
        cheques_pagados=None,
        manejo_cuenta=manejo_cuenta,
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos_abonos,
        retiros_cargos=retiros_cargos,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=saldo_promedio_minimo_mensual,
        saldo_global=saldo_global,
    )
