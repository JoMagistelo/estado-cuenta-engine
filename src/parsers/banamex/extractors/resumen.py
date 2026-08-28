from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from math import hypot
from typing import Any, Callable, Dict, List, Optional

from models.resumen_financiero import ResumenFinanciero


# ============================================================
# CONFIGURACIÓN ESPACIAL — RESUMEN FINANCIERO BANAMEX
# ============================================================
#
# El extractor conserva las cajas históricas de "MiCuenta" y
# agrega "Cuenta Base Banamex" mediante perfiles de layout.
#
# Cada perfil contiene sus señales de detección y las celdas
# de sus valores. La lógica para validar, elegir y convertir
# candidatos es única y compartida por todos los perfiles.
#
# ============================================================


Box = tuple[float, float, float, float]

PAGE_GENERAL = 1
NA_VALUE = "N/A"

TOLERANCE_X = 6.0
TOLERANCE_Y = 4.0

SUMMARY_LINE_Y_TOLERANCE = 4.0
LABELED_ROW_MAX_VERTICAL_SHIFT = 30.0


@dataclass(frozen=True, slots=True)
class FieldRegion:
    """Página y caja espacial en la que vive un campo."""

    page: int
    box: Box


@dataclass(frozen=True, slots=True)
class ResumenLayout:
    """Perfil espacial de un resumen financiero Banamex."""

    key: str
    markers: tuple[tuple[int, str], ...]
    saldo_promedio: FieldRegion
    dias_periodo: FieldRegion
    saldo_anterior: FieldRegion
    depositos_abonos: FieldRegion
    retiros_cargos: FieldRegion
    saldo_final: FieldRegion


# ============================================================
# LAYOUT HISTÓRICO — MICUENTA
# ============================================================
#
# Se conservan exactamente las cajas originales y sus nombres
# públicos BOX_* para mantener compatibilidad con imports y
# pruebas existentes.
#
# ============================================================


BOX_SALDO_ANTERIOR: Box = (
    260.0,
    335.0,
    476.0,
    497.0,
)

BOX_DEPOSITOS_ABONOS: Box = (
    250.0,
    335.0,
    487.0,
    506.0,
)

BOX_RETIROS_CARGOS: Box = (
    250.0,
    335.0,
    498.0,
    519.0,
)

BOX_SALDO_FINAL: Box = (
    255.0,
    340.0,
    509.0,
    534.0,
)

BOX_SALDO_PROMEDIO: Box = (
    175.0,
    250.0,
    535.0,
    560.0,
)

BOX_DIAS_PERIODO: Box = (
    205.0,
    250.0,
    546.0,
    568.0,
)


LAYOUT_MICUENTA = ResumenLayout(
    key="micuenta",
    markers=(
        (PAGE_GENERAL, "MICUENTA"),
        (PAGE_GENERAL, "MI CUENTA"),
    ),
    saldo_promedio=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_PROMEDIO,
    ),
    dias_periodo=FieldRegion(
        PAGE_GENERAL,
        BOX_DIAS_PERIODO,
    ),
    saldo_anterior=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_ANTERIOR,
    ),
    depositos_abonos=FieldRegion(
        PAGE_GENERAL,
        BOX_DEPOSITOS_ABONOS,
    ),
    retiros_cargos=FieldRegion(
        PAGE_GENERAL,
        BOX_RETIROS_CARGOS,
    ),
    saldo_final=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_FINAL,
    ),
)


# ============================================================
# LAYOUT NUEVO — CUENTA BASE BANAMEX
# ============================================================
#
# Valores observados en página 1:
#
#     Saldo Anterior       y ~= 401.23
#     Depósitos            y ~= 413.14
#     Retiros              y ~= 424.64
#     Saldo Final          y ~= 436.14
#     Saldo Promedio       y ~= 473.34
#     Días Transcurridos   y ~= 484.84
#
# Las cajas separan las filas; las tolerancias globales se
# aplican después para absorber desplazamientos pequeños.
#
# ============================================================


BOX_SALDO_ANTERIOR_CUENTA_BASE: Box = (
    270.0,
    342.0,
    397.0,
    405.0,
)

BOX_DEPOSITOS_ABONOS_CUENTA_BASE: Box = (
    270.0,
    342.0,
    409.0,
    417.0,
)

BOX_RETIROS_CARGOS_CUENTA_BASE: Box = (
    270.0,
    342.0,
    420.5,
    428.5,
)

BOX_SALDO_FINAL_CUENTA_BASE: Box = (
    280.0,
    347.0,
    432.0,
    440.0,
)

BOX_SALDO_PROMEDIO_CUENTA_BASE: Box = (
    180.0,
    250.0,
    464.0,
    482.0,
)

BOX_DIAS_PERIODO_CUENTA_BASE: Box = (
    205.0,
    250.0,
    476.0,
    493.0,
)


LAYOUT_CUENTA_BASE = ResumenLayout(
    key="cuenta_base",
    markers=(
        (
            PAGE_GENERAL,
            "RESUMEN GENERAL CUENTA BASE BANAMEX",
        ),
        (PAGE_GENERAL, "CUENTA BASE BANAMEX"),
    ),
    saldo_promedio=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_PROMEDIO_CUENTA_BASE,
    ),
    dias_periodo=FieldRegion(
        PAGE_GENERAL,
        BOX_DIAS_PERIODO_CUENTA_BASE,
    ),
    saldo_anterior=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_ANTERIOR_CUENTA_BASE,
    ),
    depositos_abonos=FieldRegion(
        PAGE_GENERAL,
        BOX_DEPOSITOS_ABONOS_CUENTA_BASE,
    ),
    retiros_cargos=FieldRegion(
        PAGE_GENERAL,
        BOX_RETIROS_CARGOS_CUENTA_BASE,
    ),
    saldo_final=FieldRegion(
        PAGE_GENERAL,
        BOX_SALDO_FINAL_CUENTA_BASE,
    ),
)


BANAMEX_LAYOUTS = (
    LAYOUT_CUENTA_BASE,
    LAYOUT_MICUENTA,
)

DEFAULT_LAYOUT = LAYOUT_MICUENTA


# ============================================================
# DETECCIÓN DE LAYOUT
# ============================================================


def normalize_text(value: str) -> str:
    """Normaliza texto para comparar señales del layout."""

    normalized = unicodedata.normalize(
        "NFD",
        str(value or ""),
    )

    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )

    normalized = normalized.upper()
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)

    return " ".join(normalized.split())


def _page_texts(
    words: List[Dict[str, Any]],
) -> Dict[int, str]:
    """Reconstruye texto normalizado por página para detección."""

    pages: Dict[int, List[Dict[str, Any]]] = {}

    for word in words:
        page = int(word.get("page", PAGE_GENERAL))
        pages.setdefault(page, []).append(word)

    result: Dict[int, str] = {}

    for page, page_words in pages.items():
        ordered = sorted(
            page_words,
            key=lambda word: (
                word.get("top", 0),
                word.get("x0", 0),
            ),
        )

        result[page] = normalize_text(
            " ".join(
                str(word.get("text", ""))
                for word in ordered
            )
        )

    return result


def detect_resumen_layout(
    words: List[Dict[str, Any]],
) -> ResumenLayout:
    """
    Selecciona el perfil con más señales reconocidas.

    El fallback sigue siendo MiCuenta para que documentos
    históricos sin marcador explícito conserven el resultado
    anterior.
    """

    page_texts = _page_texts(words)

    best_layout = DEFAULT_LAYOUT
    best_score = 0

    for layout in BANAMEX_LAYOUTS:
        score = sum(
            1
            for page, marker in layout.markers
            if normalize_text(marker) in page_texts.get(page, "")
        )

        if score > best_score:
            best_layout = layout
            best_score = score

    return best_layout


def _resolve_layout(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout],
) -> ResumenLayout:
    return layout or detect_resumen_layout(words)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def _expand_box(
    box: Box,
    tolerance_x: float = TOLERANCE_X,
    tolerance_y: float = TOLERANCE_Y,
) -> Box:
    """Expande una caja para absorber variaciones pequeñas."""

    xmin, xmax, ymin, ymax = box

    return (
        xmin - tolerance_x,
        xmax + tolerance_x,
        ymin - tolerance_y,
        ymax + tolerance_y,
    )


def word_inside_box(
    word: Dict[str, Any],
    box: Box,
    page_number: int,
) -> bool:
    """Determina por su centro si una palabra está en la caja."""

    page = int(word.get("page", PAGE_GENERAL))

    if page != page_number:
        return False

    x0 = float(word.get("x0", 0))
    x1 = float(word.get("x1", 0))
    top = float(word.get("top", 0))
    bottom = float(word.get("bottom", 0))

    xmin, xmax, ymin, ymax = _expand_box(box)

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return (
        xmin <= center_x <= xmax
        and ymin <= center_y <= ymax
    )


def words_in_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int = PAGE_GENERAL,
) -> List[Dict[str, Any]]:
    """Devuelve las palabras ordenadas dentro de una región."""

    result = [
        word
        for word in words
        if word_inside_box(
            word=word,
            box=box,
            page_number=page_number,
        )
    ]

    result.sort(
        key=lambda word: (
            word.get("top", 0),
            word.get("x0", 0),
        )
    )

    return result


# ============================================================
# UTILIDADES DE TEXTO Y CONVERSIÓN
# ============================================================


_MONEY_PATTERN = re.compile(
    r"""
    ^
    \(?
    [-+]?
    \$?
    (?:
        \d{1,3}(?:,\d{3})+
        |
        \d+
    )
    (?:\.\d{2})?
    \)?
    -?
    $
    """,
    re.VERBOSE,
)


def is_money_text(text: str) -> bool:
    """Indica si un fragmento representa una cantidad."""

    if not text:
        return False

    return bool(_MONEY_PATTERN.fullmatch(text.strip()))


def is_integer_text(text: str) -> bool:
    """Indica si un fragmento es un entero simple."""

    if not text:
        return False

    return bool(re.fullmatch(r"\d{1,3}", text.strip()))


def _parse_amount(value: Optional[str]) -> Optional[float]:
    """Convierte texto monetario a float de forma segura."""

    if value is None or value == NA_VALUE:
        return None

    cleaned_value = value.strip()
    is_negative = False

    if (
        cleaned_value.startswith("(")
        and cleaned_value.endswith(")")
    ):
        is_negative = True
        cleaned_value = cleaned_value[1:-1]

    if cleaned_value.endswith("-"):
        is_negative = True
        cleaned_value = cleaned_value[:-1]

    cleaned_value = (
        cleaned_value.replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        parsed = float(cleaned_value)
    except (ValueError, TypeError):
        return None

    if is_negative:
        parsed = -abs(parsed)

    return parsed


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Convierte texto entero de forma segura."""

    if value is None or value == NA_VALUE:
        return None

    try:
        return int(float(value.strip()))
    except (ValueError, TypeError):
        return None


def _candidate_distance(
    word: Dict[str, Any],
    target_x: float,
    target_y: float,
) -> float:
    """Distancia del centro de una palabra al centro esperado."""

    x0 = float(word.get("x0", 0))
    x1 = float(word.get("x1", 0))
    top = float(word.get("top", 0))
    bottom = float(word.get("bottom", 0))

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return hypot(
        center_x - target_x,
        center_y - target_y,
    )


def _box_center(box: Box) -> tuple[float, float]:
    """Devuelve el centro geométrico de una caja."""

    xmin, xmax, ymin, ymax = box

    return (
        (xmin + xmax) / 2,
        (ymin + ymax) / 2,
    )


def extract_value_from_box(
    words: List[Dict[str, Any]],
    box: Box,
    validator: Callable[[str], bool],
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """Elige el candidato válido más cercano al centro."""

    selected = words_in_box(
        words=words,
        box=box,
        page_number=page_number,
    )

    candidates = [
        word
        for word in selected
        if validator(str(word.get("text", "")).strip())
    ]

    if not candidates:
        return None

    target_x, target_y = _box_center(box)

    candidates.sort(
        key=lambda word: _candidate_distance(
            word=word,
            target_x=target_x,
            target_y=target_y,
        )
    )

    value = str(candidates[0].get("text", "")).strip()

    return value or None


def extract_money_from_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """Extrae una cantidad monetaria de una región."""

    return extract_value_from_box(
        words=words,
        box=box,
        validator=is_money_text,
        page_number=page_number,
    )


def extract_integer_from_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """Extrae un entero de una región."""

    return extract_value_from_box(
        words=words,
        box=box,
        validator=is_integer_text,
        page_number=page_number,
    )


def _money_from_region(
    words: List[Dict[str, Any]],
    region: FieldRegion,
) -> Optional[float]:
    return _parse_amount(
        extract_money_from_box(
            words=words,
            box=region.box,
            page_number=region.page,
        )
    )


def _integer_from_region(
    words: List[Dict[str, Any]],
    region: FieldRegion,
) -> Optional[int]:
    return _parse_int(
        extract_integer_from_box(
            words=words,
            box=region.box,
            page_number=region.page,
        )
    )


# ============================================================
# FORTALECIMIENTO SEMÁNTICO — RENGLONES DEL RESUMEN
# ============================================================


def _word_center_y(word: Dict[str, Any]) -> float:
    return (
        float(word.get("top", 0))
        + float(word.get("bottom", 0))
    ) / 2


def _money_from_labeled_row(
    words: List[Dict[str, Any]],
    region: FieldRegion,
    label_options: tuple[tuple[str, ...], ...],
) -> Optional[float]:
    """
    Extrae el importe del mismo renglón que su etiqueta.

    La búsqueda mantiene la página, la columna X y una ventana
    vertical cercana a la caja del layout. Así absorbe renglones
    desplazados sin tomar importes de otras tablas.
    """

    xmin, xmax, _, _ = region.box
    target_x, target_y = _box_center(region.box)
    anchor_tokens = {
        option[0]
        for option in label_options
        if option
    }
    page_words = [
        word
        for word in words
        if int(word.get("page", PAGE_GENERAL))
        == region.page
    ]

    for anchor in page_words:
        anchor_text = normalize_text(anchor.get("text", ""))

        if anchor_text not in anchor_tokens:
            continue

        anchor_y = _word_center_y(anchor)

        if (
            abs(anchor_y - target_y)
            > LABELED_ROW_MAX_VERTICAL_SHIFT
        ):
            continue

        line = sorted(
            (
                word
                for word in page_words
                if abs(_word_center_y(word) - anchor_y)
                <= SUMMARY_LINE_Y_TOLERANCE
            ),
            key=lambda word: float(word.get("x0", 0)),
        )

        normalized_line = normalize_text(
            " ".join(
                str(word.get("text", "")).strip()
                for word in line
                if str(word.get("text", "")).strip()
            )
        )
        line_tokens = set(normalized_line.split())

        if not any(
            set(option).issubset(line_tokens)
            for option in label_options
        ):
            continue

        candidates = []

        for word in line:
            text = str(word.get("text", "")).strip()
            x0 = float(word.get("x0", 0))
            x1 = float(word.get("x1", 0))
            center_x = (x0 + x1) / 2

            if (
                xmin - TOLERANCE_X
                <= center_x
                <= xmax + TOLERANCE_X
                and is_money_text(text)
            ):
                candidates.append(word)

        if not candidates:
            continue

        candidates.sort(
            key=lambda word: abs(
                (
                    float(word.get("x0", 0))
                    + float(word.get("x1", 0))
                )
                / 2
                - target_x
            )
        )

        value = _parse_amount(
            str(candidates[0].get("text", "")).strip()
        )

        if value is not None:
            return value

    return None


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_saldo_promedio(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[float]:
    profile = _resolve_layout(words, layout)
    return _money_from_region(words, profile.saldo_promedio)


def extract_dias_periodo(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[int]:
    profile = _resolve_layout(words, layout)
    return _integer_from_region(words, profile.dias_periodo)


def extract_saldo_anterior(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[float]:
    profile = _resolve_layout(words, layout)
    return _money_from_region(words, profile.saldo_anterior)


def extract_depositos_abonos(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[float]:
    profile = _resolve_layout(words, layout)

    anchored_value = _money_from_labeled_row(
        words,
        profile.depositos_abonos,
        (
            ("DEPOSITO",),
            ("DEPOSITOS",),
            ("ABONO",),
            ("ABONOS",),
        ),
    )

    if anchored_value is not None:
        return anchored_value

    return _money_from_region(words, profile.depositos_abonos)


def extract_retiros_cargos(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[float]:
    profile = _resolve_layout(words, layout)

    anchored_value = _money_from_labeled_row(
        words,
        profile.retiros_cargos,
        (
            ("RETIRO",),
            ("RETIROS",),
            ("CARGO",),
            ("CARGOS",),
        ),
    )

    if anchored_value is not None:
        return anchored_value

    return _money_from_region(words, profile.retiros_cargos)


def extract_saldo_final(
    words: List[Dict[str, Any]],
    layout: Optional[ResumenLayout] = None,
) -> Optional[float]:
    profile = _resolve_layout(words, layout)

    anchored_value = _money_from_labeled_row(
        words,
        profile.saldo_final,
        (("SALDO", "AL"),),
    )

    if anchored_value is not None:
        return anchored_value

    return _money_from_region(words, profile.saldo_final)


# ============================================================
# CAMPOS NO DISPONIBLES EN LOS LAYOUTS OBSERVADOS
# ============================================================
#
# Se conserva el contrato público del extractor original. No
# se infieren conceptos que no estén inequívocamente presentes.
#
# ============================================================


def extract_tasa_bruta_anual(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_saldo_promedio_gravable(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_intereses_a_favor(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_isr_retenido(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_cheques_pagados(
    words: List[Dict[str, Any]],
) -> Optional[int]:
    return None


def extract_manejo_cuenta(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_cargos_objetados(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_abonos_objetados(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_saldo_promedio_minimo_mensual(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


def extract_saldo_global(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    return None


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_resumen_financiero_words(
    words: List[Dict[str, Any]],
) -> ResumenFinanciero:
    """
    Extrae el resumen financiero Banamex con selección previa
    del perfil espacial adecuado.

    Layouts soportados:

        - MiCuenta (comportamiento histórico)
        - Cuenta Base Banamex
    """

    layout = detect_resumen_layout(words)

    return ResumenFinanciero(
        saldo_promedio=extract_saldo_promedio(
            words,
            layout,
        ),
        dias_periodo=extract_dias_periodo(
            words,
            layout,
        ),
        tasa_bruta_anual=extract_tasa_bruta_anual(words),
        saldo_promedio_gravable=(
            extract_saldo_promedio_gravable(words)
        ),
        intereses_a_favor=extract_intereses_a_favor(words),
        isr_retenido=extract_isr_retenido(words),
        cheques_pagados=extract_cheques_pagados(words),
        manejo_cuenta=extract_manejo_cuenta(words),
        cargos_objetados=extract_cargos_objetados(words),
        abonos_objetados=extract_abonos_objetados(words),
        saldo_anterior=extract_saldo_anterior(
            words,
            layout,
        ),
        depositos_abonos=extract_depositos_abonos(
            words,
            layout,
        ),
        retiros_cargos=extract_retiros_cargos(
            words,
            layout,
        ),
        saldo_final=extract_saldo_final(
            words,
            layout,
        ),
        saldo_promedio_minimo_mensual=(
            extract_saldo_promedio_minimo_mensual(words)
        ),
        saldo_global=extract_saldo_global(words),
    )
