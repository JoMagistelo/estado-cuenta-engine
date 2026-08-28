from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.datos_cuenta import DatosCuenta


# ============================================================
# CONFIGURACIÓN ESPACIAL — DATOS DE CUENTA BANAMEX
# ============================================================
#
# El extractor conserva el layout histórico "MiCuenta" y
# agrega "Cuenta Base Banamex" mediante perfiles espaciales.
#
# Cada perfil declara:
#
#     - señales textuales para reconocer el layout
#     - página donde vive cada dato
#     - caja/celda espacial de cada dato
#
# Para soportar un layout futuro basta con agregar un nuevo
# perfil. La lógica de extracción no se duplica.
#
# ============================================================


Box = tuple[float, float, float, float]

PAGE_GENERAL = 1
PAGE_CLIENTE = 2

PERIOD_LINE_Y_TOLERANCE = 4.0

_PERIOD_DATE_PATTERN = re.compile(
    r"\b\d{1,2}\s*/\s*(?:\d{1,2}|[A-ZÁÉÍÓÚÜÑ]{3,12})"
    r"\s*/\s*\d{4}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FieldRegion:
    """Página y caja espacial en la que vive un campo."""

    page: int
    box: Box


@dataclass(frozen=True, slots=True)
class DatosCuentaLayout:
    """Perfil espacial completo de un layout Banamex."""

    key: str
    markers: tuple[tuple[int, str], ...]
    producto_principal: FieldRegion
    periodo_inicio: FieldRegion
    periodo_fin: FieldRegion
    fecha_corte: FieldRegion
    numero_cuenta: FieldRegion
    numero_cliente: FieldRegion
    rfc: FieldRegion
    clabe: FieldRegion
    nombre_cliente: FieldRegion


# ============================================================
# LAYOUT HISTÓRICO — MICUENTA
# ============================================================
#
# Estas son exactamente las regiones que ya utilizaba el
# extractor estable. Se conservan también los nombres públicos
# BOX_* para no romper imports o pruebas existentes.
#
# ============================================================


BOX_PRODUCTO_PRINCIPAL: Box = (
    17.0,
    178.0,
    389.0,
    405.0,
)

BOX_NUMERO_CUENTA: Box = (
    178.0,
    249.0,
    389.0,
    405.0,
)

BOX_PERIODO_INICIO: Box = (
    98.0,
    170.0,
    453.0,
    471.0,
)

BOX_PERIODO_FIN: Box = (
    186.0,
    257.0,
    453.0,
    471.0,
)

BOX_FECHA_CORTE: Box = (
    406.0,
    467.0,
    377.0,
    393.0,
)

BOX_NUMERO_CLIENTE: Box = (
    420.0,
    482.0,
    17.0,
    35.0,
)

BOX_NOMBRE_CLIENTE: Box = (
    18.0,
    280.0,
    40.0,
    58.0,
)

BOX_RFC: Box = (
    392.0,
    483.0,
    28.0,
    47.0,
)

BOX_CLABE: Box = (
    133.0,
    250.0,
    400.0,
    417.0,
)


LAYOUT_MICUENTA = DatosCuentaLayout(
    key="micuenta",
    markers=(
        (PAGE_GENERAL, "MICUENTA"),
        (PAGE_GENERAL, "MI CUENTA"),
    ),
    producto_principal=FieldRegion(
        PAGE_GENERAL,
        BOX_PRODUCTO_PRINCIPAL,
    ),
    periodo_inicio=FieldRegion(
        PAGE_GENERAL,
        BOX_PERIODO_INICIO,
    ),
    periodo_fin=FieldRegion(
        PAGE_GENERAL,
        BOX_PERIODO_FIN,
    ),
    fecha_corte=FieldRegion(
        PAGE_GENERAL,
        BOX_FECHA_CORTE,
    ),
    numero_cuenta=FieldRegion(
        PAGE_GENERAL,
        BOX_NUMERO_CUENTA,
    ),
    numero_cliente=FieldRegion(
        PAGE_CLIENTE,
        BOX_NUMERO_CLIENTE,
    ),
    rfc=FieldRegion(
        PAGE_GENERAL,
        BOX_RFC,
    ),
    clabe=FieldRegion(
        PAGE_GENERAL,
        BOX_CLABE,
    ),
    nombre_cliente=FieldRegion(
        PAGE_CLIENTE,
        BOX_NOMBRE_CLIENTE,
    ),
)


# ============================================================
# LAYOUT NUEVO — CUENTA BASE BANAMEX
# ============================================================
#
# En este layout todos los datos se encuentran en página 1.
# Las regiones corresponden a las celdas observadas en
# banamex_cuenta_base_2024_raw_words.json.
#
# ============================================================


BOX_PRODUCTO_PRINCIPAL_CUENTA_BASE: Box = (
    14.0,
    150.0,
    316.0,
    335.0,
)

BOX_NUMERO_CUENTA_CUENTA_BASE: Box = (
    165.0,
    245.0,
    316.0,
    335.0,
)

BOX_PERIODO_INICIO_CUENTA_BASE: Box = (
    140.0,
    215.0,
    369.0,
    387.0,
)

BOX_PERIODO_FIN_CUENTA_BASE: Box = (
    228.0,
    295.0,
    369.0,
    387.0,
)

BOX_FECHA_CORTE_CUENTA_BASE: Box = (
    410.0,
    478.0,
    304.0,
    322.0,
)

BOX_NUMERO_CLIENTE_CUENTA_BASE: Box = (
    420.0,
    482.0,
    18.0,
    36.0,
)

BOX_NOMBRE_CLIENTE_CUENTA_BASE: Box = (
    60.0,
    265.0,
    145.0,
    163.0,
)

BOX_RFC_CUENTA_BASE: Box = (
    389.0,
    480.0,
    30.0,
    48.0,
)

BOX_CLABE_CUENTA_BASE: Box = (
    130.0,
    245.0,
    328.0,
    346.0,
)


LAYOUT_CUENTA_BASE = DatosCuentaLayout(
    key="cuenta_base",
    markers=(
        (
            PAGE_GENERAL,
            "RESUMEN GENERAL CUENTA BASE BANAMEX",
        ),
        (PAGE_GENERAL, "CUENTA BASE BANAMEX"),
    ),
    producto_principal=FieldRegion(
        PAGE_GENERAL,
        BOX_PRODUCTO_PRINCIPAL_CUENTA_BASE,
    ),
    periodo_inicio=FieldRegion(
        PAGE_GENERAL,
        BOX_PERIODO_INICIO_CUENTA_BASE,
    ),
    periodo_fin=FieldRegion(
        PAGE_GENERAL,
        BOX_PERIODO_FIN_CUENTA_BASE,
    ),
    fecha_corte=FieldRegion(
        PAGE_GENERAL,
        BOX_FECHA_CORTE_CUENTA_BASE,
    ),
    numero_cuenta=FieldRegion(
        PAGE_GENERAL,
        BOX_NUMERO_CUENTA_CUENTA_BASE,
    ),
    numero_cliente=FieldRegion(
        PAGE_GENERAL,
        BOX_NUMERO_CLIENTE_CUENTA_BASE,
    ),
    rfc=FieldRegion(
        PAGE_GENERAL,
        BOX_RFC_CUENTA_BASE,
    ),
    clabe=FieldRegion(
        PAGE_GENERAL,
        BOX_CLABE_CUENTA_BASE,
    ),
    nombre_cliente=FieldRegion(
        PAGE_GENERAL,
        BOX_NOMBRE_CLIENTE_CUENTA_BASE,
    ),
)


# Los perfiles específicos se evalúan primero. Si ningún
# marcador conocido aparece, el fallback sigue siendo el
# layout histórico para preservar el comportamiento anterior.
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


def detect_datos_cuenta_layout(
    words: List[Dict[str, Any]],
) -> DatosCuentaLayout:
    """
    Selecciona el perfil con mayor cantidad de señales.

    Si el documento no contiene una señal conocida, conserva
    el perfil histórico como fallback compatible.
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
    layout: Optional[DatosCuentaLayout],
) -> DatosCuentaLayout:
    return layout or detect_datos_cuenta_layout(words)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


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

    xmin, xmax, ymin, ymax = box

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return (
        xmin <= center_x <= xmax
        and ymin <= center_y <= ymax
    )


def words_in_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int,
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
            word.get("page", page_number),
            word.get("top", 0),
            word.get("x0", 0),
        )
    )

    return result


def text_from_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int,
) -> Optional[str]:
    """Concatena el texto existente dentro de una caja."""

    selected = words_in_box(
        words=words,
        box=box,
        page_number=page_number,
    )

    values = [
        str(word.get("text", "")).strip()
        for word in selected
        if str(word.get("text", "")).strip()
    ]

    if not values:
        return None

    return " ".join(values).strip()


def numeric_text_from_box(
    words: List[Dict[str, Any]],
    box: Box,
    page_number: int,
) -> Optional[str]:
    """Concatena únicamente fragmentos completamente numéricos."""

    selected = words_in_box(
        words=words,
        box=box,
        page_number=page_number,
    )

    parts = [
        str(word.get("text", "")).strip()
        for word in selected
        if str(word.get("text", "")).strip().isdigit()
    ]

    if not parts:
        return None

    return "".join(parts)


def _text_from_region(
    words: List[Dict[str, Any]],
    region: FieldRegion,
) -> Optional[str]:
    return text_from_box(
        words=words,
        box=region.box,
        page_number=region.page,
    )


def _numeric_text_from_region(
    words: List[Dict[str, Any]],
    region: FieldRegion,
) -> Optional[str]:
    return numeric_text_from_box(
        words=words,
        box=region.box,
        page_number=region.page,
    )


# ============================================================
# FORTALECIMIENTO SEMÁNTICO — PERIODO
# ============================================================


def _is_complete_period_date(value: Optional[str]) -> bool:
    """Valida que una caja haya devuelto únicamente una fecha."""

    if value is None:
        return False

    return bool(_PERIOD_DATE_PATTERN.fullmatch(value.strip()))


def _word_center_y(word: Dict[str, Any]) -> float:
    return (
        float(word.get("top", 0))
        + float(word.get("bottom", 0))
    ) / 2


def _extract_period_dates_from_anchor(
    words: List[Dict[str, Any]],
    page_number: int,
) -> tuple[Optional[str], Optional[str]]:
    """
    Busca el renglón ``RESUMEN DEL <fecha> AL <fecha>``.

    Esta ruta sólo se usa cuando la caja histórica no contiene
    una fecha completa, por lo que el comportamiento estable se
    conserva para los layouts que ya coinciden con sus cajas.
    """

    page_words = [
        word
        for word in words
        if int(word.get("page", PAGE_GENERAL))
        == page_number
    ]

    for anchor in page_words:
        if normalize_text(anchor.get("text", "")) != "RESUMEN":
            continue

        anchor_y = _word_center_y(anchor)
        line = sorted(
            (
                word
                for word in page_words
                if abs(_word_center_y(word) - anchor_y)
                <= PERIOD_LINE_Y_TOLERANCE
            ),
            key=lambda word: float(word.get("x0", 0)),
        )
        line_text = " ".join(
            str(word.get("text", "")).strip()
            for word in line
            if str(word.get("text", "")).strip()
        )
        normalized_line = normalize_text(line_text)
        line_tokens = set(normalized_line.split())

        if not {"RESUMEN", "DEL", "AL"}.issubset(
            line_tokens
        ):
            continue

        dates = [
            re.sub(r"\s*/\s*", "/", match.group(0))
            for match in _PERIOD_DATE_PATTERN.finditer(
                line_text
            )
        ]

        if len(dates) >= 2:
            return dates[0], dates[1]

    return None, None


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_producto_principal(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    return _text_from_region(words, profile.producto_principal)


def extract_periodo_inicio(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    value = _text_from_region(words, profile.periodo_inicio)

    if _is_complete_period_date(value):
        return value

    periodo_inicio, _ = _extract_period_dates_from_anchor(
        words,
        profile.periodo_inicio.page,
    )

    return periodo_inicio


def extract_periodo_fin(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    value = _text_from_region(words, profile.periodo_fin)

    if _is_complete_period_date(value):
        return value

    _, periodo_fin = _extract_period_dates_from_anchor(
        words,
        profile.periodo_fin.page,
    )

    return periodo_fin


def extract_fecha_corte(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    return _text_from_region(words, profile.fecha_corte)


def extract_numero_cuenta(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    return _text_from_region(words, profile.numero_cuenta)


def extract_numero_cliente(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    return _text_from_region(words, profile.numero_cliente)


def extract_rfc(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    value = _text_from_region(words, profile.rfc)

    if value is None:
        return None

    return value.replace(" ", "")


def extract_clabe(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    value = _numeric_text_from_region(words, profile.clabe)

    if value is None or len(value) != 18:
        return None

    return value


def extract_nombre_cliente(
    words: List[Dict[str, Any]],
    layout: Optional[DatosCuentaLayout] = None,
) -> Optional[str]:
    profile = _resolve_layout(words, layout)
    return _text_from_region(words, profile.nombre_cliente)


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_datos_cuenta_words(
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extrae los datos generales Banamex con selección previa
    del perfil espacial adecuado.

    Layouts soportados:

        - MiCuenta (comportamiento histórico)
        - Cuenta Base Banamex
    """

    layout = detect_datos_cuenta_layout(words)

    return DatosCuenta(
        producto_principal=extract_producto_principal(
            words,
            layout,
        ),
        periodo_inicio=extract_periodo_inicio(
            words,
            layout,
        ),
        periodo_fin=extract_periodo_fin(
            words,
            layout,
        ),
        fecha_corte=extract_fecha_corte(
            words,
            layout,
        ),
        numero_cuenta=extract_numero_cuenta(
            words,
            layout,
        ),
        numero_cliente=extract_numero_cliente(
            words,
            layout,
        ),
        rfc=extract_rfc(
            words,
            layout,
        ),
        clabe=extract_clabe(
            words,
            layout,
        ),
        nombre_cliente=extract_nombre_cliente(
            words,
            layout,
        ),
    )
