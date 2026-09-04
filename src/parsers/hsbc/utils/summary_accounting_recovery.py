from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.resumen_financiero import ResumenFinanciero


LINE_Y_TOLERANCE = 5.0
VALUE_MAX_HORIZONTAL_DISTANCE = 180.0
VALUE_VERTICAL_TOLERANCE = 7.0
ACCOUNTING_TOLERANCE = 0.05


@dataclass(frozen=True)
class SummaryAnchorValue:
    field: str
    value: float
    page: int
    top: float
    distance: float


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1))
    except (TypeError, ValueError):
        return 1


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").upper())
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", text).strip()


def _token(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _normalize(value))


def _word_center_y(word: Dict[str, Any]) -> float:
    top = _safe_float(word.get("top", 0.0))
    bottom = _safe_float(word.get("bottom", top))
    return (top + bottom) / 2.0


def _group_page_lines(
    words: Sequence[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    ordered = sorted(
        (
            word
            for word in words
            if str(word.get("text", "")).strip()
        ),
        key=lambda word: (
            _safe_page(word),
            _word_center_y(word),
            _safe_float(word.get("x0", 0.0)),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []

    for word in ordered:
        page = _safe_page(word)
        center_y = _word_center_y(word)

        target: Optional[List[Dict[str, Any]]] = None

        for line in reversed(lines):
            if not line:
                continue
            line_page = _safe_page(line[0])
            if line_page != page:
                if line_page < page:
                    break
                continue

            line_y = sum(_word_center_y(item) for item in line) / len(line)
            if abs(line_y - center_y) <= LINE_Y_TOLERANCE:
                target = line
                break
            if center_y - line_y > LINE_Y_TOLERANCE:
                break

        if target is None:
            lines.append([word])
        else:
            target.append(word)

    for line in lines:
        line.sort(key=lambda word: _safe_float(word.get("x0", 0.0)))

    return lines


def _parse_money_token(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None

    compact = text.replace(" ", "").replace("$", "")

    # Ruta normal. No se cambia la interpretación de importes bien
    # formados que ya funcionan en PDF digital y OCR limpio.
    standard = re.fullmatch(
        r"-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?|-?\d+(?:\.\d{2})?",
        compact,
    )
    if standard is not None:
        try:
            return float(compact.replace(",", ""))
        except ValueError:
            return None

    # Respaldo extremadamente acotado para la celda monetaria anclada.
    # En escaneados Tesseract puede leer, por ejemplo, $:15/445:63.
    # Se acepta únicamente cuando el token conserva señal monetaria o
    # varios separadores y termina en dos dígitos de centavos.
    digits = re.sub(r"\D", "", compact)
    separator_count = len(re.findall(r"[.,/:;]", text))

    if (
        len(digits) >= 4
        and len(digits) <= 12
        and ("$" in text or separator_count >= 2)
    ):
        integer_digits = digits[:-2]
        cents = digits[-2:]
        if integer_digits:
            try:
                return float(f"{int(integer_digits)}.{cents}")
            except ValueError:
                return None

    return None


def _anchor_matches(
    line: Sequence[Dict[str, Any]],
) -> List[Tuple[str, float, float]]:
    """Devuelve campo, x final y centro Y de cada etiqueta fuerte."""

    matches: List[Tuple[str, float, float]] = []
    tokens = [_token(word.get("text", "")) for word in line]

    for index, token in enumerate(tokens):
        if token == "SALDO" and index + 1 < len(tokens):
            next_token = tokens[index + 1]
            if next_token.startswith("INICIAL"):
                matches.append(
                    (
                        "saldo_anterior",
                        _safe_float(line[index + 1].get("x1", 0.0)),
                        _word_center_y(line[index]),
                    )
                )
            elif next_token.startswith("FINAL"):
                matches.append(
                    (
                        "saldo_final",
                        _safe_float(line[index + 1].get("x1", 0.0)),
                        _word_center_y(line[index]),
                    )
                )

        if token.startswith("DEPOSIT"):
            matches.append(
                (
                    "depositos_abonos",
                    _safe_float(line[index].get("x1", 0.0)),
                    _word_center_y(line[index]),
                )
            )

        if token.startswith("RETIROS") or token.startswith("RETIROSCARGOS"):
            matches.append(
                (
                    "retiros_cargos",
                    _safe_float(line[index].get("x1", 0.0)),
                    _word_center_y(line[index]),
                )
            )

    return matches


def _candidate_values_for_anchor(
    page_words: Sequence[Dict[str, Any]],
    field: str,
    anchor_x1: float,
    anchor_y: float,
) -> List[SummaryAnchorValue]:
    candidates: List[SummaryAnchorValue] = []

    for word in page_words:
        x0 = _safe_float(word.get("x0", 0.0))
        if x0 <= anchor_x1 + 2.0:
            continue

        horizontal_distance = x0 - anchor_x1
        if horizontal_distance > VALUE_MAX_HORIZONTAL_DISTANCE:
            continue

        vertical_distance = abs(_word_center_y(word) - anchor_y)
        if vertical_distance > VALUE_VERTICAL_TOLERANCE:
            continue

        value = _parse_money_token(word.get("text", ""))
        if value is None:
            continue

        candidates.append(
            SummaryAnchorValue(
                field=field,
                value=value,
                page=_safe_page(word),
                top=_safe_float(word.get("top", 0.0)),
                distance=horizontal_distance + vertical_distance * 4.0,
            )
        )

    candidates.sort(key=lambda item: (item.distance, item.top))
    return candidates


def extract_summary_accounting_candidates(
    words: Sequence[Dict[str, Any]],
) -> Dict[str, List[SummaryAnchorValue]]:
    """Extrae sólo valores unidos a etiquetas contables explícitas."""

    pages: Dict[int, List[Dict[str, Any]]] = {}
    for word in words:
        pages.setdefault(_safe_page(word), []).append(word)

    result: Dict[str, List[SummaryAnchorValue]] = {
        "saldo_anterior": [],
        "depositos_abonos": [],
        "retiros_cargos": [],
        "saldo_final": [],
    }

    for line in _group_page_lines(words):
        if not line:
            continue
        page = _safe_page(line[0])

        for field, anchor_x1, anchor_y in _anchor_matches(line):
            result[field].extend(
                _candidate_values_for_anchor(
                    pages.get(page, []),
                    field,
                    anchor_x1,
                    anchor_y,
                )
            )

    # Deduplicación estable por valor/página/posición para que una
    # etiqueta repetida (gráfico de cierre) aporte evidencia sin
    # multiplicar la misma celda.
    for field, candidates in result.items():
        unique: List[SummaryAnchorValue] = []
        seen: set[Tuple[float, int, int]] = set()
        for candidate in candidates:
            identity = (
                round(candidate.value, 2),
                candidate.page,
                int(round(candidate.top)),
            )
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(candidate)
        result[field] = unique

    return result


def _direct_values(
    candidates: Dict[str, List[SummaryAnchorValue]],
) -> Dict[str, float]:
    values: Dict[str, float] = {}

    for field, field_candidates in candidates.items():
        if not field_candidates:
            continue

        # Si el mismo valor aparece más de una vez en el documento,
        # se privilegia como evidencia repetida. En empate se conserva
        # la candidata geométricamente más cercana a su etiqueta.
        counts: Dict[float, int] = {}
        for candidate in field_candidates:
            rounded = round(candidate.value, 2)
            counts[rounded] = counts.get(rounded, 0) + 1

        best = min(
            field_candidates,
            key=lambda candidate: (
                -counts[round(candidate.value, 2)],
                candidate.distance,
                candidate.page,
                candidate.top,
            ),
        )
        values[field] = round(best.value, 2)

    return values


def _complete_one_missing_value(
    values: Dict[str, float],
) -> Optional[Dict[str, float]]:
    fields = (
        "saldo_anterior",
        "depositos_abonos",
        "retiros_cargos",
        "saldo_final",
    )
    present = [field for field in fields if field in values]

    if len(present) < 3:
        return None

    completed = dict(values)

    if "saldo_anterior" not in completed:
        completed["saldo_anterior"] = round(
            completed["saldo_final"]
            - completed["depositos_abonos"]
            + completed["retiros_cargos"],
            2,
        )
    elif "depositos_abonos" not in completed:
        completed["depositos_abonos"] = round(
            completed["saldo_final"]
            - completed["saldo_anterior"]
            + completed["retiros_cargos"],
            2,
        )
    elif "retiros_cargos" not in completed:
        completed["retiros_cargos"] = round(
            completed["saldo_anterior"]
            + completed["depositos_abonos"]
            - completed["saldo_final"],
            2,
        )
    elif "saldo_final" not in completed:
        completed["saldo_final"] = round(
            completed["saldo_anterior"]
            + completed["depositos_abonos"]
            - completed["retiros_cargos"],
            2,
        )

    if any(field not in completed for field in fields):
        return None

    if completed["depositos_abonos"] < 0 or completed["retiros_cargos"] < 0:
        return None

    expected_final = round(
        completed["saldo_anterior"]
        + completed["depositos_abonos"]
        - completed["retiros_cargos"],
        2,
    )

    if abs(expected_final - completed["saldo_final"]) > ACCOUNTING_TOLERANCE:
        return None

    return completed


def strengthen_hsbc_summary_accounting(
    words: Sequence[Dict[str, Any]],
    summary: ResumenFinanciero,
) -> bool:
    """
    Corrige el bloque contable sólo con tres evidencias directas y
    una identidad de saldo válida.

    Si OCR pierde dos o más valores, no fuerza ninguna reparación.
    El resto del ResumenFinanciero queda completamente intacto.
    """

    if not words:
        return False

    candidates = extract_summary_accounting_candidates(words)
    direct = _direct_values(candidates)
    completed = _complete_one_missing_value(direct)

    if completed is None:
        return False

    old_values = (
        round(float(summary.saldo_anterior or 0.0), 2),
        round(float(summary.depositos_abonos or 0.0), 2),
        round(float(summary.retiros_cargos or 0.0), 2),
        round(float(summary.saldo_final or 0.0), 2),
    )
    new_values = (
        completed["saldo_anterior"],
        completed["depositos_abonos"],
        completed["retiros_cargos"],
        completed["saldo_final"],
    )

    if old_values == new_values:
        return False

    summary.saldo_anterior = new_values[0]
    summary.depositos_abonos = new_values[1]
    summary.retiros_cargos = new_values[2]
    summary.saldo_final = new_values[3]

    return True
