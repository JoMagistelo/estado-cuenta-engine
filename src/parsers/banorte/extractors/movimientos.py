from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.movimiento import Movimiento
from parsers.banorte.utils.words_after_last_movement import remove_after_last_movement
from parsers.banorte.utils.words_footer_filter import remove_banorte_footer



# ============================================================
# EXTRACTOR ESPACIAL — MOVIMIENTOS BANORTE
# ============================================================
#
# Layout observado:
#
#   FECHA
#   DESCRIPCIÓN / ESTABLECIMIENTO
#   MONTO DEL DEPÓSITO
#   MONTO DEL RETIRO
#   SALDO
#
# El parser trabaja exclusivamente mediante coordenadas
# espaciales para separar las columnas.
#
# Características particulares del PDF BANORTE:
#
#   1. La fecha y el primer fragmento del concepto pueden
#      venir físicamente unidos:
#
#          02-JUN-25OXXOLAS
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
#
# Coordenadas observadas:
#
# FECHA
#     aproximadamente x=53 → 84
#
# DESCRIPCIÓN / ESTABLECIMIENTO
#     aproximadamente x=84 → 352
#
# MONTO DEL DEPÓSITO
#     aproximadamente x=353 → 428
#
# MONTO DEL RETIRO
#     aproximadamente x=429 → 520
#
# SALDO
#     aproximadamente x=521 → 566
#
# IMPORTANTE:
#
# Los límites se construyen como regiones de columna y no
# como distancia respecto al centro de la cabecera.
#
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
#
# Banorte puede entregar:
#
#     02-JUN-25
#
# pegado al concepto:
#
#     02-JUN-25OXXOLAS
#
# Por ello usamos match sobre el INICIO del texto.
#
# ============================================================

DATE_PREFIX_PATTERN = re.compile(
    r"^"
    r"(?P<date>"
    r"\d{1,2}"
    r"-"
    r"[A-ZÁÉÍÓÚÑ]{3}"
    r"-"
    r"\d{2,4}"
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

    Esto hace el extractor más tolerante a:
        - palabras anchas
        - pequeños desplazamientos
        - diferencias de renderizado
        - límites de columna
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

    Es suficientemente tolerante para el espaciado observado
    en BANORTE.
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

    Ejemplo:

        FECHA
        DESCRIPCIÓN / ESTABLECIMIENTO
        MONTO DEL DEPOSITO
        MONTO DEL RETIRO
        SALDO
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

    Para importes se utiliza una función específica basada en
    x1.
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

    Esto es deliberado.

    Los importes BANORTE están alineados hacia la derecha:

        255.00
        350.00
        40.00

    por lo que X1 es una señal mucho más estable que el centro.
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

    El importe puede encontrarse en:
        - la línea principal
        - una línea posterior

    Se conserva el último importe que pertenezca a la columna.

    En el patrón observado, esto permite obtener correctamente
    el valor asociado a la operación completa.
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

    Soporta casos como:

        02-JUN-25
        02-JUN-2025
        02-JUN-25OXXOLAS
        31-MAY-25SALDO
        06-JUN-25036CLAR...
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

    En BANORTE normalmente está en la primera palabra:
        02-JUN-25OXXOLAS
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

    No requiere que toda la palabra sea una fecha.
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
    Elimina únicamente el prefijo de fecha de una cadena.

    Ejemplo:

        02-JUN-25OXXOLAS
        ↓
        OXXOLAS
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

    La descripción BANORTE puede contener datos adicionales:

        OXXOLAS
        VEGAS
        TRC
        RFC:CCO
        ...
    
    De momento TODOS esos elementos permanecen dentro de
    concepto_original/concepto.

    Únicamente eliminamos el prefijo de fecha de la primera
    línea del movimiento.
    """

    selected = words_in_column(
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

    Cada línea se conserva.

    NO intenta extraer todavía:
        - referencia
        - beneficiario
        - RFC
        - autorización
        - CLABE
        - cuenta
        - sucursal
        - caja
        - hora

    Esas funciones quedan preparadas para una siguiente etapa.
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

    NO elimina líneas internas de movimientos.
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

    No depende de una utilidad externa para evitar acoplar
    este parser a filtros de BANAMEX.
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
            word_top(word)
            < cutoff_y
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

    Esto permite manejar:

        línea principal
        detalle SPEI
        cliente
        CLABE
        referencia
        beneficiario
        RFC
        etc.

    aunque todo eso aparezca en varias líneas.
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

        # No procesamos páginas previas al bloque de movimientos.
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
# FUNCIONES PREPARADAS — CONCEPTO
# ============================================================
#
# De momento NO extraemos estas variables.
#
# Se deja la API preparada para una siguiente iteración.
#
# ============================================================


def extract_referencia_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO.

    Futuramente puede extraer:
        REFERENCIA:
        REFERENCIA
        etc.
    """

    return None


def extract_autorizacion_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO.

    Futuramente puede extraer:
        AUT
        AUT:
        AUT-
        etc.
    """

    return None


def extract_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

    return None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.

    Posibles fuentes:
        CTA/CLABE:
        CUENTA:
        CTA:
    """

    return None


def extract_clabe_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

    return None


def extract_rfc_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

    return None


def extract_sucursal_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

    return None


def extract_caja_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

    return None


def extract_hora_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    PREPARADO PARA FUTURA IMPLEMENTACIÓN.
    """

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

    BANORTE tiene una ventaja importante:
    no necesitamos inferirlo inicialmente desde el concepto.

        deposito > 0  -> ABONO
        retiro > 0    -> CARGO
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
    # VARIABLES PREPARADAS
    # --------------------------------------------------------

    referencia = (
        extract_referencia_from_concepto(
            concepto
        )
    )

    autorizacion = (
        extract_autorizacion_from_concepto(
            concepto
        )
    )

    beneficiario = (
        extract_beneficiario_from_concepto(
            concepto
        )
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

    rfc = (
        extract_rfc_from_concepto(
            concepto
        )
    )

    sucursal = (
        extract_sucursal_from_concepto(
            concepto
        )
    )

    caja = (
        extract_caja_from_concepto(
            concepto
        )
    )

    hora = (
        extract_hora_from_concepto(
            concepto
        )
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

        autorizacion=(
            autorizacion
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
            sucursal
        ),

        caja=(
            caja
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
            concepto
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