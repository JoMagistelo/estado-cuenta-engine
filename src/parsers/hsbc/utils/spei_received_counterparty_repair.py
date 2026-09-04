from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional, Sequence, Tuple

from catalog.bank_signatures import BANK_SIGNATURES


MIN_BOUNDARY_OVERLAP = 6.0
MAX_ALIAS_COMPLETION = 2


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFD", _clean(value).upper())
    text = "".join(
        char for char in text if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]", "", text)


def _participant_aliases() -> Tuple[str, ...]:
    aliases: list[str] = []

    for signature in BANK_SIGNATURES.values():
        for value in (
            *(signature.get("keywords") or ()),
            signature.get("display_name"),
            *(signature.get("filename_keywords") or ()),
        ):
            alias = _clean(value)
            if alias and alias not in aliases:
                aliases.append(alias)

    return tuple(aliases)


PARTICIPANT_ALIASES = _participant_aliases()


def _complete_known_participant(value: str) -> Optional[Tuple[str, int]]:
    """Valida un participante y permite completar hasta dos letras finales."""

    compact_value = _compact(value)
    if not compact_value:
        return None

    candidates: list[Tuple[int, int, str]] = []

    for alias in PARTICIPANT_ALIASES:
        compact_alias = _compact(alias)
        if compact_alias == compact_value:
            candidates.append((0, -len(compact_alias), alias))
            continue

        if compact_alias.startswith(compact_value):
            missing = len(compact_alias) - len(compact_value)
            if 1 <= missing <= MAX_ALIAS_COMPLETION:
                candidates.append((missing, -len(compact_alias), alias))

    if not candidates:
        return None

    candidates.sort()
    missing, _, alias = candidates[0]
    return alias, missing


def _bounds(word: dict[str, Any]) -> Tuple[float, float]:
    try:
        x0 = float(word.get("x0", 0.0))
        return x0, float(word.get("x1", x0))
    except (TypeError, ValueError):
        return 0.0, 0.0


def _ordered_words(row: Any) -> list[dict[str, Any]]:
    words = [
        word
        for line in getattr(row, "lines", ())
        for word in line
        if _clean(word.get("text", ""))
    ]

    def sort_key(word: dict[str, Any]) -> Tuple[float, float, float]:
        try:
            page = float(word.get("page", 1) or 1)
        except (TypeError, ValueError):
            page = 1.0
        try:
            top = float(word.get("top", 0.0) or 0.0)
        except (TypeError, ValueError):
            top = 0.0
        try:
            x0 = float(word.get("x0", 0.0) or 0.0)
        except (TypeError, ValueError):
            x0 = 0.0
        return page, top, x0

    words.sort(key=sort_key)
    return words


def _overlap_ratio(
    word: dict[str, Any],
    xmin: float,
    xmax: float,
) -> float:
    x0, x1 = _bounds(word)
    width = max(x1 - x0, 0.001)
    overlap = max(0.0, min(x1, xmax) - max(x0, xmin))
    return overlap / width


def repair_received_spei_counterparty(
    row: Any,
    participant_box: Sequence[float],
    counterparty_box: Sequence[float],
) -> bool:
    """
    Repara sólo un SPEI recibido cuyo OCR fusionó Participante Emisor
    y Nombre del Ordenante dentro de la misma ``word``.

    La frontera X de las columnas decide dónde partir. El catálogo
    bancario únicamente valida/completa el participante; no se usa un
    diccionario de nombres ni se roba al ordenante la letra compartida
    en el borde (por ejemplo la ``R`` de ``...BANCOMEROGELIO``).
    """

    if getattr(row, "tipo", None) != "recibidos":
        return False

    participant_min = float(participant_box[0])
    boundary = float(participant_box[1])
    counterparty_max = float(counterparty_box[1])
    words = _ordered_words(row)

    for fused_word in words:
        text = _clean(fused_word.get("text", ""))
        x0, x1 = _bounds(fused_word)
        width = x1 - x0

        if (
            width <= 0.0
            or boundary - x0 < MIN_BOUNDARY_OVERLAP
            or x1 - boundary < MIN_BOUNDARY_OVERLAP
            or len(re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", text)) < 6
        ):
            continue

        base_parts = []
        for word in words:
            if word is fused_word:
                continue
            if _overlap_ratio(word, participant_min, boundary) < 0.70:
                continue
            if _bounds(word)[1] > boundary:
                continue

            value = _clean(word.get("text", ""))
            if value and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", value):
                base_parts.append(value)

        if not base_parts:
            continue

        estimated_index = ((boundary - x0) / width) * len(text)
        center_index = int(round(estimated_index))
        candidates: list[Tuple[float, str, str]] = []

        for index in range(
            max(2, center_index - 2),
            min(len(text) - 2, center_index + 2) + 1,
        ):
            left_fragment = text[:index].strip()
            right_fragment = text[index:].strip()
            if len(left_fragment) < 2 or len(right_fragment) < 2:
                continue

            completion = _complete_known_participant(
                " ".join([*base_parts, left_fragment])
            )
            if completion is None:
                continue

            participant, missing_chars = completion

            # La geometría tiene prioridad. Completar una o dos letras
            # del participante sólo valida el corte y recibe una pequeña
            # penalización para no apropiarse de la primera letra del
            # Nombre del Ordenante.
            score = (
                abs(index - estimated_index)
                + missing_chars * 0.15
            )
            candidates.append((score, participant, right_fragment))

        if not candidates:
            continue

        candidates.sort(key=lambda item: item[0])
        _, participant, right_fragment = candidates[0]

        name_parts: list[str] = []
        for word in words:
            if word is fused_word:
                name_parts.append(right_fragment)
                continue
            if _overlap_ratio(word, boundary, counterparty_max) < 0.70:
                continue

            value = _clean(word.get("text", ""))
            if value and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", value):
                name_parts.append(value)

        nombre_ordenante = " ".join(name_parts).strip()
        if not nombre_ordenante:
            continue

        row.participante = participant
        row.nombre_ordenante = nombre_ordenante
        row.beneficiario = nombre_ordenante
        return True

    return False


def repair_received_spei_counterparties(
    movements: list[Any],
    spatial_words: Sequence[dict[str, Any]],
) -> None:
    """Reaplica sólo los SPEI recibidos cuya frontera fue reparada."""

    if not movements or not spatial_words:
        return

    # Imports locales: esta utilidad permanece desacoplada de la clase
    # SpeiRow y reutiliza exactamente las cajas y reglas de cruce del
    # extractor existente.
    from parsers.hsbc.extractors.movimientos import (
        BOX_SPEI_BENEFICIARIO,
        BOX_SPEI_PARTICIPANTE,
        enrich_movements_from_spei,
        extract_spei_rows,
    )
    from parsers.hsbc.utils.words_footer_filter import (
        filter_hsbc_footer_words,
    )

    filtered_words = filter_hsbc_footer_words(list(spatial_words))
    if not filtered_words:
        return

    repaired_rows = []

    for row in extract_spei_rows(filtered_words):
        if repair_received_spei_counterparty(
            row,
            BOX_SPEI_PARTICIPANTE,
            BOX_SPEI_BENEFICIARIO,
        ):
            repaired_rows.append(row)

    if repaired_rows:
        enrich_movements_from_spei(movements, repaired_rows)
