"""Lectura de las tablas del resumen BBVA por sección, página y renglón."""

import re
import unicodedata
from typing import Any


_BEHAVIOR = {
    "saldo_anterior": {"SALDO", "ANTERIOR"},
    "depositos_abonos": {"DEPOSITOS", "ABONOS"},
    "retiros_cargos": {"RETIROS", "CARGOS"},
    "saldo_final": {"SALDO", "FINAL"},
    "saldo_promedio_minimo_mensual": {"SALDO", "PROMEDIO", "MINIMO", "MENSUAL"},
    "saldo_global": {"SALDO", "GLOBAL"},
}
_LEFT = {
    "saldo_promedio": {"SALDO", "PROMEDIO"},
    "dias_periodo": {"DIAS", "DEL", "PERIODO"},
    "tasa_bruta_anual": {"TASA", "BRUTA", "ANUAL"},
    "saldo_promedio_gravable": {"SALDO", "PROMEDIO", "GRAVABLE"},
    "intereses_a_favor": {"INTERESES", "FAVOR"},
    "isr_retenido": {"ISR", "RETENIDO"},
    "cheques_pagados": {"CHEQUES", "PAGADOS"},
    "manejo_cuenta": {"MANEJO", "CUENTA"},
    "cargos_objetados": {"CARGOS", "OBJETADOS"},
    "abonos_objetados": {"ABONOS", "OBJETADOS"},
}
_CORE = {"saldo_anterior", "depositos_abonos", "retiros_cargos", "saldo_final"}
_AMOUNT = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2,}-?$")
_COUNT = re.compile(r"^\d{1,3}(?:,\d{3})*$")


def _tokens(value: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return set(re.findall(r"[A-Z0-9]+", plain.upper()))


def _cy(word: dict[str, Any]) -> float:
    return (float(word["top"]) + float(word["bottom"])) / 2


def _labels(
    words: list[dict[str, Any]], x0: float, x1: float, y0: float, y1: float,
    definitions: dict[str, set[str]],
) -> dict[str, tuple[float, float]]:
    relevant = sorted(
        (word for word in words if x0 <= float(word.get("x0", 0)) < x1
         and y0 <= _cy(word) < y1),
        key=lambda word: (_cy(word), float(word["x0"])),
    )
    rows: list[list[dict[str, Any]]] = []
    for word in relevant:
        if rows and abs(_cy(word) - sum(map(_cy, rows[-1])) / len(rows[-1])) <= 6:
            rows[-1].append(word)
        else:
            rows.append([word])

    found: dict[str, tuple[float, float]] = {}
    for row in rows:
        tokens = _tokens(" ".join(str(word.get("text", "")) for word in row))
        for field, required in sorted(definitions.items(), key=lambda pair: -len(pair[1])):
            if required <= tokens and field not in found:
                # La primera etiqueta específica de la fila prevalece sobre
                # "Saldo Promedio" y sobre otras palabras del mismo renglón.
                found[field] = (sum(map(_cy, row)) / len(row),
                                max(float(word["x1"]) for word in row))
                break
    return found


def _values(
    words: list[dict[str, Any]], labels: dict[str, tuple[float, float]],
    x_min: float, x_max: float, counts: frozenset[str] = frozenset(),
) -> dict[str, float]:
    selected: dict[str, tuple[float, float]] = {}
    if not labels:
        return {}
    for word in words:
        x = float(word.get("x0", 0))
        if not x_min <= x < x_max:
            continue
        raw = str(word.get("text", "")).strip().replace("$", "").strip()
        if not (_AMOUNT.fullmatch(raw) or _COUNT.fullmatch(raw)):
            continue
        field = min(labels, key=lambda name: abs(_cy(word) - labels[name][0]))
        y, label_end = labels[field]
        if abs(_cy(word) - y) > 9 or x <= label_end + 4:
            continue
        if not (_COUNT if field in counts else _AMOUNT).fullmatch(raw):
            continue
        amount = float(raw.rstrip("-").replace(",", ""))
        if raw.endswith("-"):
            amount = -amount
        # Se toma el importe más a la derecha, no la columna de conteo.
        if field not in selected or x > selected[field][0]:
            selected[field] = (x, amount)
    return {field: item[1] for field, item in selected.items()}


def extract_summary_tables(
    words: list[dict[str, Any]],
) -> tuple[int, dict[str, float], dict[str, float], bool] | None:
    """Devuelve (página, Comportamiento, Rendimiento, etiquetas izquierda).

    Si no hay suficientes etiquetas, el llamador conserva las cajas digitales
    históricas. Nunca combina valores de páginas ni de filas distintas.
    """
    pages: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        pages.setdefault(int(word.get("page", 1)), []).append(word)

    candidates = []
    for page, page_words in sorted(pages.items()):
        width = max(float(word.get("x1", 0)) for word in page_words)
        headers = [w for w in page_words if "COMPORTAMIENTO" in
                   _tokens(str(w.get("text", "")))]
        # Si OCR pierde el título, dos filas de la misma tabla bastan.
        anchors = headers or [w for w in page_words
                              if float(w.get("x0", 0)) >= width * .40
                              and _tokens(str(w.get("text", ""))) &
                              {"SALDO", "DEPOSITOS", "RETIROS"}]
        for anchor in anchors:
            x, y = float(anchor["x0"]), _cy(anchor)
            labels = _labels(page_words, x - 22, x + 185,
                             y + (5 if anchor in headers else -5), y + 205,
                             _BEHAVIOR)
            core = len(_CORE & labels.keys())
            if core >= 2 or (anchor in headers and core):
                candidates.append((core, anchor in headers, -page,
                                   page, page_words, x, y, labels, width))

    if not candidates:
        return None
    _, _, _, page, page_words, right_x, right_y, labels, width = max(
        candidates, key=lambda item: item[:3]
    )
    right = _values(page_words, labels, right_x + 130, width + 1)

    left_headers = [w for w in page_words if "RENDIMIENTO" in
                    _tokens(str(w.get("text", "")))
                    and float(w.get("x0", 0)) < right_x - 50
                    and abs(_cy(w) - right_y) < 30]
    if not left_headers:
        return page, right, {}, False
    header = min(left_headers, key=lambda w: abs(_cy(w) - right_y))
    left_x, left_y = float(header["x0"]), _cy(header)
    left_labels = _labels(page_words, left_x - 15, left_x + 155,
                          left_y + 5, left_y + 210, _LEFT)
    left = _values(page_words, left_labels, left_x + 140, right_x - 5,
                   frozenset({"dias_periodo", "cheques_pagados"}))
    return page, right, left, bool(left_labels)
