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
#     x ≈ 60 ... 279
#
# Referencia / Serial
#     x ≈ 280 ... 345
#
# Retiro / Cargo
#     x ≈ 350 ... 415
#
# Depósito / Abono
#     x ≈ 420 ... 505
#
# Saldo
#     x ≈ 520 ... 575
#
# Las cajas representan regiones estructurales.
# No se pretende que sean coordenadas absolutas perfectas.
#


BOX_DAY = (
    35.0,
    60.0,
    0.0,
    900.0,
)

BOX_CONCEPTO = (
    55.0,
    278.0,
    0.0,
    900.0,
)

BOX_REFERENCIA_SERIAL = (
    280.0,
    345.0,
    0.0,
    900.0,
)

# Compatibilidad semántica con código existente/futuro.
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
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_page(
    word: Dict[str, Any],
) -> int:
    """
    Devuelve la página de una word.
    """
    try:
        return int(word.get("page", 1))
    except (TypeError, ValueError):
        return 1


def normalize_text(
    value: Any,
) -> str:
    """
    Normaliza texto para comparación semántica.
    """
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFD",
        text,
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
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

    return str(value).strip()


# ============================================================
# GEOMETRÍA
# ============================================================

def word_bounds(
    word: Dict[str, Any],
) -> Tuple[float, float, float, float]:
    """
    Devuelve la caja espacial de una word.
    """
    x0 = safe_float(
        word.get("x0", 0.0)
    )

    x1 = safe_float(
        word.get("x1", x0)
    )

    top = safe_float(
        word.get("top", 0.0)
    )

    bottom = safe_float(
        word.get("bottom", top)
    )

    return (
        x0,
        x1,
        top,
        bottom,
    )


def word_center(
    word: Dict[str, Any],
) -> Tuple[float, float]:
    """
    Centro geométrico de una word.
    """
    x0, x1, top, bottom = word_bounds(word)

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

    Se utiliza solapamiento geométrico en lugar de exigir
    que el centro de la word quede dentro de la caja.

    Esto es más tolerante frente a pequeñas variaciones
    producidas por OCR y documentos escaneados.
    """
    xmin, xmax, ymin, ymax = box

    word_x0, word_x1, word_top, word_bottom = (
        word_bounds(word)
    )

    box_xmin = xmin - padding_x
    box_xmax = xmax + padding_x
    box_ymin = ymin - padding_y
    box_ymax = ymax + padding_y

    overlaps_x = (
        word_x1 >= box_xmin
        and word_x0 <= box_xmax
    )

    overlaps_y = (
        word_bottom >= box_ymin
        and word_top <= box_ymax
    )

    return overlaps_x and overlaps_y


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
    _, _, ymin, ymax = line_bounds(line)

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
            parts.append(text)

    return " ".join(parts).strip()


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
        page = safe_page(word)

        center_y = word_center(word)[1]

        page_lines = (
            lines_by_page.setdefault(
                page,
                [],
            )
        )

        best_line = None
        best_distance = float("inf")

        for line in reversed(page_lines):
            distance = abs(
                center_y - line_center_y(line)
            )

            if (
                distance <= y_tolerance
                and distance < best_distance
            ):
                best_distance = distance
                best_line = line

            if (
                line_center_y(line)
                < center_y - y_tolerance
            ):
                break

        if best_line is None:
            page_lines.append([word])
        else:
            best_line.append(word)

    result = []

    for page in sorted(lines_by_page):
        for line in lines_by_page[page]:
            line.sort(
                key=lambda word: safe_float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
            )

            result.append(line)

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
    lines = group_words_into_lines(words)

    candidates = []

    for line in lines:
        normalized = normalize_text(
            line_text(line)
        )

        if "PERIODO" not in normalized:
            continue

        text = line_text(line)

        matches = DATE_PATTERN.findall(text)

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
        and "MOVIMIENTOS" in normalized
    )


def is_column_header_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta encabezado de columnas.
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
# FILA LÓGICA
# ============================================================

@dataclass
class MovementRow:
    """
    Representa una fila lógica de movimiento.

    Puede contener múltiples líneas físicas.

    La región Referencia / Serial se conserva completa
    y además separada en sus dos niveles estructurales.
    """

    page: int

    lines: List[
        List[
            Dict[str, Any]
        ]
    ]

    # --------------------------------------------------------
    # Estructura Referencia / Serial
    # --------------------------------------------------------

    referencia_serial_superior: Optional[str] = None

    referencia_serial_inferior: Optional[str] = None

    referencia_serial_completo: Optional[str] = None

    # --------------------------------------------------------
    # Dato seleccionado para uso semántico futuro.
    #
    # Actualmente prioriza el dato inferior.
    # Si no existe inferior, utiliza el superior.
    # --------------------------------------------------------

    referencia_principal: Optional[str] = None


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

        if not DAY_PATTERN.fullmatch(text):
            continue

        try:
            day = int(text)
        except ValueError:
            continue

        if DAY_MIN <= day <= DAY_MAX:
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
        extract_day_from_line(line)
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
    Detecta texto posterior a la tabla.
    """
    normalized = normalize_text(
        line_text(line)
    )

    if not normalized:
        return False

    if normalized.startswith("CODI"):
        return True

    if "OPERACION PROCESADA POR CODI" in normalized:
        return True

    if normalized.startswith("CIFRAS EXPRESADAS"):
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

    lines = group_words_into_lines(words)

    rows: List[MovementRow] = []

    current_row: Optional[MovementRow] = None
    table_started = False

    for line in lines:
        if not line:
            continue

        page = safe_page(line[0])

        # ----------------------------------------------------
        # Encabezados
        # ----------------------------------------------------

        if is_movement_header_line(line):
            table_started = True
            continue

        if is_column_header_line(line):
            table_started = True
            continue

        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        if is_footer_like_line(line):
            if current_row is not None:
                rows.append(current_row)
                current_row = None

            break

        # ----------------------------------------------------
        # Fin de tabla
        # ----------------------------------------------------

        if (
            table_started
            and is_table_breaker_line(line)
        ):
            if current_row is not None:
                rows.append(current_row)
                current_row = None

            break

        # ----------------------------------------------------
        # Nuevo movimiento
        # ----------------------------------------------------

        if line_starts_movement(line):
            if current_row is not None:
                rows.append(current_row)

            current_row = MovementRow(
                page=page,
                lines=[list(line)],
            )

            table_started = True
            continue

        # ----------------------------------------------------
        # Antes de la tabla
        # ----------------------------------------------------

        if not table_started:
            continue

        # ----------------------------------------------------
        # Línea de continuación
        # ----------------------------------------------------

        if current_row is not None:
            previous_line = current_row.lines[-1]

            gap = (
                line_center_y(line)
                - line_center_y(previous_line)
            )

            if (
                0.0 <= gap <= MOVEMENT_ROW_MAX_GAP
            ):
                current_row.lines.append(
                    list(line)
                )

    if current_row is not None:
        rows.append(current_row)

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
                selected.append(word)

    selected.sort(
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
            parts.append(text)

    return " ".join(parts).strip()


# ============================================================
# CONCEPTO
# ============================================================

def extract_concepto(
    row: MovementRow,
) -> str:
    """
    Extrae la descripción completa del movimiento.

    La caja se extiende hasta inmediatamente antes de
    Referencia / Serial.

    De esta forma un concepto puede ocupar más espacio
    horizontal sin capturar la referencia.
    """
    words = words_from_rows_in_box(
        row,
        BOX_CONCEPTO,
        padding_x=5.0,
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
            parts.append(text)

    return " ".join(parts).strip()


# ============================================================
# REFERENCIA / SERIAL
# ============================================================

def reference_serial_words(
    row: MovementRow,
) -> List[
    Dict[str, Any]
]:
    """
    Obtiene todas las words de la región Referencia / Serial.
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
    Agrupa exclusivamente la zona Referencia / Serial
    en renglones lógicos.

    Resultado esperado:

        [
            [dato_superior],
            [dato_inferior],
        ]
    """
    words = reference_serial_words(row)

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
    Determina si un renglón contiene un dato válido
    de Referencia / Serial.
    """
    text = line_text(line)

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
        REFERENCE_PATTERN.fullmatch(compact)
    )


def compact_reference_line(
    line: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Compacta todas las words de un renglón de
    Referencia / Serial.

    Ejemplo:

        13 61 10 89

    →

        13611089
    """
    if not valid_reference_line(line):
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
            parts.append(cleaned)

    value = "".join(parts)

    if not value:
        return None

    return value


def extract_referencia_serial(
    row: MovementRow,
) -> Tuple[
    Optional[str],
    Optional[str],
]:
    """
    Extrae y conserva los dos niveles de la región
    Referencia / Serial.

    Retorna:

        (
            referencia_serial_superior,
            referencia_serial_inferior,
        )

    Reglas:

        - Primer dato válido -> superior.
        - Segundo dato válido -> inferior.
        - Si solo existe uno, se conserva ese único dato.
        - Nunca se reemplaza un dato existente por None.
    """
    lines = reference_serial_lines(row)

    if not lines:
        return (
            None,
            None,
        )

    valid_values: List[str] = []

    for line in lines:
        value = compact_reference_line(line)

        if value:
            valid_values.append(value)

    if not valid_values:
        return (
            None,
            None,
        )

    referencia_superior = valid_values[0]

    referencia_inferior = (
        valid_values[1]
        if len(valid_values) >= 2
        else None
    )

    return (
        referencia_superior,
        referencia_inferior,
    )


def build_referencia_serial_completo(
    referencia_superior: Optional[str],
    referencia_inferior: Optional[str],
) -> Optional[str]:
    """
    Construye la representación completa de Referencia / Serial.

    Cuando existen ambos datos se conservan separados por
    salto de línea.

    Ejemplo:

        123456789
        987654321
    """
    values = []

    if referencia_superior:
        values.append(referencia_superior)

    if referencia_inferior:
        values.append(referencia_inferior)

    if not values:
        return None

    return "\n".join(values)


def populate_reference_serial_data(
    row: MovementRow,
) -> None:
    """
    Calcula y conserva toda la estructura de
    Referencia / Serial dentro de MovementRow.

    Además determina la referencia principal.

    La referencia principal mantiene la regla actual:

        inferior > superior

    Es decir:

        - Si existe dato inferior, ese es el objetivo.
        - Si no existe inferior pero sí superior,
          se utiliza el superior.
    """
    (
        referencia_superior,
        referencia_inferior,
    ) = extract_referencia_serial(row)

    row.referencia_serial_superior = (
        referencia_superior
    )

    row.referencia_serial_inferior = (
        referencia_inferior
    )

    row.referencia_serial_completo = (
        build_referencia_serial_completo(
            referencia_superior,
            referencia_inferior,
        )
    )

    row.referencia_principal = (
        referencia_inferior
        or referencia_superior
    )


def extract_referencia(
    row: MovementRow,
) -> Optional[str]:
    """
    Devuelve la referencia principal para futuras
    extracciones semánticas.

    Prioridad:

        1. dato inferior;
        2. dato superior.

    Importante:
    esta función NO elimina ni altera el contenido completo.
    Ese contenido permanece disponible en:

        row.referencia_serial_completo
    """
    if (
        row.referencia_serial_superior is None
        and row.referencia_serial_inferior is None
        and row.referencia_serial_completo is None
    ):
        populate_reference_serial_data(row)

    return row.referencia_principal


def extract_referencia_completa(
    row: MovementRow,
) -> Optional[str]:
    """
    Devuelve todos los datos de Referencia / Serial
    conservados por la fila.

    Cuando existen dos datos los devuelve separados por
    salto de línea.

    Cuando existe uno solo devuelve ese dato.
    """
    if (
        row.referencia_serial_superior is None
        and row.referencia_serial_inferior is None
        and row.referencia_serial_completo is None
    ):
        populate_reference_serial_data(row)

    return row.referencia_serial_completo


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
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

        if re.fullmatch(
            r"\d+(?:\.\d{1,2})?",
            normalized,
        ):
            parts.append(normalized)

    if not parts:
        return 0.0

    value = "".join(parts)

    if not re.fullmatch(
        r"\d+(?:\.\d{1,2})?",
        value,
    ):
        return 0.0

    try:
        return float(value)
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

    Si no existe periodo conserva DD.
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
        ).strftime("%d/%m/%Y")
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
    normalized = normalize_text(concepto)

    if normalized.startswith("RETIRO"):
        return "Retiro"

    if normalized.startswith("DEPOSITO"):
        return "Depósito"

    if normalized.startswith("ABONO"):
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
    Convierte una fila lógica en Movimiento.

    Antes de construir el modelo se conserva la estructura
    completa Referencia / Serial.
    """
    # --------------------------------------------------------
    # Preparar ambos datos.
    # --------------------------------------------------------

    populate_reference_serial_data(row)

    day = extract_day_from_row(row)

    fecha_operacion = build_operation_date(
        day,
        periodo_inicio,
    )

    concepto = extract_concepto(row)

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

    # --------------------------------------------------------
    # Importante:
    #
    # referencia_principal conserva el dato semánticamente
    # relevante para futuras funciones.
    #
    # referencia_completa conserva ambos datos cuando existen.
    #
    # El modelo recibe la representación completa para no
    # perder información.
    # --------------------------------------------------------

    referencia_principal = extract_referencia(row)

    referencia_completa = extract_referencia_completa(row)

    # --------------------------------------------------------
    # Si por alguna razón no se construyó la representación
    # completa pero existe referencia principal, se conserva.
    # Nunca forzamos N/A aquí.
    # --------------------------------------------------------

    referencia_modelo = (
        referencia_completa
        or referencia_principal
        or None
    )

    return Movimiento(
        fecha_operacion=fecha_operacion,
        fecha_liquidacion=None,
        concepto=concepto,
        tipo_operacion=None,
        cargo=cargo,
        abono=abono,
        referencia=referencia_modelo,
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
        and movement.abono == 0.0
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
    Extractor robusto de movimientos HSBC.

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

    Información estructural conservada internamente:
        - referencia_serial_superior
        - referencia_serial_inferior
        - referencia_serial_completo
        - referencia_principal

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
        CONCEPTO COMPLETO
          ↓
        REFERENCIA / SERIAL
             ├── superior
             ├── inferior
             ├── completo
             └── principal
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
        filter_hsbc_footer_words(words)
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
            [],
        ).append(word)

    # ========================================================
    # 4. RECONSTRUIR FILAS
    # ========================================================

    movement_rows: List[
        MovementRow
    ] = []

    for page in sorted(pages):
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

    movements: List[Movimiento] = []

    for row in movement_rows:
        movement = movement_row_to_model(
            row,
            periodo_inicio,
        )

        if is_valid_movement(movement):
            movements.append(movement)

    # ========================================================
    # 6. CONSERVAR ORDEN DOCUMENTAL
    # ========================================================

    return movements