from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento
from parsers.hsbc.extractors.movimientos import (
    BOX_ABONO,
    BOX_CARGO,
    BOX_DAY,
    BOX_SALDO,
    MovementRow,
    enrich_movements_from_spei,
    extract_day_from_line,
    extract_period_from_words,
    extract_spei_rows,
    is_valid_movement,
    movement_row_to_model,
    repair_corrupted_balances,
    repair_missing_operation_dates,
    split_page_into_movement_rows,
)
from parsers.hsbc.utils.spei_received_party_repair import (
    repair_received_spei_parties,
)
from parsers.hsbc.utils.summary_accounting_recovery import (
    extract_summary_accounting_candidates,
)
from parsers.hsbc.utils.words_footer_filter import filter_hsbc_footer_words


LINE_Y_TOLERANCE = 5.0
BALANCE_TOLERANCE = 0.06
MIN_STRONG_ROWS_PER_PAGE = 2

DATE_PATTERN = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])"
    r"[/-](?:0?[1-9]|1[0-2])"
    r"[/-]\d{4}\b"
)
MONEY_PATTERN = re.compile(r"^\$?\s*[\d,]+(?:\.\d{2})$")


@dataclass
class SupplementalMovement:
    movement: Movimiento
    row: MovementRow
    page: int
    top: float


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
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _normalize(value))


def _word_center_y(word: Dict[str, Any]) -> float:
    top = _safe_float(word.get("top", 0.0))
    bottom = _safe_float(word.get("bottom", top))
    return (top + bottom) / 2.0


def _line_center_y(line: Sequence[Dict[str, Any]]) -> float:
    if not line:
        return 0.0
    return sum(_word_center_y(word) for word in line) / len(line)


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
            if abs(_line_center_y(line) - center_y) <= LINE_Y_TOLERANCE:
                target = line
                break
            if center_y - _line_center_y(line) > LINE_Y_TOLERANCE:
                break

        if target is None:
            lines.append([word])
        else:
            target.append(word)

    for line in lines:
        line.sort(key=lambda word: _safe_float(word.get("x0", 0.0)))

    return lines


def _word_center_x(word: Dict[str, Any]) -> float:
    x0 = _safe_float(word.get("x0", 0.0))
    x1 = _safe_float(word.get("x1", x0))
    return (x0 + x1) / 2.0


def _center_inside(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding: float = 5.0,
) -> bool:
    xmin, xmax, _, _ = box
    center_x = _word_center_x(word)
    return xmin - padding <= center_x <= xmax + padding


def _is_money_word(word: Dict[str, Any]) -> bool:
    text = str(word.get("text", "")).strip()
    return bool(MONEY_PATTERN.fullmatch(text))


def _strong_movement_line(line: Sequence[Dict[str, Any]]) -> bool:
    if extract_day_from_line(line) is None:
        return False

    has_transaction = any(
        _is_money_word(word)
        and (
            _center_inside(word, BOX_CARGO)
            or _center_inside(word, BOX_ABONO)
        )
        for word in line
    )
    has_balance = any(
        _is_money_word(word)
        and _center_inside(word, BOX_SALDO)
        for word in line
    )

    return has_transaction and has_balance


def _synthetic_header_for_page(
    page: int,
    first_data_top: float,
) -> Dict[str, Any]:
    top = max(0.0, first_data_top - 24.0)
    return {
        "text": "DETALLE MOVIMIENTOS",
        "x0": 38.0,
        "x1": 180.0,
        "top": top,
        "bottom": top + 7.0,
        "page": page,
        "confidence": 100.0,
        "_synthetic_hsbc_recovery": True,
    }


def _supplemental_page_rows(
    page_words: Sequence[Dict[str, Any]],
) -> List[MovementRow]:
    lines = _group_page_lines(page_words)
    strong_lines = [line for line in lines if _strong_movement_line(line)]

    if len(strong_lines) < MIN_STRONG_ROWS_PER_PAGE:
        return []

    first_top = min(
        _safe_float(word.get("top", 0.0))
        for line in strong_lines
        for word in line
    )
    page = _safe_page(strong_lines[0][0])

    augmented = list(page_words)
    augmented.append(_synthetic_header_for_page(page, first_top))

    return split_page_into_movement_rows(augmented)


def _row_top(row: MovementRow) -> float:
    values = [
        _safe_float(word.get("top", 0.0))
        for line in row.lines
        for word in line
        if not word.get("_synthetic_hsbc_recovery")
    ]
    return min(values) if values else 0.0


def build_supplemental_movements(
    words: Sequence[Dict[str, Any]],
) -> List[SupplementalMovement]:
    """
    Reejecuta el parser histórico sólo en páginas que demuestran al
    menos dos filas financieras completas. El encabezado sintético no
    aporta ningún dato: únicamente permite que una página cuyo título
    fue cortado por OCR sea recorrida desde su primera fila real.
    """

    if not words:
        return []

    filtered = filter_hsbc_footer_words(words)
    periodo_inicio, _ = extract_period_from_words(filtered)

    pages: Dict[int, List[Dict[str, Any]]] = {}
    for word in filtered:
        pages.setdefault(_safe_page(word), []).append(word)

    result: List[SupplementalMovement] = []

    for page in sorted(pages):
        for row in _supplemental_page_rows(pages[page]):
            movement = movement_row_to_model(row, periodo_inicio)
            if not is_valid_movement(
                movement,
                allow_partial=row.partial_recovery,
            ):
                continue

            result.append(
                SupplementalMovement(
                    movement=movement,
                    row=row,
                    page=page,
                    top=_row_top(row),
                )
            )

    result.sort(key=lambda item: (item.page, item.top))
    return result


def _amount_delta(movement: Movimiento) -> Optional[float]:
    cargo = movement.cargo
    abono = movement.abono

    if cargo is None and abono is None:
        return None

    try:
        return round(float(abono or 0.0) - float(cargo or 0.0), 2)
    except (TypeError, ValueError):
        return None


def _balance(movement: Movimiento) -> Optional[float]:
    value = movement.saldo_operacion
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _balance_before(movement: Movimiento) -> Optional[float]:
    balance = _balance(movement)
    delta = _amount_delta(movement)
    if balance is None or delta is None:
        return None
    return round(balance - delta, 2)


def _same_amounts(first: Movimiento, second: Movimiento) -> bool:
    first_delta = _amount_delta(first)
    second_delta = _amount_delta(second)
    if first_delta is None or second_delta is None:
        return False
    return abs(first_delta - second_delta) <= BALANCE_TOLERANCE


def _movement_already_present(
    candidate: Movimiento,
    movements: Sequence[Movimiento],
) -> bool:
    candidate_reference = _compact(candidate.referencia)
    candidate_concept = _compact(candidate.concepto)
    candidate_balance = _balance(candidate)

    for movement in movements:
        if (
            candidate_reference
            and candidate_reference == _compact(movement.referencia)
            and _same_amounts(candidate, movement)
        ):
            return True

        if (
            candidate_concept
            and candidate_concept == _compact(movement.concepto)
            and candidate.fecha_operacion == movement.fecha_operacion
            and _same_amounts(candidate, movement)
        ):
            return True

        movement_balance = _balance(movement)
        if (
            candidate_balance is not None
            and movement_balance is not None
            and abs(candidate_balance - movement_balance) <= BALANCE_TOLERANCE
            and candidate.fecha_operacion == movement.fecha_operacion
            and _same_amounts(candidate, movement)
        ):
            return True

    return False


def _find_balance_chain(
    start_balance: float,
    target_balance: float,
    candidates: Sequence[SupplementalMovement],
    used: set[int],
) -> List[SupplementalMovement]:
    """Busca una cadena cronológica exacta entre dos saldos conocidos."""

    if abs(start_balance - target_balance) <= BALANCE_TOLERANCE:
        return []

    # DFS pequeño: en los estados reales el número de candidatas no
    # emparejadas es bajo. Se limita la profundidad para impedir que
    # una tabla ajena con muchos importes pueda convertirse en una
    # búsqueda combinatoria.
    available = [
        (index, item)
        for index, item in enumerate(candidates)
        if index not in used
    ]

    def search(
        current: float,
        start_index: int,
        path: List[Tuple[int, SupplementalMovement]],
    ) -> Optional[List[Tuple[int, SupplementalMovement]]]:
        if len(path) >= 16:
            return None

        for position in range(start_index, len(available)):
            candidate_index, candidate = available[position]
            before = _balance_before(candidate.movement)
            after = _balance(candidate.movement)

            if before is None or after is None:
                continue
            if abs(before - current) > BALANCE_TOLERANCE:
                continue

            next_path = [*path, (candidate_index, candidate)]
            if abs(after - target_balance) <= BALANCE_TOLERANCE:
                return next_path

            resolved = search(after, position + 1, next_path)
            if resolved is not None:
                return resolved

        return None

    resolved = search(start_balance, 0, [])
    if resolved is None:
        return []

    for candidate_index, _ in resolved:
        used.add(candidate_index)

    return [candidate for _, candidate in resolved]


def insert_accounting_bridge_movements(
    movements: Sequence[Movimiento],
    supplemental: Sequence[SupplementalMovement],
    opening_balance: Optional[float],
    closing_balance: Optional[float],
) -> List[Movimiento]:
    """
    Inserta sólo filas que formen una cadena exacta entre fronteras
    contables ya observadas. Una candidata aislada por monto o fecha
    nunca se inserta.
    """

    if not movements:
        return [item.movement for item in supplemental]

    candidates = [
        item
        for item in supplemental
        if not _movement_already_present(item.movement, movements)
    ]
    if not candidates:
        return list(movements)

    used: set[int] = set()
    result: List[Movimiento] = []

    first = movements[0]
    first_before = _balance_before(first)

    if opening_balance is not None and first_before is not None:
        result.extend(
            item.movement
            for item in _find_balance_chain(
                opening_balance,
                first_before,
                candidates,
                used,
            )
        )

    result.append(first)

    for index in range(len(movements) - 1):
        current = movements[index]
        following = movements[index + 1]
        current_balance = _balance(current)
        following_before = _balance_before(following)

        if current_balance is not None and following_before is not None:
            result.extend(
                item.movement
                for item in _find_balance_chain(
                    current_balance,
                    following_before,
                    candidates,
                    used,
                )
            )

        result.append(following)

    if closing_balance is not None:
        last_balance = _balance(result[-1]) if result else None
        if last_balance is not None:
            result.extend(
                item.movement
                for item in _find_balance_chain(
                    last_balance,
                    closing_balance,
                    candidates,
                    used,
                )
            )

    return result


def _direct_summary_value(
    words: Sequence[Dict[str, Any]],
    field: str,
) -> Optional[float]:
    candidates = extract_summary_accounting_candidates(words).get(field, [])
    if not candidates:
        return None

    counts: Dict[float, int] = {}
    for candidate in candidates:
        rounded = round(candidate.value, 2)
        counts[rounded] = counts.get(rounded, 0) + 1

    best = min(
        candidates,
        key=lambda candidate: (
            -counts[round(candidate.value, 2)],
            candidate.distance,
            candidate.page,
            candidate.top,
        ),
    )
    return round(best.value, 2)


def infer_single_missing_amount(
    movements: Sequence[Movimiento],
    opening_balance: Optional[float],
    closing_balance: Optional[float],
) -> bool:
    """
    Si exactamente una fila perdió ambos importes, recupera únicamente
    ese delta a partir de los saldos de apertura/cierre. Con dos o más
    importes ausentes no realiza inferencia.
    """

    if opening_balance is None or closing_balance is None:
        return False

    missing = [
        movement
        for movement in movements
        if movement.cargo is None and movement.abono is None
    ]
    if len(missing) != 1:
        return False

    known_delta = 0.0
    for movement in movements:
        delta = _amount_delta(movement)
        if delta is None:
            continue
        known_delta += delta

    required_delta = round(
        closing_balance - opening_balance - known_delta,
        2,
    )
    if abs(required_delta) < 0.01:
        return False

    movement = missing[0]
    if required_delta < 0.0:
        movement.cargo = abs(required_delta)
        movement.abono = 0.0
    else:
        movement.cargo = 0.0
        movement.abono = required_delta

    return True


def reconcile_balances_if_statement_closes(
    movements: Sequence[Movimiento],
    opening_balance: Optional[float],
    closing_balance: Optional[float],
) -> bool:
    """
    Recalcula saldos sólo si toda la serie de importes conduce desde
    el saldo inicial impreso hasta el saldo final impreso. Si la serie
    no cierra, conserva todos los saldos OCR originales.
    """

    if opening_balance is None or closing_balance is None:
        return False

    running = round(opening_balance, 2)
    expected: List[float] = []

    for movement in movements:
        delta = _amount_delta(movement)
        if delta is None:
            return False
        running = round(running + delta, 2)
        expected.append(running)

    if abs(running - closing_balance) > BALANCE_TOLERANCE:
        return False

    changed = False
    for movement, expected_balance in zip(movements, expected):
        observed = _balance(movement)
        if observed is None or abs(observed - expected_balance) > 0.01:
            movement.saldo_operacion = expected_balance
            changed = True

    return changed


def _line_text(line: Sequence[Dict[str, Any]]) -> str:
    return " ".join(str(word.get("text", "")).strip() for word in line).strip()


def _degraded_spei_period_headers(
    words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detecta un título SPEI recortado sólo cuando debajo existe carga
    tabular fuerte (claves, cuentas e importes). Esto evita confundir
    el `Periodo del` del resumen financiero con una tabla SPEI.
    """

    lines = _group_page_lines(words)
    synthetic: List[Dict[str, Any]] = []

    for line in lines:
        if not line:
            continue

        text = _normalize(_line_text(line))
        if "ERIODO" not in text:
            continue
        dates = DATE_PATTERN.findall(text)
        if len(dates) < 2:
            continue

        page = _safe_page(line[0])
        header_y = _line_center_y(line)

        window_words = [
            word
            for word in words
            if _safe_page(word) == page
            and header_y + 15.0 <= _word_center_y(word) <= header_y + 180.0
        ]

        tracking_count = 0
        account_count = 0
        amount_count = 0

        for word in window_words:
            text_word = str(word.get("text", "")).strip()
            compact = _compact(text_word)
            digits = re.sub(r"\D", "", text_word)
            center_x = _word_center_x(word)

            if 455.0 <= center_x <= 520.0 and (
                compact.startswith("MBAN")
                or compact.startswith("HSB")
            ):
                tracking_count += 1

            if 235.0 <= center_x <= 390.0 and len(digits) >= 14:
                account_count += 1

            if 390.0 <= center_x <= 470.0 and MONEY_PATTERN.fullmatch(text_word):
                amount_count += 1

        if min(tracking_count, account_count, amount_count) < 2:
            continue

        first_top = min(_safe_float(word.get("top", 0.0)) for word in line)
        synthetic.append(
            {
                "text": (
                    "Información durante el periodo "
                    f"{dates[0]} al {dates[1]}"
                ),
                "x0": 120.0,
                "x1": 445.0,
                "top": first_top,
                "bottom": first_top + 7.0,
                "page": page,
                "confidence": 100.0,
                "_synthetic_hsbc_spei_header": True,
            }
        )

    return synthetic


def extract_spei_rows_with_header_recovery(
    words: Sequence[Dict[str, Any]],
):
    augmented = list(words)
    augmented.extend(_degraded_spei_period_headers(words))
    rows = extract_spei_rows(augmented)
    repair_received_spei_parties(rows)
    return rows


def strengthen_hsbc_scanned_movements(
    words: Sequence[Dict[str, Any]],
    movements: List[Movimiento],
) -> List[Movimiento]:
    """
    Refuerzo posterior y conservador para HSBC escaneado:

    1. recupera páginas cuyo encabezado de movimientos fue recortado;
    2. inserta únicamente cadenas que cierren una discontinuidad;
    3. permite inferir un solo importe totalmente ausente;
    4. recalcula saldos sólo si toda la cuenta cierra contra apertura
       y cierre impresos;
    5. reintenta SPEI cuando su encabezado de periodo quedó recortado.
    """

    if not words or not movements:
        return movements

    filtered = filter_hsbc_footer_words(words)
    if not filtered:
        return movements

    opening_balance = _direct_summary_value(filtered, "saldo_anterior")
    closing_balance = _direct_summary_value(filtered, "saldo_final")

    supplemental = build_supplemental_movements(filtered)
    strengthened = insert_accounting_bridge_movements(
        movements,
        supplemental,
        opening_balance,
        closing_balance,
    )

    infer_single_missing_amount(
        strengthened,
        opening_balance,
        closing_balance,
    )

    reconcile_balances_if_statement_closes(
        strengthened,
        opening_balance,
        closing_balance,
    )

    # Conserva las reparaciones históricas para casos parciales que no
    # cumplen las condiciones globales anteriores.
    repair_corrupted_balances(strengthened)
    repair_missing_operation_dates(strengthened)

    spei_rows = extract_spei_rows_with_header_recovery(filtered)
    if spei_rows:
        enrich_movements_from_spei(strengthened, spei_rows)

    return strengthened
