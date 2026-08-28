from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.datos_cuenta import DatosCuenta


# ============================================================
# CONFIGURACIÓN ESPACIAL — DATOS DE CUENTA HSBC
# ============================================================
#
# Las coordenadas corresponden al formato observado en el
# estado de cuenta HSBC proporcionado.
#
# IMPORTANTE:
#
# Las coordenadas NO son utilizadas como posición absoluta
# rígida del documento.
#
# Se utilizan como referencia espacial para:
#
#   1. localizar la zona correcta;
#   2. distinguir columnas;
#   3. descartar palabras vecinas;
#   4. validar que el valor encontrado pertenezca al campo.
#
# La etiqueta textual actúa como ancla semántica.
#
# Esto permite soportar:
#
#   - PDF digital;
#   - PDF procesado mediante OCR;
#   - pequeños desplazamientos de OCR;
#   - palabras separadas;
#   - diferentes páginas iniciales;
#   - variaciones moderadas del layout.
#
# ============================================================


# ------------------------------------------------------------
# PRODUCTO PRINCIPAL
# ------------------------------------------------------------

BOX_PRODUCTO_PRINCIPAL = (
    240.0,
    370.0,
    15.0,
    55.0,
)


# ------------------------------------------------------------
# NOMBRE DEL CLIENTE
# ------------------------------------------------------------

BOX_NOMBRE_CLIENTE = (
    30.0,
    230.0,
    90.0,
    130.0,
)


# ------------------------------------------------------------
# NUMERO DE CUENTA
#
# Etiqueta:
#
#     NUMERO DE CUENTA
#
# Valor:
#
#     6270638192
#
# El límite derecho es IMPORTANTE:
#
#     no debe capturar columnas posteriores.
# ------------------------------------------------------------

BOX_NUMERO_CUENTA = (
    35.0,
    145.0,
    220.0,
    245.0,
)


# ------------------------------------------------------------
# CLABE
#
# Etiqueta:
#
#     CLABE INTERBANCARIA
#
# Valor:
#
#     021905062706381
#     925
#
# Resultado:
#
#     021905062706381925
# ------------------------------------------------------------

BOX_CLABE = (
    170.0,
    300.0,
    220.0,
    245.0,
)


# ------------------------------------------------------------
# NUMERO DE CLIENTE
#
# Valor:
#
#     38801782
# ------------------------------------------------------------

BOX_NUMERO_CLIENTE = (
    35.0,
    145.0,
    235.0,
    265.0,
)


# ------------------------------------------------------------
# RFC
#
# Valor:
#
#     GACJ700226PP2
# ------------------------------------------------------------

BOX_RFC = (
    35.0,
    145.0,
    250.0,
    280.0,
)


# ------------------------------------------------------------
# PERIODO
# ------------------------------------------------------------

BOX_PERIODO = (
    350.0,
    560.0,
    265.0,
    295.0,
)


# ============================================================
# CONSTANTES DE TOLERANCIA
# ============================================================

LINE_Y_TOLERANCE = 5.0

BOX_PADDING_X = 12.0
BOX_PADDING_Y = 10.0

VALUE_MAX_VERTICAL_DISTANCE = 45.0

MAX_CANDIDATE_PAGES = 12


# ============================================================
# PATRONES DE VALIDACIÓN
# ============================================================

ACCOUNT_PATTERN = re.compile(
    r"^\d{8,18}$"
)


CLIENT_PATTERN = re.compile(
    r"^\d{5,15}$"
)


CLABE_PATTERN = re.compile(
    r"^\d{18}$"
)


RFC_PATTERN = re.compile(
    r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,4}$",
    re.IGNORECASE,
)



DATE_PATTERN = re.compile(
    r"\b\d{2}[/-]\d{2}[/-]\d{4}\b"
)


# Algunos OCR de HSBC omiten únicamente el primer separador
# de la segunda fecha del periodo:
#
#     31/08/2024  ->  3108/2024
#
# El patrón conserva la estructura día/mes/año y exige el
# separador anterior al año. De esta manera no confunde una
# cuenta, una tarjeta o una CLABE con una fecha.
OCR_DATE_PATTERN = re.compile(
    r"(?<!\d)(\d{2})[/-]?(\d{2})[/-](\d{4})(?!\d)"
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
    Limpia el texto individual de una word.
    """

    if value is None:
        return ""

    return str(value).strip()


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
# UTILIDADES GEOMÉTRICAS
# ============================================================


def word_center(
    word: Dict[str, Any],
) -> Tuple[float, float]:
    """
    Devuelve el centro geométrico de una word.
    """

    x0 = float(
        word.get(
            "x0",
            0.0,
        )
    )

    x1 = float(
        word.get(
            "x1",
            x0,
        )
    )

    top = float(
        word.get(
            "top",
            0.0,
        )
    )

    bottom = float(
        word.get(
            "bottom",
            top,
        )
    )

    return (
        (x0 + x1) / 2,
        (top + bottom) / 2,
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
    Determina si el centro de la palabra está dentro
    de una región espacial.
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


def words_in_box(
    words: Sequence[
        Dict[str, Any]
    ],
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
    padding_x: float = BOX_PADDING_X,
    padding_y: float = BOX_PADDING_Y,
) -> List[
    Dict[str, Any]
]:
    """
    Devuelve las words localizadas dentro de una caja.
    """

    selected = [
        word
        for word in words
        if word_inside_box(
            word,
            box,
            padding_x=padding_x,
            padding_y=padding_y,
        )
    ]

    selected.sort(
        key=lambda word: (
            int(
                word.get(
                    "page",
                    1,
                )
            ),
            float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    return selected


def box_center(
    box: Tuple[
        float,
        float,
        float,
        float,
    ],
) -> Tuple[
    float,
    float,
]:
    """
    Devuelve el centro de una caja.
    """

    xmin, xmax, ymin, ymax = box

    return (
        (xmin + xmax) / 2,
        (ymin + ymax) / 2,
    )


# ============================================================
# AGRUPACIÓN DE WORDS EN RENGLONES
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
    Agrupa words que pertenecen al mismo renglón.

    Se utiliza únicamente para localizar y entender
    las etiquetas y estructuras del documento.

    IMPORTANTE:

    El resultado de esta función NO se utiliza como
    valor final de un campo.

    Para extraer valores se vuelven a seleccionar
    las words mediante coordenadas.
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

    valid_words = sorted(
        valid_words,
        key=lambda word: (
            int(
                word.get(
                    "page",
                    1,
                )
            ),
            float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        ),
    )

    lines: List[
        List[
            Dict[str, Any]
        ]
    ] = []

    for word in valid_words:

        _, center_y = word_center(
            word
        )

        placed = False

        for line in reversed(lines):

            if not line:
                continue

            _, line_center_y = word_center(
                line[-1]
            )

            if (
                abs(
                    center_y
                    -
                    line_center_y
                )
                <= y_tolerance
            ):

                line.append(
                    word
                )

                placed = True
                break

        if not placed:

            lines.append(
                [word]
            )

    for line in lines:

        line.sort(
            key=lambda word: (
                float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
            )
        )

    return lines


def line_text(
    line: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Concatena las palabras de un renglón.
    """

    values = []

    for word in line:

        text = clean_word_text(
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


def normalized_line_text(
    line: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Devuelve el texto normalizado de un renglón.
    """

    return normalize_text(
        line_text(
            line
        )
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
    Calcula la caja envolvente del renglón.
    """

    if not line:

        return (
            0.0,
            0.0,
            0.0,
            0.0,
        )

    xmin = min(
        float(
            word.get(
                "x0",
                0.0,
            )
        )
        for word in line
    )

    xmax = max(
        float(
            word.get(
                "x1",
                0.0,
            )
        )
        for word in line
    )

    ymin = min(
        float(
            word.get(
                "top",
                0.0,
            )
        )
        for word in line
    )

    ymax = max(
        float(
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


# ============================================================
# LOCALIZACIÓN DE ETIQUETAS
# ============================================================


def line_contains_tokens(
    line: Sequence[
        Dict[str, Any]
    ],
    tokens: Sequence[str],
) -> bool:
    """
    Determina si un renglón contiene todos los tokens indicados.
    """

    normalized = normalized_line_text(
        line
    )

    return all(
        normalize_text(token)
        in normalized
        for token in tokens
    )


def find_lines_containing_tokens(
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
    Busca renglones que contengan todos los tokens.
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
    expected_box: Optional[
        Tuple[
            float,
            float,
            float,
            float,
        ]
    ] = None,
) -> Optional[
    List[
        Dict[str, Any]
    ]
]:
    """
    Busca la mejor coincidencia textual y espacial.

    El texto determina si la línea es una etiqueta válida.

    La coordenada determina cuál coincidencia es la
    más probable.
    """

    candidates = (
        find_lines_containing_tokens(
            lines,
            tokens,
        )
    )

    if not candidates:

        return None

    if expected_box is None:

        return candidates[0]

    expected_x, expected_y = (
        box_center(
            expected_box
        )
    )

    best_line = None

    best_score = float(
        "inf"
    )

    for line in candidates:

        xmin, xmax, ymin, ymax = (
            line_bounds(
                line
            )
        )

        center_x = (
            xmin + xmax
        ) / 2

        center_y = (
            ymin + ymax
        ) / 2

        distance = (
            abs(
                center_x
                -
                expected_x
            )
            +
            abs(
                center_y
                -
                expected_y
            )
        )

        if distance < best_score:

            best_score = distance

            best_line = list(
                line
            )

    return best_line


# ============================================================
# PÁGINA DE DATOS HSBC
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
    Agrupa words por número de página.
    """

    result: Dict[
        int,
        List[
            Dict[str, Any]
        ]
    ] = {}

    for word in words:

        try:

            page = int(
                word.get(
                    "page",
                    1,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            page = 1

        result.setdefault(
            page,
            []
        ).append(
            word
        )

    return result


def score_data_page(
    words: Sequence[
        Dict[str, Any]
    ],
) -> int:
    """
    Calcula qué tan probable es que una página sea
    la página principal de datos de cuenta HSBC.
    """

    score = 0

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

    if (
        "NUMERO DE CUENTA"
        in joined
    ):
        score += 10

    if "CLABE" in joined:

        score += 7

    if (
        "NUMERO DE CLIENTE"
        in joined
    ):
        score += 7

    if re.search(
        r"\bRFC\b",
        joined,
    ):
        score += 6

    if (
        "RESUMEN DE CUENTAS"
        in joined
    ):
        score += 5

    if "PERIODO" in joined:

        score += 3

    if (
        "SALDO INICIAL"
        in joined
    ):
        score += 2

    if (
        "SALDO FINAL"
        in joined
    ):
        score += 2

    return score


def find_data_page(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[int]:
    """
    Encuentra automáticamente la página de datos.

    No depende de que sea página 2.
    """

    groups = page_groups(
        words
    )

    scored_pages = []

    for page, page_words in groups.items():

        score = score_data_page(
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
# UTILIDADES DE POSICIONAMIENTO DE VALORES
# ============================================================


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
    ) / 2


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
    ) / 2


def value_words_near_anchor(
    words: Sequence[
        Dict[str, Any]
    ],
    anchor: Sequence[
        Dict[str, Any]
    ],
    value_box: Tuple[
        float,
        float,
        float,
        float,
    ],
    max_vertical_distance: float = VALUE_MAX_VERTICAL_DISTANCE,
    padding_x: float = BOX_PADDING_X,
) -> List[
    Dict[str, Any]
]:
    """
    Obtiene ÚNICAMENTE las words que pertenecen a la región
    espacial del valor.

    Este es el punto clave del extractor HSBC.

    La etiqueta sirve como ancla.

    La caja del valor determina:

        - columna;
        - posición;
        - rango vertical.

    De esta manera NO se captura todo el renglón.

    Ejemplo:

        NUMERO DE CUENTA
        6270638192                         Saldo Final 9,949.54

    solo devuelve:

        6270638192
    """

    if not anchor:

        return []

    anchor_bottom = max(
        float(
            word.get(
                "bottom",
                0.0,
            )
        )
        for word in anchor
    )

    xmin, xmax, ymin, ymax = value_box

    result = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        _, center_y = word_center(
            word
        )

        center_x, _ = word_center(
            word
        )

        # ----------------------------------------------------
        # El valor debe estar después de la etiqueta.
        # ----------------------------------------------------

        if center_y < anchor_bottom:

            continue

        if (
            center_y
            >
            anchor_bottom
            +
            max_vertical_distance
        ):
            continue

        # ----------------------------------------------------
        # Restricción espacial horizontal.
        #
        # ESTE es el cambio fundamental.
        # ----------------------------------------------------

        if not (
            xmin - padding_x
            <= center_x
            <= xmax + padding_x
        ):
            continue

        # ----------------------------------------------------
        # Restricción espacial vertical adicional.
        # ----------------------------------------------------

        if (
            center_y
            <
            ymin - BOX_PADDING_Y
        ):
            continue

        if (
            center_y
            >
            ymax + BOX_PADDING_Y
        ):
            continue

        result.append(
            word
        )

    result.sort(
        key=lambda word: (
            float(
                word.get(
                    "top",
                    0.0,
                )
            ),
            float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )
    )

    return result


def compact_digits_from_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Concatena exclusivamente los dígitos encontrados
    en las words seleccionadas.
    """

    parts = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:

            parts.append(
                digits
            )

    return "".join(
        parts
    )


def compact_alphanumeric_from_words(
    words: Sequence[
        Dict[str, Any]
    ],
) -> str:
    """
    Concatena contenido alfanumérico de las words.
    """

    parts = []

    for word in words:

        text = clean_word_text(
            word.get(
                "text",
                "",
            )
        )

        cleaned = re.sub(
            r"[^A-Z0-9Ñ&]",
            "",
            text.upper(),
        )

        if cleaned:

            parts.append(
                cleaned
            )

    return "".join(
        parts
    )


# ============================================================
# EXTRACTOR NUMERO DE CUENTA
# ============================================================

def extract_account_from_anchor(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae únicamente el número de cuenta asociado a:

        NUMERO DE CUENTA

    El valor esperado está en la línea inmediatamente
    posterior a la etiqueta.

    La coordenada se utiliza para limitar la columna,
    evitando concatenar el número de cliente u otros
    valores que aparezcan más abajo dentro de la misma
    región horizontal.
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "NUMERO",
            "DE",
            "CUENTA",
        ),
        expected_box=(
            40.0,
            140.0,
            210.0,
            225.0,
        ),
    )

    if anchor is None:
        return None

    anchor_y = line_center_y(
        anchor
    )

    xmin, xmax, ymin, ymax = BOX_NUMERO_CUENTA

    # --------------------------------------------------------
    # Buscar solamente las líneas inmediatamente posteriores
    # a la etiqueta.
    # --------------------------------------------------------

    candidate_lines = []

    for line in lines:

        if not line:
            continue

        line_y = line_center_y(
            line
        )

        if line_y <= anchor_y:
            continue

        # No permitir que se vaya hasta campos posteriores.
        if line_y > anchor_y + 25.0:
            continue

        # ----------------------------------------------------
        # Seleccionar únicamente words de la columna de
        # número de cuenta.
        # ----------------------------------------------------

        value_words = [
            word
            for word in line
            if (
                xmin - BOX_PADDING_X
                <= word_center(word)[0]
                <= xmax + BOX_PADDING_X
            )
        ]

        if not value_words:
            continue

        value_words.sort(
            key=lambda word: float(
                word.get(
                    "x0",
                    0.0,
                )
            )
        )

        value = compact_digits_from_words(
            value_words
        )

        # ----------------------------------------------------
        # Debe existir un único número de cuenta válido.
        # ----------------------------------------------------

        if ACCOUNT_PATTERN.match(
            value
        ):
            return value

    return None


def extract_account_from_movement_header(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
) -> Optional[str]:
    """
    Fallback para layouts HSBC que no muestran la etiqueta:

        NUMERO DE CUENTA

    En esos formatos el dato continúa apareciendo de forma
    explícita en el encabezado semántico de movimientos:

        DETALLE MOVIMIENTOS ... NO. 6426571729

    Solo se consideran los dígitos posteriores a ``NO.``.
    Esto evita utilizar como cuenta el número de tarjeta que
    aparece en el bloque de datos generales.
    """

    candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if not (
            "DETALLE" in normalized
            and
            "MOVIMIENTOS" in normalized
        ):
            continue

        ordered_words = sorted(
            line,
            key=lambda word: float(
                word.get(
                    "x0",
                    0.0,
                )
            ),
        )

        marker_index = None

        for index, word in enumerate(
            ordered_words
        ):

            token = normalize_text(
                word.get(
                    "text",
                    "",
                )
            )

            token = token.rstrip(
                ".:"
            )

            if token == "NO":

                marker_index = index
                break

        if marker_index is None:
            continue

        value_words = ordered_words[
            marker_index + 1:
        ]

        value = compact_digits_from_words(
            value_words
        )

        if not ACCOUNT_PATTERN.fullmatch(
            value
        ):
            continue

        candidates.append(
            (
                line_center_y(line),
                value,
            )
        )

    if not candidates:
        return None

    # En el layout alterno el encabezado se encuentra en la
    # mitad inferior de la primera página. Si hubiera más de
    # uno, se conserva el primero en orden de lectura.
    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]

# ============================================================
# EXTRACTOR CLABE
# ============================================================


def extract_clabe_from_anchor(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae CLABE utilizando:

        CLABE INTERBANCARIA

    como ancla semántica.

    La extracción se restringe horizontalmente a BOX_CLABE.

    Esto evita capturar valores de otras columnas del
    mismo renglón.
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "CLABE",
        ),
        expected_box=(
            180.0,
            280.0,
            210.0,
            225.0,
        ),
    )

    if anchor is None:

        return None

    value_words = value_words_near_anchor(
        words,
        anchor,
        BOX_CLABE,
    )

    value = compact_digits_from_words(
        value_words
    )

    if CLABE_PATTERN.match(
        value
    ):

        return value

    # --------------------------------------------------------
    # Fallback:
    #
    # Algunos OCR pueden dividir la CLABE en pequeños
    # fragmentos y desplazar ligeramente uno de ellos.
    #
    # Permitimos buscar nuevamente en una caja ligeramente
    # mayor, pero seguimos restringiendo la columna.
    # --------------------------------------------------------

    expanded_box = (
        BOX_CLABE[0] - 15.0,
        BOX_CLABE[1] + 15.0,
        BOX_CLABE[2] - 5.0,
        BOX_CLABE[3] + 15.0,
    )

    value_words = value_words_near_anchor(
        words,
        anchor,
        expanded_box,
        max_vertical_distance=55.0,
        padding_x=15.0,
    )

    value = compact_digits_from_words(
        value_words
    )

    if CLABE_PATTERN.match(
        value
    ):

        return value

    return None


# ============================================================
# EXTRACTOR NUMERO DE CLIENTE
# ============================================================


def extract_numero_cliente_from_anchor(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae únicamente el número de cliente asociado a:

        NUMERO DE CLIENTE

    El extractor toma el valor de la línea siguiente a la
    etiqueta y limita la selección a la columna correspondiente.

    Esto evita concatenar el número de cuenta u otros valores
    que aparezcan posteriormente en la misma zona.
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "NUMERO",
            "DE",
            "CLIENTE",
        ),
        expected_box=(
            40.0,
            140.0,
            225.0,
            245.0,
        ),
    )

    if anchor is None:
        return None

    anchor_y = line_center_y(
        anchor
    )

    xmin, xmax, ymin, ymax = BOX_NUMERO_CLIENTE

    # --------------------------------------------------------
    # Buscar solamente la línea inmediatamente posterior.
    # --------------------------------------------------------

    candidate_lines = []

    for line in lines:

        if not line:
            continue

        line_y = line_center_y(
            line
        )

        if line_y <= anchor_y:
            continue

        # Evita alcanzar RFC u otros campos posteriores.
        if line_y > anchor_y + 25.0:
            continue

        # ----------------------------------------------------
        # Seleccionar únicamente words de la columna del
        # número de cliente.
        # ----------------------------------------------------

        value_words = [
            word
            for word in line
            if (
                xmin - BOX_PADDING_X
                <= word_center(word)[0]
                <= xmax + BOX_PADDING_X
            )
        ]

        if not value_words:
            continue

        value_words.sort(
            key=lambda word: float(
                word.get(
                    "x0",
                    0.0,
                )
            )
        )

        value = compact_digits_from_words(
            value_words
        )

        # ----------------------------------------------------
        # Debe existir un único número de cliente válido.
        # ----------------------------------------------------

        if CLIENT_PATTERN.match(
            value
        ):
            return value

    # --------------------------------------------------------
    # Fallback por word individual.
    #
    # Algunos OCR encadenan en un solo renglón lógico el valor
    # del cliente, la etiqueta RFC y el periodo. En ese caso la
    # concatenación del renglón deja de ser válida, aunque la
    # word inmediata posterior a NUMERO DE CLIENTE sí lo sea.
    # --------------------------------------------------------

    direct_candidates = []

    for word in words:

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
            anchor_y
            < center_y
            <= anchor_y + 25.0
        ):
            continue

        candidate = re.sub(
            r"\D",
            "",
            clean_word_text(
                word.get(
                    "text",
                    "",
                )
            ),
        )

        if CLIENT_PATTERN.fullmatch(
            candidate
        ):

            direct_candidates.append(
                (
                    center_y,
                    center_x,
                    candidate,
                )
            )

    if direct_candidates:

        direct_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        return direct_candidates[0][2]

    return None


# ============================================================
# EXTRACTOR RFC
# ============================================================


def extract_rfc_from_anchor(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae el RFC utilizando la etiqueta RFC como ancla
    semántica y la coordenada como delimitador de columna.

    Ejemplo del layout HSBC:

        RFC
        GACJ700226PP2
        CURP
        GACJ700226HVZRRN04

    El extractor NO toma toda la zona vertical porque eso
    podría mezclar RFC + CURP.

    La estrategia es:

        1. encontrar la línea "RFC";
        2. localizar las líneas posteriores;
        3. tomar únicamente las words de la columna RFC;
        4. evaluar cada línea por separado;
        5. devolver la primera que cumpla RFC_PATTERN.
    """

    anchor = find_best_anchor_line(
        lines,
        (
            "RFC",
        ),
        expected_box=(
            40.0,
            110.0,
            248.0,
            265.0,
        ),
    )

    if anchor is None:
        return None

    anchor_y = line_center_y(
        anchor
    )

    xmin, xmax, ymin, ymax = BOX_RFC

    candidate_lines = []

    for line in lines:

        if not line:
            continue

        line_y = line_center_y(
            line
        )

        # ----------------------------------------------------
        # La línea debe estar después de la etiqueta RFC.
        # ----------------------------------------------------

        if line_y <= anchor_y:
            continue

        # ----------------------------------------------------
        # Solo consideramos líneas razonablemente cercanas.
        # ----------------------------------------------------

        if (
            line_y
            >
            anchor_y
            +
            VALUE_MAX_VERTICAL_DISTANCE
        ):
            continue

        # ----------------------------------------------------
        # Tomamos SOLO las words que pertenecen a la
        # columna espacial del RFC.
        # ----------------------------------------------------

        value_words = [
            word
            for word in line
            if (
                xmin - BOX_PADDING_X
                <= word_center(word)[0]
                <= xmax + BOX_PADDING_X
            )
        ]

        if not value_words:
            continue

        value_words.sort(
            key=lambda word: (
                float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
            )
        )

        raw_value = "".join(
            clean_word_text(
                word.get(
                    "text",
                    "",
                )
            )
            for word in value_words
        )

        candidate = re.sub(
            r"[^A-Z0-9Ñ&]",
            "",
            raw_value.upper(),
        )

        # ----------------------------------------------------
        # Validamos EL RENGLÓN individualmente.
        #
        # Así:
        #
        #     GACJ700226PP2
        #
        # es válido.
        #
        # Pero:
        #
        #     GACJ700226PP2CURP
        #
        # no lo sería.
        # ----------------------------------------------------

        if RFC_PATTERN.match(
            candidate
        ):

            return candidate

        candidate_lines.append(
            (
                line_y,
                candidate,
            )
        )

    # --------------------------------------------------------
    # Fallback por ancla RFC individual.
    #
    # Se activa cuando el agrupador OCR fusiona RFC, CURP y
    # periodo en un mismo renglón lógico. La relación espacial
    # entre la word RFC y su valor continúa siendo estable.
    # --------------------------------------------------------

    rfc_anchors = [
        word
        for word in words
        if normalize_text(
            word.get(
                "text",
                "",
            )
        ).rstrip(".:")
        == "RFC"
    ]

    if rfc_anchors:

        expected_x, expected_y = box_center(
            BOX_RFC
        )

        best_word_anchor = min(
            rfc_anchors,
            key=lambda word: (
                abs(
                    word_center(word)[0]
                    - expected_x
                )
                +
                abs(
                    word_center(word)[1]
                    - expected_y
                )
            ),
        )

        _, word_anchor_y = word_center(
            best_word_anchor
        )

        direct_candidates = []

        for word in words:

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
                word_anchor_y
                < center_y
                <= word_anchor_y
                + VALUE_MAX_VERTICAL_DISTANCE
            ):
                continue

            candidate = re.sub(
                r"[^A-Z0-9Ñ&]",
                "",
                clean_word_text(
                    word.get(
                        "text",
                        "",
                    )
                ).upper(),
            )

            if RFC_PATTERN.fullmatch(
                candidate
            ):

                direct_candidates.append(
                    (
                        center_y,
                        center_x,
                        candidate,
                    )
                )

        if direct_candidates:

            direct_candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                )
            )

            return direct_candidates[0][2]

    return None



# ============================================================
# EXTRACTOR PERIODO
# ============================================================


def extract_dates(
    text: str,
) -> List[str]:
    """
    Extrae fechas completas y tolera la omisión OCR del
    primer separador.
    """

    exact_dates = DATE_PATTERN.findall(
        text
    )

    if len(exact_dates) >= 2:

        return exact_dates

    tolerant_dates = []

    for match in OCR_DATE_PATTERN.finditer(
        text
    ):

        day, month, year = match.groups()

        tolerant_dates.append(
            f"{day}/{month}/{year}"
        )

    return tolerant_dates


def normalize_date(
    value: str,
) -> str:
    """
    Normaliza separador de fecha.
    """

    return value.replace(
        "-",
        "/",
    )


def extract_periodo(
    lines: Sequence[
        Sequence[
            Dict[str, Any]
        ]
    ],
) -> Tuple[
    Optional[str],
    Optional[str],
]:
    """
    Extrae:

        Periodo del 01/06/2026 al 30/06/2026
    """

    candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if "PERIODO" not in normalized:
            continue

        dates = extract_dates(
            line_text(
                line
            )
        )

        if len(dates) >= 2:

            candidates.append(
                (
                    line,
                    dates[:2],
                )
            )

    best_dates = None

    if candidates:

        expected_y = 277.0

        best_line, best_dates = min(
            candidates,
            key=lambda item: abs(
                line_center_y(item[0])
                -
                expected_y
            ),
        )

    # --------------------------------------------------------
    # Fallback para el layout CUENTA FLEXIBLE SIMPLE HSBC.
    #
    # En este formato la etiqueta y el valor están en líneas
    # distintas:
    #
    #     Periodo
    #                  01/08/2024 al 3108/2024
    #
    # La relación etiqueta -> línea inmediata posterior es
    # estable. La segunda fecha puede perder un separador por
    # OCR, situación atendida por extract_dates().
    # --------------------------------------------------------

    if best_dates is None:

        anchors = [
            line
            for line in lines
            if "PERIODO" in normalized_line_text(
                line
            )
        ]

        date_lines = []

        for line in lines:

            dates = extract_dates(
                line_text(
                    line
                )
            )

            if len(dates) >= 2:

                date_lines.append(
                    (
                        line,
                        dates[:2],
                    )
                )

        nearby_candidates = []

        for anchor in anchors:

            anchor_y = line_center_y(
                anchor
            )

            for date_line, dates in date_lines:

                date_y = line_center_y(
                    date_line
                )

                vertical_gap = (
                    date_y
                    -
                    anchor_y
                )

                if (
                    vertical_gap
                    <
                    -LINE_Y_TOLERANCE
                ):
                    continue

                if (
                    vertical_gap
                    >
                    VALUE_MAX_VERTICAL_DISTANCE
                ):
                    continue

                # Al menos una de las words con fecha debe
                # pertenecer a la columna derecha del periodo.
                date_words = [
                    word
                    for word in date_line
                    if extract_dates(
                        clean_word_text(
                            word.get(
                                "text",
                                "",
                            )
                        )
                    )
                ]

                if not any(
                    word_inside_box(
                        word,
                        BOX_PERIODO,
                        padding_x=30.0,
                        padding_y=25.0,
                    )
                    for word in date_words
                ):
                    continue

                nearby_candidates.append(
                    (
                        vertical_gap,
                        abs(
                            date_y
                            -
                            box_center(
                                BOX_PERIODO
                            )[1]
                        ),
                        dates,
                    )
                )

        if nearby_candidates:

            nearby_candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                )
            )

            best_dates = (
                nearby_candidates[0][2]
            )

    if best_dates is None:

        return (
            None,
            None,
        )

    periodo_inicio = normalize_date(
        best_dates[0]
    )

    periodo_fin = normalize_date(
        best_dates[1]
    )

    return (
        periodo_inicio,
        periodo_fin,
    )


# ============================================================
# EXTRACTOR PRODUCTO PRINCIPAL
# ============================================================


def extract_producto_principal(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae producto principal.

    En el layout observado:

        CUENTA PREMIER
    """

    lines = group_words_into_lines(
        words
    )

    candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if (
            "CUENTA"
            in normalized
            and
            "PREMIER"
            in normalized
        ):

            candidates.append(
                line
            )

    if candidates:

        expected_x, expected_y = (
            box_center(
                BOX_PRODUCTO_PRINCIPAL
            )
        )

        best = min(
            candidates,
            key=lambda line: (
                abs(
                    line_center_x(line)
                    -
                    expected_x
                )
                +
                abs(
                    line_center_y(line)
                    -
                    expected_y
                )
            ),
        )

        text = line_text(
            best
        )

        normalized = normalize_text(
            text
        )

        if (
            "CUENTA PREMIER"
            in normalized
        ):

            return "Cuenta Premier"

        return text.strip()

    # --------------------------------------------------------
    # Layout alterno:
    #
    #     CUENTA FLEXIBLE SIMPLE HSBC
    #
    # Se exige la combinación completa de tokens para no
    # confundirla con "Estado de Cuenta" ni con encabezados
    # genéricos. La distancia a la caja superior prioriza el
    # título principal sobre sus repeticiones en el resumen o
    # en el encabezado de movimientos.
    # --------------------------------------------------------

    flexible_candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if all(
            token in normalized
            for token in (
                "CUENTA",
                "FLEXIBLE",
                "SIMPLE",
            )
        ):

            flexible_candidates.append(
                line
            )

    if flexible_candidates:

        expected_x, expected_y = (
            box_center(
                BOX_PRODUCTO_PRINCIPAL
            )
        )

        best = min(
            flexible_candidates,
            key=lambda line: (
                abs(
                    line_center_x(line)
                    -
                    expected_x
                )
                +
                abs(
                    line_center_y(line)
                    -
                    expected_y
                )
            ),
        )

        normalized = normalized_line_text(
            best
        )

        if "HSBC" in normalized:

            return "Cuenta Flexible Simple HSBC"

        return "Cuenta Flexible Simple"

    # --------------------------------------------------------
    # Layout AHORRO FLEXIBLE HSBC.
    #
    # La misma leyenda puede repetirse en el resumen y en el
    # encabezado de movimientos. Se conserva la selección por
    # distancia a la caja superior para elegir el título.
    # --------------------------------------------------------

    ahorro_flexible_candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if (
            "AHORRO" in normalized
            and
            "FLEXIBLE" in normalized
        ):

            ahorro_flexible_candidates.append(
                line
            )

    if ahorro_flexible_candidates:

        expected_x, expected_y = box_center(
            BOX_PRODUCTO_PRINCIPAL
        )

        best = min(
            ahorro_flexible_candidates,
            key=lambda line: (
                abs(
                    line_center_x(line)
                    - expected_x
                )
                +
                abs(
                    line_center_y(line)
                    - expected_y
                )
            ),
        )

        return "Ahorro Flexible HSBC"

    # --------------------------------------------------------
    # Fallback espacial.
    # --------------------------------------------------------

    selected = words_in_box(
        words,
        BOX_PRODUCTO_PRINCIPAL,
    )

    text = line_text(
        selected
    )

    if not text:

        return None

    normalized = normalize_text(
        text
    )

    if (
        "CUENTA"
        in normalized
        and
        "PREMIER"
        in normalized
    ):

        return "Cuenta Premier"

    return None


# ============================================================
# EXTRACTOR NOMBRE CLIENTE
# ============================================================


def is_probable_person_name(
    line: Sequence[
        Dict[str, Any]
    ],
) -> bool:
    """
    Determina si un renglón parece corresponder a un
    nombre de cliente.
    """

    text = line_text(
        line
    )

    normalized = normalize_text(
        text
    )

    if not text:

        return False

    if any(
        token in normalized
        for token in (
            "HSBC",
            "CUENTA",
            "PREMIER",
            "ESTADO",
            "RESUMEN",
            "NUMERO",
            "RFC",
            "CLABE",
            "PERIODO",
            "SUCURSAL",
            "INFORMATIVO",
        )
    ):

        return False

    if re.search(
        r"\d",
        text,
    ):

        return False

    letters = re.findall(
        r"[A-ZÁÉÍÓÚÜÑ]+",
        text.upper(),
    )

    if len(letters) < 2:

        return False

    total_letters = sum(
        len(value)
        for value in letters
    )

    if total_letters < 5:

        return False

    return True


def extract_nombre_cliente(
    words: Sequence[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Extrae:

        JUAN ANTONIO GARCIA CARRADA
    """

    lines = group_words_into_lines(
        words
    )

    candidates = []

    for line in lines:

        # El nombre vive en la columna izquierda. Se descartan
        # marcas OCR de los códigos de barras que aparecen a
        # ambos lados, sin modificar la agrupación general.
        name_line = [
            word
            for word in line
            if (
                BOX_NOMBRE_CLIENTE[0]
                <= float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
                <= BOX_NOMBRE_CLIENTE[1]
                + BOX_PADDING_X
            )
        ]

        if not name_line:
            continue

        xmin, xmax, ymin, ymax = (
            line_bounds(
                name_line
            )
        )

        synthetic_word = {
            "x0": xmin,
            "x1": xmax,
            "top": ymin,
            "bottom": ymax,
            "page": (
                line[0].get(
                    "page",
                    1,
                )
                if line
                else 1
            ),
        }

        if word_inside_box(
            synthetic_word,
            BOX_NOMBRE_CLIENTE,
            padding_x=25.0,
            padding_y=20.0,
        ):

            if is_probable_person_name(
                name_line
            ):

                candidates.append(
                    name_line
                )

    if candidates:

        expected_x, expected_y = (
            box_center(
                BOX_NOMBRE_CLIENTE
            )
        )

        best = min(
            candidates,
            key=lambda line: (
                abs(
                    line_center_x(line)
                    -
                    expected_x
                )
                +
                abs(
                    line_center_y(line)
                    -
                    expected_y
                )
            ),
        )

        return line_text(
            best
        )

    # --------------------------------------------------------
    # Fallback.
    # --------------------------------------------------------

    selected = words_in_box(
        words,
        BOX_NOMBRE_CLIENTE,
        padding_x=30.0,
        padding_y=25.0,
    )

    if not selected:

        return None

    selected_lines = (
        group_words_into_lines(
            selected
        )
    )

    for line in selected_lines:

        name_line = [
            word
            for word in line
            if (
                BOX_NOMBRE_CLIENTE[0]
                <= float(
                    word.get(
                        "x0",
                        0.0,
                    )
                )
                <= BOX_NOMBRE_CLIENTE[1]
                + BOX_PADDING_X
            )
        ]

        if is_probable_person_name(
            name_line
        ):

            return line_text(
                name_line
            )

    return None


# ============================================================
# VALIDACIONES
# ============================================================


def validate_numero_cuenta(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida número de cuenta.
    """

    if value is None:

        return None

    value = re.sub(
        r"\D",
        "",
        value,
    )

    if not ACCOUNT_PATTERN.match(
        value
    ):

        return None

    return value


def validate_numero_cliente(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida número de cliente.
    """

    if value is None:

        return None

    value = re.sub(
        r"\D",
        "",
        value,
    )

    if not CLIENT_PATTERN.match(
        value
    ):

        return None

    return value


def validate_clabe(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida CLABE.
    """

    if value is None:

        return None

    value = re.sub(
        r"\D",
        "",
        value,
    )

    if not CLABE_PATTERN.match(
        value
    ):

        return None

    return value


def validate_rfc(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida RFC.
    """

    if value is None:

        return None

    value = re.sub(
        r"[^A-Z0-9Ñ&]",
        "",
        value.upper(),
    )

    if not RFC_PATTERN.match(
        value
    ):

        return None

    return value



def validate_date(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida fecha.
    """

    if value is None:

        return None

    value = normalize_date(
        value
    )

    if not re.fullmatch(
        r"\d{2}/\d{2}/\d{4}",
        value,
    ):

        return None

    return value


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_datos_cuenta_words(
    words: List[
        Dict[str, Any]
    ],
) -> DatosCuenta:
    """
    Extractor robusto de datos generales de cuenta HSBC.

    Arquitectura:

        TEXTO
           ↓
        ANCLA
           ↓
        COORDENADAS DEL CAMPO
           ↓
        WORDS DEL CAMPO
           ↓
        VALIDACIÓN
           ↓
        DatosCuenta

    La principal diferencia respecto al extractor BBVA
    es que las coordenadas de HSBC funcionan como límites
    espaciales del valor, no solamente como una caja para
    leer un renglón completo.

    Campos:

        - producto_principal
        - periodo_inicio
        - periodo_fin
        - fecha_corte
        - numero_cuenta
        - numero_cliente
        - rfc
        - clabe
        - nombre_cliente
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
    # 1. IDENTIFICAR PÁGINA DE DATOS
    # ========================================================

    data_page = find_data_page(
        words
    )

    if data_page is not None:

        data_words = [
            word
            for word in words
            if int(
                word.get(
                    "page",
                    1,
                )
            )
            == data_page
        ]

    else:

        data_words = list(
            words
        )

    # ========================================================
    # 2. AGRUPAR WORDS EN RENGLONES
    # ========================================================

    lines = group_words_into_lines(
        data_words
    )

    # ========================================================
    # 3. PRODUCTO PRINCIPAL
    # ========================================================

    producto_principal = (
        extract_producto_principal(
            data_words
        )
    )

    # ========================================================
    # 4. NOMBRE CLIENTE
    # ========================================================

    nombre_cliente = (
        extract_nombre_cliente(
            data_words
        )
    )

    # ========================================================
    # 5. NUMERO DE CUENTA
    # ========================================================

    numero_cuenta = (
        extract_account_from_anchor(
            lines,
            data_words,
        )
    )

    if numero_cuenta is None:

        numero_cuenta = (
            extract_account_from_movement_header(
                lines
            )
        )

    numero_cuenta = (
        validate_numero_cuenta(
            numero_cuenta
        )
    )

    # ========================================================
    # 6. CLABE
    # ========================================================

    clabe = (
        extract_clabe_from_anchor(
            lines,
            data_words,
        )
    )

    clabe = validate_clabe(
        clabe
    )

    # ========================================================
    # 7. NUMERO DE CLIENTE
    # ========================================================

    numero_cliente = (
        extract_numero_cliente_from_anchor(
            lines,
            data_words,
        )
    )

    numero_cliente = (
        validate_numero_cliente(
            numero_cliente
        )
    )

    # ========================================================
    # 8. RFC
    # ========================================================

    rfc = (
        extract_rfc_from_anchor(
            lines,
            data_words,
        )
    )

    rfc = validate_rfc(
        rfc
    )


    # ========================================================
    # 9. PERIODO
    # ========================================================

    periodo_inicio, periodo_fin = (
        extract_periodo(
            lines
        )
    )

    periodo_inicio = (
        validate_date(
            periodo_inicio
        )
    )

    periodo_fin = (
        validate_date(
            periodo_fin
        )
    )

    # ========================================================
    # 10. FECHA DE CORTE
    # ========================================================
    #
    # En el formato HSBC observado:
    #
    #     Periodo del 01/06/2026 al 30/06/2026
    #
    # El cierre corresponde a la fecha final del periodo.
    #
    # ========================================================

    fecha_corte = periodo_fin

    # ========================================================
    # 11. MODELO
    # ========================================================
    #
    # Se conserva EXACTAMENTE la estructura de DatosCuenta
    # que estamos utilizando actualmente.
    #
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
