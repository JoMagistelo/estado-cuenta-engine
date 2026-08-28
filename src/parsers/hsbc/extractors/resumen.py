from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.resumen_financiero import ResumenFinanciero


# ============================================================
# CONFIGURACIÓN ESPACIAL — RESUMEN FINANCIERO HSBC
# ============================================================
#
# Las coordenadas corresponden al layout HSBC observado.
#
# IMPORTANTE:
#
# Las coordenadas NO se utilizan como posiciones absolutas
# rígidas.
#
# Se utilizan como referencia espacial para:
#
#   - localizar la región financiera;
#   - distinguir columna de conceptos y valores;
#   - resolver campos repetidos;
#   - seleccionar el valor correcto;
#   - tolerar desplazamientos moderados de OCR.
#
# El texto continúa siendo el ancla semántica principal.
#
# ============================================================


# ------------------------------------------------------------
# REGIÓN GENERAL DE LA TABLA FINANCIERA
#
# La tabla continúa hasta los renglones de ISR.
# ------------------------------------------------------------

BOX_RESUMEN_FINANCIERO = (
    350.0,
    565.0,
    130.0,
    480.0,
)


# ------------------------------------------------------------
# COLUMNA DE CONCEPTOS
# ------------------------------------------------------------

BOX_FINANCIAL_LABEL = (
    350.0,
    500.0,
    130.0,
    480.0,
)


# ------------------------------------------------------------
# COLUMNA DE VALORES
#
# Valores observados:
#
#   x ≈ 509 ... 564
#
# ------------------------------------------------------------

BOX_FINANCIAL_VALUE = (
    500.0,
    570.0,
    130.0,
    480.0,
)


# Columnas monetarias del detalle de movimientos. Se utilizan
# únicamente como respaldo para los dos conceptos mensuales
# que HSBC también registra como movimientos independientes.
MOVEMENT_CARGO_X = (
    345.0,
    415.0,
)

MOVEMENT_ABONO_X = (
    420.0,
    505.0,
)


# ============================================================
# REFERENCIAS ESPACIALES DE LOS VALORES
# ============================================================
#
# Estas coordenadas corresponden al CENTRO aproximado de la
# word / importe del valor, no al centro de la etiqueta.
#
# Esto es fundamental para etiquetas de una o varias líneas.
# ============================================================


EXPECTED_Y_SALDO_ANTERIOR = 140.5

EXPECTED_Y_DEPOSITOS_ABONOS = 159.8

EXPECTED_Y_RETIROS_CARGOS = 177.8

EXPECTED_Y_INTERESES_NETOS = 203.5

EXPECTED_Y_SALDO_FINAL = 230.5

EXPECTED_Y_DIAS_PERIODO = 270.7

EXPECTED_Y_COMISIONES_COBRADAS = 380.8

EXPECTED_Y_SALDO_PROMEDIO_MINIMO = 399.6

EXPECTED_Y_SALDO_PROMEDIO = 409.0

EXPECTED_Y_TASA_PROMEDIO_NOMINAL = 420.4

EXPECTED_Y_PAGO_INTERES_MES = 429.5

EXPECTED_Y_ISR_RETENIDO_MES = 457.9


# ============================================================
# TOLERANCIAS
# ============================================================


LINE_Y_TOLERANCE = 5.0

VALUE_Y_TOLERANCE = 24.0

BOX_PADDING_X = 10.0

BOX_PADDING_Y = 10.0


# ============================================================
# PATRONES
# ============================================================


INTEGER_PATTERN = re.compile(
    r"^\d+$"
)


MONEY_PATTERN = re.compile(
    r"^\$?\s*[\d,]+(?:\.\d{1,2})?$"
)


PERCENTAGE_PATTERN = re.compile(
    r"^\d+(?:[.,]\d+)?%?$"
)


PERIOD_DATE_PATTERN = re.compile(
    r"\b\d{2}[/-]\d{2}[/-]\d{4}\b"
)


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================


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
    Limpia el texto de una word.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip()


def normalized_word_text(
    word: Dict[str, Any],
) -> str:
    """
    Devuelve el texto normalizado de una word.
    """

    return normalize_text(
        word.get(
            "text",
            "",
        )
    )


# ============================================================
# UTILIDADES NUMÉRICAS SEGURAS
# ============================================================


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte de forma segura a float.
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
    Devuelve el número de página.
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
    Determina si el centro de la word está dentro de la caja.
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
    Calcula la caja envolvente de un renglón.
    """

    if not line:
        return (
            0.0,
            0.0,
            0.0,
            0.0,
        )

    xmin = min(
        safe_float(
            word.get(
                "x0",
                0.0,
            )
        )
        for word in line
    )

    xmax = max(
        safe_float(
            word.get(
                "x1",
                0.0,
            )
        )
        for word in line
    )

    ymin = min(
        safe_float(
            word.get(
                "top",
                0.0,
            )
        )
        for word in line
    )

    ymax = max(
        safe_float(
            word.get(
                "bottom",
                0.0,
            )
        )
        for word in line
    )

    return (
        xmin,
        xmax,
        ymin,
        ymax,
    )


def line_center_x(
    line: Sequence[
        Dict[str, Any]
    ],
) -> float:
    """
    Centro horizontal de un renglón.
    """

    xmin, xmax, _, _ = line_bounds(
        line
    )

    return (
        xmin + xmax
    ) / 2.0


def line_center_y(
    line: Sequence[
        Dict[str, Any]
    ],
) -> float:
    """
    Centro vertical de un renglón.
    """

    _, _, ymin, ymax = line_bounds(
        line
    )

    return (
        ymin + ymax
    ) / 2.0


# ============================================================
# AGRUPACIÓN EN RENGLONES
# ============================================================


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
    Agrupa words en renglones lógicos.

    La agrupación se realiza por página y proximidad vertical.

    Las palabras de una misma línea pueden presentar pequeñas
    diferencias verticales por efecto del OCR.
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

        _, center_y = word_center(
            word
        )

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

            line_y = line_center_y(
                line
            )

            distance = abs(
                center_y
                -
                line_y
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
                line_y
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


def normalized_line_text(
    line: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Texto normalizado del renglón.
    """

    return normalize_text(
        line_text(
            line
        )
    )


# ============================================================
# AGRUPACIÓN POR PÁGINA
# ============================================================


def page_groups(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Dict[
    int,
    List[
        Dict[str, Any]
    ]
]:
    """
    Agrupa words por página.
    """

    result: Dict[
        int,
        List[
            Dict[str, Any]
        ]
    ] = {}

    for word in words:

        page = safe_page(
            word
        )

        result.setdefault(
            page,
            []
        ).append(
            word
        )

    return result


# ============================================================
# DETECCIÓN DE PÁGINA
# ============================================================


def score_financial_page(
    words: Sequence[
        Dict[str, Any]
    ],
) -> int:
    """
    Calcula evidencia de que una página contiene el resumen
    financiero HSBC.
    """

    lines = group_words_into_lines(
        words
    )

    normalized_lines = [
        normalized_line_text(
            line
        )
        for line in lines
    ]

    joined = " ".join(
        normalized_lines
    )

    score = 0

    if "RESUMEN" in joined:
        score += 5

    if "SALDO INICIAL" in joined:
        score += 8

    elif (
        "SALDO" in joined
        and
        "INICIAL" in joined
    ):
        score += 5

    if "DEPOSITOS" in joined:
        score += 4

    if "ABONOS" in joined:
        score += 4

    if "RETIROS" in joined:
        score += 3

    if "CARGOS" in joined:
        score += 3

    if (
        "INTERESES" in joined
        and
        "NETOS" in joined
    ):
        score += 5

    if "SALDO FINAL" in joined:
        score += 8

    if (
        "DIAS" in joined
        and
        "TRANSCURRIDOS" in joined
    ):
        score += 5

    if (
        "COMISIONES COBRADAS"
        in joined
    ):
        score += 6

    if (
        "SALDO PROMEDIO"
        in joined
    ):
        score += 6

    if (
        "TASA PROMEDIO NOMINAL"
        in joined
    ):
        score += 6

    if (
        "ISR RETENIDO"
        in joined
    ):
        score += 6

    if (
        "PAGO INTERES NOMINAL"
        in joined
    ):
        score += 6

    right_side_words = [
        word
        for word in words
        if (
            safe_float(
                word.get(
                    "x0",
                    0.0,
                )
            )
            >= BOX_FINANCIAL_VALUE[0]
        )
    ]

    if right_side_words:
        score += 2

    return score


def find_financial_page(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[int]:
    """
    Encuentra la página más probable del resumen financiero.
    """

    groups = page_groups(
        words
    )

    if not groups:
        return None

    scored_pages = []

    for page, page_words in groups.items():

        score = score_financial_page(
            page_words
        )

        if score > 0:

            scored_pages.append(
                (
                    score,
                    page,
                )
            )

    if not scored_pages:
        return None

    scored_pages.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    return scored_pages[0][1]


# ============================================================
# LOCALIZACIÓN DE ANCLAS
# ============================================================


def line_contains_tokens(
    line: Sequence[
        Dict[str, Any]
    ],
    tokens: Sequence[str],
) -> bool:
    """
    Determina si el renglón contiene todos los tokens.
    """

    normalized = normalized_line_text(
        line
    )

    return all(
        normalize_text(token)
        in normalized
        for token in tokens
    )


def find_anchor_lines(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    tokens: Sequence[str],
) -> List[
    List[
        Dict[str, Any]
    ]
]:
    """
    Busca todos los renglones que contienen la etiqueta.
    """

    return [
        list(line)
        for line in lines
        if line_contains_tokens(
            line,
            tokens,
        )
    ]


def find_best_anchor_line(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    tokens: Sequence[str],
    expected_y: Optional[float] = None,
) -> Optional[
    List[
        Dict[str, Any]
    ]
]:
    """
    Selecciona la mejor línea ancla.

    El texto determina los candidatos.

    expected_y únicamente resuelve ambigüedades entre
    múltiples coincidencias.
    """

    candidates = find_anchor_lines(
        lines,
        tokens,
    )

    if not candidates:
        return None

    if expected_y is None:
        return list(
            candidates[0]
        )

    return min(
        candidates,
        key=lambda line: abs(
            line_center_y(line)
            -
            expected_y
        ),
    )


# ============================================================
# DETECCIÓN DE WORDS NUMÉRICAS
# ============================================================


def normalize_numeric_text(
    value: str,
) -> str:
    """
    Normaliza un valor numérico sin convertirlo todavía.
    """

    text = value.strip()

    if not text:
        return ""

    text = text.replace(
        "$",
        "",
    )

    text = text.replace(
        " ",
        "",
    )

    text = text.replace(
        ",",
        "",
    )

    return text


def is_numeric_word(
    word: Dict[str, Any],
) -> bool:
    """
    Determina si la word representa una parte de un valor
    financiero.
    """

    text = clean_word_text(
        word.get(
            "text",
            "",
        )
    )

    if not text:
        return False

    if text == "$":
        return True

    normalized = normalize_numeric_text(
        text
    )

    if not normalized:
        return False

    if MONEY_PATTERN.fullmatch(
        text
    ):
        return True

    if INTEGER_PATTERN.fullmatch(
        normalized
    ):
        return True

    if PERCENTAGE_PATTERN.fullmatch(
        normalized
    ):
        return True

    return False


def extract_numeric_text_from_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Reconstruye un valor desde sus words numéricas.
    """

    if not words:
        return None

    ordered = sorted(
        words,
        key=lambda word: safe_float(
            word.get(
                "x0",
                0.0,
            )
        ),
    )

    parts = []

    for word in ordered:

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

        normalized = normalize_numeric_text(
            text
        )

        if normalized:
            parts.append(
                normalized
            )

    if not parts:
        return None

    value = "".join(
        parts
    )

    if not re.fullmatch(
        r"\d+(?:\.\d+)?",
        value,
    ):
        return None

    return value


# ============================================================
# PARSERS DE TIPO
# ============================================================


def parse_money(
    value: Optional[str],
) -> Optional[float]:
    """
    Convierte importe monetario a float.
    """

    if value is None:
        return None

    value = normalize_numeric_text(
        value
    )

    if not re.fullmatch(
        r"\d+(?:\.\d{1,2})?",
        value,
    ):
        return None

    try:
        return float(
            value
        )
    except ValueError:
        return None


def parse_integer(
    value: Optional[str],
) -> Optional[int]:
    """
    Convierte entero a int.
    """

    if value is None:
        return None

    value = value.strip()

    if not re.fullmatch(
        r"\d+",
        value,
    ):
        return None

    try:
        return int(
            value
        )
    except ValueError:
        return None


def parse_percentage(
    value: Optional[str],
) -> Optional[float]:
    """
    Convierte porcentaje a float.

    Ejemplo:

        0.0000%

    →

        0.0
    """

    if value is None:
        return None

    value = value.strip()

    value = value.replace(
        "%",
        "",
    )

    value = value.replace(
        ",",
        ".",
    )

    if not re.fullmatch(
        r"\d+(?:\.\d+)?",
        value,
    ):
        return None

    try:
        return float(
            value
        )
    except ValueError:
        return None


# ============================================================
# COLUMNA FINANCIERA
# ============================================================


def value_column_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Devuelve únicamente words numéricas ubicadas dentro de la
    columna financiera derecha.
    """

    result = []

    xmin, xmax, ymin, ymax = (
        BOX_FINANCIAL_VALUE
    )

    for word in words:

        if not is_numeric_word(
            word
        ):
            continue

        center_x, center_y = word_center(
            word
        )

        if not (
            xmin - BOX_PADDING_X
            <= center_x
            <= xmax + BOX_PADDING_X
        ):
            continue

        if not (
            ymin - BOX_PADDING_Y
            <= center_y
            <= ymax + BOX_PADDING_Y
        ):
            continue

        result.append(
            word
        )

    return result


# ============================================================
# ASOCIACIÓN ANCLA → VALOR
# ============================================================


def value_candidates_near_anchor(
    words: Sequence[
        Dict[str, Any]
    ],
    anchor: Sequence[
        Dict[str, Any]
    ],
    expected_y: Optional[float] = None,
) -> List[
    Dict[str, Any]
]:
    """
    Busca candidatos numéricos en la columna financiera.

    La asociación utiliza:

        1. ancla semántica;
        2. columna X;
        3. proximidad Y.

    Cuando expected_y existe, se utiliza como referencia
    principal del VALOR.

    Esto evita errores en etiquetas multilínea.
    """

    if not anchor:
        return []

    anchor_y = line_center_y(
        anchor
    )

    reference_y = (
        expected_y
        if expected_y is not None
        else anchor_y
    )

    candidates = []

    for word in value_column_words(
        words
    ):

        _, center_y = word_center(
            word
        )

        distance = abs(
            center_y
            -
            reference_y
        )

        if (
            distance
            >
            VALUE_Y_TOLERANCE
        ):
            continue

        candidates.append(
            (
                distance,
                word,
            )
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            word_center(
                item[1]
            )[1],
            word_center(
                item[1]
            )[0],
        )
    )

    return [
        word
        for _, word in candidates
    ]


def select_value_row(
    candidates: Sequence[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Selecciona el grupo de words que forma el mismo valor.

    Por ejemplo:

        $
        7,589.17

    se considera un único valor.
    """

    if not candidates:
        return []

    first_y = word_center(
        candidates[0]
    )[1]

    result = [
        word
        for word in candidates
        if abs(
            word_center(word)[1]
            -
            first_y
        )
        <= LINE_Y_TOLERANCE
    ]

    result.sort(
        key=lambda word: safe_float(
            word.get(
                "x0",
                0.0,
            )
        )
    )

    return result


def extract_value_near_anchor(
    words: Sequence[
        Dict[str, Any]
    ],
    anchor: Sequence[
        Dict[str, Any]
    ],
    expected_y: Optional[float] = None,
) -> Optional[str]:
    """
    Extrae el texto numérico asociado a un ancla.
    """

    candidates = value_candidates_near_anchor(
        words,
        anchor,
        expected_y=expected_y,
    )

    if not candidates:
        return None

    value_words = select_value_row(
        candidates
    )

    if not value_words:
        return None

    return extract_numeric_text_from_words(
        value_words
    )


# ============================================================
# FALLBACKS SEMÁNTICOS PARA LAYOUTS OCR ALTERNOS
# ============================================================


def extract_money_from_line_column(
    line: Sequence[
        Dict[str, Any]
    ],
    column: Tuple[
        float,
        float,
    ],
) -> Optional[float]:
    """Extrae el importe contenido en una columna del renglón."""

    xmin, xmax = column

    value_words = [
        word
        for word in line
        if (
            is_numeric_word(word)
            and
            xmin
            <= word_center(word)[0]
            <= xmax
        )
    ]

    value = extract_numeric_text_from_words(
        value_words
    )

    return parse_money(
        value
    )


def extract_movement_total(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    tokens: Sequence[str],
    column: Tuple[
        float,
        float,
    ],
) -> Optional[float]:
    """
    Suma movimientos que contienen los tokens indicados.

    Se excluyen explícitamente las filas resumen mensuales y
    anuales; sólo se aceptan importes dentro de la columna del
    detalle de movimientos.
    """

    values = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if not all(
            normalize_text(token)
            in normalized
            for token in tokens
        ):
            continue

        if (
            "MES" in normalized
            or
            "ANO" in normalized
        ):
            continue

        value = extract_money_from_line_column(
            line,
            column,
        )

        if value is not None:
            values.append(
                value
            )

    if not values:
        return None

    return sum(
        values
    )


def extract_days_from_period(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
) -> Optional[int]:
    """Calcula los días inclusivos desde el periodo impreso."""

    for line in lines:

        if "PERIODO" not in normalized_line_text(
            line
        ):
            continue

        dates = PERIOD_DATE_PATTERN.findall(
            line_text(
                line
            )
        )

        if len(dates) < 2:
            continue

        try:

            start = datetime.strptime(
                dates[0].replace("-", "/"),
                "%d/%m/%Y",
            )

            end = datetime.strptime(
                dates[1].replace("-", "/"),
                "%d/%m/%Y",
            )

        except ValueError:
            continue

        days = (
            end - start
        ).days + 1

        if 1 <= days <= 62:
            return days

    return None


def extract_first_numeric_after_token(
    line: Sequence[
        Dict[str, Any]
    ],
    token: str,
) -> Optional[str]:
    """Toma el primer valor ubicado a la derecha del token."""

    label_words = [
        word
        for word in line
        if normalize_text(token)
        in normalized_word_text(word)
    ]

    if not label_words:
        return None

    label_right = max(
        safe_float(
            word.get(
                "x1",
                0.0,
            )
        )
        for word in label_words
    )

    candidates = sorted(
        (
            word
            for word in line
            if (
                is_numeric_word(word)
                and
                safe_float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
                >= label_right - 1.0
            )
        ),
        key=lambda word: safe_float(
            word.get(
                "x0",
                0.0,
            )
        ),
    )

    if not candidates:
        return None

    value_words = [
        candidates[0]
    ]

    if (
        clean_word_text(
            candidates[0].get(
                "text",
                "",
            )
        )
        == "$"
        and
        len(candidates) > 1
        and
        abs(
            word_center(candidates[1])[1]
            - word_center(candidates[0])[1]
        )
        <= LINE_Y_TOLERANCE
    ):

        value_words.append(
            candidates[1]
        )

    return extract_numeric_text_from_words(
        value_words
    )


def extract_saldo_promedio_by_order(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Recupera el saldo promedio cuando su etiqueta no fue OCR.

    HSBC imprime el saldo promedio antes del pago de interés
    mensual. Sólo se usa este respaldo cuando el mismo importe
    mensual también fue confirmado en movimientos.
    """

    monthly_interest = extract_movement_total(
        lines,
        (
            "PAGO",
            "INTERES",
            "NOMINAL",
        ),
        MOVEMENT_ABONO_X,
    )

    if monthly_interest is None:
        return None

    annual_anchor = find_best_anchor_line(
        lines,
        (
            "PAGO",
            "INTERES",
            "NOMINAL",
            "ANO",
        ),
        expected_y=EXPECTED_Y_PAGO_INTERES_MES,
    )

    if annual_anchor is None:
        return None

    annual_y = line_center_y(
        annual_anchor
    )

    rows = []

    for word in sorted(
        value_column_words(words),
        key=lambda item: word_center(item)[1],
    ):

        _, center_y = word_center(
            word
        )

        if not (
            annual_y - 85.0
            <= center_y
            <= annual_y - LINE_Y_TOLERANCE
        ):
            continue

        matching_row = next(
            (
                row
                for row in rows
                if abs(
                    row[0]
                    - center_y
                )
                <= LINE_Y_TOLERANCE
            ),
            None,
        )

        if matching_row is None:
            rows.append(
                [
                    center_y,
                    [word],
                ]
            )
        else:
            matching_row[1].append(
                word
            )

    parsed_rows = []

    for center_y, row_words in rows:

        value = parse_money(
            extract_numeric_text_from_words(
                row_words
            )
        )

        if value is not None:
            parsed_rows.append(
                (
                    center_y,
                    value,
                )
            )

    monthly_rows = [
        row
        for row in parsed_rows
        if abs(
            row[1]
            - monthly_interest
        )
        <= 0.01
    ]

    if not monthly_rows:
        return None

    monthly_y = max(
        row[0]
        for row in monthly_rows
    )

    previous_rows = [
        row
        for row in parsed_rows
        if (
            row[0]
            < monthly_y - LINE_Y_TOLERANCE
            and
            abs(row[1])
            > abs(monthly_interest) + 0.01
        )
    ]

    if not previous_rows:
        return None

    previous_rows.sort(
        key=lambda row: row[0],
        reverse=True,
    )

    return previous_rows[0][1]


def is_producto_basico_general_summary(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
) -> bool:
    """
    Confirma el layout cuyo título es PRODUCTO BASICO GENERAL.

    En este formato Tesseract puede omitir por completo los ``$0.00``
    de la tabla inferior aunque las etiquetas mensuales sí estén
    presentes. La marca de producto limita el respaldo a ese layout
    y evita convertir ausencias de otros productos en ceros.
    """

    return any(
        all(
            token in normalized_line_text(line)
            for token in (
                "PRODUCTO",
                "BASICO",
                "GENERAL",
            )
        )
        for line in lines
    )


def zero_for_missing_basic_product_value(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    anchor: Optional[
        Sequence[
            Dict[str, Any]
        ]
    ],
) -> Optional[float]:
    """Devuelve cero sólo para una etiqueta existente del layout."""

    if anchor is None:
        return None

    if not is_producto_basico_general_summary(lines):
        return None

    return 0.0


# ============================================================
# EXTRACTORES EXISTENTES
# ============================================================


def extract_saldo_anterior(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Saldo Inicial del -> saldo_anterior
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "SALDO",
            "INICIAL",
        ),
        expected_y=EXPECTED_Y_SALDO_ANTERIOR,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_SALDO_ANTERIOR,
    )

    return parse_money(
        value
    )


def extract_depositos_abonos(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Depósitos/ -> depositos_abonos
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "DEPOSITOS/",
        ),
        expected_y=EXPECTED_Y_DEPOSITOS_ABONOS,
    )

    if anchor is None:

        anchor = find_best_anchor_line(
            lines,
            (
                "DEPOSITOS",
            ),
            expected_y=EXPECTED_Y_DEPOSITOS_ABONOS,
        )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_DEPOSITOS_ABONOS,
    )

    return parse_money(
        value
    )


def extract_retiros_cargos(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Retiros/Cargos -> retiros_cargos
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "RETIROS/CARGOS",
        ),
        expected_y=EXPECTED_Y_RETIROS_CARGOS,
    )

    if anchor is None:

        anchor = find_best_anchor_line(
            lines,
            (
                "RETIROS",
                "CARGOS",
            ),
            expected_y=EXPECTED_Y_RETIROS_CARGOS,
        )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_RETIROS_CARGOS,
    )

    return parse_money(
        value
    )


def extract_intereses_a_favor(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae exclusivamente:

        Pago Interés Nominal en el Mes

    Este es el importe que aparece como abono independiente
    dentro del detalle de movimientos.

    La etiqueta mensual determina el renglón.

    El valor se obtiene respecto a la posición REAL del ancla
    encontrada para evitar confundirlo con:

        Pago de Interés Nominal en el Año
    """

    movement_value = extract_movement_total(
        lines,
        (
            "PAGO",
            "INTERES",
            "NOMINAL",
        ),
        MOVEMENT_ABONO_X,
    )

    if movement_value is not None:
        return movement_value

    anchor = find_best_anchor_line(
        lines,
        (
            "PAGO",
            "INTERES",
            "NOMINAL",
            "MES",
        ),
        expected_y=EXPECTED_Y_PAGO_INTERES_MES,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
    )

    parsed_value = parse_money(
        value
    )

    if parsed_value is not None:
        return parsed_value

    return zero_for_missing_basic_product_value(
        lines,
        anchor,
    )


def extract_dias_periodo(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[int]:
    """
    Días Transcurridos en el mes -> dias_periodo
    """

    period_days = extract_days_from_period(
        lines
    )

    anchor = find_best_anchor_line(
        lines,
        (
            "DIAS",
            "TRANSCURRIDOS",
            "MES",
        ),
        expected_y=EXPECTED_Y_DIAS_PERIODO,
    )

    if anchor is None:

        anchor = find_best_anchor_line(
            lines,
            (
                "DIAS",
                "TRANSCURRIDOS",
            ),
            expected_y=EXPECTED_Y_DIAS_PERIODO,
        )

    if anchor is None:
        return period_days

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_DIAS_PERIODO,
    )

    parsed_days = parse_integer(
        value
    )

    if (
        period_days is not None
        and
        parsed_days != period_days
    ):
        return period_days

    return parsed_days


def extract_saldo_final(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Saldo Final -> saldo_final
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "SALDO",
            "FINAL",
        ),
        expected_y=EXPECTED_Y_SALDO_FINAL,
    )

    if anchor is None:
        return None

    same_line_value = extract_first_numeric_after_token(
        anchor,
        "FINAL",
    )

    parsed_same_line_value = parse_money(
        same_line_value
    )

    if parsed_same_line_value is not None:
        return parsed_same_line_value

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_SALDO_FINAL,
    )

    return parse_money(
        value
    )


# ============================================================
# NUEVOS EXTRACTORES
# ============================================================


def extract_saldo_promedio(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae:

        El Saldo Promedio en el Mes
        (promedio de los saldos diarios del periodo)
        de su cuenta fue:

                            $ 7,589.17

    Se utiliza expected_y porque la descripción ocupa un
    renglón largo y el valor aparece posteriormente.
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "SALDO",
            "PROMEDIO",
            "MES",
        ),
        expected_y=EXPECTED_Y_SALDO_PROMEDIO,
    )

    if anchor is not None:

        value = extract_value_near_anchor(
            words,
            anchor,
        )

        parsed_value = parse_money(
            value
        )

        if parsed_value is not None:
            return parsed_value

        basic_product_zero = (
            zero_for_missing_basic_product_value(
                lines,
                anchor,
            )
        )

        if basic_product_zero is not None:
            return basic_product_zero

    return extract_saldo_promedio_by_order(
        lines,
        words,
    )


def extract_tasa_bruta_anual(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae:

        Tasa Promedio Nominal       0.0000%

    y la asigna a:

        tasa_bruta_anual
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "TASA",
            "PROMEDIO",
            "NOMINAL",
        ),
        expected_y=EXPECTED_Y_TASA_PROMEDIO_NOMINAL,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_TASA_PROMEDIO_NOMINAL,
    )

    return parse_percentage(
        value
    )


def extract_manejo_cuenta(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae:

        Comisiones Cobradas en el Mes       $ 0.00

    y lo asigna a:

        manejo_cuenta
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "COMISIONES",
            "COBRADAS",
            "MES",
        ),
        expected_y=EXPECTED_Y_COMISIONES_COBRADAS,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_COMISIONES_COBRADAS,
    )

    return parse_money(
        value
    )


def extract_saldo_promedio_minimo_mensual(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae el valor asociado a:

        El Saldo Promedio Mínimo Requerido para
        Exentar el Cobro de la Comisión de Administración
        Renta es:

                            $ 0.00

    y lo asigna a:

        saldo_promedio_minimo_mensual
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "SALDO",
            "PROMEDIO",
            "MINIMO",
            "REQUERIDO",
        ),
        expected_y=EXPECTED_Y_SALDO_PROMEDIO_MINIMO,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
        expected_y=EXPECTED_Y_SALDO_PROMEDIO_MINIMO,
    )

    return parse_money(
        value
    )


def extract_isr_retenido(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Extrae exclusivamente:

        ISR Retenido en el Mes

    Este es el importe que aparece como cargo independiente
    dentro del detalle de movimientos.

    La etiqueta mensual determina el renglón.

    El valor se obtiene respecto a la posición REAL del ancla
    encontrada para evitar confundirlo con:

        ISR Retenido en el Año
    """

    movement_value = extract_movement_total(
        lines,
        (
            "RETENIDO",
        ),
        MOVEMENT_CARGO_X,
    )

    if movement_value is not None:
        return movement_value

    anchor = find_best_anchor_line(
        lines,
        (
            "ISR",
            "RETENIDO",
            "MES",
        ),
        expected_y=EXPECTED_Y_ISR_RETENIDO_MES,
    )

    if anchor is None:
        return None

    value = extract_value_near_anchor(
        words,
        anchor,
    )

    parsed_value = parse_money(
        value
    )

    if parsed_value is not None:
        return parsed_value

    return zero_for_missing_basic_product_value(
        lines,
        anchor,
    )


# ============================================================
# CAMPOS SIN EVIDENCIA SUFICIENTE TODAVÍA
# ============================================================


def extract_saldo_promedio_gravable(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Pendiente.

    No se encuentra una etiqueta inequívoca de
    "Saldo promedio gravable" en las coordenadas proporcionadas.
    """

    return None


def extract_cheques_pagados(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[int]:
    """
    Pendiente.

    No se proporcionó todavía un renglón inequívoco de
    cheques pagados.
    """

    return None


def extract_cargos_objetados(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Pendiente.

    No se proporcionó todavía el renglón correspondiente.
    """

    return None


def extract_abonos_objetados(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Pendiente.

    No se proporcionó todavía el renglón correspondiente.
    """

    return None


def extract_saldo_global(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[float]:
    """
    Pendiente.

    No se proporcionó todavía una etiqueta inequívoca
    para saldo global.
    """

    return None


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_resumen_financiero_words(
    words: List[
        Dict[str, Any]
    ],
) -> ResumenFinanciero:
    """
    Extractor robusto de ResumenFinanciero HSBC.

    Arquitectura:

        WORDS
          ↓
        PÁGINA FINANCIERA
          ↓
        RENGLONES LÓGICOS
          ↓
        ANCLA SEMÁNTICA
          ↓
        COLUMNA DE VALORES
          ↓
        REFERENCIA Y DEL VALOR
          ↓
        RECONSTRUCCIÓN DEL VALOR
          ↓
        PARSING / VALIDACIÓN
          ↓
        ResumenFinanciero

    Características:

        - trabaja directamente con words;
        - reconstruye renglones lógicos;
        - usa texto como ancla;
        - usa X para distinguir la columna;
        - usa Y esperado del VALOR;
        - soporta etiquetas multilínea;
        - soporta valores compuestos por varias words;
        - tolera desplazamientos moderados del OCR;
        - no depende de texto concatenado previamente.
    """

    # ========================================================
    # 1. SIN WORDS
    # ========================================================

    if not words:

        return ResumenFinanciero(
            saldo_promedio=None,
            dias_periodo=None,
            tasa_bruta_anual=None,
            saldo_promedio_gravable=None,
            intereses_a_favor=None,
            isr_retenido=None,
            cheques_pagados=None,
            manejo_cuenta=None,
            cargos_objetados=None,
            abonos_objetados=None,
            saldo_anterior=None,
            depositos_abonos=None,
            retiros_cargos=None,
            saldo_final=None,
            saldo_promedio_minimo_mensual=None,
            saldo_global=None,
        )

    # ========================================================
    # 2. LOCALIZAR PÁGINA FINANCIERA
    # ========================================================

    financial_page = find_financial_page(
        words
    )

    if financial_page is not None:

        financial_words = [
            word
            for word in words
            if safe_page(word)
            ==
            financial_page
        ]

    else:

        financial_words = list(
            words
        )

    # ========================================================
    # 3. AGRUPAR EN RENGLONES
    # ========================================================

    lines = group_words_into_lines(
        financial_words
    )

    # ========================================================
    # 4. CAMPOS EXISTENTES
    # ========================================================

    saldo_anterior = (
        extract_saldo_anterior(
            lines,
            financial_words,
        )
    )

    depositos_abonos = (
        extract_depositos_abonos(
            lines,
            financial_words,
        )
    )

    retiros_cargos = (
        extract_retiros_cargos(
            lines,
            financial_words,
        )
    )

    intereses_a_favor = (
        extract_intereses_a_favor(
            lines,
            financial_words,
        )
    )

    dias_periodo = (
        extract_dias_periodo(
            lines,
            financial_words,
        )
    )

    saldo_final = (
        extract_saldo_final(
            lines,
            financial_words,
        )
    )

    # ========================================================
    # 5. NUEVOS CAMPOS
    # ========================================================

    saldo_promedio = (
        extract_saldo_promedio(
            lines,
            financial_words,
        )
    )

    tasa_bruta_anual = (
        extract_tasa_bruta_anual(
            lines,
            financial_words,
        )
    )

    manejo_cuenta = (
        extract_manejo_cuenta(
            lines,
            financial_words,
        )
    )

    saldo_promedio_minimo_mensual = (
        extract_saldo_promedio_minimo_mensual(
            lines,
            financial_words,
        )
    )

    isr_retenido = (
        extract_isr_retenido(
            lines,
            financial_words,
        )
    )

    # ========================================================
    # 6. CAMPOS TODAVÍA NO IDENTIFICADOS
    # ========================================================

    saldo_promedio_gravable = (
        extract_saldo_promedio_gravable(
            lines,
            financial_words,
        )
    )

    cheques_pagados = (
        extract_cheques_pagados(
            lines,
            financial_words,
        )
    )

    cargos_objetados = (
        extract_cargos_objetados(
            lines,
            financial_words,
        )
    )

    abonos_objetados = (
        extract_abonos_objetados(
            lines,
            financial_words,
        )
    )

    saldo_global = (
        extract_saldo_global(
            lines,
            financial_words,
        )
    )

    # ========================================================
    # 7. AJUSTE DE TOTALES PARA VALIDACIÓN DE MOVIMIENTOS
    # ========================================================
    #
    # HSBC presenta en el resumen:
    #
    #     Depósitos / Abonos
    #     Retiros / Cargos
    #
    # sin incorporar en esos dos importes los movimientos
    # separados correspondientes a:
    #
    #     Pago Interés Nominal en el Mes
    #     ISR Retenido en el Mes
    #
    # Como dichos conceptos sí aparecen individualmente dentro
    # del detalle de movimientos, reconstruimos los totales
    # antes de enviarlos al modelo.
    #
    # Ejemplo:
    #
    #     3,000.00 + 248.51 = 3,248.51
    #
    #     0.00 + 56.96 = 56.96
    #
    # No se fabrica ningún total cuando falta alguno de los
    # componentes requeridos.
    # ========================================================

    if (
        depositos_abonos is not None
        and intereses_a_favor is not None
    ):
        depositos_abonos += intereses_a_favor

    if (
        retiros_cargos is not None
        and isr_retenido is not None
    ):
        retiros_cargos += isr_retenido

    # ========================================================
    # 8. MODELO
    # ========================================================

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,

        dias_periodo=dias_periodo,

        tasa_bruta_anual=tasa_bruta_anual,

        saldo_promedio_gravable=(
            saldo_promedio_gravable
        ),

        intereses_a_favor=(
            intereses_a_favor
        ),

        isr_retenido=(
            isr_retenido
        ),

        cheques_pagados=(
            cheques_pagados
        ),

        manejo_cuenta=(
            manejo_cuenta
        ),

        cargos_objetados=(
            cargos_objetados
        ),

        abonos_objetados=(
            abonos_objetados
        ),

        saldo_anterior=(
            saldo_anterior
        ),

        depositos_abonos=(
            depositos_abonos
        ),

        retiros_cargos=(
            retiros_cargos
        ),

        saldo_final=(
            saldo_final
        ),

        saldo_promedio_minimo_mensual=(
            saldo_promedio_minimo_mensual
        ),

        saldo_global=(
            saldo_global
        ),
    )
