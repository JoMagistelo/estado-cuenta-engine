from __future__ import annotations

import re
import unicodedata

from typing import Any, Dict, List, Sequence, Tuple

from models.movimiento import Movimiento
from parsers.hsbc.extractors.movimientos import (
    BOX_SPEI_PARTICIPANTE,
    SpeiRow,
    enrich_movements_from_spei,
    extract_spei_rows,
)
from parsers.hsbc.utils.words_footer_filter import filter_hsbc_footer_words


# Nombres de participantes que pueden quedar pegados al inicio del
# Nombre del Ordenante cuando Tesseract une ambas celdas en una sola
# word. La lista es deliberadamente conservadora: sólo se usa para
# validar una separación que ya está respaldada por la geometría de
# las dos columnas.
SPEI_PARTICIPANT_ALIASES: Tuple[str, ...] = (
    "BBVA BANCOMER",
    "BBVA MEXICO",
    "BANCO SANTANDER",
    "BANCO AZTECA",
    "BANCA AFIRME",
    "BANCOPPEL",
    "CITIBANAMEX",
    "SCOTIABANK",
    "SANTANDER",
    "BANAMEX",
    "BANORTE",
    "HSBC MEXICO",
    "AFIRME",
    "MIFEL",
    "AZTECA",
    "HSBC",
    "STP",
    # Variante de participante observada en layouts HSBC recibidos.
    "PAGEDER",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFD", _clean_text(value).upper())
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]", "", text)


def _row_words(row: SpeiRow) -> List[Dict[str, Any]]:
    words = [
        word
        for line in row.lines
        for word in line
        if _clean_text(word.get("text", ""))
    ]
    words.sort(
        key=lambda word: (
            _safe_float(word.get("top", 0.0)),
            _safe_float(word.get("x0", 0.0)),
        )
    )
    return words


def _participant_prefix_before_word(
    row: SpeiRow,
    crossing_word: Dict[str, Any],
) -> str:
    xmin, boundary, _, _ = BOX_SPEI_PARTICIPANTE
    crossing_x0 = _safe_float(crossing_word.get("x0", 0.0))
    crossing_top = _safe_float(crossing_word.get("top", 0.0))

    selected: List[Dict[str, Any]] = []

    for word in _row_words(row):
        if word is crossing_word:
            continue

        x0 = _safe_float(word.get("x0", 0.0))
        x1 = _safe_float(word.get("x1", x0))
        top = _safe_float(word.get("top", 0.0))

        if not (xmin - 6.0 <= x0 and x1 <= boundary + 2.0):
            continue
        if x1 > crossing_x0 + 1.0:
            continue
        if abs(top - crossing_top) > 12.0:
            continue

        selected.append(word)

    selected.sort(key=lambda word: _safe_float(word.get("x0", 0.0)))

    return " ".join(
        _clean_text(word.get("text", ""))
        for word in selected
    ).strip()


def _alias_for_geometric_prefix(prefix: str) -> str | None:
    compact_prefix = _compact(prefix)
    if not compact_prefix:
        return None

    candidates: List[Tuple[int, int, str]] = []

    for alias in SPEI_PARTICIPANT_ALIASES:
        compact_alias = _compact(alias)

        # El corte geométrico puede caer justo antes del último glifo
        # del participante. Ese mismo glifo puede ser el primero del
        # nombre contiguo (p. ej. ...BANCOME|ROSA). Se tolera como
        # máximo un carácter faltante y nunca se inventa el resto.
        if compact_alias.startswith(compact_prefix):
            missing = len(compact_alias) - len(compact_prefix)
            if 0 <= missing <= 1:
                candidates.append((missing, -len(compact_alias), alias))

    if not candidates:
        return None

    candidates.sort()
    return candidates[0][2]


def _split_crossing_word(
    row: SpeiRow,
    word: Dict[str, Any],
) -> Tuple[str, str] | None:
    text = _clean_text(word.get("text", ""))
    if len(_compact(text)) < 6:
        return None

    _, boundary, _, _ = BOX_SPEI_PARTICIPANTE
    x0 = _safe_float(word.get("x0", 0.0))
    x1 = _safe_float(word.get("x1", x0))

    if not (x0 < boundary < x1) or x1 <= x0:
        return None

    ratio = (boundary - x0) / (x1 - x0)
    estimated_index = int(round(ratio * len(text)))
    estimated_index = max(1, min(len(text) - 1, estimated_index))

    prefix = _participant_prefix_before_word(row, word)

    # Primero se respeta el corte geométrico. Sólo si no valida contra
    # un participante conocido se prueban dos posiciones contiguas;
    # esto absorbe pequeñas diferencias de caja sin convertir el
    # catálogo en un separador general de nombres.
    for delta in (0, -1, 1, -2, 2):
        index = estimated_index + delta
        if not 1 <= index < len(text):
            continue

        left = text[:index]
        right = text[index:]
        if len(_compact(right)) < 2:
            continue

        candidate_prefix = " ".join(
            part
            for part in (prefix, left)
            if part
        )
        alias = _alias_for_geometric_prefix(candidate_prefix)
        if alias is None:
            continue

        return alias, right.strip()

    return None


def _prepend_missing_name_piece(
    name_piece: str,
    current_name: str | None,
) -> str:
    piece = re.sub(r"\s+", " ", _clean_text(name_piece))
    current = re.sub(r"\s+", " ", _clean_text(current_name))

    if not current:
        return piece

    if _compact(current).startswith(_compact(piece)):
        return current

    return f"{piece} {current}".strip()


def repair_received_spei_row_party(row: SpeiRow) -> bool:
    """Repara una invasión participante -> ordenante con evidencia X."""

    if row.tipo != "recibidos":
        return False

    for word in _row_words(row):
        split = _split_crossing_word(row, word)
        if split is None:
            continue

        participant, name_piece = split
        repaired_name = _prepend_missing_name_piece(
            name_piece,
            row.nombre_ordenante or row.beneficiario,
        )

        if not participant or not repaired_name:
            continue

        row.participante = participant
        row.nombre_ordenante = repaired_name
        row.beneficiario = repaired_name
        return True

    return False


def repair_received_spei_parties(
    rows: Sequence[SpeiRow],
) -> bool:
    changed = False

    for row in rows:
        if repair_received_spei_row_party(row):
            changed = True

    return changed


def repair_received_spei_parties_in_movements(
    words: Sequence[Dict[str, Any]],
    movements: List[Movimiento],
) -> None:
    """
    Reaplica únicamente cruces SPEI que tuvieron una separación
    geométrica validada. Si no hay evidencia suficiente, no modifica
    ningún Movimiento existente.
    """

    if not words or not movements:
        return

    filtered_words = filter_hsbc_footer_words(words)
    if not filtered_words:
        return

    rows = extract_spei_rows(filtered_words)
    if not rows:
        return

    if not repair_received_spei_parties(rows):
        return

    enrich_movements_from_spei(movements, rows)
