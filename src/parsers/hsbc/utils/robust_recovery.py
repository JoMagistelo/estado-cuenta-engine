from __future__ import annotations

import re
import unicodedata

from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.datos_cuenta import DatosCuenta
from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero


LINE_Y_TOLERANCE = 5.0
SUMMARY_VALUE_MIN_X = 480.0
ACCOUNT_VALUE_MAX_X = 190.0
CLIENT_VALUE_MAX_X = 190.0

MONEY_TOKEN_PATTERN = re.compile(
    r"^\$?\s*[\d,]+(?:\.\d{1,2})?$"
)
RFC_PATTERN = re.compile(
    r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,4}$",
    re.IGNORECASE,
)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1))
    except (TypeError, ValueError):
        return 1


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    text = text.upper()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_center(
    word: Dict[str, Any],
) -> Tuple[float, float]:
    x0 = safe_float(word.get("x0", 0.0))
    x1 = safe_float(word.get("x1", x0))
    top = safe_float(word.get("top", 0.0))
    bottom = safe_float(word.get("bottom", top))

    return (
        (x0 + x1) / 2.0,
        (top + bottom) / 2.0,
    )


def line_bounds(
    line: Sequence[Dict[str, Any]],
) -> Tuple[float, float, float, float]:
    if not line:
        return 0.0, 0.0, 0.0, 0.0

    return (
        min(safe_float(word.get("x0", 0.0)) for word in line),
        max(safe_float(word.get("x1", 0.0)) for word in line),
        min(safe_float(word.get("top", 0.0)) for word in line),
        max(safe_float(word.get("bottom", 0.0)) for word in line),
    )


def line_center_y(
    line: Sequence[Dict[str, Any]],
) -> float:
    _, _, top, bottom = line_bounds(line)
    return (top + bottom) / 2.0


def line_text(
    line: Sequence[Dict[str, Any]],
) -> str:
    return " ".join(
        clean_text(word.get("text", ""))
        for word in line
        if clean_text(word.get("text", ""))
    ).strip()


def group_words_into_lines(
    words: Sequence[Dict[str, Any]],
    y_tolerance: float = LINE_Y_TOLERANCE,
) -> List[List[Dict[str, Any]]]:
    valid_words = [
        word
        for word in words
        if clean_text(word.get("text", ""))
    ]
    valid_words.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    lines_by_page: Dict[
        int,
        List[List[Dict[str, Any]]],
    ] = {}

    for word in valid_words:
        page = safe_page(word)
        center_y = word_center(word)[1]
        page_lines = lines_by_page.setdefault(page, [])

        best_line: Optional[List[Dict[str, Any]]] = None
        best_distance = float("inf")

        for line in reversed(page_lines):
            current_y = line_center_y(line)
            distance = abs(center_y - current_y)

            if (
                distance <= y_tolerance
                and distance < best_distance
            ):
                best_distance = distance
                best_line = line

            if current_y < center_y - y_tolerance:
                break

        if best_line is None:
            page_lines.append([word])
        else:
            best_line.append(word)

    result: List[List[Dict[str, Any]]] = []

    for page in sorted(lines_by_page):
        page_lines = lines_by_page[page]
        page_lines.sort(key=line_center_y)

        for line in page_lines:
            line.sort(
                key=lambda word: safe_float(
                    word.get("x0", 0.0)
                )
            )
            result.append(line)

    return result


def _normalized_alpha_token(value: Any) -> str:
    return re.sub(
        r"[^A-Z]",
        "",
        normalize_text(value),
    )


def normalize_hsbc_ocr_words(
    words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Aplica correcciones OCR extremadamente acotadas.

    No modifica coordenadas ni reescribe conceptos. Actualmente
    sólo recupera el encabezado ``DETALLE MOVIMIENTOS`` cuando
    Tesseract pierde la D inicial y entrega ``ETALLE``.
    """

    normalized_words = [
        dict(word)
        for word in words
    ]

    words_by_page: Dict[
        int,
        List[Dict[str, Any]],
    ] = {}

    for word in normalized_words:
        words_by_page.setdefault(
            safe_page(word),
            [],
        ).append(word)

    for page_words in words_by_page.values():
        movement_words = [
            word
            for word in page_words
            if (
                _normalized_alpha_token(
                    word.get("text", "")
                )
                == "MOVIMIENTOS"
            )
        ]

        if not movement_words:
            continue

        for word in page_words:
            if (
                _normalized_alpha_token(
                    word.get("text", "")
                )
                != "ETALLE"
            ):
                continue

            word_x, word_y = word_center(word)

            is_header = any(
                (
                    other_x >= word_x
                    and abs(other_y - word_y)
                    <= LINE_Y_TOLERANCE + 1.0
                )
                for other_x, other_y in (
                    word_center(other)
                    for other in movement_words
                )
            )

            if is_header:
                word["text"] = "DETALLE"

    return normalized_words


def _line_has_tokens(
    line: Sequence[Dict[str, Any]],
    required_tokens: Sequence[str],
    forbidden_tokens: Sequence[str] = (),
) -> bool:
    normalized = normalize_text(line_text(line))

    if not all(
        normalize_text(token) in normalized
        for token in required_tokens
    ):
        return False

    return not any(
        normalize_text(token) in normalized
        for token in forbidden_tokens
    )


def _numeric_word_candidate(
    word: Dict[str, Any],
    min_digits: int,
    max_digits: int,
) -> Optional[str]:
    raw = clean_text(word.get("text", ""))
    compact = re.sub(r"[\s.,;:|_-]", "", raw)

    if not compact.isdigit():
        return None

    if not min_digits <= len(compact) <= max_digits:
        return None

    return compact


def _find_numeric_below_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
    required_tokens: Sequence[str],
    min_digits: int,
    max_digits: int,
    max_x: float,
    max_vertical_gap: float = 30.0,
) -> Optional[str]:
    anchors = [
        line
        for line in lines
        if _line_has_tokens(
            line,
            required_tokens,
        )
    ]

    if not anchors:
        return None

    candidates = []

    for anchor in anchors:
        anchor_page = safe_page(anchor[0])
        anchor_y = line_center_y(anchor)

        for line in lines:
            if not line:
                continue
            if safe_page(line[0]) != anchor_page:
                continue

            line_y = line_center_y(line)
            gap = line_y - anchor_y

            if gap <= 0.0 or gap > max_vertical_gap:
                continue

            for word in line:
                center_x, _ = word_center(word)
                if center_x > max_x:
                    continue

                value = _numeric_word_candidate(
                    word,
                    min_digits=min_digits,
                    max_digits=max_digits,
                )

                if value is None:
                    continue

                candidates.append(
                    (
                        gap,
                        center_x,
                        value,
                    )
                )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return candidates[0][2]


def _find_rfc_below_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    anchors = [
        line
        for line in lines
        if _line_has_tokens(line, ("RFC",))
    ]

    if not anchors:
        return None

    candidates = []

    for anchor in anchors:
        page = safe_page(anchor[0])
        anchor_y = line_center_y(anchor)

        for line in lines:
            if not line or safe_page(line[0]) != page:
                continue

            gap = line_center_y(line) - anchor_y
            if gap <= 0.0 or gap > 35.0:
                continue

            for word in line:
                center_x, _ = word_center(word)
                if center_x > ACCOUNT_VALUE_MAX_X:
                    continue

                candidate = re.sub(
                    r"[^A-Z0-9Ñ&]",
                    "",
                    normalize_text(
                        word.get("text", "")
                    ),
                )

                if RFC_PATTERN.fullmatch(candidate):
                    candidates.append(
                        (
                            gap,
                            center_x,
                            candidate,
                        )
                    )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return candidates[0][2]


def _find_clabe_below_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    anchors = [
        line
        for line in lines
        if _line_has_tokens(line, ("CLABE",))
    ]

    candidates = []

    for anchor in anchors:
        page = safe_page(anchor[0])
        anchor_y = line_center_y(anchor)

        for line in lines:
            if not line or safe_page(line[0]) != page:
                continue

            gap = line_center_y(line) - anchor_y
            if gap <= 0.0 or gap > 30.0:
                continue

            for word in line:
                value = _numeric_word_candidate(
                    word,
                    min_digits=18,
                    max_digits=18,
                )
                if value is None:
                    continue

                center_x, _ = word_center(word)
                candidates.append(
                    (
                        gap,
                        -center_x,
                        value,
                    )
                )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )
    return candidates[0][2]


def _find_standalone_rfc(
    words: Sequence[Dict[str, Any]],
) -> Optional[str]:
    candidates = []

    for word in words:
        center_x, center_y = word_center(word)

        if center_x > ACCOUNT_VALUE_MAX_X:
            continue

        # Zona de datos del titular; evita textos legales de páginas
        # posteriores que también pueden contener RFC.
        if not 150.0 <= center_y <= 320.0:
            continue

        candidate = re.sub(
            r"[^A-Z0-9Ñ&]",
            "",
            normalize_text(
                word.get("text", "")
            ),
        )

        if not RFC_PATTERN.fullmatch(candidate):
            continue

        candidates.append(
            (
                safe_page(word),
                center_y,
                center_x,
                candidate,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )
    return candidates[0][3]


def repair_datos_cuenta(
    words: Sequence[Dict[str, Any]],
    datos: DatosCuenta,
) -> None:
    """
    Añade fallbacks conservadores a los datos de cuenta.

    Los valores ya válidos conservan prioridad. Sólo se reemplaza
    un número de cliente existente cuando se demuestra que contiene
    al candidato puro como prefijo y después agregó dígitos de otra
    columna (caso típico: dígitos del RFC unidos por OCR).
    """

    lines = group_words_into_lines(words)

    if not datos.producto_principal:
        product_candidates = [
            line
            for line in lines
            if (
                _line_has_tokens(
                    line,
                    (
                        "NOMINA",
                        "FLEXIBLE",
                    ),
                )
                and line_center_y(line) <= 90.0
            )
        ]

        if product_candidates:
            datos.producto_principal = (
                "Nómina Flexible HSBC"
            )

    account_candidate = _find_numeric_below_anchor(
        lines,
        (
            "NUMERO",
            "CUENTA",
        ),
        min_digits=8,
        max_digits=18,
        max_x=ACCOUNT_VALUE_MAX_X,
    )

    if (
        datos.numero_cuenta is None
        and account_candidate is not None
    ):
        datos.numero_cuenta = account_candidate

    client_candidate = _find_numeric_below_anchor(
        lines,
        (
            "NUMERO",
            "CLIENTE",
        ),
        min_digits=5,
        max_digits=15,
        max_x=CLIENT_VALUE_MAX_X,
    )

    if client_candidate is not None:
        current = re.sub(
            r"\D",
            "",
            datos.numero_cliente or "",
        )

        if not current:
            datos.numero_cliente = client_candidate
        elif (
            len(current) > len(client_candidate)
            and current.startswith(client_candidate)
        ):
            datos.numero_cliente = client_candidate

    if datos.clabe is None:
        clabe_candidate = _find_clabe_below_anchor(
            lines
        )
        if clabe_candidate is not None:
            datos.clabe = clabe_candidate

    if datos.rfc is None:
        rfc_candidate = _find_rfc_below_anchor(
            lines
        )

        if rfc_candidate is None:
            rfc_candidate = _find_standalone_rfc(
                words
            )

        if rfc_candidate is not None:
            datos.rfc = rfc_candidate


def _money_candidates(
    line: Sequence[Dict[str, Any]],
) -> List[Tuple[float, float]]:
    result = []

    for word in line:
        text = clean_text(
            word.get("text", "")
        )

        if not text or text == "$":
            continue

        if not MONEY_TOKEN_PATTERN.fullmatch(text):
            continue

        normalized = (
            text
            .replace("$", "")
            .replace(",", "")
            .replace(" ", "")
        )

        if not re.fullmatch(
            r"\d+(?:\.\d{1,2})?",
            normalized,
        ):
            continue

        # Evita tratar códigos, referencias o días como dinero.
        if (
            "." not in normalized
            and "," not in text
            and "$" not in text
        ):
            continue

        try:
            value = float(normalized)
        except ValueError:
            continue

        result.append(
            (
                word_center(word)[0],
                value,
            )
        )

    return result


def _money_from_line(
    line: Sequence[Dict[str, Any]],
    min_x: Optional[float] = None,
) -> Optional[float]:
    candidates = _money_candidates(line)

    if min_x is not None:
        candidates = [
            candidate
            for candidate in candidates
            if candidate[0] >= min_x
        ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[-1][1]


def _find_summary_page(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[int]:
    for line in lines:
        if _line_has_tokens(
            line,
            (
                "RESUMEN",
                "CUENTAS",
            ),
        ):
            return safe_page(line[0])

    return None


def _find_semantic_money(
    lines: Sequence[Sequence[Dict[str, Any]]],
    required_tokens: Sequence[str],
    forbidden_tokens: Sequence[str] = (),
    page: Optional[int] = None,
    min_x: Optional[float] = None,
) -> Optional[float]:
    candidates = []

    for line in lines:
        if not line:
            continue

        if (
            page is not None
            and safe_page(line[0]) != page
        ):
            continue

        if not _line_has_tokens(
            line,
            required_tokens,
            forbidden_tokens,
        ):
            continue

        value = _money_from_line(
            line,
            min_x=min_x,
        )

        if value is None:
            continue

        candidates.append(
            (
                safe_page(line[0]),
                line_center_y(line),
                value,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return candidates[0][2]


def _find_orphan_money_after_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
    anchor_tokens: Sequence[str],
    max_gap: float,
) -> Optional[float]:
    anchors = [
        line
        for line in lines
        if _line_has_tokens(
            line,
            anchor_tokens,
        )
    ]

    candidates = []

    for anchor in anchors:
        page = safe_page(anchor[0])
        anchor_y = line_center_y(anchor)

        for line in lines:
            if not line or safe_page(line[0]) != page:
                continue

            gap = line_center_y(line) - anchor_y

            if gap <= 0.0 or gap > max_gap:
                continue

            text_without_money = re.sub(
                r"[\d\s$.,%+-]",
                "",
                normalize_text(
                    line_text(line)
                ),
            )

            if text_without_money:
                continue

            value = _money_from_line(line)
            if value is None:
                continue

            candidates.append(
                (
                    gap,
                    value,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def _find_saldo_promedio_fallback(
    lines: Sequence[Sequence[Dict[str, Any]]],
    summary_page: Optional[int],
) -> Optional[float]:
    direct = _find_semantic_money(
        lines,
        (
            "SALDO",
            "PROMEDIO",
            "MES",
        ),
        forbidden_tokens=("MINIMO",),
        page=summary_page,
    )

    if direct is not None:
        return direct

    anchors = [
        line
        for line in lines
        if (
            (
                summary_page is None
                or safe_page(line[0]) == summary_page
            )
            and _line_has_tokens(
                line,
                (
                    "SALDO",
                    "PROMEDIO",
                    "MINIMO",
                ),
            )
        )
    ]

    for anchor in anchors:
        page = safe_page(anchor[0])
        anchor_y = line_center_y(anchor)

        candidates = []

        for line in lines:
            if not line or safe_page(line[0]) != page:
                continue

            gap = line_center_y(line) - anchor_y

            if gap <= 0.0 or gap > 45.0:
                continue

            normalized = normalize_text(
                line_text(line)
            )

            # La fila siguiente del saldo promedio conserva al menos
            # la palabra SALDO aun cuando OCR destruya PROMEDIO/MES.
            if "SALDO" not in normalized:
                continue

            value = _money_from_line(line)
            if value is None:
                continue

            candidates.append(
                (
                    gap,
                    value,
                )
            )

        if candidates:
            candidates.sort(
                key=lambda item: item[0]
            )
            return candidates[0][1]

    return None


def _movement_section_has_tokens(
    lines: Sequence[Sequence[Dict[str, Any]]],
    required_tokens: Sequence[str],
) -> bool:
    in_movements = False

    for line in lines:
        normalized = normalize_text(
            line_text(line)
        )

        if (
            "MOVIMIENTOS" in normalized
            and (
                "DETALLE" in normalized
                or "ETALLE" in normalized
            )
        ):
            in_movements = True
            continue

        if in_movements and (
            (
                "INFORMACION" in normalized
                and "SPEI" in normalized
            )
            or normalized.startswith("CODI")
        ):
            in_movements = False

        if (
            in_movements
            and all(
                normalize_text(token)
                in normalized
                for token in required_tokens
            )
        ):
            return True

    return False


def repair_resumen_financiero(
    words: Sequence[Dict[str, Any]],
    resumen: ResumenFinanciero,
) -> None:
    """
    Repara únicamente valores que poseen evidencia semántica fuerte.

    La diferencia respecto al extractor histórico es que el Y del
    renglón encontrado manda; no se desplaza el valor a un Y fijo.
    Las coordenadas fijas permanecen intactas en el extractor
    existente y esta capa sólo corrige fallos demostrables.
    """

    lines = group_words_into_lines(words)
    summary_page = _find_summary_page(lines)

    raw_saldo_anterior = _find_semantic_money(
        lines,
        ("SALDO", "INICIAL"),
        page=summary_page,
        min_x=SUMMARY_VALUE_MIN_X,
    )

    if raw_saldo_anterior is None:
        raw_saldo_anterior = _find_semantic_money(
            lines,
            ("SALDO", "INICIAL"),
        )

    raw_depositos = _find_semantic_money(
        lines,
        ("DEPOSITOS",),
        page=summary_page,
        min_x=SUMMARY_VALUE_MIN_X,
    )

    raw_retiros = _find_semantic_money(
        lines,
        ("RETIROS", "CARGOS"),
        page=summary_page,
        min_x=SUMMARY_VALUE_MIN_X,
    )

    raw_saldo_final = _find_semantic_money(
        lines,
        ("SALDO", "FINAL"),
        page=summary_page,
        min_x=SUMMARY_VALUE_MIN_X,
    )

    if raw_saldo_final is None:
        raw_saldo_final = _find_semantic_money(
            lines,
            ("SALDO", "FINAL"),
        )

    if raw_saldo_anterior is not None:
        resumen.saldo_anterior = (
            raw_saldo_anterior
        )

    if raw_saldo_final is not None:
        resumen.saldo_final = raw_saldo_final

    monthly_interest = _find_semantic_money(
        lines,
        (
            "PAGO",
            "INTERES",
            "NOMINAL",
            "MES",
        ),
        forbidden_tokens=("ANO",),
        page=summary_page,
    )

    monthly_isr = _find_semantic_money(
        lines,
        (
            "ISR",
            "RETENIDO",
            "MES",
        ),
        forbidden_tokens=("ANO",),
        page=summary_page,
    )

    if monthly_interest is not None:
        resumen.intereses_a_favor = (
            monthly_interest
        )

    if monthly_isr is not None:
        resumen.isr_retenido = monthly_isr

    average_balance = (
        _find_saldo_promedio_fallback(
            lines,
            summary_page,
        )
    )

    if average_balance is not None:
        resumen.saldo_promedio = (
            average_balance
        )

    minimum_average = (
        _find_semantic_money(
            lines,
            (
                "SALDO",
                "PROMEDIO",
                "MINIMO",
            ),
            page=summary_page,
        )
    )

    if minimum_average is None:
        minimum_average = (
            _find_orphan_money_after_anchor(
                lines,
                (
                    "SALDO",
                    "PROMEDIO",
                    "MINIMO",
                ),
                max_gap=15.0,
            )
        )

    if minimum_average is not None:
        resumen.saldo_promedio_minimo_mensual = (
            minimum_average
        )
    elif (
        average_balance is not None
        and resumen.saldo_promedio_minimo_mensual
        is not None
    ):
        try:
            minimum_value = float(
                resumen.saldo_promedio_minimo_mensual
            )
        except (TypeError, ValueError):
            minimum_value = None

        if (
            minimum_value is not None
            and abs(
                minimum_value - average_balance
            ) <= 0.01
        ):
            # Evita conservar el saldo promedio real como si fuera
            # el mínimo requerido cuando OCR omitió el $0.00.
            resumen.saldo_promedio_minimo_mensual = None

    core_values = (
        raw_saldo_anterior,
        raw_depositos,
        raw_retiros,
        raw_saldo_final,
    )

    base_equation_closes = (
        all(
            value is not None
            for value in core_values
        )
        and abs(
            (
                float(raw_saldo_anterior)
                + float(raw_depositos)
                - float(raw_retiros)
            )
            - float(raw_saldo_final)
        )
        <= 0.01
    )

    if base_equation_closes:
        if (
            resumen.intereses_a_favor is None
            and not _movement_section_has_tokens(
                lines,
                (
                    "PAGO",
                    "INTERES",
                    "NOMINAL",
                ),
            )
        ):
            resumen.intereses_a_favor = 0.0

        if (
            resumen.isr_retenido is None
            and not _movement_section_has_tokens(
                lines,
                (
                    "ISR",
                    "RETENIDO",
                ),
            )
        ):
            resumen.isr_retenido = 0.0

    if raw_depositos is not None:
        resumen.depositos_abonos = (
            raw_depositos
            + float(
                resumen.intereses_a_favor
                or 0.0
            )
        )

    if raw_retiros is not None:
        resumen.retiros_cargos = (
            raw_retiros
            + float(
                resumen.isr_retenido
                or 0.0
            )
        )


def _movement_delta(
    movement: Movimiento,
) -> Optional[float]:
    cargo = movement.cargo
    abono = movement.abono

    if cargo is None and abono is None:
        return None

    try:
        return (
            float(abono or 0.0)
            - float(cargo or 0.0)
        )
    except (TypeError, ValueError):
        return None


def _movement_has_amount(
    movement: Movimiento,
) -> bool:
    try:
        return (
            abs(float(movement.cargo or 0.0))
            > 0.005
            or abs(float(movement.abono or 0.0))
            > 0.005
        )
    except (TypeError, ValueError):
        return False


def repair_leading_partial_movement(
    movements: List[Movimiento],
    resumen: ResumenFinanciero,
) -> None:
    """
    Recupera el importe del primer movimiento únicamente cuando
    la contabilidad lo demuestra con tres evidencias:

      1. el primer movimiento existe pero perdió importe/saldo;
      2. el segundo movimiento permite reconstruir el saldo que
         quedó después del primero;
      3. al agregar el importe inferido, la suma de movimientos
         coincide con el total del resumen.

    No se aplica a ningún movimiento que ya tenga importe.
    """

    if len(movements) < 2:
        return

    first = movements[0]
    second = movements[1]

    if _movement_has_amount(first):
        return

    try:
        opening_balance = float(
            resumen.saldo_anterior
        )
        second_balance = float(
            second.saldo_operacion
        )
    except (TypeError, ValueError):
        return

    second_delta = _movement_delta(second)

    if (
        second_delta is None
        or abs(second_balance) < 0.005
    ):
        return

    balance_after_first = (
        second_balance - second_delta
    )

    first_delta = (
        balance_after_first
        - opening_balance
    )

    if abs(first_delta) <= 0.005:
        return

    if first_delta < 0.0:
        inferred_amount = abs(first_delta)

        try:
            expected_total = float(
                resumen.retiros_cargos
            )
        except (TypeError, ValueError):
            return

        current_total = sum(
            float(movement.cargo or 0.0)
            for movement in movements
        )

        if abs(
            (
                current_total
                + inferred_amount
            )
            - expected_total
        ) > 0.02:
            return

        first.cargo = round(
            inferred_amount,
            2,
        )
        first.abono = 0.0

    else:
        inferred_amount = first_delta

        try:
            expected_total = float(
                resumen.depositos_abonos
            )
        except (TypeError, ValueError):
            return

        current_total = sum(
            float(movement.abono or 0.0)
            for movement in movements
        )

        if abs(
            (
                current_total
                + inferred_amount
            )
            - expected_total
        ) > 0.02:
            return

        first.abono = round(
            inferred_amount,
            2,
        )
        first.cargo = 0.0

    if (
        first.saldo_operacion is None
        or abs(
            safe_float(
                first.saldo_operacion,
                0.0,
            )
        )
        <= 0.005
    ):
        first.saldo_operacion = round(
            balance_after_first,
            2,
        )


def repair_movimientos(
    movements: List[Movimiento],
    resumen: ResumenFinanciero,
) -> None:
    repair_leading_partial_movement(
        movements,
        resumen,
    )
