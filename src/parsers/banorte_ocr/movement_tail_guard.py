from __future__ import annotations

from statistics import median

from .extractors.datos import SpatialWord, _group_lines, _page, _x0
from .extractors.movimientos import (
    _column_limits,
    _date_from_line,
    _line_y,
    _money_words,
    _movement_pages,
)


# ============================================================
# GUARDIA DEL ÚLTIMO MOVIMIENTO — BANORTE OCR
# ============================================================
#
# Un estado de cuenta escaneado puede terminar la tabla con una imagen
# promocional. Tesseract extrae texto de esa imagen y, si no aparece otra fecha,
# el extractor histórico puede considerarlo continuación del último movimiento.
#
# Este guard NO depende de frases publicitarias, del día 30/31 ni del nombre del
# producto. Se activa únicamente cuando la última fila fechada tiene evidencia
# estructural fuerte de movimiento:
#
#     FECHA + IMPORTE DE OPERACIÓN + SALDO
#
# A partir de esa fila aprende la escala visual de la propia tabla y corta sólo
# cuando aparece una separación vertical claramente anómala. Una línea con una
# separación moderadamente anómala sólo corta si además cambia la altura del
# texto o regresa al margen izquierdo. Si la última fila está incompleta por OCR,
# no se aplica este guard y se conserva exactamente el comportamiento anterior.
#
# La función opera sobre la COPIA de words destinada a movimientos. Los words
# originales usados por datos de cuenta, resumen y productos no se modifican.
# ============================================================

SOFT_GAP_MIN = 14.0
HARD_GAP_MIN = 20.0
HEIGHT_OUTLIER_RATIO = 1.25
LEFT_MARGIN_X = 82.0


def _word_top(word: SpatialWord) -> float:
    try:
        return float(word.get("top", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _word_bottom(word: SpatialWord) -> float:
    try:
        return float(word.get("bottom", _word_top(word)) or _word_top(word))
    except (TypeError, ValueError):
        return _word_top(word)


def _line_top(line: list[SpatialWord]) -> float:
    if not line:
        return 0.0
    return min(_word_top(word) for word in line)


def _line_height(line: list[SpatialWord]) -> float:
    heights = sorted(
        max(0.0, _word_bottom(word) - _word_top(word))
        for word in line
        if _word_bottom(word) > _word_top(word)
    )
    if not heights:
        return 0.0
    return float(median(heights))


def _confirmed_movement_line(
    line: list[SpatialWord],
    *,
    balance_start: float,
) -> bool:
    """Confirma una fila por estructura, no por el día del mes ni por su texto."""
    if _date_from_line(line) is None:
        return False

    amounts = _money_words(line)
    if not amounts:
        return False

    # Todo importe monetario detectado a la izquierda de SALDO pertenece a una
    # de las columnas de depósito/retiro. A la derecha esperamos el saldo.
    has_operation_amount = any(x < balance_start for x, _, _ in amounts)
    has_balance = any(x >= balance_start for x, _, _ in amounts)

    return has_operation_amount and has_balance


def _typical_transaction_height(
    lines: list[list[SpatialWord]],
    pages: set[int],
    *,
    balance_start: float,
) -> float:
    heights = [
        _line_height(line)
        for line in lines
        if line
        and _page(line[0]) in pages
        and _confirmed_movement_line(line, balance_start=balance_start)
        and _line_height(line) > 0.0
    ]
    return float(median(heights)) if heights else 0.0


def _typical_table_step(
    lines: list[list[SpatialWord]],
    pages: set[int],
    *,
    last_date_index: int,
    typical_height: float,
) -> float:
    """Aprende la separación vertical normal antes del último movimiento."""
    max_learning_gap = max(18.0, typical_height * 3.0)
    samples: list[float] = []
    previous_y_by_page: dict[int, float] = {}
    table_started_by_page: set[int] = set()

    for index, line in enumerate(lines):
        if index >= last_date_index:
            break
        if not line:
            continue

        page = _page(line[0])
        if page not in pages:
            continue

        if _date_from_line(line) is not None:
            table_started_by_page.add(page)

        if page not in table_started_by_page:
            continue

        current_y = _line_y(line)
        previous_y = previous_y_by_page.get(page)

        if previous_y is not None:
            gap = current_y - previous_y
            if 0.0 < gap <= max_learning_gap:
                samples.append(gap)

        previous_y_by_page[page] = current_y

    if samples:
        return float(median(samples))

    # Fallback conservador para documentos con muy pocos movimientos.
    return max(10.0, typical_height * 1.7)


def trim_after_last_confirmed_movement(
    words: list[SpatialWord],
) -> list[SpatialWord]:
    """
    Elimina ruido OCR posterior al último movimiento confirmado.

    La última fecha NO se considera suficiente por sí sola. El corte sólo se
    habilita si esa fila también contiene un importe de operación y un saldo.
    Así, movimientos parciales/corruptos conservan el comportamiento histórico.
    """
    if not words:
        return []

    lines = _group_lines(words)
    if not lines:
        return words

    pages = _movement_pages(lines)
    if not pages:
        return words

    _, _, balance_start = _column_limits(lines, pages)

    dated_indices = [
        index
        for index, line in enumerate(lines)
        if line
        and _page(line[0]) in pages
        and _date_from_line(line) is not None
    ]
    if not dated_indices:
        return words

    last_date_index = dated_indices[-1]
    last_date_line = lines[last_date_index]

    # Regla de seguridad principal: si el último movimiento no tiene evidencia
    # monetaria completa, no intentamos adivinar dónde termina su concepto.
    if not _confirmed_movement_line(
        last_date_line,
        balance_start=balance_start,
    ):
        return words

    typical_height = _typical_transaction_height(
        lines,
        pages,
        balance_start=balance_start,
    )
    if typical_height <= 0.0:
        return words

    typical_step = _typical_table_step(
        lines,
        pages,
        last_date_index=last_date_index,
        typical_height=typical_height,
    )

    soft_gap = max(
        SOFT_GAP_MIN,
        typical_step * 1.50,
        typical_height * 2.20,
    )
    hard_gap = max(
        HARD_GAP_MIN,
        typical_step * 1.95,
        typical_height * 3.00,
    )

    last_page = _page(last_date_line[0])
    previous_y = _line_y(last_date_line)

    for line in lines[last_date_index + 1 :]:
        if not line:
            continue

        page = _page(line[0])
        if page != last_page:
            break

        # Si aparece otra fecha o un importe monetario suelto, preferimos no
        # destruir información. El guard sólo corta texto sin evidencia de tabla.
        if _date_from_line(line) is not None or _money_words(line):
            previous_y = _line_y(line)
            continue

        current_y = _line_y(line)
        gap = current_y - previous_y
        if gap <= 0.0:
            previous_y = current_y
            continue

        line_height = _line_height(line)
        leftmost_x = min(_x0(word) for word in line)

        visual_outlier = (
            line_height > 0.0
            and line_height >= typical_height * HEIGHT_OUTLIER_RATIO
        )
        left_margin_break = leftmost_x < LEFT_MARGIN_X

        should_cut = (
            gap > hard_gap
            or (
                gap > soft_gap
                and (visual_outlier or left_margin_break)
            )
        )

        if should_cut:
            cutoff_top = _line_top(line)
            return [
                word
                for word in words
                if (
                    _page(word) < last_page
                    or (
                        _page(word) == last_page
                        and _word_top(word) < cutoff_top
                    )
                )
            ]

        previous_y = current_y

    return words
