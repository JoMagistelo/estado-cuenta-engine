from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.resumen_financiero import ResumenFinanciero

from .movimientos import (
    SpatialLine,
    compact_text,
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


@dataclass(frozen=True, slots=True)
class SummaryTableGeometry:
    """Geometría de la tabla impresa ``Resumen de Saldos``."""

    width: float
    title_y: Optional[float]
    label_right: float
    amount_left: float
    amount_right: float
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class SummaryPageContext:
    """Página física donde realmente se encuentra el resumen bancario."""

    page: Optional[int]
    words: List[SpatialWord]
    lines: List[SpatialLine]
    geometry: SummaryTableGeometry


# Las primeras siete filas del cuadro son regulares y conservan el mismo orden.
# Esta secuencia se usa únicamente para localizar una fila cuyo rótulo haya sido
# omitido por OCR. Nunca se usa para calcular o reconstruir un importe.
_CORE_ROW_RULES: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("saldo_anterior", ("SALDO", "INICIAL"), ("FINAL",)),
    ("depositos_abonos", ("DEPOSIT",), ()),
    ("intereses_a_favor", ("INTERES", "RECIB"), ()),
    ("retiros_cargos", ("RETIRO",), ()),
    ("manejo_cuenta", ("COMISION", "COBR"), ()),
    ("impuestos", ("IMPUEST",), ()),
    ("saldo_final", ("SALDO", "FINAL", "CUENTA"), ("INVERSION",)),
)

_SUPPLEMENTAL_ROW_RULES: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("SDO", "PROM", "CTA"), ("MIN", "REQUERIDO")),
    (("SDO", "PROM", "MIN", "REQUERIDO"), ()),
    (("SALDO", "FINAL", "CUENTA", "INVERSION"), ()),
)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def _page_words(
    words: Sequence[SpatialWord],
    page: int,
) -> List[SpatialWord]:
    return [word for word in words if safe_page(word) == page]


def _document_width(words: Sequence[SpatialWord]) -> float:
    max_x = max((safe_float(word.get("x1")) for word in words), default=592.0)
    return max(612.0, max_x + 18.0)


def _label_signature(value: Any) -> str:
    """Normaliza rótulos para tolerar errores OCR leves sin tocar importes."""

    compact = compact_text(value)
    return compact.translate(str.maketrans({"0": "O", "1": "I", "5": "S"}))


def _summary_label_text(
    line: SpatialLine,
    geometry: SummaryTableGeometry,
) -> str:
    parts = [
        normalize_text(word.get("text", ""))
        for word in line.words
        if word_center_x(word) <= geometry.label_right
    ]
    return " ".join(part for part in parts if part).strip()


def _matches_stems(
    value: Any,
    stems: Sequence[str],
    excludes: Sequence[str] = (),
) -> bool:
    signature = _label_signature(value)
    return (
        all(stem in signature for stem in stems)
        and not any(stem in signature for stem in excludes)
    )


def _summary_title_line(
    lines: Sequence[SpatialLine],
    width: float,
) -> Optional[SpatialLine]:
    # El título vive en la mitad izquierda. Restringir X impide confundirlo con
    # textos de la gráfica de comportamiento situada a la derecha.
    label_right = width * 0.32

    for line in lines:
        text = " ".join(
            normalize_text(word.get("text", ""))
            for word in line.words
            if word_center_x(word) <= label_right
        )
        signature = _label_signature(text)
        if "RESUMEN" in signature and "SALDO" in signature:
            return line

    return None


def _summary_geometry(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
) -> SummaryTableGeometry:
    # El ancho se calcula sólo con la página candidata. Una portada o publicidad
    # con dimensiones distintas no puede desplazar las columnas del resumen.
    width = _document_width(words)
    title = _summary_title_line(lines, width)
    title_y = title.center_y if title is not None else None

    # Coordenadas relativas al ancho para soportar PDF digital y OCR con escala
    # distinta. En los layouts observados, los rótulos terminan antes de 30% y
    # la columna de importes ocupa aproximadamente 30%-41% de la página.
    label_right = width * 0.305
    amount_left = width * 0.305
    amount_right = width * 0.415

    if title_y is None:
        top = 0.0
        bottom = float("inf")
    else:
        top = title_y + max(4.0, width * 0.006)
        bottom = title_y + width * 0.35

    return SummaryTableGeometry(
        width=width,
        title_y=title_y,
        label_right=label_right,
        amount_left=amount_left,
        amount_right=amount_right,
        top=top,
        bottom=bottom,
    )


def _row_lines(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
) -> List[SpatialLine]:
    return [
        line
        for line in lines
        if geometry.top <= line.center_y <= geometry.bottom
    ]


def _find_labeled_row_y(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
    stems: Sequence[str],
    excludes: Sequence[str] = (),
) -> Optional[float]:
    for line in _row_lines(lines, geometry):
        label = _summary_label_text(line, geometry)
        if _matches_stems(label, stems, excludes):
            return line.center_y
    return None


def _money_text_value(value: Any) -> Optional[float]:
    """Interpreta únicamente texto monetario explícito de la tabla.

    Tesseract puede perder el punto decimal después del separador de miles
    (``$47,90456`` -> ``$47,904.56``). Esa forma es recuperable porque conserva
    tres dígitos de miles y dos de centavos. Casos ambiguos como ``$15,1604``
    se rechazan: completar un dígito ausente sería estimar un importe.
    """

    text = normalize_text(value)
    if not text or not re.search(r"\d", text):
        return None

    normalized = (
        text
        .replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace(" ", "")
    )
    numeric = re.sub(r"[^0-9.,]", "", normalized)

    if numeric.count(",") == 1 and "." not in numeric:
        left, right = numeric.split(",", 1)
        if 1 <= len(left) <= 3 and len(right) == 5:
            digits = f"{left}{right}"
            amount = float(f"{digits[:-2]}.{digits[-2:]}")
            negative = (
                normalized.startswith("-")
                or normalized.endswith("-")
                or ("(" in normalized and ")" in normalized)
            )
            return round(-amount if negative else amount, 2)

        if 1 <= len(left) <= 3 and len(right) in {3, 4}:
            # ``12,345`` podría ser entero con separador de miles; ``15,1604``
            # además puede representar un token mutilado. Ninguno permite saber
            # con certeza los centavos impresos.
            return None

    if not is_money_text(text):
        return None
    return parse_money(text)


def _money_candidates(
    words: Sequence[SpatialWord],
    anchor_y: float,
    x_min: float,
    x_max: float,
    y_tolerance: float,
) -> List[Tuple[float, float, float]]:
    """Obtiene importes impresos cerca de una fila, sin derivar valores.

    Además del token individual se prueban secuencias cortas de tokens de la
    misma línea. Esto cubre OCR que separa ``$``/signo/número, pero el importe
    sigue procediendo literalmente de las words de la tabla.
    """

    nearby = [
        word
        for word in words
        if x_min <= word_center_x(word) <= x_max
        and abs(word_center_y(word) - anchor_y) <= y_tolerance
    ]
    nearby.sort(key=lambda word: (word_center_y(word), safe_float(word.get("x0"))))

    raw_candidates: List[Tuple[float, float, float]] = []

    for word in nearby:
        value = _money_text_value(word.get("text", ""))
        if value is None:
            continue
        raw_candidates.append(
            (abs(word_center_y(word) - anchor_y), word_center_x(word), value)
        )

    # Agrupa sólo tokens realmente alineados y próximos horizontalmente.
    max_y_delta = max(2.5, min(5.0, y_tolerance * 0.55))
    max_gap = max(5.0, (x_max - x_min) * 0.13)

    for start in range(len(nearby)):
        sequence = [nearby[start]]
        for end in range(start + 1, min(len(nearby), start + 4)):
            previous = sequence[-1]
            current = nearby[end]
            if abs(word_center_y(current) - word_center_y(previous)) > max_y_delta:
                break
            gap = safe_float(current.get("x0")) - safe_float(previous.get("x1"))
            if gap > max_gap:
                break
            sequence.append(current)
            joined = "".join(normalize_text(item.get("text", "")) for item in sequence)
            value = _money_text_value(joined)
            if value is None:
                continue
            center_y = sum(word_center_y(item) for item in sequence) / len(sequence)
            center_x = (
                safe_float(sequence[0].get("x0"))
                + safe_float(sequence[-1].get("x1"))
            ) / 2.0
            raw_candidates.append((abs(center_y - anchor_y), center_x, value))

    # Deduplicación estable; prioriza la coincidencia vertical más cercana.
    seen: set[Tuple[float, float]] = set()
    result: List[Tuple[float, float, float]] = []
    for item in sorted(raw_candidates, key=lambda candidate: (candidate[0], candidate[1])):
        key = (round(item[1], 2), round(item[2], 2))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _core_row_anchors(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
) -> Dict[int, float]:
    anchors: Dict[int, float] = {}

    for index, (_, stems, excludes) in enumerate(_CORE_ROW_RULES):
        y = _find_labeled_row_y(lines, geometry, stems, excludes)
        if y is not None:
            anchors[index] = y

    return anchors


def _core_row_grid(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
) -> Tuple[Optional[float], Optional[float]]:
    """Estima sólo la posición Y de las filas regulares del resumen.

    La geometría puede estimarse porque las filas conservan su orden; los
    importes jamás se calculan. Si OCR pierde el rótulo ``Depósitos`` pero sí
    conserva su monto en la columna de importes, esta cuadrícula permite ubicar
    ese monto sin recurrir a movimientos ni a ecuaciones financieras.
    """

    anchors = _core_row_anchors(lines, geometry)
    default_step = geometry.width * 0.029

    slopes: List[float] = []
    indexes = sorted(anchors)
    for left_pos, left_index in enumerate(indexes):
        for right_index in indexes[left_pos + 1 :]:
            distance = right_index - left_index
            if distance <= 0:
                continue
            slope = (anchors[right_index] - anchors[left_index]) / distance
            if geometry.width * 0.015 <= slope <= geometry.width * 0.05:
                slopes.append(slope)

    if slopes:
        step = statistics.median(slopes)
    else:
        step = default_step

    if anchors:
        first_y = statistics.median(
            anchors[index] - (index * step)
            for index in indexes
        )
    elif geometry.title_y is not None:
        first_y = geometry.title_y + geometry.width * 0.025
    else:
        return None, None

    return first_y, step


def _supplemental_anchor_count(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
) -> int:
    count = 0
    for stems, excludes in _SUPPLEMENTAL_ROW_RULES:
        if _find_labeled_row_y(lines, geometry, stems, excludes) is not None:
            count += 1
    return count


def _statement_header_anchor_count(lines: Sequence[SpatialLine]) -> int:
    signature = " ".join(_label_signature(line.text) for line in lines)
    return sum(
        marker in signature
        for marker in (
            "FECHADECORTE",
            "PERIODO",
            "CLABE",
        )
    )


def _summary_page_context(words: Sequence[SpatialWord]) -> SummaryPageContext:
    """Localiza la página real del resumen sin asumir que sea la primera.

    Scotiabank puede anteponer páginas publicitarias, de seguridad o avisos. La
    selección exige evidencia estructural del ``Resumen de Saldos``: título,
    filas financieras y, como apoyo, anclas del encabezado del estado de cuenta.
    Una portada que mencione palabras como "saldo" o incluso "resumen" no es
    suficiente por sí sola.

    La función sólo decide *dónde* leer. No calcula ningún importe.
    """

    if not words:
        geometry = _summary_geometry([], [])
        return SummaryPageContext(None, [], [], geometry)

    all_lines = group_words_into_lines(words)
    pages = sorted({safe_page(word) for word in words if safe_page(word) > 0})

    candidates: List[
        Tuple[int, int, int, List[SpatialWord], List[SpatialLine], SummaryTableGeometry]
    ] = []

    for page in pages:
        page_words = _page_words(words, page)
        page_lines = [line for line in all_lines if line.page == page]
        geometry = _summary_geometry(page_words, page_lines)

        has_title = geometry.title_y is not None
        core_count = len(_core_row_anchors(page_lines, geometry))
        supplemental_count = _supplemental_anchor_count(page_lines, geometry)
        header_count = _statement_header_anchor_count(page_lines)

        qualifies = (
            (has_title and core_count >= 2)
            or (has_title and core_count >= 1 and (supplemental_count >= 1 or header_count >= 2))
            or core_count >= 4
            or (core_count >= 3 and supplemental_count >= 1)
        )
        if not qualifies:
            continue

        score = (
            (20 if has_title else 0)
            + (core_count * 4)
            + (supplemental_count * 2)
            + header_count
        )
        # Se conserva la página más temprana únicamente como desempate. La
        # evidencia estructural pesa antes que la posición física del PDF.
        candidates.append(
            (
                score,
                -page,
                page,
                page_words,
                page_lines,
                geometry,
            )
        )

    if candidates:
        _, _, page, page_words, page_lines, geometry = max(
            candidates,
            key=lambda item: (item[0], item[1]),
        )
        return SummaryPageContext(page, page_words, page_lines, geometry)

    # Compatibilidad conservadora para documentos realmente monopágina: no hay
    # otra portada que descartar. En documentos multipágina, si no existe
    # evidencia suficiente, es preferible devolver ausencia que leer publicidad.
    if len(pages) == 1:
        page = pages[0]
        page_words = _page_words(words, page)
        page_lines = [line for line in all_lines if line.page == page]
        geometry = _summary_geometry(page_words, page_lines)
        return SummaryPageContext(page, page_words, page_lines, geometry)

    geometry = _summary_geometry([], [])
    return SummaryPageContext(None, [], [], geometry)


def _money_from_summary_row(
    words: Sequence[SpatialWord],
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
    stems: Sequence[str],
    excludes: Sequence[str] = (),
    *,
    core_index: Optional[int] = None,
    y_tolerance: Optional[float] = None,
) -> Optional[float]:
    direct_y = _find_labeled_row_y(lines, geometry, stems, excludes)
    first_y, step = _core_row_grid(lines, geometry)

    tolerance = y_tolerance
    if tolerance is None:
        reference_step = step or geometry.width * 0.029
        tolerance = max(5.0, min(11.0, reference_step * 0.48))

    candidate_ys: List[float] = []
    if direct_y is not None:
        candidate_ys.append(direct_y)
    if core_index is not None and first_y is not None and step is not None:
        predicted_y = first_y + (core_index * step)
        if not candidate_ys or abs(predicted_y - candidate_ys[0]) > 1.0:
            candidate_ys.append(predicted_y)

    for anchor_y in candidate_ys:
        candidates = _money_candidates(
            words,
            anchor_y,
            geometry.amount_left,
            geometry.amount_right,
            tolerance,
        )
        if candidates:
            return candidates[0][2]

    return None


def _period_days(
    summary_words: Sequence[SpatialWord],
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

    if not summary_words:
        return 0

    # ``extract_statement_period`` es compartido con movimientos y conserva la
    # convención histórica de leer la página lógica 1. Le entregamos únicamente
    # la página del resumen, remapeada en copias, para no reintroducir una
    # dependencia respecto de la página física del PDF.
    logical_page_words = [dict(word, page=1) for word in summary_words]
    start, end = extract_statement_period(logical_page_words)
    if start is not None and end is not None and end >= start:
        return (end - start).days + 1

    return 0


def _annual_rate(
    lines: Sequence[SpatialLine],
    geometry: SummaryTableGeometry,
) -> float:
    # Prioridad: tasa impresa en la fila de intereses del Resumen de Saldos.
    for line in lines:
        label = _summary_label_text(line, geometry)
        if not _matches_stems(label, ("INTERES", "RECIB")):
            continue
        for word in line.words:
            text = normalize_text(word.get("text", ""))
            if "%" not in text:
                continue
            value = parse_money(text.replace("%", ""))
            if value is not None:
                return value

    # Algunos layouts imprimen la tasa sólo en la tabla de sobregiro de la misma
    # página del resumen. Sigue siendo una fuente textual explícita; no se deriva.
    for line in lines:
        signature = _label_signature(line.text)
        if not all(stem in signature for stem in ("TASA", "INTERES", "ORDINARIA")):
            continue
        for word in line.words:
            text = normalize_text(word.get("text", ""))
            if "%" not in text:
                continue
            value = parse_money(text.replace("%", ""))
            if value is not None:
                return value

    return 0.0


def _amount_or_zero(value: Optional[float], default: float = 0.0) -> float:
    return round(value if value is not None else default, 2)


# ============================================================
# CONSTRUCCIÓN DEL RESUMEN DESDE SU FUENTE IMPRESA
# ============================================================


def _build_summary_values(words: List[SpatialWord]) -> SummaryValues:
    """Extrae el resumen desde la página que contiene su tabla impresa.

    La página física se localiza por evidencia semántica y estructural, por lo
    que pueden existir portadas, publicidad o avisos antes del estado de cuenta.
    Los movimientos no participan como fuente alternativa y ningún saldo o total
    se reconstruye mediante ecuaciones. Si el OCR omite un importe, el campo
    queda en su valor por defecto para revelar la ausencia, no para estimarla.
    """

    context = _summary_page_context(words)
    summary_words = context.words
    summary_lines = context.lines
    geometry = context.geometry

    initial_balance = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("SALDO", "INICIAL"),
        ("FINAL",),
        core_index=0,
    )
    deposits = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("DEPOSIT",),
        core_index=1,
    )
    interest = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("INTERES", "RECIB"),
        core_index=2,
    )
    withdrawals = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("RETIRO",),
        core_index=3,
    )
    commissions = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("COMISION", "COBR"),
        core_index=4,
    )
    final_balance = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("SALDO", "FINAL", "CUENTA"),
        ("INVERSION",),
        core_index=6,
    )

    average_balance = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("SDO", "PROM", "CTA"),
        ("MIN", "REQUERIDO"),
        y_tolerance=12.0,
    )
    minimum_average = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("SDO", "PROM", "MIN", "REQUERIDO"),
        y_tolerance=10.0,
    )
    explicit_isr = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("ISR",),
        y_tolerance=10.0,
    )
    global_balance = _money_from_summary_row(
        summary_words,
        summary_lines,
        geometry,
        ("SALDO", "FINAL", "CUENTA", "INVERSION"),
        y_tolerance=10.0,
    )

    return SummaryValues(
        saldo_promedio=_amount_or_zero(average_balance),
        dias_periodo=_period_days(summary_words, summary_lines),
        tasa_bruta_anual=_annual_rate(summary_lines, geometry),
        saldo_promedio_gravable=0.0,
        intereses_a_favor=_amount_or_zero(interest),
        isr_retenido=_amount_or_zero(explicit_isr),
        cheques_pagados=0,
        manejo_cuenta=_amount_or_zero(commissions),
        cargos_objetados=0.0,
        abonos_objetados=0.0,
        saldo_anterior=_amount_or_zero(initial_balance),
        depositos_abonos=_amount_or_zero(deposits),
        retiros_cargos=_amount_or_zero(withdrawals),
        saldo_final=_amount_or_zero(final_balance),
        saldo_promedio_minimo_mensual=_amount_or_zero(minimum_average),
        saldo_global=_amount_or_zero(global_balance),
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
    """Extrae el resumen financiero Scotiabank desde sus words impresas.

    La fuente de verdad es la tabla ``Resumen de Saldos`` donde aparezca dentro
    del estado de cuenta, aunque existan páginas preliminares. No se suman
    cargos/abonos de movimientos y no se recalculan saldos para completar datos
    que el motor de lectura no haya entregado.
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
