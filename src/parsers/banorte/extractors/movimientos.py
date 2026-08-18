from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


from models.movimiento import Movimiento
from parsers.banamex.utils.words_header_filter import remove_banamex_header
from parsers.banamex.utils.words_grafico_filter import remove_after_grafico_transaccional

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
#
# BANAMEX
#
# Tabla:
#
#     FECHA | CONCEPTO | RETIROS | DEPOSITOS | SALDO
#
# IMPORTANTE:
#
# Las palabras del concepto NO necesariamente están cerca del
# centro horizontal de la palabra "CONCEPTO".
#
# Por ejemplo:
#
#     DEPOSITO
#     POR
#     RETIRO
#     DE
#     AHORRO
#     A
#     LA
#     VISTA
#
# empiezan alrededor de x=57.
#
# Por ello utilizamos LÍMITES DE COLUMNA y no distancia al
# centro de la cabecera.
#
# ============================================================


PAGE_MOVIMIENTOS = 2


# ============================================================
# TOLERANCIAS
# ============================================================


LINE_Y_TOLERANCE = 3.5

COLUMN_TOLERANCE = 6.0


# ============================================================
# CONFIGURACIÓN BASE DE LA TABLA OBSERVADA
# ============================================================


DEFAULT_COLUMN_BOUNDS = {
    "FECHA": (
        8.0,
        52.0,
    ),

    "CONCEPTO": (
        52.0,
        255.0,
    ),

    "RETIROS": (
        255.0,
        324.0,
    ),

    "DEPOSITOS": (
        324.0,
        408.0,
    ),

    "SALDO": (
        408.0,
        490.0,
    ),
}


# ============================================================
# HEADER
# ============================================================


HEADER_NAMES = {
    "FECHA",
    "CONCEPTO",
    "RETIROS",
    "DEPOSITOS",
    "SALDO",
}


# ============================================================
# REGEX
# ============================================================


DATE_PATTERN = re.compile(
    r"""
    ^
    (?:
        \d{1,2}\s+[A-ZÁÉÍÓÚÑ]{3,9}
        |
        \d{1,2}/[A-ZÁÉÍÓÚÑ]{3,9}
        |
        \d{1,2}-[A-ZÁÉÍÓÚÑ]{3,9}
        |
        \d{1,2}\s+[A-ZÁÉÍÓÚÑ]{3,9}\s+\d{4}
        |
        \d{1,2}/[A-ZÁÉÍÓÚÑ]{3,9}/\d{4}
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


MONEY_PATTERN = re.compile(
    r"""
    ^
    [+-]?
    \(?
    \$?
    \d{1,3}
    (?:,\d{3})*
    (?:\.\d{2})?
    \)?
    $
    """,
    re.VERBOSE,
)


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
    r"\b([01]?\d|2[0-3]):[0-5]\d\b"
)


AUTH_PATTERN = re.compile(
    r"""
    \b
    AUT
    \s*[:#-]?
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
    \s*[:#-]?
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
    \s*[:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CLABE_PATTERN = re.compile(
    r"(?<!\d)(\d{18})(?!\d)"
)


# ============================================================
# ESTRUCTURA DE CONFIGURACIÓN
# ============================================================


@dataclass
class ColumnConfig:
    """
    Define los límites espaciales de cada columna.

    A diferencia de la implementación anterior, no usamos un
    centro y una tolerancia pequeña.

    Usamos una región real.
    """

    fecha: tuple[float, float]

    concepto: tuple[float, float]

    retiros: tuple[float, float]

    depositos: tuple[float, float]

    saldo: tuple[float, float]


# ============================================================
# NORMALIZACIÓN
# ============================================================


def normalize_text(
    value: str,
) -> str:

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
    value: str,
) -> str:

    return normalize_text(
        value
    ).upper()


# ============================================================
# COORDENADAS
# ============================================================


def word_center_x(
    word: Dict[str, Any],
) -> float:

    x0 = float(
        word.get("x0", 0)
        or 0
    )

    x1 = float(
        word.get("x1", x0)
        or x0
    )

    return (x0 + x1) / 2


def word_center_y(
    word: Dict[str, Any],
) -> float:

    top = float(
        word.get("top", 0)
        or 0
    )

    bottom = float(
        word.get(
            "bottom",
            top,
        )
        or top
    )

    return (top + bottom) / 2


def word_height(
    word: Dict[str, Any],
) -> float:

    top = float(
        word.get("top", 0)
        or 0
    )

    bottom = float(
        word.get(
            "bottom",
            top,
        )
        or top
    )

    return abs(
        bottom - top
    )


# ============================================================
# AGRUPACIÓN DE LÍNEAS
# ============================================================


def group_words_into_lines(
    words: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:

    if not words:

        return []

    words = sorted(
        words,
        key=lambda word: (
            word.get("page", 1),
            word_center_y(word),
            word.get("x0", 0),
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
        List[Dict[str, Any]]
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

            current.append(
                word
            )

            current_y = sum(
                word_center_y(item)
                for item in current
            ) / len(current)

        else:

            current.sort(
                key=lambda item: item.get(
                    "x0",
                    0,
                )
            )

            lines.append(
                current
            )

            current = [word]

            current_page = page

            current_y = y

    if current:

        current.sort(
            key=lambda item: item.get(
                "x0",
                0,
            )
        )

        lines.append(
            current
        )

    return lines


# ============================================================
# TEXTO DE LÍNEA
# ============================================================


def line_text(
    line: List[Dict[str, Any]],
) -> str:

    values = []

    for word in sorted(
        line,
        key=lambda item: item.get(
            "x0",
            0,
        ),
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


def find_word(
    line: List[Dict[str, Any]],
    expected: str,
) -> Optional[Dict[str, Any]]:

    expected = normalize_upper(
        expected
    )

    for word in line:

        text = normalize_upper(
            word.get(
                "text",
                "",
            )
        )

        if text == expected:

            return word

    return None


def is_movements_header(
    line: List[Dict[str, Any]],
) -> bool:

    found = 0

    for name in HEADER_NAMES:

        if find_word(
            line,
            name,
        ):

            found += 1

    return found >= 4


def detect_header(
    line: List[Dict[str, Any]],
) -> Optional[Dict[str, Dict[str, float]]]:

    if not is_movements_header(
        line
    ):

        return None

    result = {}

    for name in HEADER_NAMES:

        word = find_word(
            line,
            name,
        )

        if word is None:

            continue

        result[name] = {
            "x0": float(
                word.get(
                    "x0",
                    0,
                )
                or 0
            ),
            "x1": float(
                word.get(
                    "x1",
                    0,
                )
                or 0
            ),
        }

    return result


# ============================================================
# CONSTRUCCIÓN DE COLUMNAS
# ============================================================


def build_default_config() -> ColumnConfig:

    return ColumnConfig(
        fecha=DEFAULT_COLUMN_BOUNDS[
            "FECHA"
        ],

        concepto=DEFAULT_COLUMN_BOUNDS[
            "CONCEPTO"
        ],

        retiros=DEFAULT_COLUMN_BOUNDS[
            "RETIROS"
        ],

        depositos=DEFAULT_COLUMN_BOUNDS[
            "DEPOSITOS"
        ],

        saldo=DEFAULT_COLUMN_BOUNDS[
            "SALDO"
        ],
    )


def build_config_from_header(
    header: Dict[str, Dict[str, float]],
) -> ColumnConfig:
    """
    Construye regiones espaciales a partir del encabezado.

    Para FECHA y CONCEPTO se utilizan regiones normales.

    Para RETIROS, DEPOSITOS y SALDO se construyen fronteras
    NO SOLAPADAS usando los centros de los encabezados.

    Los importes posteriormente se asignan utilizando x1,
    porque los números están alineados hacia la derecha.
    """

    fallback = build_default_config()

    # --------------------------------------------------------
    # FECHA
    # --------------------------------------------------------

    fecha = fallback.fecha

    # --------------------------------------------------------
    # RETIROS / DEPOSITOS / SALDO
    # --------------------------------------------------------

    retiros = fallback.retiros

    depositos = fallback.depositos

    saldo = fallback.saldo

    if (
        "RETIROS" in header
        and "DEPOSITOS" in header
        and "SALDO" in header
    ):

        retiros_center = (
            header["RETIROS"]["x0"]
            + header["RETIROS"]["x1"]
        ) / 2.0

        depositos_center = (
            header["DEPOSITOS"]["x0"]
            + header["DEPOSITOS"]["x1"]
        ) / 2.0

        saldo_center = (
            header["SALDO"]["x0"]
            + header["SALDO"]["x1"]
        ) / 2.0

        retiros_depositos_boundary = (
            retiros_center
            + depositos_center
        ) / 2.0

        depositos_saldo_boundary = (
            depositos_center
            + saldo_center
        ) / 2.0

        retiros = (
            fallback.retiros[0],
            retiros_depositos_boundary,
        )

        depositos = (
            retiros_depositos_boundary,
            depositos_saldo_boundary,
        )

        saldo = (
            depositos_saldo_boundary,
            fallback.saldo[1],
        )

    # --------------------------------------------------------
    # CONCEPTO
    # --------------------------------------------------------

    concepto = fallback.concepto

    if (
        "FECHA" in header
        and "RETIROS" in header
    ):

        fecha_right = (
            header["FECHA"]["x1"]
        )

        retiros_left = (
            header["RETIROS"]["x0"]
        )

        concepto = (
            fecha_right + 5.0,
            retiros_left - 5.0,
        )

    return ColumnConfig(
        fecha=fecha,

        concepto=concepto,

        retiros=retiros,

        depositos=depositos,

        saldo=saldo,
    )


# ============================================================
# CONFIGURACIÓN POR PÁGINA
# ============================================================


def build_page_configs(
    lines: List[List[Dict[str, Any]]],
) -> Dict[int, ColumnConfig]:

    configs: Dict[
        int,
        ColumnConfig
    ] = {}

    default = build_default_config()

    for line in lines:

        if not line:

            continue

        header = detect_header(
            line
        )

        if header is None:

            continue

        page = int(
            line[0].get(
                "page",
                1,
            )
        )

        config = build_config_from_header(
            header
        )

        if config is None:

            config = default

        configs[
            page
        ] = config

    return configs


def get_config(
    page: int,
    configs: Dict[int, ColumnConfig],
) -> ColumnConfig:

    if page in configs:

        return configs[
            page
        ]

    return build_default_config()


# ============================================================
# PERTENENCIA A COLUMNA
# ============================================================


def word_inside_column(
    word: Dict[str, Any],
    column: tuple[float, float],
) -> bool:

    center = word_center_x(
        word
    )

    xmin, xmax = column

    return (
        xmin - COLUMN_TOLERANCE
        <= center
        <= xmax + COLUMN_TOLERANCE
    )


def words_in_column(
    line: List[Dict[str, Any]],
    column: tuple[float, float],
) -> List[Dict[str, Any]]:

    result = []

    for word in line:

        if word_inside_column(
            word,
            column,
        ):

            result.append(
                word
            )

    result.sort(
        key=lambda item: item.get(
            "x0",
            0,
        )
    )

    return result


def column_text(
    line: List[Dict[str, Any]],
    column: tuple[float, float],
) -> str:

    selected = words_in_column(
        line=line,
        column=column,
    )

    values = []

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
# PERTENENCIA DE IMPORTES
# ============================================================


def money_word_inside_column(
    word: Dict[str, Any],
    column: tuple[float, float],
) -> bool:
    """
    Determina si un importe pertenece a una columna utilizando
    su borde derecho x1.

    Esto es importante porque los importes monetarios están
    alineados hacia la derecha.

    Ejemplo:

        350.00
        1,234,567.89

    pueden tener x1 prácticamente igual aunque x0 cambie mucho.
    """

    x1 = float(
        word.get(
            "x1",
            word.get(
                "x0",
                0,
            ),
        )
        or 0
    )

    xmin, xmax = column

    return (
        xmin <= x1 <= xmax
    )


# ============================================================
# EXTRACCIÓN DE COLUMNAS
# ============================================================


def extract_fecha_operacion(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> str:

    return column_text(
        line,
        config.fecha,
    )


def extract_concepto(
    block: List[
        List[Dict[str, Any]]
    ],
    configs: Dict[int, ColumnConfig],
) -> str:

    result = []

    for line in block:

        if not line:

            continue

        page = int(
            line[0].get(
                "page",
                1,
            )
        )

        config = get_config(
            page,
            configs,
        )

        text = column_text(
            line,
            config.concepto,
        )

        if text:

            result.append(
                text
            )

    return "\n".join(
        result
    ).strip()


def is_money(
    text: str,
) -> bool:

    return bool(
        MONEY_PATTERN.fullmatch(
            normalize_text(text)
        )
    )


def parse_amount(
    text: str,
) -> float:

    if not text:

        return 0.0

    value = (
        normalize_text(text)
        .replace("$", "")
        .replace(",", "")
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


def extract_amount_from_block(
    block: List[
        List[Dict[str, Any]]
    ],
    column_name: str,
    configs: Dict[int, ColumnConfig],
) -> float:
    """
    Busca importes en TODAS las líneas del movimiento.

    El importe puede aparecer varias líneas debajo de la fecha.

    La pertenencia a columna se determina por x1 del importe,
    no por el centro de la palabra.
    """

    candidates = []

    for line_index, line in enumerate(
        block
    ):

        if not line:

            continue

        page = int(
            line[0].get(
                "page",
                1,
            )
        )

        config = get_config(
            page,
            configs,
        )

        current_column = getattr(
            config,
            column_name,
        )

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
                current_column,
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

    # El último importe válido de esa columna es el más
    # probable, porque las líneas superiores pueden contener
    # textos/valores auxiliares.
    _, word = candidates[-1]

    return parse_amount(
        word.get(
            "text",
            "",
        )
    )


def extract_cargo(
    block,
    configs: Dict[int, ColumnConfig],
) -> float:

    return extract_amount_from_block(
        block,
        "retiros",
        configs,
    )


def extract_abono(
    block,
    configs: Dict[int, ColumnConfig],
) -> float:

    return extract_amount_from_block(
        block,
        "depositos",
        configs,
    )


def extract_saldo(
    block,
    configs: Dict[int, ColumnConfig],
) -> float:

    return extract_amount_from_block(
        block,
        "saldo",
        configs,
    )


# ============================================================
# FECHA
# ============================================================


def is_date_text(
    text: str,
) -> bool:

    text = normalize_upper(
        text
    )

    if not text:

        return False

    if DATE_PATTERN.fullmatch(
        text
    ):

        return True

    parts = text.split()

    if len(parts) == 2:

        day = parts[0]

        month = parts[1][:3]

        if (
            day.isdigit()
            and month
            in {
                "ENE",
                "FEB",
                "MAR",
                "ABR",
                "MAY",
                "JUN",
                "JUL",
                "AGO",
                "SEP",
                "OCT",
                "NOV",
                "DIC",
            }
            and 1
            <= int(day)
            <= 31
        ):

            return True

    return False


def is_start_movement(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> bool:

    fecha = extract_fecha_operacion(
        line,
        config,
    )

    return is_date_text(
        fecha
    )


# ============================================================
# SALDO ANTERIOR
# ============================================================


def is_saldo_anterior(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> bool:

    concepto = normalize_upper(
        column_text(
            line,
            config.concepto,
        )
    )

    return (
        "SALDO ANTERIOR"
        in concepto
    )


# ============================================================
# HEADER / TÍTULOS
# ============================================================


def should_skip_line(
    line: List[Dict[str, Any]],
) -> bool:

    if not line:

        return True

    text = normalize_upper(
        line_text(line)
    )

    if not text:

        return True

    if (
        "DETALLE DE OPERACIONES"
        in text
    ):

        return True

    if is_movements_header(
        line
    ):

        return True

    return False


# ============================================================
# BLOQUES
# ============================================================


def build_blocks(
    lines: List[
        List[Dict[str, Any]]
    ],
    configs: Dict[int, ColumnConfig],
) -> List[
    List[
        List[Dict[str, Any]]
    ]
]:

    blocks = []

    current = []

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

        config = get_config(
            page,
            configs,
        )

        if is_start_movement(
            line,
            config,
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
# CONCEPTO → DATOS ESTRUCTURADOS
# ============================================================


def extract_referencia_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    patterns = (
        r"\bREFERENCIA\s*[:#-]?\s*([A-Z0-9*_-]+)",
        r"\bREF\s*[:#-]?\s*([A-Z0-9*_-]+)",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            concepto,
            re.IGNORECASE,
        )

        if match:

            value = (
                match.group(
                    1
                )
                .strip()
            )

            if value:

                return value

    match = re.search(
        r"(?<!\S)(\*{2,}[A-Z0-9_-]+)",
        concepto,
        re.IGNORECASE,
    )

    if match:

        return match.group(
            1
        )

    return None


def extract_auth_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = AUTH_PATTERN.search(
        concepto
    )

    if match:

        return match.group(
            1
        ).strip()

    return None


def extract_hora_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    explicit = re.search(
        r"\bHORA\s*[:#-]?\s*([01]?\d|2[0-3]):[0-5]\d\b",
        concepto,
        re.IGNORECASE,
    )

    if explicit:

        return TIME_PATTERN.search(
            explicit.group(0)
        ).group(0)

    match = TIME_PATTERN.search(
        concepto
    )

    if match:

        return match.group(0)

    return None


def extract_rfc_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = RFC_PATTERN.search(
        concepto
    )

    if not match:

        return None

    return (
        match.group(
            1
        )
        .replace(" ", "")
        .upper()
    )


def extract_sucursal_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = SUC_PATTERN.search(
        concepto
    )

    if match:

        return match.group(
            1
        ).strip()

    return None


def extract_caja_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = CAJA_PATTERN.search(
        concepto
    )

    if match:

        return match.group(
            1
        ).strip()

    return None


def extract_clabe_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = CLABE_PATTERN.search(
        concepto
    )

    if match:

        return match.group(
            1
        )

    return None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    patterns = (
        r"\bCUENTA\s*[:#-]?\s*(\d{4,20})\b",
        r"\bCTA\s*[:#-]?\s*(\d{4,20})\b",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            concepto,
            re.IGNORECASE,
        )

        if match:

            return match.group(
                1
            )

    return None


def extract_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:

    if not concepto:

        return None

    match = re.search(
        r"\bBENEFICIARIO\s*[:#-]?\s*(.+)",
        concepto,
        re.IGNORECASE,
    )

    if match:

        value = normalize_text(
            match.group(
                1
            )
        )

        return (
            value
            if value
            else None
        )

    match = re.search(
        r"\bA\s+FAVOR\s+DE\s+(.+)",
        concepto,
        re.IGNORECASE,
    )

    if match:

        value = normalize_text(
            match.group(
                1
            )
        )

        return (
            value
            if value
            else None
        )

    return None


# ============================================================
# TIPO OPERACIÓN
# ============================================================


def extract_tipo_operacion(
    cargo: float,
    abono: float,
    concepto: str,
) -> Optional[str]:

    if cargo > 0:

        return "CARGO"

    if abono > 0:

        return "ABONO"

    texto = normalize_upper(
        concepto
    )

    if any(
        word in texto
        for word in (
            "DEPOSITO",
            "DEPÓSITO",
            "ABONO",
            "TRANSFERENCIA RECIBIDA",
            "TRASPASO RECIBIDO",
        )
    ):

        return "ABONO"

    if any(
        word in texto
        for word in (
            "RETIRO",
            "CARGO",
            "PAGO",
            "TRANSFERENCIA ENVIADA",
            "TRASPASO ENVIADO",
        )
    ):

        return "CARGO"

    return None


# ============================================================
# CONSTRUCTOR
# ============================================================


def build_movimiento(
    block: List[
        List[Dict[str, Any]]
    ],
    configs: Dict[int, ColumnConfig],
) -> Optional[Movimiento]:

    if not block:

        return None

    first_line = block[0]

    first_page = int(
        first_line[0].get(
            "page",
            PAGE_MOVIMIENTOS,
        )
    )

    config = get_config(
        first_page,
        configs,
    )

    # --------------------------------------------------------
    # SALDO ANTERIOR NO ES MOVIMIENTO
    # --------------------------------------------------------

    if is_saldo_anterior(
        first_line,
        config,
    ):

        return None

    # --------------------------------------------------------
    # CONCEPTO COMPLETO
    # --------------------------------------------------------

    concepto = extract_concepto(
        block,
        configs,
    )

    # --------------------------------------------------------
    # IMPORTES
    # --------------------------------------------------------

    cargo = extract_cargo(
        block,
        configs,
    )

    abono = extract_abono(
        block,
        configs,
    )

    saldo = extract_saldo(
        block,
        configs,
    )

    # --------------------------------------------------------
    # CAMPOS DERIVADOS
    # --------------------------------------------------------

    tipo = extract_tipo_operacion(
        cargo,
        abono,
        concepto,
    )

    referencia = (
        extract_referencia_from_concepto(
            concepto
        )
    )

    autorizacion = (
        extract_auth_from_concepto(
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

    fecha_operacion = (
        extract_fecha_operacion(
            first_line,
            config,
        )
    )

    # --------------------------------------------------------
    # MOVIMIENTO
    # --------------------------------------------------------

    return Movimiento(

        fecha_operacion=
            fecha_operacion,

        fecha_liquidacion=None,

        concepto=
            concepto,

        tipo_operacion=
            tipo,

        cargo=
            cargo,

        abono=
            abono,

        referencia=
            referencia,

        autorizacion=
            autorizacion,

        beneficiario=
            beneficiario,

        cuenta_beneficiario=
            cuenta_beneficiario,

        clabe_beneficiario=
            clabe_beneficiario,

        rfc=
            rfc,

        sucursal=
            sucursal,

        caja=
            caja,

        hora_operacion=
            hora,

        saldo_operacion=
            saldo,

        saldo_liquidacion=
            0.0,

        concepto_original=
            concepto,
    )


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================


def extract_movimientos_words(
    words: List[
        Dict[str, Any]
    ],
) -> List[Movimiento]:

    if not words:

        return []


    # --------------------------------------------------------
    # ELIMINAR TODO DESPUÉS DE GRAFICO TRANSACCIONAL (2DA TABLA DE MOVIMIENTOS)
    # --------------------------------------------------------

    words = remove_after_grafico_transaccional(
        words
    )


    # --------------------------------------------------------
    # 0. ELIMINAR ENCABEZADO INSTITUCIONAL BANAMEX
    # --------------------------------------------------------

    words = remove_banamex_header(
        words
    )


    # --------------------------------------------------------
    # 1. AGRUPAR PALABRAS EN LÍNEAS
    # --------------------------------------------------------

    lines = group_words_into_lines(
        words
    )

    if not lines:

        return []

    # --------------------------------------------------------
    # 2. DETECTAR CONFIGURACIÓN POR PÁGINA
    # --------------------------------------------------------

    configs = build_page_configs(
        lines
    )

    if not configs:

        default = (
            build_default_config()
        )

        pages = {
            int(
                line[0].get(
                    "page",
                    1,
                )
            )
            for line in lines
            if line
        }

        for page in pages:

            configs[
                page
            ] = default

    # --------------------------------------------------------
    # 3. CONSTRUIR BLOQUES
    # --------------------------------------------------------

    blocks = build_blocks(
        lines,
        configs,
    )

    if not blocks:

        return []

    # --------------------------------------------------------
    # 4. CONSTRUIR MOVIMIENTOS
    # --------------------------------------------------------

    movimientos = []

    for block in blocks:

        movimiento = build_movimiento(
            block,
            configs,
        )

        if movimiento is None:

            continue

        if (
            movimiento.cargo == 0.0
            and movimiento.abono == 0.0
            and movimiento.saldo_operacion == 0.0
        ):

            continue

        movimientos.append(
            movimiento
        )

    return movimientos