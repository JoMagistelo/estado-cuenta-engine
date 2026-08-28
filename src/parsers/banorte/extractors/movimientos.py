from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.movimiento import Movimiento

from parsers.banorte.utils.words_after_last_movement import (
    remove_after_last_movement,
)

from parsers.banorte.utils.words_footer_filter import (
    remove_banorte_footer,
)


# ============================================================
# EXTRACTOR ESPACIAL — MOVIMIENTOS BANORTE
# ============================================================
#
# Layout observado:
#
#     FECHA
#     DESCRIPCIÓN / ESTABLECIMIENTO
#     MONTO DEL DEPÓSITO
#     MONTO DEL RETIRO
#     SALDO
#
# El parser trabaja exclusivamente mediante coordenadas
# espaciales para separar las columnas.
#
# Características particulares del PDF BANORTE:
#
#   1. La fecha y el primer fragmento del concepto pueden
#      venir físicamente unidos.
#
#   2. Una operación puede ocupar muchas líneas verticales.
#
#   3. Los importes aparecen en columnas independientes.
#
#   4. Los encabezados se repiten en páginas posteriores.
#
#   5. Una página posterior puede continuar el movimiento
#      anterior.
#
#   6. La descripción puede extenderse muy hacia la derecha,
#      por lo que NO se utiliza el centro de la palabra
#      "DESCRIPCIÓN" como referencia.
#
# ============================================================


# ============================================================
# PÁGINAS
# ============================================================

FIRST_MOVEMENTS_PAGE = 2


# ============================================================
# TOLERANCIAS ESPACIALES
# ============================================================

LINE_Y_TOLERANCE = 3.5

COLUMN_TOLERANCE = 2.0

BOX_TOLERANCE_X = 1.5

BOX_TOLERANCE_Y = 1.5


# ============================================================
# CONFIGURACIÓN ESPACIAL BANORTE
# ============================================================

DEFAULT_COLUMN_BOUNDS = {

    "FECHA": (
        50.0,
        84.0,
    ),

    "DESCRIPCION": (
        84.0,
        352.0,
    ),

    "DEPOSITO": (
        352.0,
        428.0,
    ),

    "RETIRO": (
        428.0,
        520.0,
    ),

    "SALDO": (
        520.0,
        568.0,
    ),

}


# ============================================================
# HEADER
# ============================================================

HEADER_REQUIRED = {
    "FECHA",
    "DESCRIPCIÓN",
    "MONTO",
    "SALDO",
}


# ============================================================
# REGEX — FECHAS
# ============================================================

DATE_PREFIX_PATTERN = re.compile(

    r"^"

    r"(?P<date>"

    r"\d{1,2}"

    r"-"

    r"[A-ZÁÉÍÓÚÑ]{3}"

    r"-"

    r"(?:"
        r"\d{4}(?!\d)"
        r"|"
        r"\d{2}"
    ")"

    r")",

    re.IGNORECASE,

)


# ============================================================
# REGEX — IMPORTES
# ============================================================

MONEY_PATTERN = re.compile(
    r"""
    ^
    [+-]?
    \(?
    \$?
    \d{1,3}
    (?:,\d{3})*
    (?:\.\d{1,2})?
    \)?
    $
    """,
    re.VERBOSE,
)


# ============================================================
# REGEX PREPARADOS PARA FUTURO
# ============================================================

RFC_PATTERN = re.compile(
    r"""
    \b
    (
        [A-Z&Ñ]{3,4}
        \s?
        \d{6}
        \s?
        [A-Z0-9]{3}
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


TIME_PATTERN = re.compile(
    r"\b([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b"
)


AUTH_PATTERN = re.compile(
    r"""
    \b
    AUT
    \s*
    [:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


SUC_PATTERN = re.compile(
    r"""
    \b
    SUC
    \s*
    [:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CAJA_PATTERN = re.compile(
    r"""
    \b
    CAJA
    \s*
    [:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CLABE_PATTERN = re.compile(
    r"(?<!\d)(\d{18})(?!\d)"
)


REFERENCE_PATTERN = re.compile(
    r"""
    \b
    REFERENCIA
    \s*
    [:#=-]?
    \s*
    ([A-Z0-9*_-]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ============================================================
# ESTRUCTURA DE CONFIGURACIÓN
# ============================================================

@dataclass(frozen=True)
class ColumnConfig:

    """
    Define los límites horizontales de las columnas BANORTE.
    """

    fecha: tuple[float, float]

    descripcion: tuple[float, float]

    deposito: tuple[float, float]

    retiro: tuple[float, float]

    saldo: tuple[float, float]


# ============================================================
# CONFIGURACIÓN BASE
# ============================================================

def build_default_config() -> ColumnConfig:

    """
    Construye la configuración espacial BANORTE.
    """

    return ColumnConfig(

        fecha=DEFAULT_COLUMN_BOUNDS[
            "FECHA"
        ],

        descripcion=DEFAULT_COLUMN_BOUNDS[
            "DESCRIPCION"
        ],

        deposito=DEFAULT_COLUMN_BOUNDS[
            "DEPOSITO"
        ],

        retiro=DEFAULT_COLUMN_BOUNDS[
            "RETIRO"
        ],

        saldo=DEFAULT_COLUMN_BOUNDS[
            "SALDO"
        ],

    )


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalize_text(
    value: Any,
) -> str:

    """
    Normaliza espacios y caracteres básicos.
    """

    if value is None:
        return ""

    value = str(value)

    value = (
        value
        .replace("\xa0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_upper(
    value: Any,
) -> str:

    """
    Normaliza y convierte a mayúsculas.
    """

    return normalize_text(
        value
    ).upper()


# ============================================================
# COORDENADAS
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    """
    Conversión segura a float.
    """

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def word_x0(
    word: Dict[str, Any],
) -> float:

    return safe_float(
        word.get(
            "x0",
            0,
        )
    )


def word_x1(
    word: Dict[str, Any],
) -> float:

    return safe_float(
        word.get(
            "x1",
            word_x0(word),
        )
    )


def word_center_x(
    word: Dict[str, Any],
) -> float:

    return (
        word_x0(word)
        + word_x1(word)
    ) / 2.0


def word_top(
    word: Dict[str, Any],
) -> float:

    return safe_float(
        word.get(
            "top",
            0,
        )
    )


def word_bottom(
    word: Dict[str, Any],
) -> float:

    return safe_float(
        word.get(
            "bottom",
            word_top(word),
        )
    )


def word_center_y(
    word: Dict[str, Any],
) -> float:

    return (
        word_top(word)
        + word_bottom(word)
    ) / 2.0


def word_height(
    word: Dict[str, Any],
) -> float:

    return abs(
        word_bottom(word)
        - word_top(word)
    )


# ============================================================
# SOLAPAMIENTO ESPACIAL
# ============================================================

def word_inside_box(
    word: Dict[str, Any],
    box: tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: Optional[int] = None,
) -> bool:

    """
    Determina si una palabra se encuentra espacialmente
    dentro de una caja.

    Se utiliza SOLAPAMIENTO de rectángulos y no solamente
    el centro de la palabra.
    """

    if (
        page_number is not None
        and int(
            word.get(
                "page",
                1,
            )
            or 1
        )
        != page_number
    ):
        return False

    xmin, xmax, ymin, ymax = box

    xmin -= BOX_TOLERANCE_X
    xmax += BOX_TOLERANCE_X
    ymin -= BOX_TOLERANCE_Y
    ymax += BOX_TOLERANCE_Y

    x0 = word_x0(word)
    x1 = word_x1(word)

    top = word_top(word)
    bottom = word_bottom(word)

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

    vertical_overlap = (
        min(
            bottom,
            ymax,
        )
        - max(
            top,
            ymin,
        )
    )

    return (
        horizontal_overlap > 0
        and vertical_overlap > 0
    )


def words_in_box(
    words: List[
        Dict[str, Any]
    ],
    box: tuple[
        float,
        float,
        float,
        float,
    ],
    page_number: Optional[int] = None,
) -> List[
    Dict[str, Any]
]:

    """
    Devuelve las palabras contenidas en una caja espacial.
    """

    result = [
        word
        for word in words
        if word_inside_box(
            word,
            box,
            page_number,
        )
    ]

    result.sort(
        key=lambda word: (
            safe_float(
                word.get(
                    "top",
                    0,
                )
            ),
            word_x0(word),
        )
    )

    return result


# ============================================================
# AGRUPACIÓN DE LÍNEAS
# ============================================================

def group_words_into_lines(
    words: List[
        Dict[str, Any]
    ],
) -> List[
    List[
        Dict[str, Any]
    ]
]:

    """
    Agrupa palabras por posición vertical.
    Conserva la separación por página.
    """

    if not words:
        return []

    words = sorted(

        words,

        key=lambda word: (

            int(
                word.get(
                    "page",
                    1,
                )
                or 1
            ),

            word_center_y(word),

            word_x0(word),

        ),

    )

    heights = [
        word_height(word)
        for word in words
        if word_height(word) > 0
    ]

    if heights:

        heights.sort()

        typical_height = heights[
            len(heights) // 2
        ]

        tolerance = max(
            LINE_Y_TOLERANCE,
            typical_height * 0.45,
        )

    else:

        tolerance = LINE_Y_TOLERANCE

    lines: List[
        List[
            Dict[str, Any]
        ]
    ] = []

    current: List[
        Dict[str, Any]
    ] = []

    current_page: Optional[int] = None

    current_y: Optional[float] = None

    for word in words:

        page = int(
            word.get(
                "page",
                1,
            )
            or 1
        )

        y = word_center_y(
            word
        )

        if current_y is None:

            current = [
                word
            ]

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

            current.append(
                word
            )

            current_y = (
                sum(
                    word_center_y(
                        item
                    )
                    for item in current
                )
                / len(current)
            )

        else:

            current.sort(
                key=word_x0
            )

            lines.append(
                current
            )

            current = [
                word
            ]

            current_page = page

            current_y = y

    if current:

        current.sort(
            key=word_x0
        )

        lines.append(
            current
        )

    return lines


# ============================================================
# TEXTO DE LÍNEA
# ============================================================

def line_text(
    line: List[
        Dict[str, Any]
    ],
) -> str:

    """
    Construye el texto completo de una línea.
    """

    values: List[str] = []

    for word in sorted(
        line,
        key=word_x0,
    ):

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if text:

            values.append(
                text
            )

    return " ".join(
        values
    ).strip()


# ============================================================
# HEADER
# ============================================================

def find_normalized_token(
    line: List[
        Dict[str, Any]
    ],
    token: str,
) -> bool:

    """
    Busca un token normalizado dentro de una línea.
    """

    token = normalize_upper(
        token
    )

    for word in line:

        text = normalize_upper(
            word.get(
                "text",
                "",
            )
        )

        if text == token:

            return True

    return False


def is_movements_header(
    line: List[
        Dict[str, Any]
    ],
) -> bool:

    """
    Detecta los encabezados repetidos de movimientos BANORTE.
    """

    if not line:
        return False

    text = normalize_upper(
        line_text(line)
    )

    has_fecha = (
        "FECHA" in text
    )

    has_descripcion = (
        "DESCRIPCIÓN" in text
        or "DESCRIPCION" in text
    )

    has_monto = (
        "MONTO" in text
    )

    has_saldo = (
        "SALDO" in text
    )

    return (
        has_fecha
        and has_descripcion
        and has_monto
        and has_saldo
    )


# ============================================================
# ENCABEZADOS SECUNDARIOS
# ============================================================

def is_detail_title(
    line: List[
        Dict[str, Any]
    ],
) -> bool:

    """
    Detecta:

        DETALLE DE MOVIMIENTOS
    """

    text = normalize_upper(
        line_text(line)
    )

    return (
        "DETALLE" in text
        and "MOVIMIENTOS" in text
    )


def is_product_header(
    line: List[
        Dict[str, Any]
    ],
) -> bool:

    """
    Detecta el encabezado auxiliar:

        Nomina Banorte Sin Chequera
    """

    text = normalize_upper(
        line_text(line)
    )

    return (
        "NOMINA" in text
        and "BANORTE" in text
    )


# ============================================================
# COLUMNA
# ============================================================

def word_inside_column(
    word: Dict[str, Any],
    column: tuple[
        float,
        float,
    ],
) -> bool:

    """
    Determina pertenencia a una columna mediante el centro X.

    Para texto general esto funciona adecuadamente.
    Para importes se utiliza una función específica basada
    en x1.
    """

    center_x = word_center_x(
        word
    )

    xmin, xmax = column

    return (
        xmin - COLUMN_TOLERANCE
        <= center_x
        <= xmax + COLUMN_TOLERANCE
    )


def words_in_column(
    line: List[
        Dict[str, Any]
    ],
    column: tuple[
        float,
        float,
    ],
) -> List[
    Dict[str, Any]
]:

    """
    Devuelve palabras pertenecientes a una columna.
    """

    result = [

        word

        for word in line

        if word_inside_column(
            word,
            column,
        )

    ]

    result.sort(
        key=word_x0
    )

    return result


# ============================================================
# COLUMNA DE TEXTO — SOLAPAMIENTO HORIZONTAL
# ============================================================

def word_overlaps_text_column(
    word: Dict[str, Any],
    column: tuple[
        float,
        float,
    ],
) -> bool:
    """
    Determina si una palabra tiene solapamiento horizontal
    con una columna de texto.

    Para la extracción de conceptos no usamos el centro de
    la palabra, porque Banorte puede unir físicamente la fecha
    con el primer fragmento del concepto:

        06-JUN-25SALDO
        06-JUN-25Retiro
        06-JUN-25Pago

    Aunque el centro de toda la palabra quede dentro de la
    columna FECHA, una parte del texto puede extenderse hacia
    la columna DESCRIPCIÓN.

    Se considera perteneciente a la columna si existe
    cualquier solapamiento horizontal real.
    """

    x0 = word_x0(
        word
    )

    x1 = word_x1(
        word
    )

    xmin, xmax = column

    return (
        min(
            x1,
            xmax,
        )
        > max(
            x0,
            xmin,
        )
    )


def words_in_text_column(
    line: List[
        Dict[str, Any]
    ],
    column: tuple[
        float,
        float,
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Devuelve las palabras que tienen solapamiento horizontal
    con una columna de texto.

    A diferencia de words_in_column(), aquí no usamos el
    centro de la palabra.
    """

    result = [
        word
        for word in line
        if word_overlaps_text_column(
            word,
            column,
        )
    ]

    result.sort(
        key=word_x0
    )

    return result



def column_text(
    line: List[
        Dict[str, Any]
    ],
    column: tuple[
        float,
        float,
    ],
) -> str:

    """
    Extrae texto de una columna dentro de una línea.
    """

    selected = words_in_column(
        line,
        column,
    )

    values: List[str] = []

    for word in selected:

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if text:

            values.append(
                text
            )

    return " ".join(
        values
    ).strip()


# ============================================================
# IMPORTES
# ============================================================

def is_money(
    text: str,
) -> bool:

    """
    Determina si una cadena representa un importe.
    """

    return bool(
        MONEY_PATTERN.fullmatch(
            normalize_text(text)
        )
    )


def parse_amount(
    text: str,
) -> float:

    """
    Convierte un importe textual a float.
    """

    value = normalize_text(
        text
    )

    if not value:

        return 0.0

    value = (
        value
        .replace(
            "$",
            "",
        )
        .replace(
            ",",
            "",
        )
        .strip()
    )

    negative = (
        value.startswith("(")
        and value.endswith(")")
    )

    if negative:

        value = value[
            1:-1
        ].strip()

    try:

        amount = float(
            value
        )

    except (
        ValueError,
        TypeError,
    ):

        return 0.0

    if negative:

        return -amount

    return amount


def money_word_inside_column(
    word: Dict[str, Any],
    column: tuple[
        float,
        float,
    ],
) -> bool:

    """
    Determina si un importe pertenece a una columna usando
    su borde derecho X1.
    """

    x1 = word_x1(
        word
    )

    xmin, xmax = column

    return (
        xmin
        <= x1
        <= xmax
    )


def extract_amount_from_block(
    block: List[
        List[
            Dict[str, Any]
        ]
    ],
    column: tuple[
        float,
        float,
    ],
) -> float:

    """
    Busca importes en todas las líneas del movimiento.

    Se conserva el último importe que pertenezca a la columna.
    """

    candidates: List[
        tuple[
            int,
            Dict[str, Any]
        ]
    ] = []

    for line_index, line in enumerate(
        block
    ):

        for word in line:

            text = normalize_text(
                word.get(
                    "text",
                    "",
                )
            )

            if not is_money(
                text
            ):

                continue

            if not money_word_inside_column(
                word,
                column,
            ):

                continue

            candidates.append(
                (
                    line_index,
                    word,
                )
            )

    if not candidates:

        return 0.0

    _, selected = candidates[
        -1
    ]

    return parse_amount(
        selected.get(
            "text",
            "",
        )
    )


# ============================================================
# FECHA — BANORTE
# ============================================================

def extract_date_prefix(
    text: str,
) -> Optional[str]:

    """
    Extrae una fecha al principio del texto.

    Soporta:

        02-JUN-25
        02-JUN-2025
        02-JUN-25OXXOLAS
    """

    text = normalize_text(
        text
    )

    if not text:

        return None

    match = DATE_PREFIX_PATTERN.match(
        text
    )

    if not match:

        return None

    return match.group(
        "date"
    ).upper()


def is_movement_date(
    text: str,
) -> bool:

    """
    Determina si el texto empieza con una fecha Banorte.
    """

    return (
        extract_date_prefix(
            text
        )
        is not None
    )


def extract_date_from_line(
    line: List[
        Dict[str, Any]
    ],
) -> Optional[str]:

    """
    Busca la fecha al inicio de cualquiera de las palabras
    de la línea.
    """

    for word in sorted(
        line,
        key=word_x0,
    ):

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        date = extract_date_prefix(
            text
        )

        if date is not None:

            return date

    return None


def is_movement_start(
    line: List[
        Dict[str, Any]
    ],
) -> bool:

    """
    Detecta el comienzo de una operación.
    """

    return (
        extract_date_from_line(
            line
        )
        is not None
    )


# ============================================================
# LIMPIEZA DE FECHA DEL CONCEPTO
# ============================================================

def remove_date_prefix(
    text: str,
) -> str:

    """
    Elimina únicamente el prefijo de fecha.
    """

    text = normalize_text(
        text
    )

    if not text:

        return ""

    return DATE_PREFIX_PATTERN.sub(
        "",
        text,
        count=1,
    ).strip()


# ============================================================
# EXTRACCIÓN DEL CONCEPTO
# ============================================================

def extract_concepto_from_line(
    line: List[
        Dict[str, Any]
    ],
    config: ColumnConfig,
    first_line: bool = False,
) -> str:
    """
    Extrae la descripción de una línea.

    Para el concepto se utiliza solapamiento horizontal y no
    el centro de la palabra.

    Esto permite recuperar correctamente casos donde Banorte
    une físicamente la fecha con el primer fragmento del
    concepto, por ejemplo:

        06-JUN-25SALDO
        06-JUN-25Retiro
        06-JUN-25Pago

    En esos casos remove_date_prefix() elimina únicamente
    la fecha y conserva el texto real del concepto.
    """

    selected = words_in_text_column(
        line,
        config.descripcion,
    )

    values: List[str] = []

    for word in selected:

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        if first_line:

            text = remove_date_prefix(
                text
            )

            first_line = False

            if not text:
                continue

        values.append(
            text
        )

    return " ".join(
        values
    ).strip()


def extract_concepto(
    block: List[
        List[
            Dict[str, Any]
        ]
    ],
    config: ColumnConfig,
) -> str:

    """
    Construye el concepto completo de una operación.

    Todas las líneas se conservan.
    """

    values: List[str] = []

    for index, line in enumerate(
        block
    ):

        text = extract_concepto_from_line(
            line=line,
            config=config,
            first_line=(
                index == 0
            ),
        )

        if text:

            values.append(
                text
            )

    return "\n".join(
        values
    ).strip()


# ============================================================
# SALDO ANTERIOR
# ============================================================

def is_saldo_anterior(
    line: List[
        Dict[str, Any]
    ],
    config: ColumnConfig,
) -> bool:

    """
    Detecta la fila:

        31-MAY-25SALDO
        ANTERIOR
    """

    date = extract_date_from_line(
        line
    )

    if date is None:

        return False

    text = normalize_upper(
        column_text(
            line,
            config.descripcion,
        )
    )

    return (
        "SALDO" in text
        and "ANTERIOR" in text
    )


# ============================================================
# FILTROS DE LÍNEAS
# ============================================================

def should_skip_line(
    line: List[
        Dict[str, Any]
    ],
) -> bool:

    """
    Determina si una línea debe ignorarse.
    """

    if not line:

        return True

    text = normalize_upper(
        line_text(line)
    )

    if not text:

        return True

    if is_movements_header(
        line
    ):

        return True

    if is_detail_title(
        line
    ):

        return True

    if is_product_header(
        line
    ):

        return True

    return False


# ============================================================
# TRUNCAMIENTO OPCIONAL
# ============================================================

def truncate_after_marker(
    words: List[
        Dict[str, Any]
    ],
    markers: tuple[
        str,
        ...,
    ] = (
        "GRÁFICO TRANSACCIONAL",
        "GRAFICO TRANSACCIONAL",
    ),
) -> List[
    Dict[str, Any]
]:

    """
    Detiene el análisis si aparece una sección posterior
    irrelevante.
    """

    if not words:

        return []

    lines = group_words_into_lines(
        words
    )

    cutoff_page: Optional[int] = None

    cutoff_y: Optional[float] = None

    for line in lines:

        text = normalize_upper(
            line_text(line)
        )

        for marker in markers:

            marker = normalize_upper(
                marker
            )

            if marker in text:

                cutoff_page = int(
                    line[0].get(
                        "page",
                        1,
                    )
                )

                cutoff_y = word_top(
                    line[0]
                )

                break

        if cutoff_page is not None:

            break

    if cutoff_page is None:

        return words

    result: List[
        Dict[str, Any]
    ] = []

    for word in words:

        page = int(
            word.get(
                "page",
                1,
            )
            or 1
        )

        if page < cutoff_page:

            result.append(
                word
            )

            continue

        if page > cutoff_page:

            continue

        if (
            cutoff_y is not None
            and word_top(word) < cutoff_y
        ):

            result.append(
                word
            )

    return result


# ============================================================
# BLOQUES DE MOVIMIENTOS
# ============================================================

def build_movement_blocks(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
    config: ColumnConfig,
) -> List[
    List[
        List[
            Dict[str, Any]
        ]
    ]
]:

    """
    Divide el documento en bloques de movimientos.

    Regla principal:

        una nueva fecha = nuevo movimiento

    Todo lo posterior hasta encontrar la siguiente fecha
    pertenece al movimiento actual.
    """

    blocks: List[
        List[
            List[
                Dict[str, Any]
            ]
        ]
    ] = []

    current: List[
        List[
            Dict[str, Any]
        ]
    ] = []

    for line in lines:

        if should_skip_line(
            line
        ):

            continue

        page = int(
            line[0].get(
                "page",
                1,
            )
        )

        if page < FIRST_MOVEMENTS_PAGE:

            continue

        if is_movement_start(
            line
        ):

            if current:

                blocks.append(
                    current
                )

            current = [
                line
            ]

        else:

            if current:

                current.append(
                    line
                )

    if current:

        blocks.append(
            current
        )

    return blocks


# ============================================================
# UTILIDADES DE CONCEPTO
# ============================================================

def get_concepto_lines(
    concepto: str,
) -> List[str]:

    """
    Convierte el concepto completo en líneas limpias.
    """

    if not concepto:

        return []

    return [
        line.strip()
        for line in concepto.splitlines()
        if line.strip()
    ]


def get_first_concepto_line(
    concepto: str,
) -> Optional[str]:

    """
    Devuelve la primera línea no vacía del concepto.
    """

    lines = get_concepto_lines(
        concepto
    )

    return (
        lines[0]
        if lines
        else None
    )


def normalize_concepto_for_search(
    concepto: str,
) -> str:

    """
    Normaliza el concepto para búsquedas mediante regex.

    Convierte saltos de línea y espacios múltiples en un
    único espacio, sin alterar el concepto original almacenado.
    """

    return normalize_text(
        concepto.replace(
            "\n",
            " ",
        )
    )


# ============================================================
# SPEI RECIBIDO
# ============================================================


def is_spei_recibido_movement(
    concepto: str,
) -> bool:

    """
    Determina si el movimiento corresponde a:

        SPEI RECIBIDO

    Banorte puede colocar antes del texto
    un identificador de rastreo, por ejemplo:

        062025101259L0CNKLIYC SPEI RECIBIDO, ...
        5902081890317359 SPEI RECIBIDO, ...
        HSBC432658 SPEI RECIBIDO, ...
    """

    first_line = get_first_concepto_line(
        concepto
    )

    if not first_line:
        return False

    return bool(
        re.search(
            r"\bSPEI\s+RECIBIDO\b",
            first_line,
            re.IGNORECASE,
        )
    )



def extract_hora_from_spei_recibido(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la hora de liquidación de un SPEI RECIBIDO.

    Formatos soportados:

        HR LIQ: 10:22:45
        HR LIQ: 07:37:35
        HR LIQ: 180246

    En el último caso se interpreta como:

        HHMMSS

    y se devuelve:

        HH:MM:SS
    """

    if not is_spei_recibido_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    # --------------------------------------------------------
    # FORMATO NORMAL
    #
    # 10:22:45
    # --------------------------------------------------------

    match = re.search(
        r"\bHR\s+LIQ\s*:\s*"
        r"((?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    # --------------------------------------------------------
    # FORMATO COMPACTO
    #
    # 180246
    #
    # HHMMSS
    # --------------------------------------------------------

    match = re.search(
        r"\bHR\s+LIQ\s*:\s*"
        r"(\d{6})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        value = match.group(1)

        hours = value[0:2]
        minutes = value[2:4]
        seconds = value[4:6]

        try:
            h = int(hours)
            m = int(minutes)
            s = int(seconds)
        except ValueError:
            return None

        if (
            0 <= h <= 23
            and 0 <= m <= 59
            and 0 <= s <= 59
        ):
            return (
                f"{h:02d}:"
                f"{m:02d}:"
                f"{s:02d}"
            )

    return None


def extract_beneficiario_from_spei_recibido(
    concepto: str,
) -> Optional[str]:

    """
    Extrae el beneficiario de un SPEI RECIBIDO.

    Estructura:

        DEL CLIENTE
        DISTRIBUIDORA LIVERPOOL SA DE CV
        DE LA CLABE ...

    Resultado:

        DISTRIBUIDORA LIVERPOOL SA DE CV
    """

    if not is_spei_recibido_movement(
        concepto
    ):

        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bDEL\s+CLIENTE\s+"
        r"(.*?)"
        r"\s+DE\s+LA\s+CLABE\b",
        text,
        re.IGNORECASE,
    )

    if not match:

        return None

    beneficiario = normalize_text(
        match.group(1)
    )

    return beneficiario or None


def extract_clabe_beneficiario_from_spei_recibido(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la CLABE del beneficiario de un SPEI RECIBIDO.

    Estructura:

        DE LA CLABE 646180284630000004
    """

    if not is_spei_recibido_movement(
        concepto
    ):

        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bDE\s+LA\s+CLABE\s+"
        r"(\d{18})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        return match.group(
            1
        )

    # Fallback por si el PDF introduce texto adicional
    # alrededor de la etiqueta.
    match = re.search(
        r"\bCLABE\s+"
        r"(\d{18})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        return match.group(
            1
        )

    return None


def extract_rfc_from_spei_recibido(
    concepto: str,
) -> Optional[str]:

    """
    Extrae el RFC del cliente que envía el SPEI.

    Estructura:

        CON RFC DLI931201MI9
    """

    if not is_spei_recibido_movement(
        concepto
    ):

        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bCON\s+RFC\s+"
        r"([A-Z&Ñ]{3,4}"
        r"\d{6}"
        r"[A-Z0-9]{3})\b",
        text,
        re.IGNORECASE,
    )

    if not match:

        return None

    return match.group(
        1
    ).upper()


def extract_concepto_original_from_spei_recibido(
    concepto: str,
) -> Optional[str]:

    """
    Extrae el concepto escrito por el emisor de un
    SPEI RECIBIDO.

    Estructura:

        CONCEPTO: DISPOSICION EFE REFERENCIA: 3322101

    Resultado:

        DISPOSICION EFE
    """

    if not is_spei_recibido_movement(
        concepto
    ):

        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bCONCEPTO\s*:\s*"
        r"(.*?)"
        r"\s+REFERENCIA\s*:",
        text,
        re.IGNORECASE,
    )

    if not match:

        return None

    concepto_original = normalize_text(
        match.group(1)
    )

    return (
        concepto_original
        if concepto_original
        else None
    )


def extract_referencia_from_spei_recibido(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la referencia de un SPEI RECIBIDO.

    Estructura:

        REFERENCIA: 3322101 CVE RAST:

    Resultado:

        3322101
    """

    if not is_spei_recibido_movement(
        concepto
    ):

        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bREFERENCIA\s*:\s*"
        r"(.*?)"
        r"\s+CVE\s+RAST\s*:",
        text,
        re.IGNORECASE,
    )

    if not match:

        return None

    referencia = normalize_text(
        match.group(1)
    )

    return referencia or None



# ============================================================
# DISPATCHERS DE CAMPOS EXTRAÍDOS DESDE CONCEPTO
# ============================================================

def extract_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae el beneficiario según el tipo de movimiento.

    Actualmente:

        SPEI RECIBIDO
        ORDEN DE PAGO SPEI
    """

    if is_spei_recibido_movement(
        concepto
    ):

        return extract_beneficiario_from_spei_recibido(
            concepto
        )

    if is_orden_pago_spei_movement(
        concepto
    ):

        return extract_beneficiario_from_orden_pago_spei(
            concepto
        )

    return None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la cuenta del beneficiario.

    Actualmente no se utiliza para:

        SPEI RECIBIDO
        ORDEN DE PAGO SPEI

    porque en ambos casos estamos obteniendo la CLABE
    mediante clabe_beneficiario.
    """

    return None


def extract_clabe_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la CLABE del beneficiario según el tipo
    de movimiento.
    """

    if is_spei_recibido_movement(
        concepto
    ):

        return extract_clabe_beneficiario_from_spei_recibido(
            concepto
        )

    if is_orden_pago_spei_movement(
        concepto
    ):

        return extract_clabe_beneficiario_from_orden_pago_spei(
            concepto
        )

    return None


def extract_concepto_original_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae el concepto original según el tipo
    de movimiento.
    """

    if is_spei_recibido_movement(
        concepto
    ):

        return extract_concepto_original_from_spei_recibido(
            concepto
        )

    if is_orden_pago_spei_movement(
        concepto
    ):

        return extract_concepto_original_from_orden_pago_spei(
            concepto
        )

    return None


def extract_referencia_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la referencia según el tipo
    de movimiento.
    """

    if is_spei_recibido_movement(
        concepto
    ):

        return extract_referencia_from_spei_recibido(
            concepto
        )

    if is_orden_pago_spei_movement(
        concepto
    ):

        return extract_referencia_from_orden_pago_spei(
            concepto
        )

    return None



def extract_clave_rastreo_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la clave de rastreo de movimientos SPEI Banorte.

    Formatos soportados:

        CVE RASTREO: 38432P01202606075396752889
        CVE RAST: 062025101259L0CNKLIYC

    También soporta SPEI RECIBIDO donde la clave aparece
    al inicio del concepto, antes de:

        SPEI RECIBIDO

    Ejemplos:

        062025101259L0CNKLIYC SPEI RECIBIDO, ...
        5902081890317359 SPEI RECIBIDO, ...
        HSBC432658 SPEI RECIBIDO, ...

    Devuelve únicamente la clave de rastreo.
    """

    if not concepto:
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    # --------------------------------------------------------
    # CASO 1:
    #
    # CVE RASTREO: 38432P01202606075396752889
    # CVE RAST: 062025101259L0CNKLIYC
    # --------------------------------------------------------

    match = re.search(
        r"\bCVE\s+RAST(?:REO)?\s*:\s*"
        r"([A-Z0-9_-]+)",
        text,
        re.IGNORECASE,
    )

    if match:

        clave_rastreo = (
            match.group(1)
            .strip()
            .upper()
        )

        return clave_rastreo or None

    # --------------------------------------------------------
    # CASO 2:
    #
    # 062025101259L0CNKLIYC SPEI RECIBIDO, ...
    # HSBC432658 SPEI RECIBIDO, ...
    #
    # Banorte puede colocar la clave directamente antes
    # de la firma SPEI RECIBIDO.
    # --------------------------------------------------------

    if is_spei_recibido_movement(
        concepto
    ):

        first_line = get_first_concepto_line(
            concepto
        )

        if first_line:

            match = re.search(
                r"^\s*"
                r"([A-Z0-9_-]+)"
                r"\s+SPEI\s+RECIBIDO\b",
                first_line,
                re.IGNORECASE,
            )

            if match:

                clave_rastreo = (
                    match.group(1)
                    .strip()
                    .upper()
                )

                return clave_rastreo or None

    return None


def extract_rfc_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    Extrae el RFC según el tipo de movimiento.

    Prioridad:

        1. SPEI RECIBIDO
        2. ORDEN DE PAGO SPEI
        3. MOVIMIENTO GENERAL

    Esto evita que el extractor general interfiera con los
    formatos específicos ya implementados.
    """

    # --------------------------------------------------------
    # SPEI RECIBIDO
    # --------------------------------------------------------

    if is_spei_recibido_movement(
        concepto
    ):
        return extract_rfc_from_spei_recibido(
            concepto
        )

    # --------------------------------------------------------
    # ORDEN DE PAGO SPEI
    # --------------------------------------------------------

    if is_orden_pago_spei_movement(
        concepto
    ):
        return extract_rfc_from_orden_pago_spei(
            concepto
        )

    # --------------------------------------------------------
    # MOVIMIENTO GENERAL
    # --------------------------------------------------------

    return extract_rfc_from_general_concepto(
        concepto
    )


def extract_hora_from_concepto(
    concepto: str,
) -> Optional[str]:

    """
    Extrae la hora de operación según el tipo
    de movimiento.
    """

    if is_spei_recibido_movement(
        concepto
    ):

        return extract_hora_from_spei_recibido(
            concepto
        )

    if is_orden_pago_spei_movement(
        concepto
    ):

        return extract_hora_from_orden_pago_spei(
            concepto
        )

    return None


# ============================================================
# ORDEN DE PAGO SPEI
# ============================================================

def is_orden_pago_spei_movement(
    concepto: str,
) -> bool:
    """
    Determina si el movimiento corresponde a:

        ORDEN DE PAGO SPEI

    El texto puede contener un pequeño prefijo residual
    antes de la expresión debido a la extracción espacial.

    Lo importante es detectar de forma robusta la firma:

        ORDEN DE PAGO SPEI
    """

    first_line = get_first_concepto_line(
        concepto
    )

    if not first_line:
        return False

    text = normalize_text(
        first_line
    )

    return bool(
        re.search(
            r"\bORDEN\s+DE\s+PAGO\s+SPEI\b",
            text,
            re.IGNORECASE,
        )
    )


def extract_referencia_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la referencia de un movimiento
    ORDEN DE PAGO SPEI.

    Ejemplo:

        ORDEN DE PAGO SPEI 0250605 =REFERENCIA ...

    Resultado:

        0250605
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    first_line = get_first_concepto_line(
        concepto
    )

    if not first_line:
        return None

    match = re.search(
        r"\bORDEN\s+DE\s+PAGO\s+SPEI\s+"
        r"([A-Z0-9]+)"
        r"\s*=?\s*REFERENCIA\b",
        first_line,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(
        1
    ).strip() or None


def extract_clabe_beneficiario_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la CLABE/cuenta indicada después de:

        CTA/CLABE:

    Ejemplo:

        CTA/CLABE: 722969010122398083
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bCTA/CLABE\s*:\s*"
        r"(\d{16,18})\b",
        text,
        re.IGNORECASE,
    )

    if not match:

        # Fallback por si el PDF introduce
        # espacios alrededor de la diagonal.

        match = re.search(
            r"\bCTA\s*/\s*CLABE\s*:\s*"
            r"(\d{16,18})\b",
            text,
            re.IGNORECASE,
        )

    if not match:
        return None

    return match.group(
        1
    ).strip() or None


def extract_beneficiario_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae el beneficiario después de:

        BENEF:

    Ejemplos:

        BENEF:NO INGRESADO
        BENEF:Oma
        BENEF:Reward

    Cuando existe:

        (DATO NO VERIF POR ESTA INST)

    se toma todo lo anterior.

    También existe fallback hasta:

        , Pago
        , Pgo
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    # --------------------------------------------------------
    # CASO PRINCIPAL
    # --------------------------------------------------------

    match = re.search(
        r"\bBENEF\s*:\s*"
        r"(.*?)"
        r"\s*\(?\s*DATO\s+NO\s+VERIF\s+POR\s+ESTA\s+INST\s*\)?",
        text,
        re.IGNORECASE,
    )

    if match:

        beneficiario = normalize_text(
            match.group(1)
        )

        return beneficiario or None

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    match = re.search(
        r"\bBENEF\s*:\s*"
        r"(.*?)(?:,\s*(?:PAGO|PGO)\b)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    beneficiario = normalize_text(
        match.group(1)
    )

    return beneficiario or None


def extract_rfc_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae el RFC de un movimiento ORDEN DE PAGO SPEI.

    Ejemplos:

        RFC: ND
        RFC: No capturado
        RFC: ABC123456XYZ

    ND / No capturado no se consideran RFC válido.
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bRFC\s*:\s*"
        r"([A-Z&Ñ0-9]+(?:\s+[A-Z&Ñ0-9]+)?)\b",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    rfc = normalize_text(
        match.group(1)
    )

    if not rfc:
        return None

    if normalize_upper(rfc) in {
        "ND",
        "N D",
        "NO CAPTURADO",
    }:
        return None

    return re.sub(
        r"\s+",
        "",
        rfc,
    ).upper()


def extract_hora_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la hora de liquidación.

    Ejemplos:

        HORA LIQ: 07:37:35
        HORA LIQ: 06:32:05
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\bHORA\s+LIQ\s*:\s*"
        r"((?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(
        1
    ).strip()


def extract_concepto_original_from_orden_pago_spei(
    concepto: str,
) -> Optional[str]:
    """
    Extrae el concepto original del pago.

    Ejemplos:

        ), Pago CVE RASTREO:
        ), Pago 97 CVE RASTREO:
        ), Sin información CVE RASTREO:

    Resultado:

        Pago
        Pago 97
        Sin información
    """

    if not is_orden_pago_spei_movement(
        concepto
    ):
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    match = re.search(
        r"\)\s*,\s*"
        r"(.*?)"
        r"\s+CVE\s+RASTREO\s*:",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    concepto_original = normalize_text(
        match.group(1)
    )

    return concepto_original or None


# ============================================================
# RFC — MOVIMIENTO GENERAL
# ============================================================


def extract_rfc_from_general_concepto(
    concepto: str,
) -> Optional[str]:
    """
    Extrae el RFC de movimientos generales.

    Patrones:

        RFC:NWM 9709244W4
        RFC:MAG 2105031W3
        RFC:DLI 931201MI9

    También:

        AL RFC BMN930209927
    """

    if not concepto:
        return None

    text = normalize_concepto_for_search(
        concepto
    )

    # --------------------------------------------------------
    # CASO:
    #
    # RFC:NWM 9709244W4
    # RFC:MAG 2105031W3
    # RFC:DLI 931201MI9
    # --------------------------------------------------------

    match = re.search(
        r"\bRFC\s*:\s*"
        r"([A-Z&Ñ]{3,4}"
        r"\s*"
        r"\d{6}"
        r"\s*"
        r"[A-Z0-9]{2,3})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        rfc = re.sub(
            r"\s+",
            "",
            match.group(1),
        ).upper()

        if rfc:
            return rfc

    # --------------------------------------------------------
    # CASO:
    #
    # AL RFC BMN930209927
    # --------------------------------------------------------

    match = re.search(
        r"\bAL\s+RFC\s+"
        r"([A-Z&Ñ]{3,4}"
        r"\s*"
        r"\d{6}"
        r"\s*"
        r"[A-Z0-9]{2,3})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        rfc = re.sub(
            r"\s+",
            "",
            match.group(1),
        ).upper()

        if rfc:
            return rfc

    return None




# ============================================================
# TIPO DE OPERACIÓN
# ============================================================

def extract_tipo_operacion(
    deposito: float,
    retiro: float,
) -> Optional[str]:

    """
    Determina el tipo directamente desde la columna monetaria.

        deposito > 0 -> ABONO
        retiro > 0   -> CARGO
    """

    if retiro > 0:

        return "CARGO"

    if deposito > 0:

        return "ABONO"

    return None


# ============================================================
# CONSTRUCCIÓN DEL MOVIMIENTO
# ============================================================

def build_movimiento(
    block: List[
        List[
            Dict[str, Any]
        ]
    ],
    config: ColumnConfig,
) -> Optional[Movimiento]:

    """
    Construye un Movimiento a partir de un bloque espacial.
    """

    if not block:

        return None

    first_line = block[0]

    fecha = extract_date_from_line(
        first_line
    )

    if fecha is None:

        return None

    # --------------------------------------------------------
    # SALDO ANTERIOR
    # --------------------------------------------------------

    if is_saldo_anterior(
        first_line,
        config,
    ):

        return None

    # --------------------------------------------------------
    # CONCEPTO
    # --------------------------------------------------------

    concepto = extract_concepto(
        block,
        config,
    )

    # --------------------------------------------------------
    # IMPORTES
    # --------------------------------------------------------

    deposito = extract_amount_from_block(
        block=block,
        column=config.deposito,
    )

    retiro = extract_amount_from_block(
        block=block,
        column=config.retiro,
    )

    saldo = extract_amount_from_block(
        block=block,
        column=config.saldo,
    )

    # --------------------------------------------------------
    # TIPO
    # --------------------------------------------------------

    tipo_operacion = extract_tipo_operacion(
        deposito=deposito,
        retiro=retiro,
    )

    # --------------------------------------------------------
    # CAMPOS DERIVADOS DEL CONCEPTO
    # --------------------------------------------------------

    referencia = extract_referencia_from_concepto(
        concepto
    )

    clave_rastreo = extract_clave_rastreo_from_concepto(
        concepto
    )


    beneficiario = extract_beneficiario_from_concepto(
        concepto
    )

    cuenta_beneficiario = (
        extract_cuenta_beneficiario_from_concepto(
            concepto
        )
    )

    clabe_beneficiario = (
        extract_clabe_beneficiario_from_concepto(
            concepto
        )
    )

    concepto_original = (
        extract_concepto_original_from_concepto(
            concepto
        )
    )

    rfc = extract_rfc_from_concepto(
        concepto
    )

    hora = extract_hora_from_concepto(
        concepto
    )

    # --------------------------------------------------------
    # VALIDACIÓN MÍNIMA
    # --------------------------------------------------------

    if (
        deposito == 0.0
        and retiro == 0.0
        and saldo == 0.0
        and not concepto
    ):

        return None

    # --------------------------------------------------------
    # OBJETO FINAL
    # --------------------------------------------------------

    return Movimiento(

        fecha_operacion=(
            fecha
        ),

        fecha_liquidacion=(
            None
        ),

        concepto=(
            concepto
        ),

        tipo_operacion=(
            tipo_operacion
        ),

        cargo=(
            retiro
        ),

        abono=(
            deposito
        ),

        referencia=(
            referencia
        ),

        clave_rastreo=(
            clave_rastreo
        ),

        autorizacion=(
            None
        ),

        beneficiario=(
            beneficiario
        ),

        cuenta_beneficiario=(
            cuenta_beneficiario
        ),

        clabe_beneficiario=(
            clabe_beneficiario
        ),

        rfc=(
            rfc
        ),

        sucursal=(
            None
        ),

        caja=(
            None
        ),

        hora_operacion=(
            hora
        ),

        saldo_operacion=(
            saldo
        ),

        saldo_liquidacion=(
            0.0
        ),

        concepto_original=(
            concepto_original
        ),

    )


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================

def extract_movimientos_words(
    words: List[
        Dict[str, Any]
    ],
) -> List[Movimiento]:

    """
    Extractor espacial principal de movimientos BANORTE.
    """

    if not words:

        return []

    # --------------------------------------------------------
    # ELIMINAR PIE DE PAGINA
    # --------------------------------------------------------

    words = remove_banorte_footer(
        words
    )

    # --------------------------------------------------------
    # ELIMINAR TODO DESPUÉS DEL ULTIMO MOVIMIENTO
    # --------------------------------------------------------

    words = remove_after_last_movement(
        words
    )

    # --------------------------------------------------------
    # 1. LIMITAR SECCIONES POSTERIORES
    # --------------------------------------------------------

    words = truncate_after_marker(
        words
    )

    if not words:

        return []

    # --------------------------------------------------------
    # 2. AGRUPAR PALABRAS EN LÍNEAS
    # --------------------------------------------------------

    lines = group_words_into_lines(
        words
    )

    if not lines:

        return []

    # --------------------------------------------------------
    # 3. CONFIGURACIÓN ESPACIAL
    # --------------------------------------------------------

    config = build_default_config()

    # --------------------------------------------------------
    # 4. CONSTRUIR BLOQUES
    # --------------------------------------------------------

    blocks = build_movement_blocks(
        lines=lines,
        config=config,
    )

    if not blocks:

        return []

    # --------------------------------------------------------
    # 5. CONSTRUIR MOVIMIENTOS
    # --------------------------------------------------------

    movimientos: List[
        Movimiento
    ] = []

    for block in blocks:

        movimiento = build_movimiento(
            block=block,
            config=config,
        )

        if movimiento is None:

            continue

        movimientos.append(
            movimiento
        )

    return movimientos