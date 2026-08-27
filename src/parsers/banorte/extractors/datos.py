from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import re
import unicodedata

from models.datos_cuenta import DatosCuenta


# ============================================================
# EXTRACTOR HÍBRIDO — DATOS DE CUENTA BANORTE
# ============================================================
#
# Estrategia:
#
#   1. Localización dinámica de la página de datos.
#   2. Extracción ESPACIAL como método principal.
#   3. Fallback SEMÁNTICO para OCR / coordenadas desplazadas.
#
# El extractor original estaba diseñado para:
#
#     page = 1
#
# Ahora puede localizar los datos en páginas posteriores.
#
# Además, cuando el OCR modifica ligeramente:
#
#     x
#     y
#     ancho
#     separación
#
# se intenta localizar el campo mediante su etiqueta y utilizar
# esa posición como referencia espacial.
#
# ============================================================


# ============================================================
# CONFIGURACIÓN DE PÁGINAS
# ============================================================

# Mantener esta constante por compatibilidad con código externo
# que pudiera importarla.

PAGE_DATOS = 1


# ============================================================
# TOLERANCIAS ESPACIALES
# ============================================================

SPATIAL_TOLERANCE_X = 1.5
SPATIAL_TOLERANCE_Y = 1.5


# ============================================================
# TOLERANCIA PARA FALLBACK OCR
# ============================================================
#
# El OCR puede introducir desplazamientos mayores que un PDF
# digital. Estas tolerancias solo se utilizan cuando se hace
# localización semántica.
#
# ============================================================

OCR_X_TOLERANCE = 8.0
OCR_Y_TOLERANCE = 8.0

OCR_FIELD_X_EXPANSION = 45.0
OCR_FIELD_Y_EXPANSION = 8.0


# ============================================================
# TOLERANCIA PARA AGRUPAR PALABRAS DEL MISMO RENGLÓN
# ============================================================

ROW_TOP_TOLERANCE = 1.5

OCR_ROW_TOP_TOLERANCE = 4.0


# ============================================================
# PRODUCTO PRINCIPAL
# ============================================================

BOX_PRODUCTO_PRINCIPAL = (
    49.0,
    160.0,
    217.5,
    233.0,
)


# ============================================================
# NÚMERO DE CUENTA
# ============================================================

BOX_NUMERO_CUENTA = (
    211.0,
    256.0,
    217.5,
    233.0,
)


# ============================================================
# NÚMERO DE CLIENTE
# ============================================================

BOX_NUMERO_CLIENTE = (
    95.1,
    122.9,
    137.0,
    140.0,
)


# ============================================================
# RFC
# ============================================================

BOX_RFC = (
    63.7,
    112.3,
    146.0,
    156.0,
)


# ============================================================
# NOMBRE DEL CLIENTE
# ============================================================

BOX_NOMBRE_CLIENTE = (
    47.0,
    230.0,
    59.0,
    69.5,
)


# ============================================================
# PERIODO — INICIO
# ============================================================

BOX_PERIODO_INICIO = (
    420.0,
    472.0,
    102.5,
    117.5,
)


# ============================================================
# PERIODO — FIN
# ============================================================

BOX_PERIODO_FIN = (
    473.0,
    525.0,
    102.5,
    117.5,
)


# ============================================================
# FECHA DE CORTE
# ============================================================

BOX_FECHA_CORTE = (
    393.0,
    457.0,
    117.0,
    127.0,
)


# ============================================================
# CLABE
# ============================================================

BOX_CLABE = (
    281.0,
    354.5,
    217.5,
    233.0,
)


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte un valor espacial a float de forma segura.
    """

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_int(
    value: Any,
    default: int = 1,
) -> int:
    """
    Convierte una página a entero de forma segura.
    """

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _normalize_text(
    value: Optional[str],
) -> Optional[str]:
    """
    Normaliza espacios sin modificar el contenido semántico.
    """

    if value is None:
        return None

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value or None


def _normalize_search_text(
    value: Any,
) -> str:
    """
    Normalización utilizada para búsqueda semántica.

    Elimina diferencias de acentuación para tolerar OCR como:

        INFORMACIÓN
        INFORMACION

        NÚMERO
        NUMERO

        PERÍODO
        PERIODO
    """

    text = str(value or "")

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.upper()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _normalize_compact_text(
    value: Any,
) -> str:
    """
    Normalización semántica compacta.

    Ejemplo:

        "Número de cliente"

    ->

        "NUMERODECLIENTE"
    """

    return re.sub(
        r"[^A-Z0-9]",
        "",
        _normalize_search_text(value),
    )


# ============================================================
# INFORMACIÓN ESPACIAL DE WORD
# ============================================================

def _word_page(
    word: Dict[str, Any],
) -> int:
    return _safe_int(
        word.get(
            "page",
            1,
        ),
        1,
    )


def _word_top(
    word: Dict[str, Any],
) -> float:
    return _safe_float(
        word.get(
            "top",
            0,
        )
    )


def _word_bottom(
    word: Dict[str, Any],
) -> float:
    return _safe_float(
        word.get(
            "bottom",
            word.get(
                "top",
                0,
            ),
        )
    )


def _word_center_y(
    word: Dict[str, Any],
) -> float:
    return (
        _word_top(word)
        + _word_bottom(word)
    ) / 2.0


def _word_x0(
    word: Dict[str, Any],
) -> float:
    return _safe_float(
        word.get(
            "x0",
            0,
        )
    )


def _word_x1(
    word: Dict[str, Any],
) -> float:
    return _safe_float(
        word.get(
            "x1",
            word.get(
                "x0",
                0,
            ),
        )
    )


def _word_width(
    word: Dict[str, Any],
) -> float:
    return max(
        0.0,
        _word_x1(word)
        - _word_x0(word),
    )


def _word_height(
    word: Dict[str, Any],
) -> float:
    return max(
        0.0,
        _word_bottom(word)
        - _word_top(word),
    )


# ============================================================
# INFORMACIÓN DE LÍNEA
# ============================================================

def _line_text(
    line: List[Dict[str, Any]],
) -> str:
    values: List[str] = []

    for word in sorted(
        line,
        key=_word_x0,
    ):

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if text:
            values.append(text)

    return " ".join(values).strip()


def _line_page(
    line: List[Dict[str, Any]],
) -> int:

    if not line:
        return 1

    return _word_page(
        line[0]
    )


def _line_top(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return min(
        _word_top(word)
        for word in line
    )


def _line_bottom(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return max(
        _word_bottom(word)
        for word in line
    )


def _line_center_y(
    line: List[Dict[str, Any]],
) -> float:

    return (
        _line_top(line)
        + _line_bottom(line)
    ) / 2.0


def _line_x0(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return min(
        _word_x0(word)
        for word in line
    )


def _line_x1(
    line: List[Dict[str, Any]],
) -> float:

    if not line:
        return 0.0

    return max(
        _word_x1(word)
        for word in line
    )


# ============================================================
# AGRUPACIÓN DE WORDS EN LÍNEAS
# ============================================================

def _group_words_into_lines(
    words: List[Dict[str, Any]],
    tolerance: float = OCR_ROW_TOP_TOLERANCE,
) -> List[List[Dict[str, Any]]]:

    if not words:
        return []

    ordered = sorted(
        words,
        key=lambda word: (
            _word_page(word),
            _word_center_y(word),
            _word_x0(word),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []

    current: List[Dict[str, Any]] = []
    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:

        page = _word_page(word)
        y = _word_center_y(word)

        if current_y is None:
            current = [word]
            current_page = page
            current_y = y
            continue

        same_line = (
            page == current_page
            and abs(
                y - current_y
            ) <= tolerance
        )

        if same_line:

            current.append(word)

            current_y = (
                sum(
                    _word_center_y(item)
                    for item in current
                )
                / len(current)
            )

        else:

            current.sort(
                key=_word_x0
            )

            lines.append(
                current
            )

            current = [word]
            current_page = page
            current_y = y

    if current:

        current.sort(
            key=_word_x0
        )

        lines.append(
            current
        )

    return lines


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================

def word_inside_box(
    word: Dict[str, Any],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> bool:
    """
    Determina si una palabra pertenece a una caja espacial.

    X:
        solapamiento horizontal.

    Y:
        posición TOP.

    Se mantiene la lógica original para PDF digital.
    """

    if _word_page(word) != page_number:
        return False

    x0 = _word_x0(word)
    x1 = _word_x1(word)
    top = _word_top(word)

    xmin, xmax, ymin, ymax = box

    xmin -= tolerance_x
    xmax += tolerance_x

    ymin -= tolerance_y
    ymax += tolerance_y

    horizontal_overlap = (
        min(
            x1,
            xmax,
        )
        - max(
            x0,
            xmin,
        )
    )

    if horizontal_overlap <= 0:
        return False

    if top < ymin:
        return False

    if top > ymax:
        return False

    return True


def words_in_box(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> List[Dict[str, Any]]:

    result = [
        word
        for word in words
        if word_inside_box(
            word,
            box,
            page_number,
            tolerance_x=tolerance_x,
            tolerance_y=tolerance_y,
        )
    ]

    result.sort(
        key=lambda word: (
            _word_page(word),
            _word_top(word),
            _word_x0(word),
        )
    )

    return result


# ============================================================
# PRIMER RENGLÓN
# ============================================================

def _first_row_words_in_box(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    row_tolerance: float = ROW_TOP_TOLERANCE,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> List[Dict[str, Any]]:

    selected = words_in_box(
        words,
        box,
        page_number,
        tolerance_x=tolerance_x,
        tolerance_y=tolerance_y,
    )

    if not selected:
        return []

    first_top = min(
        _word_top(word)
        for word in selected
    )

    first_row = [
        word
        for word in selected
        if abs(
            _word_top(word)
            - first_top
        ) <= row_tolerance
    ]

    first_row.sort(
        key=_word_x0
    )

    return first_row


# ============================================================
# TEXTO DE CAJA
# ============================================================

def text_from_box(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> Optional[str]:

    selected = words_in_box(
        words,
        box,
        page_number,
        tolerance_x=tolerance_x,
        tolerance_y=tolerance_y,
    )

    values: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if text:
            values.append(text)

    if not values:
        return None

    return _normalize_text(
        " ".join(values)
    )


# ============================================================
# TEXTO PRIMER RENGLÓN
# ============================================================

def text_from_first_row(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    row_tolerance: float = ROW_TOP_TOLERANCE,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> Optional[str]:

    selected = _first_row_words_in_box(
        words,
        box,
        page_number,
        row_tolerance=row_tolerance,
        tolerance_x=tolerance_x,
        tolerance_y=tolerance_y,
    )

    values: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if text:
            values.append(text)

    if not values:
        return None

    return _normalize_text(
        " ".join(values)
    )


# ============================================================
# TEXTO NUMÉRICO DE CAJA
# ============================================================

def numeric_text_from_box(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> Optional[str]:

    selected = words_in_box(
        words,
        box,
        page_number,
        tolerance_x=tolerance_x,
        tolerance_y=tolerance_y,
    )

    parts: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:
            parts.append(
                digits
            )

    if not parts:
        return None

    return "".join(parts)


# ============================================================
# TEXTO NUMÉRICO PRIMER RENGLÓN
# ============================================================

def numeric_text_from_first_row(
    words: List[Dict[str, Any]],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: int,
    *,
    row_tolerance: float = ROW_TOP_TOLERANCE,
    tolerance_x: float = SPATIAL_TOLERANCE_X,
    tolerance_y: float = SPATIAL_TOLERANCE_Y,
) -> Optional[str]:

    selected = _first_row_words_in_box(
        words,
        box,
        page_number,
        row_tolerance=row_tolerance,
        tolerance_x=tolerance_x,
        tolerance_y=tolerance_y,
    )

    parts: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:
            parts.append(
                digits
            )

    if not parts:
        return None

    return "".join(parts)


# ============================================================
# DETECCIÓN SEMÁNTICA DE PÁGINA
# ============================================================

PAGE_ANCHORS: Tuple[
    Tuple[str, int],
    ...
] = (
    ("NUMERO DE CLIENTE", 30),
    ("NÚMERO DE CLIENTE", 30),
    ("RFC", 25),
    ("CLABE", 30),
    ("FECHA DE CORTE", 20),
    ("CORTE", 15),
    ("PERIODO", 20),
    ("PRODUCTO", 10),
    ("NOMINA BANORTE", 15),
    ("NOMINA", 5),
)


def _page_score(
    page_lines: List[List[Dict[str, Any]]],
) -> int:
    """
    Calcula qué tan probable es que la página contenga los
    datos generales de la cuenta.

    No extrae ningún dato todavía.
    Solamente selecciona la página candidata.
    """

    score = 0

    page_text = " ".join(
        _normalize_search_text(
            _line_text(line)
        )
        for line in page_lines
    )

    for anchor, weight in PAGE_ANCHORS:

        normalized_anchor = (
            _normalize_search_text(
                anchor
            )
        )

        if normalized_anchor in page_text:
            score += weight

    return score


def _find_best_data_page(
    words: List[Dict[str, Any]],
) -> Optional[int]:
    """
    Localiza dinámicamente la página que contiene los datos
    generales de la cuenta.

    Si existe una página con varias señales semánticas, se
    selecciona esa página.

    En caso de empate se conserva la primera.
    """

    if not words:
        return None

    pages = sorted(
        {
            _word_page(word)
            for word in words
        }
    )

    best_page: Optional[int] = None
    best_score = 0

    for page in pages:

        page_words = [
            word
            for word in words
            if _word_page(word) == page
        ]

        page_lines = _group_words_into_lines(
            page_words
        )

        score = _page_score(
            page_lines
        )

        if score > best_score:
            best_score = score
            best_page = page

    if best_page is not None:
        return best_page

    return None


# ============================================================
# BÚSQUEDA SEMÁNTICA DE ETIQUETAS
# ============================================================

def _line_matches_patterns(
    line: List[Dict[str, Any]],
    patterns: Tuple[str, ...],
) -> bool:

    text = _normalize_search_text(
        _line_text(line)
    )

    compact = _normalize_compact_text(
        text
    )

    for pattern in patterns:

        normalized_pattern = (
            _normalize_search_text(
                pattern
            )
        )

        if (
            normalized_pattern in text
            or
            _normalize_compact_text(
                normalized_pattern
            )
            in compact
        ):
            return True

    return False


def _find_label_line(
    page_lines: List[List[Dict[str, Any]]],
    patterns: Tuple[str, ...],
) -> Optional[List[Dict[str, Any]]]:

    for line in page_lines:

        if _line_matches_patterns(
            line,
            patterns,
        ):
            return line

    return None


# ============================================================
# BÚSQUEDA DE WORD POR ETIQUETA
# ============================================================

def _find_label_word(
    page_words: List[Dict[str, Any]],
    patterns: Tuple[str, ...],
) -> Optional[Dict[str, Any]]:

    for word in sorted(
        page_words,
        key=lambda item: (
            _word_top(item),
            _word_x0(item),
        ),
    ):

        text = _normalize_search_text(
            word.get(
                "text",
                "",
            )
        )

        compact = _normalize_compact_text(
            text
        )

        for pattern in patterns:

            normalized_pattern = (
                _normalize_search_text(
                    pattern
                )
            )

            compact_pattern = (
                _normalize_compact_text(
                    normalized_pattern
                )
            )

            if (
                normalized_pattern == text
                or
                compact_pattern == compact
            ):
                return word

    return None


# ============================================================
# CONSTRUIR CAJA RELATIVA A UNA ETIQUETA
# ============================================================

def _relative_box(
    anchor_word: Dict[str, Any],
    *,
    x_offset: Tuple[float, float],
    y_offset: Tuple[float, float],
) -> Tuple[
    float,
    float,
    float,
    float,
]:

    anchor_x0 = _word_x0(
        anchor_word
    )

    anchor_x1 = _word_x1(
        anchor_word
    )

    anchor_top = _word_top(
        anchor_word
    )

    return (
        anchor_x0 + x_offset[0],
        anchor_x1 + x_offset[1],
        anchor_top + y_offset[0],
        anchor_top + y_offset[1],
    )


# ============================================================
# BUSCAR WORDS NUMÉRICOS CERCA DE UN ANCLA
# ============================================================

def _numeric_words_near_anchor(
    page_words: List[Dict[str, Any]],
    anchor_word: Dict[str, Any],
    *,
    direction: str = "right",
    max_dx: float = 220.0,
    max_dy: float = 12.0,
) -> List[Dict[str, Any]]:

    anchor_x0 = _word_x0(
        anchor_word
    )

    anchor_x1 = _word_x1(
        anchor_word
    )

    anchor_y = _word_center_y(
        anchor_word
    )

    candidates: List[
        Dict[str, Any]
    ] = []

    for word in page_words:

        if (
            word
            is anchor_word
        ):
            continue

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if not digits:
            continue

        center_y = _word_center_y(
            word
        )

        if abs(
            center_y - anchor_y
        ) > max_dy:
            continue

        x0 = _word_x0(word)
        x1 = _word_x1(word)

        if direction == "right":

            distance = x0 - anchor_x1

            if distance < -OCR_X_TOLERANCE:
                continue

        else:

            distance = anchor_x0 - x1

            if distance < -OCR_X_TOLERANCE:
                continue

        if distance > max_dx:
            continue

        candidates.append(
            word
        )

    candidates.sort(
        key=lambda word: (
            abs(
                _word_center_y(word)
                - anchor_y
            ),
            _word_x0(word),
        )
    )

    return candidates


# ============================================================
# BUSCAR FECHA CERCA DE ANCLA
# ============================================================

DATE_PATTERN = re.compile(
    r"\d{1,2}/[A-Za-zÁÉÍÓÚáéíóúÑñ]+/\d{4}\b"
)


def _extract_date_from_word(
    value: Optional[str],
) -> Optional[str]:

    if not value:
        return None

    match = DATE_PATTERN.search(
        value
    )

    if not match:
        return None

    return match.group(0)


def _find_date_near_anchor(
    page_words: List[Dict[str, Any]],
    anchor_word: Dict[str, Any],
    *,
    direction: str = "right",
    max_dx: float = 300.0,
    max_dy: float = 15.0,
) -> Optional[str]:

    anchor_x0 = _word_x0(
        anchor_word
    )

    anchor_x1 = _word_x1(
        anchor_word
    )

    anchor_y = _word_center_y(
        anchor_word
    )

    candidates: List[
        Tuple[
            float,
            str,
        ]
    ] = []

    for word in page_words:

        value = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        date = _extract_date_from_word(
            value
        )

        if not date:
            continue

        if abs(
            _word_center_y(word)
            - anchor_y
        ) > max_dy:
            continue

        if direction == "right":

            distance = (
                _word_x0(word)
                - anchor_x1
            )

        else:

            distance = (
                anchor_x0
                - _word_x1(word)
            )

        if distance < -OCR_X_TOLERANCE:
            continue

        if distance > max_dx:
            continue

        candidates.append(
            (
                abs(distance),
                date,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


# ============================================================
# EXTRACCIÓN DE NÚMERO DESDE WORDS
# ============================================================

def _join_numeric_words(
    words: List[Dict[str, Any]],
) -> Optional[str]:

    if not words:
        return None

    ordered = sorted(
        words,
        key=lambda word: (
            _word_top(word),
            _word_x0(word),
        ),
    )

    parts: List[str] = []

    for word in ordered:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:
            parts.append(
                digits
            )

    if not parts:
        return None

    return "".join(parts)


# ============================================================
# VALIDACIONES
# ============================================================

def normalize_rfc(
    value: Optional[str],
) -> Optional[str]:

    if value is None:
        return None

    cleaned_value = re.sub(
        r"(?:RFC\s*:?\s*)+",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s+",
        "",
        cleaned_value.upper(),
    )

    return value or None


def normalize_account(
    value: Optional[str],
) -> Optional[str]:

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return digits or None


def normalize_customer_number(
    value: Optional[str],
) -> Optional[str]:

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return digits or None


def normalize_clabe(
    value: Optional[str],
) -> Optional[str]:

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if len(digits) != 18:
        return None

    return digits


def extract_date_from_text(
    value: Optional[str],
) -> Optional[str]:

    return _extract_date_from_word(
        value
    )


def _looks_like_rfc(
    value: Optional[str],
) -> bool:

    if not value:
        return False

    value = normalize_rfc(
        value
    )

    if not value:
        return False

    # RFC de persona física:
    #
    #     4 letras + 6 dígitos + 3 alfanuméricos
    #
    # RFC moral:
    #
    #     3 letras + 6 dígitos + 3 alfanuméricos
    #
    return bool(
        re.fullmatch(
            r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}",
            value,
        )
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — PRODUCTO
# ============================================================

def extract_producto_principal(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_PRODUCTO_PRINCIPAL,
        page_number,
    )

    return _normalize_text(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — CUENTA
# ============================================================

def extract_numero_cuenta(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_first_row(
        words,
        BOX_NUMERO_CUENTA,
        page_number,
    )

    return normalize_account(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — CLIENTE
# ============================================================

def extract_numero_cliente(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_NUMERO_CLIENTE,
        page_number,
    )

    return normalize_customer_number(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — RFC
# ============================================================

def extract_rfc(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_RFC,
        page_number,
    )

    return normalize_rfc(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — NOMBRE
# ============================================================

def extract_nombre_cliente(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_first_row(
        words,
        BOX_NOMBRE_CLIENTE,
        page_number,
    )

    return _normalize_text(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — PERIODO INICIO
# ============================================================

def extract_periodo_inicio(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_PERIODO_INICIO,
        page_number,
    )

    return extract_date_from_text(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — PERIODO FIN
# ============================================================

def extract_periodo_fin(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_PERIODO_FIN,
        page_number,
    )

    return extract_date_from_text(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — FECHA CORTE
# ============================================================

def extract_fecha_corte(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = text_from_box(
        words,
        BOX_FECHA_CORTE,
        page_number,
    )

    return extract_date_from_text(
        value
    )


# ============================================================
# EXTRACTOR ESPACIAL ORIGINAL — CLABE
# ============================================================

def extract_clabe(
    words: List[Dict[str, Any]],
    page_number: int = PAGE_DATOS,
) -> Optional[str]:

    value = numeric_text_from_first_row(
        words,
        BOX_CLABE,
        page_number,
    )

    return normalize_clabe(
        value
    )


# ============================================================
# FALLBACK SEMÁNTICO — NÚMERO DE CLIENTE
# ============================================================

def _extract_customer_number_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label = _find_label_word(
        page_words,
        (
            "NUMERO DE CLIENTE",
            "NÚMERO DE CLIENTE",
            "NO. DE CLIENTE",
            "NO DE CLIENTE",
        ),
    )

    if label is None:
        return None

    candidates = _numeric_words_near_anchor(
        page_words,
        label,
        max_dx=180.0,
        max_dy=15.0,
    )

    for word in candidates:

        digits = re.sub(
            r"\D",
            "",
            str(
                word.get(
                    "text",
                    "",
                )
            ),
        )

        if 6 <= len(digits) <= 12:
            return digits

    return None


# ============================================================
# FALLBACK SEMÁNTICO — RFC
# ============================================================

def _extract_rfc_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label = _find_label_word(
        page_words,
        (
            "RFC",
        ),
    )

    if label is None:
        return None

    candidates = sorted(
        page_words,
        key=lambda word: (
            abs(
                _word_center_y(word)
                - _word_center_y(label)
            ),
            abs(
                _word_x0(word)
                - _word_x1(label)
            ),
        ),
    )

    for word in candidates:

        value = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        normalized = normalize_rfc(
            value
        )

        if _looks_like_rfc(
            normalized
        ):
            return normalized

    # Fallback adicional para OCR donde RFC puede venir unido
    #
    #     RFC:ROOM770801B36

    for word in page_words:

        value = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        match = re.search(
            r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b",
            value.upper(),
        )

        if match:
            return match.group(0)

    return None


# ============================================================
# FALLBACK SEMÁNTICO — NOMBRE
# ============================================================

def _extract_nombre_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label_line = _find_label_line(
        _group_words_into_lines(
            page_words
        ),
        (
            "NOMBRE DEL CLIENTE",
            "NOMBRE CLIENTE",
            "CLIENTE",
        ),
    )

    if label_line is None:
        return None

    label_y = _line_center_y(
        label_line
    )

    candidates = [
        line
        for line in _group_words_into_lines(
            page_words
        )
        if abs(
            _line_center_y(line)
            - label_y
        ) <= 16.0
    ]

    for line in candidates:

        text = _line_text(
            line
        )

        if not text:
            continue

        normalized = _normalize_search_text(
            text
        )

        if (
            "NOMBRE" in normalized
            or "CLIENTE" in normalized
        ):
            # Buscamos solamente palabras que parezcan
            # contenido y no etiquetas.
            values = []

            for word in line:

                value = str(
                    word.get(
                        "text",
                        "",
                    )
                ).strip()

                normalized_word = _normalize_search_text(
                    value
                )

                if normalized_word in {
                    "NOMBRE",
                    "DEL",
                    "CLIENTE",
                }:
                    continue

                if value:
                    values.append(value)

            if values:
                return _normalize_text(
                    " ".join(values)
                )

    return None


# ============================================================
# FALLBACK SEMÁNTICO — FECHA
# ============================================================

def _extract_periodo_semantic(
    page_words: List[Dict[str, Any]],
) -> Tuple[
    Optional[str],
    Optional[str],
]:

    periodo_label = _find_label_word(
        page_words,
        (
            "PERIODO",
            "PERÍODO",
        ),
    )

    if periodo_label is None:
        return None, None

    dates: List[
        Tuple[
            float,
            str,
        ]
    ] = []

    anchor_y = _word_center_y(
        periodo_label
    )

    anchor_x = _word_x1(
        periodo_label
    )

    for word in page_words:

        value = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        date = _extract_date_from_word(
            value
        )

        if not date:
            continue

        distance_y = abs(
            _word_center_y(word)
            - anchor_y
        )

        if distance_y > 25.0:
            continue

        distance_x = (
            _word_x0(word)
            - anchor_x
        )

        if distance_x < -20.0:
            continue

        if distance_x > 450.0:
            continue

        dates.append(
            (
                distance_x,
                date,
            )
        )

    if len(dates) >= 2:

        dates.sort(
            key=lambda item: item[0]
        )

        return (
            dates[0][1],
            dates[1][1],
        )

    if len(dates) == 1:

        return (
            dates[0][1],
            None,
        )

    return None, None


# ============================================================
# FALLBACK SEMÁNTICO — FECHA DE CORTE
# ============================================================

def _extract_fecha_corte_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label = _find_label_word(
        page_words,
        (
            "FECHA DE CORTE",
            "FECHA CORTE",
            "CORTE",
        ),
    )

    if label is None:
        return None

    return _find_date_near_anchor(
        page_words,
        label,
        max_dx=350.0,
        max_dy=18.0,
    )


# ============================================================
# FALLBACK SEMÁNTICO — CUENTA
# ============================================================

def _extract_numero_cuenta_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label = _find_label_word(
        page_words,
        (
            "NUMERO DE CUENTA",
            "NÚMERO DE CUENTA",
            "CUENTA",
        ),
    )

    if label is None:
        return None

    candidates = _numeric_words_near_anchor(
        page_words,
        label,
        max_dx=280.0,
        max_dy=18.0,
    )

    # ========================================================
    # IMPORTANTE
    # ========================================================
    #
    # No concatenamos indiscriminadamente todos los números.
    #
    # Para OCR puede ocurrir:
    #
    #     1098973139
    #     1109382534
    #
    # en dos renglones distintos.
    #
    # Tomamos únicamente el renglón más cercano verticalmente
    # al label.
    #
    # ========================================================

    if not candidates:
        return None

    anchor_y = _word_center_y(
        label
    )

    same_row = [
        word
        for word in candidates
        if abs(
            _word_center_y(word)
            - anchor_y
        ) <= OCR_ROW_TOP_TOLERANCE
    ]

    if not same_row:
        same_row = [
            min(
                candidates,
                key=lambda word: abs(
                    _word_center_y(word)
                    - anchor_y
                ),
            )
        ]

    same_row.sort(
        key=_word_x0
    )

    value = _join_numeric_words(
        same_row
    )

    return normalize_account(
        value
    )


# ============================================================
# FALLBACK SEMÁNTICO — CLABE
# ============================================================

def _extract_clabe_semantic(
    page_words: List[Dict[str, Any]],
) -> Optional[str]:

    label = _find_label_word(
        page_words,
        (
            "CLABE",
        ),
    )

    if label is None:
        return None

    candidates = _numeric_words_near_anchor(
        page_words,
        label,
        max_dx=350.0,
        max_dy=18.0,
    )

    if not candidates:
        return None

    anchor_y = _word_center_y(
        label
    )

    # ========================================================
    # SELECCIONAMOS EL PRIMER RENGLÓN
    # ========================================================

    same_row = [
        word
        for word in candidates
        if abs(
            _word_center_y(word)
            - anchor_y
        ) <= OCR_ROW_TOP_TOLERANCE
    ]

    if not same_row:

        nearest_y = min(
            abs(
                _word_center_y(word)
                - anchor_y
            )
            for word in candidates
        )

        same_row = [
            word
            for word in candidates
            if abs(
                abs(
                    _word_center_y(word)
                    - anchor_y
                )
                - nearest_y
            )
            <= OCR_ROW_TOP_TOLERANCE
        ]

    same_row.sort(
        key=_word_x0
    )

    value = _join_numeric_words(
        same_row
    )

    return normalize_clabe(
        value
    )


# ============================================================
# HELPERS DE CALIDAD
# ============================================================

def _has_value(
    value: Optional[str],
) -> bool:
    return bool(
        value
        and value.strip()
    )


# ============================================================
# EXTRACTOR PRINCIPAL
# ============================================================

def extract_datos_cuenta_words(
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extractor híbrido de datos generales BANORTE.

    Estrategia:

        1. Detecta dinámicamente la página correcta.
        2. Intenta extracción espacial.
        3. Si un campo no fue obtenido o no pasa validación,
           intenta extracción semántica/OCR.
        4. Mantiene las reglas originales para los campos
           espacialmente sensibles.

    Esto permite trabajar tanto con:

        PDF digital
        PDF renderizado
        OCR

    sin abandonar el comportamiento existente.
    """

    if not words:
        return DatosCuenta(
            producto_principal=None,
            periodo_inicio=None,
            periodo_fin=None,
            fecha_corte=None,
            numero_cuenta=None,
            numero_cliente=None,
            rfc=None,
            clabe=None,
            nombre_cliente=None,
        )

    # ========================================================
    # 1. LOCALIZAR PÁGINA DE DATOS
    # ========================================================

    data_page = _find_best_data_page(
        words
    )

    # ========================================================
    # 2. FALLBACK ABSOLUTO
    # ========================================================
    #
    # Si no se encontró ninguna señal semántica, mantenemos
    # exactamente la compatibilidad con la implementación
    # anterior: página 1.
    #
    # ========================================================

    if data_page is None:
        data_page = PAGE_DATOS

    page_words = [
        word
        for word in words
        if _word_page(word) == data_page
    ]

    # ========================================================
    # 3. EXTRACCIÓN ESPACIAL
    # ========================================================

    producto_principal = extract_producto_principal(
        page_words,
        data_page,
    )

    periodo_inicio = extract_periodo_inicio(
        page_words,
        data_page,
    )

    periodo_fin = extract_periodo_fin(
        page_words,
        data_page,
    )

    fecha_corte = extract_fecha_corte(
        page_words,
        data_page,
    )

    numero_cuenta = extract_numero_cuenta(
        page_words,
        data_page,
    )

    numero_cliente = extract_numero_cliente(
        page_words,
        data_page,
    )

    rfc = extract_rfc(
        page_words,
        data_page,
    )

    clabe = extract_clabe(
        page_words,
        data_page,
    )

    nombre_cliente = extract_nombre_cliente(
        page_words,
        data_page,
    )

    # ========================================================
    # 4. FALLBACK SEMÁNTICO / OCR
    # ========================================================
    #
    # Solo se activa para campos que no pudieron obtenerse
    # mediante las coordenadas originales.
    #
    # Así el PDF digital continúa utilizando exactamente
    # el camino espacial conocido.
    #
    # ========================================================

    if not _has_value(
        numero_cliente
    ):
        numero_cliente = (
            _extract_customer_number_semantic(
                page_words
            )
        )

    if not _has_value(
        rfc
    ) or not _looks_like_rfc(rfc):
        rfc = _extract_rfc_semantic(
            page_words
        )

    if not _has_value(
        numero_cuenta
    ):
        numero_cuenta = (
            _extract_numero_cuenta_semantic(
                page_words
            )
        )

    if not _has_value(
        clabe
    ):
        clabe = _extract_clabe_semantic(
            page_words
        )

    if not _has_value(
        fecha_corte
    ):
        fecha_corte = (
            _extract_fecha_corte_semantic(
                page_words
            )
        )

    if (
        not _has_value(periodo_inicio)
        or not _has_value(periodo_fin)
    ):
        (
            semantic_inicio,
            semantic_fin,
        ) = _extract_periodo_semantic(
            page_words
        )

        if not _has_value(
            periodo_inicio
        ):
            periodo_inicio = semantic_inicio

        if not _has_value(
            periodo_fin
        ):
            periodo_fin = semantic_fin

    if not _has_value(
        nombre_cliente
    ):
        nombre_cliente = (
            _extract_nombre_semantic(
                page_words
            )
        )

    # ========================================================
    # 5. VALIDACIÓN FINAL
    # ========================================================

    numero_cuenta = normalize_account(
        numero_cuenta
    )

    numero_cliente = normalize_customer_number(
        numero_cliente
    )

    rfc = normalize_rfc(
        rfc
    )

    clabe = normalize_clabe(
        clabe
    )

    periodo_inicio = extract_date_from_text(
        periodo_inicio
    )

    periodo_fin = extract_date_from_text(
        periodo_fin
    )

    fecha_corte = extract_date_from_text(
        fecha_corte
    )

    producto_principal = _normalize_text(
        producto_principal
    )

    nombre_cliente = _normalize_text(
        nombre_cliente
    )

    # ========================================================
    # 6. CONSTRUIR MODELO
    # ========================================================

    return DatosCuenta(
        producto_principal=producto_principal,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        fecha_corte=fecha_corte,
        numero_cuenta=numero_cuenta,
        numero_cliente=numero_cliente,
        rfc=rfc,
        clabe=clabe,
        nombre_cliente=nombre_cliente,
    )