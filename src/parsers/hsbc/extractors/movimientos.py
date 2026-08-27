from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento

from parsers.hsbc.utils.words_footer_filter import (
    filter_hsbc_footer_words,
)


# ============================================================
# CONFIGURACIÓN ESPACIAL — MOVIMIENTOS HSBC
# ============================================================
#
# Layout observado:
#
# Día
#     x ≈ 42 ... 55
#
# Descripción
#     x ≈ 60 ... 190
#
# Referencia / Serial
#     región ≈ 280 ... 340
#
# Retiro / Cargo
#     x ≈ 350 ... 405
#
# Depósito / Abono
#     x ≈ 420 ... 505
#
# Saldo
#     x ≈ 520 ... 570
#
# IMPORTANTE:
#
# Las cajas son referencias espaciales.
#
# No se consideran posiciones absolutas rígidas.
#
# ============================================================


BOX_DAY = (
    35.0,
    60.0,
    0.0,
    900.0,
)


BOX_CONCEPTO = (
    55.0,
    190.0,
    0.0,
    900.0,
)


# ------------------------------------------------------------
# REFERENCIA / SERIAL
#
# Esta es una zona estructural, no simplemente una columna.
#
# En el layout observado aparecen dos datos verticales:
#
#     dato superior
#     dato inferior
#
# El dato que nos interesa como referencia es el SEGUNDO
# renglón lógico.
# ------------------------------------------------------------

BOX_REFERENCIA_SERIAL = (
    280.0,
    345.0,
    0.0,
    900.0,
)


BOX_SERIAL = (
    290.0,
    345.0,
    0.0,
    900.0,
)


BOX_REFERENCIA = (
    280.0,
    345.0,
    0.0,
    900.0,
)


BOX_CARGO = (
    345.0,
    415.0,
    0.0,
    900.0,
)


BOX_ABONO = (
    420.0,
    505.0,
    0.0,
    900.0,
)


BOX_SALDO = (
    515.0,
    575.0,
    0.0,
    900.0,
)


# ============================================================
# TOLERANCIAS
# ============================================================


LINE_Y_TOLERANCE = 5.0

MOVEMENT_ROW_MAX_GAP = 22.0

REFERENCE_LINE_MIN_GAP = 3.0

REFERENCE_LINE_MAX_GAP = 20.0

COLUMN_PADDING_X = 8.0

COLUMN_PADDING_Y = 4.0

DAY_MIN = 1

DAY_MAX = 31


# ============================================================
# PATRONES
# ============================================================


DAY_PATTERN = re.compile(
    r"^(?:0?[1-9]|[12]\d|3[01])$"
)


DATE_PATTERN = re.compile(
    r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b"
)


MONEY_PATTERN = re.compile(
    r"^\$?\s*[\d,]+(?:\.\d{1,2})?$"
)


REFERENCE_PATTERN = re.compile(
    r"^[A-Z0-9Ñ&./_-]+$",
    re.IGNORECASE,
)


# ============================================================
# UTILIDADES GENERALES
# ============================================================


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Conversión segura a float.
    """

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


def safe_page(
    word: Dict[str, Any],
) -> int:
    """
    Devuelve la página de una word.
    """

    try:
        return int(
            word.get(
                "page",
                1,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1


def normalize_text(
    value: Any,
) -> str:
    """
    Normaliza texto para comparación semántica.
    """

    if value is None:
        return ""

    text = str(
        value
    ).strip()

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFD",
        text,
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char)
        != "Mn"
    )

    text = text.upper()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def clean_word_text(
    value: Any,
) -> str:
    """
    Limpia una word.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip()


# ============================================================
# GEOMETRÍA
# ============================================================


def word_center(
    word: Dict[str, Any],
) -> Tuple[
    float,
    float,
]:
    """
    Centro geométrico de una word.
    """

    x0 = safe_float(
        word.get(
            "x0",
            0.0,
        )
    )

    x1 = safe_float(
        word.get(
            "x1",
            x0,
        )
    )

    top = safe_float(
        word.get(
            "top",
            0.0,
        )
    )

    bottom = safe_float(
        word.get(
            "bottom",
            top,
        )
    )

    return (
        (x0 + x1) / 2.0,
        (top + bottom) / 2.0,
    )


def word_inside_box(
    word: Dict[str, Any],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    padding_x: float = 0.0,
    padding_y: float = 0.0,
) -> bool:
    """
    Determina si una word pertenece a una caja espacial.
    """

    xmin, xmax, ymin, ymax = box

    center_x, center_y = word_center(
        word
    )

    return (
        xmin - padding_x
        <= center_x
        <= xmax + padding_x
        and
        ymin - padding_y
        <= center_y
        <= ymax + padding_y
    )


# ============================================================
# RENGLONES
# ============================================================


def line_bounds(
    line: Sequence[
        Dict[str, Any]
    ],
) -> Tuple[
    float,
    float,
    float,
    float,
]:
    """
    Caja envolvente del renglón.
    """

    if not line:
        return (
            0.0,
            0.0,
            0.0,
            0.0,
        )

    return (
        min(
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            )
            for word in line
        ),
        max(
            safe_float(
                word.get(
                    "x1",
                    0.0,
                )
            )
            for word in line
        ),
        min(
            safe_float(
                word.get(
                    "top",
                    0.0,
                )
            )
            for word in line
        ),
        max(
            safe_float(
                word.get(
                    "bottom",
                    0.0,
                )
            )
            for word in line
        ),
    )


def line_center_y(
    line: Sequence[
        Dict[str, Any]
    ],
) -> float:
    """
    Centro vertical del renglón.
    """

    _, _, ymin, ymax = line_bounds(
        line
    )

    return (
        ymin + ymax
    ) / 2.0


def line_text(
    line: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Concatena las words del renglón.
    """

    parts = []

    for word in line:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if text:
            parts.append(
                text
            )

    return " ".join(
        parts
    ).strip()


def group_words_into_lines(
    words: Sequence[
        Dict[str, Any]
    ],
    y_tolerance: float = LINE_Y_TOLERANCE,
) -> List[
    List[
        Dict[str, Any]
    ]
]:
    """
    Agrupa words por renglones lógicos.

    Nunca mezcla páginas.
    """

    valid_words = [
        word
        for word in words
        if clean_word_text(
            word.get(
                "text",
                "",
            )
        )
    ]

    valid_words.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    lines_by_page: Dict[
        int,
        List[
            List[
                Dict[str, Any]
            ]
        ]
    ] = {}

    for word in valid_words:

        page = safe_page(
            word
        )

        center_y = word_center(
            word
        )[1]

        page_lines = (
            lines_by_page.setdefault(
                page,
                [],
            )
        )

        best_line = None

        best_distance = float(
            "inf"
        )

        for line in reversed(
            page_lines
        ):

            distance = abs(
                center_y
                -
                line_center_y(
                    line
                )
            )

            if (
                distance
                <=
                y_tolerance
                and
                distance
                <
                best_distance
            ):

                best_distance = distance

                best_line = line

            if (
                line_center_y(line)
                <
                center_y
                -
                y_tolerance
            ):
                break

        if best_line is None:

            page_lines.append(
                [word]
            )

        else:

            best_line.append(
                word
            )

    result = []

    for page in sorted(
        lines_by_page
    ):

        for line in lines_by_page[
            page
        ]:

            line.sort(
                key=lambda word:
                    safe_float(
                        word.get(
                            "x0",
                            0.0,
                        )
                    )
            )

            result.append(
                line
            )

    return result


# ============================================================
# PERIODO
# ============================================================


def extract_period_from_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Tuple[
    Optional[date],
    Optional[date],
]:
    """
    Busca el periodo completo del estado de cuenta.
    """

    lines = group_words_into_lines(
        words
    )

    candidates = []

    for line in lines:

        normalized = normalize_text(
            line_text(line)
        )

        if "PERIODO" not in normalized:
            continue

        text = line_text(
            line
        )

        matches = DATE_PATTERN.findall(
            text
        )

        if len(matches) < 2:
            continue

        try:

            first = date(
                int(matches[0][2]),
                int(matches[0][1]),
                int(matches[0][0]),
            )

            second = date(
                int(matches[1][2]),
                int(matches[1][1]),
                int(matches[1][0]),
            )

        except ValueError:

            continue

        candidates.append(
            (
                first,
                second,
                line_center_y(line),
            )
        )

    if not candidates:

        return (
            None,
            None,
        )

    candidates.sort(
        key=lambda item: item[2]
    )

    return (
        candidates[0][0],
        candidates[0][1],
    )


# ============================================================
# ENCABEZADOS
# ============================================================


def is_movement_header_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta encabezado principal de movimientos.
    """

    normalized = normalize_text(
        line_text(line)
    )

    return (
        "DETALLE" in normalized
        and
        "MOVIMIENTOS" in normalized
    )


def is_column_header_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta encabezado de las columnas.
    """

    normalized = normalize_text(
        line_text(line)
    )

    score = 0

    if "DIA" in normalized:
        score += 1

    if "DESCRIPCION" in normalized:
        score += 1

    if "RETIRO/CARGO" in normalized:
        score += 1

    if "DEPOSITO/ABONO" in normalized:
        score += 1

    if "SALDO" in normalized:
        score += 1

    return score >= 3


# ============================================================
# FILA LÓGICA DE MOVIMIENTO
# ============================================================


@dataclass
class MovementRow:
    """
    Fila temporal de movimiento.

    Puede contener una o varias líneas físicas.
    """

    page: int

    lines: List[
        List[
            Dict[str, Any]
        ]
    ]


# ============================================================
# DÍA
# ============================================================


def extract_day_from_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> Optional[int]:
    """
    Extrae día exclusivamente de la columna Día.
    """

    for word in line:

        if not word_inside_box(
            word,
            BOX_DAY,
            padding_x=7.0,
            padding_y=3.0,
        ):
            continue

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if not DAY_PATTERN.fullmatch(
            text
        ):
            continue

        try:
            day = int(
                text
            )
        except ValueError:
            continue

        if (
            DAY_MIN
            <=
            day
            <=
            DAY_MAX
        ):
            return day

    return None


def line_starts_movement(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Determina si un renglón inicia un movimiento.
    """

    return (
        extract_day_from_line(
            line
        )
        is not None
    )


# ============================================================
# PIE DE TABLA / BREAKERS
# ============================================================


def is_footer_like_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Protección adicional contra footer.
    """

    normalized = normalize_text(
        line_text(line)
    )

    if "EMITIDO POR" in normalized:
        return True

    if "PASEO DE LA REFORMA" in normalized:
        return True

    if "RFC:" in normalized:
        return True

    return False


def is_table_breaker_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta texto posterior a la tabla de movimientos.
    """

    normalized = normalize_text(
        line_text(line)
    )

    if not normalized:
        return False

    if normalized.startswith(
        "CODI"
    ):
        return True

    if (
        "OPERACION PROCESADA POR CODI"
        in normalized
    ):
        return True

    if normalized.startswith(
        "CIFRAS EXPRESADAS"
    ):
        return True

    return False


# ============================================================
# RECONSTRUCCIÓN DE FILAS
# ============================================================


def split_page_into_movement_rows(
    words: Sequence[
        Dict[str, Any]
    ],
) -> List[
    MovementRow
]:
    """
    Reconstruye las filas lógicas de una página.

    Soporta:

        - encabezado;
        - movimiento;
        - líneas de continuación;
        - siguiente movimiento;
        - fin de tabla.
    """

    if not words:
        return []

    lines = group_words_into_lines(
        words
    )

    rows: List[
        MovementRow
    ] = []

    current_row: Optional[
        MovementRow
    ] = None

    table_started = False

    for line in lines:

        if not line:
            continue

        page = safe_page(
            line[0]
        )

        # ----------------------------------------------------
        # Encabezados
        # ----------------------------------------------------

        if is_movement_header_line(
            line
        ):

            table_started = True

            continue

        if is_column_header_line(
            line
        ):

            table_started = True

            continue

        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        if is_footer_like_line(
            line
        ):

            if current_row is not None:

                rows.append(
                    current_row
                )

                current_row = None

            break

        # ----------------------------------------------------
        # Fin de tabla
        # ----------------------------------------------------

        if (
            table_started
            and
            is_table_breaker_line(
                line
            )
        ):

            if current_row is not None:

                rows.append(
                    current_row
                )

                current_row = None

            break

        # ----------------------------------------------------
        # Nuevo movimiento
        # ----------------------------------------------------

        if line_starts_movement(
            line
        ):

            if current_row is not None:

                rows.append(
                    current_row
                )

            current_row = MovementRow(
                page=page,
                lines=[
                    list(line)
                ],
            )

            table_started = True

            continue

        # ----------------------------------------------------
        # Antes de la tabla
        # ----------------------------------------------------

        if not table_started:
            continue

        # ----------------------------------------------------
        # Continuación del movimiento actual
        # ----------------------------------------------------

        if current_row is not None:

            previous_line = (
                current_row.lines[-1]
            )

            gap = (
                line_center_y(line)
                -
                line_center_y(previous_line)
            )

            if (
                0.0
                <=
                gap
                <=
                MOVEMENT_ROW_MAX_GAP
            ):

                current_row.lines.append(
                    list(line)
                )

    if current_row is not None:

        rows.append(
            current_row
        )

    return rows


# ============================================================
# WORDS DE COLUMNA
# ============================================================


def words_from_rows_in_box(
    row: MovementRow,
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    padding_x: float = COLUMN_PADDING_X,
) -> List[
    Dict[str, Any]
]:
    """
    Obtiene words pertenecientes a una región espacial.
    """

    selected = []

    for line in row.lines:

        for word in line:

            if word_inside_box(
                word,
                box,
                padding_x=padding_x,
                padding_y=COLUMN_PADDING_Y,
            ):

                selected.append(
                    word
                )

    selected.sort(
        key=lambda word: (
            safe_float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    return selected


def text_from_box(
    row: MovementRow,
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    padding_x: float = COLUMN_PADDING_X,
) -> str:
    """
    Concatena texto de una columna.
    """

    words = words_from_rows_in_box(
        row,
        box,
        padding_x=padding_x,
    )

    parts = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if text:
            parts.append(
                text
            )

    return " ".join(
        parts
    ).strip()


# ============================================================
# CONCEPTO
# ============================================================


def extract_concepto(
    row: MovementRow,
) -> str:
    """
    Extrae exclusivamente la columna Descripción.

    El límite horizontal impide capturar Referencia/Serial.
    """

    words = words_from_rows_in_box(
        row,
        BOX_CONCEPTO,
        padding_x=8.0,
    )

    parts = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if text:
            parts.append(
                text
            )

    return " ".join(
        parts
    ).strip()


# ============================================================
# REFERENCIA / SERIAL
# ============================================================
#
# ESTE ES EL CAMBIO PRINCIPAL DE LA V2.
#
# La región Referencia/Serial puede contener dos niveles:
#
#   línea 1 -> dato superior
#   línea 2 -> dato inferior
#
# El dato inferior es el que se devuelve como referencia.
#
# No se utiliza una longitud fija.
# No se utiliza un número concreto.
# No se asume que el valor sea siempre numérico.
# ============================================================


def reference_serial_words(
    row: MovementRow,
) -> List[
    Dict[str, Any]
]:
    """
    Obtiene las words de la región Referencia/Serial.
    """

    return words_from_rows_in_box(
        row,
        BOX_REFERENCIA_SERIAL,
        padding_x=8.0,
    )


def reference_serial_lines(
    row: MovementRow,
) -> List[
    List[
        Dict[str, Any]
    ]
]:
    """
    Reconstruye los renglones lógicos exclusivamente dentro
    de la región Referencia/Serial.

    Esto permite separar:

        13611089
        6618

    aunque el resto del movimiento tenga varias líneas.
    """

    words = reference_serial_words(
        row
    )

    if not words:
        return []

    lines = group_words_into_lines(
        words,
        y_tolerance=LINE_Y_TOLERANCE,
    )

    lines.sort(
        key=line_center_y
    )

    return lines


def valid_reference_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Determina si una línea contiene un dato de referencia.

    Se excluyen símbolos aislados y palabras vacías.

    No se exige una longitud fija.
    """

    text = line_text(
        line
    )

    if not text:
        return False

    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    if not compact:
        return False

    if compact in (
        "$",
        "-",
    ):
        return False

    return bool(
        REFERENCE_PATTERN.fullmatch(
            compact
        )
    )


def compact_reference_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Convierte una línea de Referencia/Serial a un valor
    compacto.

    Ejemplo:

        66
        18

    ->

        6618
    """

    if not valid_reference_line(
        line
    ):
        return None

    parts = []

    for word in line:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        cleaned = re.sub(
            r"[^A-Z0-9Ñ&./_-]",
            "",
            text.upper(),
        )

        if cleaned:
            parts.append(
                cleaned
            )

    value = "".join(
        parts
    )

    if not value:
        return None

    return value


def extract_referencia(
    row: MovementRow,
) -> Optional[str]:
    """
    Extrae la REFERENCIA REAL del movimiento.

    Regla estructural:

        Referencia/Serial superior
                ↓
        NO se utiliza

        Referencia/Serial inferior
                ↓
        ESTE es el valor de referencia.

    Esto permite resolver correctamente layouts como:

        13611089
        6618

    y:

        132??323
        8721

    sin depender de esos valores concretos.
    """

    lines = reference_serial_lines(
        row
    )

    if len(lines) < 2:
        return None

    # --------------------------------------------------------
    # El primer renglón corresponde al dato superior.
    # --------------------------------------------------------

    first_y = line_center_y(
        lines[0]
    )

    # --------------------------------------------------------
    # Buscar el siguiente renglón lógico por debajo.
    #
    # No tomamos simplemente lines[-1] porque en OCR una
    # fila puede ocasionalmente contener ruido adicional.
    # --------------------------------------------------------

    for line in lines[1:]:

        current_y = line_center_y(
            line
        )

        gap = (
            current_y
            -
            first_y
        )

        if gap < REFERENCE_LINE_MIN_GAP:
            continue

        if gap > REFERENCE_LINE_MAX_GAP:
            continue

        value = compact_reference_line(
            line
        )

        if value:
            return value

    return None


# ============================================================
# IMPORTE
# ============================================================


def parse_money_words(
    row: MovementRow,
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
) -> float:
    """
    Extrae importe monetario.

    Si no existe importe en la columna devuelve 0.0.
    """

    words = words_from_rows_in_box(
        row,
        box,
        padding_x=8.0,
    )

    if not words:
        return 0.0

    parts = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        if text == "$":
            continue

        normalized = (
            text
            .replace(
                ",",
                "",
            )
            .replace(
                "$",
                "",
            )
            .strip()
        )

        if re.fullmatch(
            r"\d+(?:\.\d{1,2})?",
            normalized,
        ):

            parts.append(
                normalized
            )

    if not parts:
        return 0.0

    value = "".join(
        parts
    )

    if not re.fullmatch(
        r"\d+(?:\.\d{1,2})?",
        value,
    ):
        return 0.0

    try:
        return float(
            value
        )
    except ValueError:
        return 0.0


# ============================================================
# FECHA DE OPERACIÓN
# ============================================================


def extract_day_from_row(
    row: MovementRow,
) -> Optional[int]:
    """
    Obtiene el día de la fila.
    """

    if not row.lines:
        return None

    return extract_day_from_line(
        row.lines[0]
    )


def build_operation_date(
    day: Optional[int],
    periodo_inicio: Optional[date],
) -> str:
    """
    Construye DD/MM/YYYY utilizando el periodo.

    Si no existe periodo, conserva DD.
    """

    if day is None:
        return ""

    if periodo_inicio is None:

        return f"{day:02d}"

    try:

        return date(
            periodo_inicio.year,
            periodo_inicio.month,
            day,
        ).strftime(
            "%d/%m/%Y"
        )

    except ValueError:

        return f"{day:02d}"


# ============================================================
# TIPO DE OPERACIÓN
# ============================================================


def extract_tipo_operacion(
    concepto: str,
) -> Optional[str]:
    """
    Clasificación inicial preparada para futuras extensiones.
    """

    normalized = normalize_text(
        concepto
    )

    if normalized.startswith(
        "RETIRO"
    ):
        return "Retiro"

    if normalized.startswith(
        "DEPOSITO"
    ):
        return "Depósito"

    if normalized.startswith(
        "ABONO"
    ):
        return "Abono"

    return None


# ============================================================
# FILA → MODELO
# ============================================================


def movement_row_to_model(
    row: MovementRow,
    periodo_inicio: Optional[date],
) -> Movimiento:
    """
    Convierte una fila lógica a Movimiento.
    """

    day = extract_day_from_row(
        row
    )

    fecha_operacion = (
        build_operation_date(
            day,
            periodo_inicio,
        )
    )

    concepto = extract_concepto(
        row
    )

    cargo = parse_money_words(
        row,
        BOX_CARGO,
    )

    abono = parse_money_words(
        row,
        BOX_ABONO,
    )

    saldo_operacion = parse_money_words(
        row,
        BOX_SALDO,
    )

    referencia = extract_referencia(
        row
    )

    return Movimiento(
        fecha_operacion=fecha_operacion,

        fecha_liquidacion=None,

        concepto=concepto,

        tipo_operacion=None,

        cargo=cargo,

        abono=abono,

        referencia=referencia,

        autorizacion=None,

        beneficiario=None,

        cuenta_beneficiario=None,

        clabe_beneficiario=None,

        rfc=None,

        sucursal=None,

        caja=None,

        hora_operacion=None,

        saldo_operacion=saldo_operacion,

        saldo_liquidacion=0.0,

        concepto_original=concepto,
    )


# ============================================================
# VALIDACIÓN
# ============================================================


def is_valid_movement(
    movement: Movimiento,
) -> bool:
    """
    Validación estructural mínima.
    """

    if not movement.fecha_operacion:
        return False

    if not movement.concepto:
        return False

    if (
        movement.cargo == 0.0
        and
        movement.abono == 0.0
    ):
        return False

    return True


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_movimientos_words(
    words: List[
        Dict[str, Any]
    ],
) -> List[
    Movimiento
]:
    """
    Extractor V2 robusto de movimientos HSBC.

    Variables principales:

        - fecha_operacion
        - concepto
        - cargo
        - abono
        - referencia
        - saldo_operacion

    Variables preparadas:

        - fecha_liquidacion
        - tipo_operacion
        - autorizacion
        - beneficiario
        - cuenta_beneficiario
        - clabe_beneficiario
        - rfc
        - sucursal
        - caja
        - hora_operacion
        - saldo_liquidacion

    Arquitectura:

        WORDS
          ↓
        FILTRO FOOTER
          ↓
        PÁGINAS
          ↓
        ENCABEZADOS
          ↓
        FILAS LÓGICAS
          ↓
        COLUMNAS ESPACIALES
          ↓
        REFERENCIA/SERIAL COMO SUBESTRUCTURA
          ↓
        NORMALIZACIÓN
          ↓
        VALIDACIÓN
          ↓
        Movimiento
    """

    if not words:
        return []

    # ========================================================
    # 1. ELIMINAR FOOTERS
    # ========================================================

    filtered_words = (
        filter_hsbc_footer_words(
            words
        )
    )

    if not filtered_words:
        return []

    # ========================================================
    # 2. OBTENER PERIODO
    # ========================================================

    periodo_inicio, _ = (
        extract_period_from_words(
            filtered_words
        )
    )

    # ========================================================
    # 3. AGRUPAR POR PÁGINA
    # ========================================================

    pages: Dict[
        int,
        List[
            Dict[str, Any]
        ]
    ] = {}

    for word in filtered_words:

        pages.setdefault(
            safe_page(word),
            []
        ).append(
            word
        )

    # ========================================================
    # 4. RECONSTRUIR FILAS DE MOVIMIENTOS
    # ========================================================

    movement_rows: List[
        MovementRow
    ] = []

    for page in sorted(
        pages
    ):

        page_rows = (
            split_page_into_movement_rows(
                pages[page]
            )
        )

        movement_rows.extend(
            page_rows
        )

    if not movement_rows:
        return []

    # ========================================================
    # 5. CONVERTIR FILAS A MODELO
    # ========================================================

    movements = []

    for row in movement_rows:

        movement = movement_row_to_model(
            row,
            periodo_inicio,
        )

        if is_valid_movement(
            movement
        ):

            movements.append(
                movement
            )

    # ========================================================
    # 6. CONSERVAR ORDEN DOCUMENTAL
    # ========================================================

    return movements