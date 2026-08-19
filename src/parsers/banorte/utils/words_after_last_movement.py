from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ============================================================
# UTILIDAD — RECORTE DESPUÉS DEL ÚLTIMO MOVIMIENTO
# ============================================================
#
# REGLA DEL LAYOUT BANORTE
# ------------------------------------------------------------
#
# CASO 1 — PROCESO NORMAL
# ------------------------------------------------------------
#
# Un movimiento comienza con una fecha ubicada en la columna
# FECHA.
#
# Ejemplo:
#
#     28-ABR-23IVA
#     x0 = 53.67975
#
# Después puede continuar el concepto en líneas siguientes:
#
#     TEXTO DEL CONCEPTO...
#     TEXTO DEL CONCEPTO...
#
# Esas líneas NO tienen fecha.
#
# Cuando termina la tabla principal aparece una nueva sección.
#
# Esa nueva sección comienza con una línea que tiene:
#
#     - solamente texto
#     - ninguna fecha
#     - ningún importe
#     - ningún contenido en las columnas laterales
#     - un bloque horizontal centrado
#
# Ejemplo:
#
#     INVERSION ENLACE NEGOCIOS
#
# o:
#
#     OTROS▼
#
# El texto puede cambiar.
#
# Por eso NO buscamos una palabra concreta.
#
# La utilidad busca:
#
#     FECHA DE MOVIMIENTO
#           ↓
#     continuación del movimiento
#           ↓
#     BLOQUE CENTRADO
#           ↓
#     ¿ES CONTINUACIÓN?
#        ↓          ↓
#       SÍ          NO
#       ↓            ↓
#   consumir       CORTE
#   pareja
#
#
# IMPORTANTE:
#
# En el layout Banorte, cuando los movimientos continúan en
# otra página aparece:
#
#     DETALLE DE MOVIMIENTOS (PESOS) (CONTINUACIÓN)▼
#     Enlace Negocios Pfae
#     FECHA ...
#     28-JUL-21 ...
#
# Por lo tanto, esos DOS renglones forman una unidad:
#
#     CONTINUACIÓN
#     PRODUCTO
#
# Esa unidad NO es un corte.
#
# Después los movimientos siguen normalmente.
#
# Cuando aparece:
#
#     Inversión Enlace Negocios PFAE
#
# sin un renglón de CONTINUACIÓN inmediatamente asociado,
# entonces sí es el inicio de la siguiente tabla y se hace
# el corte.
#
#
# CASO 2 — RESPALDO / FALLBACK
# ------------------------------------------------------------
#
# Si el CASO 1 no encuentra la nueva sección, se intenta un
# segundo patrón.
#
# En ciertos layouts, después del último movimiento NO aparece
# un bloque centrado, sino que comienza directamente un bloque
# de texto plano.
#
# ============================================================


# ============================================================
# CONFIGURACIÓN DEL LAYOUT
# ============================================================

DATE_COLUMN_X0_MIN = 45.0
DATE_COLUMN_X0_MAX = 88.0


# ============================================================
# TOLERANCIA VERTICAL
# ============================================================

LINE_Y_TOLERANCE = 3.5


# ============================================================
# DETECCIÓN DEL BLOQUE CENTRADO
# ============================================================

CENTER_TOLERANCE_RATIO = 0.15

MAX_CENTERED_TEXT_WIDTH_RATIO = 0.35


# ============================================================
# CASO 2 — BLOQUE DE TEXTO PLANO
# ============================================================

PLAIN_TEXT_LEFT_MARGIN_RATIO = 0.025

PLAIN_TEXT_LEFT_MARGIN_MIN = 7.0

PLAIN_TEXT_MAX_LINE_WIDTH_RATIO = 0.90

PLAIN_TEXT_MIN_CONSECUTIVE_LINES = 2

PLAIN_TEXT_MAX_LINE_GAP = 28.0


# ============================================================
# REGEX — FECHA
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
# REGEX — CONTINUACIÓN
# ============================================================

CONTINUATION_PATTERN = re.compile(
    r"\bCONTINUACI(?:Ó|O)N\b",
    re.IGNORECASE,
)


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalize_text(
    value: Any,
) -> str:
    """
    Normaliza texto.
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


# ============================================================
# CONVERSIÓN SEGURA
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte a float de forma segura.
    """

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


# ============================================================
# COORDENADAS
# ============================================================

def word_x0(
    word: Dict[str, Any],
) -> float:
    return safe_float(
        word.get(
            "x0",
            0.0,
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


def word_top(
    word: Dict[str, Any],
) -> float:
    return safe_float(
        word.get(
            "top",
            0.0,
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


def word_doctop(
    word: Dict[str, Any],
) -> float:
    """
    Coordenada vertical global dentro del PDF.
    """

    return safe_float(
        word.get(
            "doctop",
            0.0,
        )
    )


def word_page(
    word: Dict[str, Any],
) -> int:
    return int(
        word.get(
            "page",
            1,
        )
        or 1
    )


# ============================================================
# FECHAS
# ============================================================

def extract_date_prefix(
    text: str,
) -> Optional[str]:
    """
    Extrae una fecha al inicio del texto.

    Ejemplos:

        28-ABR-23
        28-ABR-23IVA
        30-JUN-25OXXOLAS
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


# ============================================================
# ¿LA PALABRA PERTENECE A LA COLUMNA FECHA?
# ============================================================

def is_date_column_word(
    word: Dict[str, Any],
) -> bool:
    """
    Determina si una palabra está en la zona horizontal de
    FECHA.

    Se utiliza x0 porque la fecha comienza en la columna
    izquierda del movimiento.
    """

    x0 = word_x0(
        word
    )

    return (
        DATE_COLUMN_X0_MIN
        <= x0
        <= DATE_COLUMN_X0_MAX
    )


# ============================================================
# ¿UNA LÍNEA ES UNA FECHA DE MOVIMIENTO?
# ============================================================

def is_movement_date_line(
    line: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta una línea que comienza un movimiento.

    Regla:

        debe existir una palabra que:

            1. esté en la columna FECHA
            2. comience con una fecha
    """

    if not line:
        return False

    for word in sorted(
        line,
        key=word_x0,
    ):

        if not is_date_column_word(
            word
        ):
            continue

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if extract_date_prefix(
            text
        ) is not None:

            return True

    return False


# ============================================================
# DINERO
# ============================================================

def is_money(
    text: str,
) -> bool:
    """
    Determina si un texto es un importe.
    """

    return bool(
        MONEY_PATTERN.fullmatch(
            normalize_text(
                text
            )
        )
    )


# ============================================================
# AGRUPACIÓN DE PALABRAS EN LÍNEAS
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
    Agrupa palabras por página y posición vertical.

    Se ordena usando doctop para preservar el orden físico
    global del documento.
    """

    if not words:
        return []

    ordered_words = sorted(
        words,
        key=lambda word: (
            word_page(word),
            word_doctop(word),
            word_x0(word),
        ),
    )

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

    for word in ordered_words:

        page = word_page(
            word
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
            )
            <= LINE_Y_TOLERANCE
        )

        if same_line:

            current.append(
                word
            )

            current_y = (
                sum(
                    word_center_y(item)
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
# GEOMETRÍA DE LÍNEA
# ============================================================

def line_x0(
    line: List[
        Dict[str, Any]
    ],
) -> float:
    """
    x0 mínimo de la línea.
    """

    return min(
        word_x0(word)
        for word in line
    )


def line_x1(
    line: List[
        Dict[str, Any]
    ],
) -> float:
    """
    x1 máximo de la línea.
    """

    return max(
        word_x1(word)
        for word in line
    )


def line_width(
    line: List[
        Dict[str, Any]
    ],
) -> float:
    """
    Anchura del bloque textual de una línea.
    """

    return (
        line_x1(line)
        - line_x0(line)
    )


def line_center_x(
    line: List[
        Dict[str, Any]
    ],
) -> float:
    """
    Centro horizontal del bloque.
    """

    return (
        line_x0(line)
        + line_x1(line)
    ) / 2.0


# ============================================================
# GEOMETRÍA DE LA PÁGINA
# ============================================================

def page_bounds(
    words: List[
        Dict[str, Any]
    ],
    page: int,
) -> Optional[
    tuple[
        float,
        float,
    ]
]:
    """
    Obtiene el rango horizontal de la página utilizando las
    palabras del propio PDF.
    """

    page_words = [
        word
        for word in words
        if word_page(word) == page
    ]

    if not page_words:
        return None

    xmin = min(
        word_x0(word)
        for word in page_words
    )

    xmax = max(
        word_x1(word)
        for word in page_words
    )

    return (
        xmin,
        xmax,
    )


def page_center_x(
    words: List[
        Dict[str, Any]
    ],
    page: int,
) -> Optional[float]:
    """
    Centro horizontal aproximado de la página.
    """

    bounds = page_bounds(
        words,
        page,
    )

    if bounds is None:
        return None

    xmin, xmax = bounds

    return (
        xmin + xmax
    ) / 2.0


# ============================================================
# TEXTO COMPLETO DE UNA LÍNEA
# ============================================================

def line_text(
    line: List[
        Dict[str, Any]
    ],
) -> str:
    """
    Reconstruye el texto visible de una línea respetando el
    orden horizontal.

    Esto es importante porque CONTINUACIÓN viene como parte
    de un renglón compuesto por varias palabras, por ejemplo:

        DETALLE
        DE
        MOVIMIENTOS
        (PESOS)
        (CONTINUACIÓN)▼
    """

    if not line:
        return ""

    ordered = sorted(
        line,
        key=word_x0,
    )

    return normalize_text(
        " ".join(
            normalize_text(
                word.get(
                    "text",
                    "",
                )
            )
            for word in ordered
            if normalize_text(
                word.get(
                    "text",
                    "",
                )
            )
        )
    )


# ============================================================
# ¿ESTE MISMO RENGLÓN ES DE CONTINUACIÓN?
# ============================================================

def is_continuation_line(
    line: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Determina si ESTE MISMO RENGLÓN corresponde al encabezado
    de continuación.

    NO inspecciona el renglón anterior.
    NO inspecciona el renglón siguiente.

    Solamente inspecciona el contenido de este mismo renglón.
    """

    if not line:
        return False

    text = line_text(
        line
    )

    if not text:
        return False

    return bool(
        CONTINUATION_PATTERN.search(
            text
        )
    )


# ============================================================
# ¿LÍNEA PURAMENTE TEXTUAL?
# ============================================================

def is_text_only_line(
    line: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Determina si una línea contiene solamente texto.

    NO acepta:

        - fechas
        - importes
        - palabras vacías
    """

    if not line:
        return False

    has_text = False

    for word in line:

        text = normalize_text(
            word.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        has_text = True

        # ----------------------------------------------------
        # No debe contener ningún importe.
        # ----------------------------------------------------

        if is_money(
            text
        ):
            return False

        # ----------------------------------------------------
        # No debe contener una fecha.
        # ----------------------------------------------------

        if extract_date_prefix(
            text
        ) is not None:
            return False

    return has_text


# ============================================================
# ¿LÍNEA CENTRADA DE SECCIÓN?
# ============================================================

def is_centered_section_line(
    line: List[
        Dict[str, Any]
    ],
    all_words: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta el patrón de inicio de una nueva sección.

    La línea debe ser:

        - texto puro
        - sin fecha
        - sin importes
        - relativamente compacta
        - centrada horizontalmente

    No se conoce el contenido textual.

    Por ejemplo:

        INVERSION ENLACE NEGOCIOS
        OTROS▼

    porque lo importante es la geometría.
    """

    if not line:
        return False

    # --------------------------------------------------------
    # 1. Solamente texto.
    # --------------------------------------------------------

    if not is_text_only_line(
        line
    ):
        return False

    # --------------------------------------------------------
    # 2. Página.
    # --------------------------------------------------------

    page = word_page(
        line[0]
    )

    # --------------------------------------------------------
    # 3. Geometría de página.
    # --------------------------------------------------------

    bounds = page_bounds(
        all_words,
        page,
    )

    if bounds is None:
        return False

    page_xmin, page_xmax = bounds

    page_width = (
        page_xmax
        - page_xmin
    )

    if page_width <= 0:
        return False

    page_center = (
        page_xmin
        + page_xmax
    ) / 2.0

    # --------------------------------------------------------
    # 4. Geometría de la línea.
    # --------------------------------------------------------

    xmin = line_x0(
        line
    )

    xmax = line_x1(
        line
    )

    width = (
        xmax
        - xmin
    )

    center = (
        xmin
        + xmax
    ) / 2.0

    # --------------------------------------------------------
    # 5. Debe ser un bloque relativamente compacto.
    # --------------------------------------------------------

    if (
        width
        > page_width
        * MAX_CENTERED_TEXT_WIDTH_RATIO
    ):
        return False

    # --------------------------------------------------------
    # 6. Debe estar centrado.
    # --------------------------------------------------------

    center_distance = abs(
        center
        - page_center
    )

    if (
        center_distance
        > page_width
        * CENTER_TOLERANCE_RATIO
    ):
        return False

    # --------------------------------------------------------
    # 7. No debe parecer una continuación normal del concepto.
    # --------------------------------------------------------

    left_zone_limit = (
        page_xmin
        + page_width
        * 0.30
    )

    if xmin < left_zone_limit:
        return False

    return True


# ============================================================
# CASO 1 — ENCONTRAR CORTE CENTRADO Y ÚLTIMO MOVIMIENTO REAL
# ============================================================

def find_centered_cutoff_and_last_movement(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
    words: List[
        Dict[str, Any]
    ],
) -> Optional[
    tuple[
        float,
        float,
    ]
]:
    """
    Busca conjuntamente:

        1. la última fecha de movimiento real antes del corte
        2. el bloque centrado que representa el corte REAL

    REGLA FUNDAMENTAL DEL LAYOUT:

        CONTINUACIÓN
        PRODUCTO
        FECHA
        MOVIMIENTOS
        ...
        MOVIMIENTOS
        ...
        PRODUCTO SIN CONTINUACIÓN
        FECHA
        MOVIMIENTOS

    Entonces:

        CONTINUACIÓN
            ↓
        ignorar
            ↓
        siguiente renglón = PRODUCTO
            ↓
        ignorar también
            ↓
        continuar recorriendo
            ↓
        seguir registrando fechas
            ↓
        encontrar finalmente un bloque centrado SIN
        CONTINUACIÓN
            ↓
        CORTE

    IMPORTANTE:

    NO se busca la última fecha del documento antes de comenzar.

    Se recorre el documento en orden físico.

    Esto evita contaminar la detección con fechas de una segunda
    tabla posterior al corte.
    """

    last_date_line: Optional[
        List[
            Dict[str, Any]
        ]
    ] = None

    # --------------------------------------------------------
    # Estado de continuación.
    #
    # True significa:
    #
    #     el renglón anterior fue CONTINUACIÓN
    #
    # Por lo tanto el siguiente renglón es el nombre del producto
    # y debe ignorarse como candidato a corte.
    # --------------------------------------------------------

    skip_next_centered_product = False

    continuation_page: Optional[int] = None

    for line in lines:

        if not line:
            continue

        current_page = word_page(
            line[0]
        )

        # ====================================================
        # 1. SI ESTAMOS EN LA PAREJA DE CONTINUACIÓN
        # ====================================================
        #
        # El siguiente renglón después de CONTINUACIÓN es el
        # nombre del producto.
        #
        # Ese renglón debe consumirse completo.
        #
        # ====================================================

        if skip_next_centered_product:

            # ------------------------------------------------
            # Defensivamente, la pareja debe estar en la misma
            # página.
            # ------------------------------------------------

            if (
                continuation_page is None
                or current_page
                == continuation_page
            ):

                skip_next_centered_product = False
                continuation_page = None

                # --------------------------------------------
                # ESTA LÍNEA ES LA PAREJA DEL RÉNGLÓN DE
                # CONTINUACIÓN.
                #
                # No importa si es centrada.
                # No importa su texto.
                #
                # Simplemente se consume y seguimos.
                # --------------------------------------------

                continue

            # ------------------------------------------------
            # Si por alguna anomalía cambia la página, se
            # cancela el estado defensivamente y la línea
            # actual vuelve a procesarse normalmente.
            # ------------------------------------------------

            skip_next_centered_product = False
            continuation_page = None

        # ====================================================
        # 2. FECHA DE MOVIMIENTO
        # ====================================================
        #
        # La fecha se actualiza ANTES del posible corte.
        #
        # Esto permite que la última fecha real siempre sea la
        # última fecha encontrada ANTES del bloque que finalmente
        # corta.
        #
        # ====================================================

        if is_movement_date_line(
            line
        ):

            last_date_line = line

            continue

        # ====================================================
        # 3. DETECTAR SI ESTE MISMO RENGLÓN ES CONTINUACIÓN
        # ====================================================
        #
        # Esta es la condición especial del layout Banorte.
        #
        # Si este renglón contiene CONTINUACIÓN:
        #
        #     NO cortar
        #
        # y además sabemos que el siguiente renglón es el nombre
        # del producto que pertenece a esa continuación.
        #
        # ====================================================

        if is_continuation_line(
            line
        ):

            skip_next_centered_product = True
            continuation_page = current_page

            continue

        # ====================================================
        # 4. DETECTAR BLOQUE CENTRADO
        # ====================================================

        if not is_centered_section_line(
            line,
            words,
        ):
            continue

        # ====================================================
        # 5. ESTE BLOQUE CENTRADO NO ES CONTINUACIÓN
        # ====================================================
        #
        # Llegar aquí significa:
        #
        #     - es texto puro
        #     - no es fecha
        #     - no es importe
        #     - es un bloque centrado
        #     - NO es un renglón CONTINUACIÓN
        #     - tampoco es el producto inmediatamente posterior
        #       a CONTINUACIÓN
        #
        # Por lo tanto:
        #
        #     ESTE ES EL CORTE REAL.
        #
        # ====================================================

        if last_date_line is None:
            continue

        cutoff_doctop = min(
            word_doctop(word)
            for word in line
        )

        last_date_doctop = max(
            word_doctop(word)
            for word in last_date_line
        )

        return (
            cutoff_doctop,
            last_date_doctop,
        )

    return None


# ============================================================
# CASO 2 — ¿LÍNEA DE TEXTO PLANO AL MARGEN IZQUIERDO?
# ============================================================

def is_plain_text_section_line(
    line: List[
        Dict[str, Any]
    ],
    all_words: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Detecta una línea candidata al inicio de un bloque de texto
    plano posterior al último movimiento.

    NO depende de palabras concretas como:

        Advertencia
        El presente
        Comprobante
        etc.

    La detección se basa en geometría + estructura.
    """

    if not line:
        return False

    # --------------------------------------------------------
    # 1. Debe ser texto puro.
    # --------------------------------------------------------

    if not is_text_only_line(
        line
    ):
        return False

    # --------------------------------------------------------
    # 2. Obtener página.
    # --------------------------------------------------------

    page = word_page(
        line[0]
    )

    # --------------------------------------------------------
    # 3. Obtener geometría de página.
    # --------------------------------------------------------

    bounds = page_bounds(
        all_words,
        page,
    )

    if bounds is None:
        return False

    page_xmin, page_xmax = bounds

    page_width = (
        page_xmax
        - page_xmin
    )

    if page_width <= 0:
        return False

    # --------------------------------------------------------
    # 4. Geometría de línea.
    # --------------------------------------------------------

    xmin = line_x0(
        line
    )

    width = line_width(
        line
    )

    # --------------------------------------------------------
    # 5. Debe comenzar cerca del margen izquierdo.
    # --------------------------------------------------------

    left_margin_tolerance = max(
        PLAIN_TEXT_LEFT_MARGIN_MIN,
        page_width
        * PLAIN_TEXT_LEFT_MARGIN_RATIO,
    )

    if (
        xmin
        > page_xmin
        + left_margin_tolerance
    ):
        return False

    # --------------------------------------------------------
    # 6. No debe ocupar prácticamente toda la página.
    # --------------------------------------------------------

    if (
        width
        > page_width
        * PLAIN_TEXT_MAX_LINE_WIDTH_RATIO
    ):
        return False

    return True


# ============================================================
# CASO 2 — ¿CONTINÚA EL BLOQUE DE TEXTO PLANO?
# ============================================================

def has_plain_text_block_following(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
    start_index: int,
    all_words: List[
        Dict[str, Any]
    ],
) -> bool:
    """
    Verifica que una línea candidata realmente sea el inicio
    de un bloque textual y no una coincidencia aislada.
    """

    if (
        start_index < 0
        or start_index >= len(lines)
    ):
        return False

    first_line = lines[
        start_index
    ]

    if not is_plain_text_section_line(
        first_line,
        all_words,
    ):
        return False

    page = word_page(
        first_line[0]
    )

    previous_doctop = min(
        word_doctop(word)
        for word in first_line
    )

    consecutive = 1

    # --------------------------------------------------------
    # Buscar las siguientes líneas.
    # --------------------------------------------------------

    for index in range(
        start_index + 1,
        len(lines),
    ):

        line = lines[
            index
        ]

        if not line:
            continue

        line_page = word_page(
            line[0]
        )

        # ----------------------------------------------------
        # El bloque tiene que permanecer en la misma página.
        # ----------------------------------------------------

        if line_page != page:
            break

        line_doctop = min(
            word_doctop(word)
            for word in line
        )

        gap = (
            line_doctop
            - previous_doctop
        )

        # ----------------------------------------------------
        # Si ya está demasiado separado verticalmente, no es
        # continuación del bloque.
        # ----------------------------------------------------

        if gap > PLAIN_TEXT_MAX_LINE_GAP:
            break

        if not is_plain_text_section_line(
            line,
            all_words,
        ):
            break

        consecutive += 1

        previous_doctop = line_doctop

        if (
            consecutive
            >= PLAIN_TEXT_MIN_CONSECUTIVE_LINES
        ):
            return True

    return (
        consecutive
        >= PLAIN_TEXT_MIN_CONSECUTIVE_LINES
    )


# ============================================================
# CASO 2 — ENCONTRAR INICIO DEL BLOQUE DE TEXTO PLANO
# ============================================================

def find_plain_text_section_cutoff(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
    all_words: List[
        Dict[str, Any]
    ],
    last_date_doctop: float,
) -> Optional[float]:
    """
    Busca el punto de corte del CASO 2.

    La búsqueda comienza estrictamente después de la última
    línea de movimiento REAL.
    """

    for index, line in enumerate(
        lines
    ):

        if not line:
            continue

        line_doctop = min(
            word_doctop(word)
            for word in line
        )

        # ----------------------------------------------------
        # Solamente después del último movimiento real.
        # ----------------------------------------------------

        if line_doctop <= last_date_doctop:
            continue

        # ----------------------------------------------------
        # Verificar que la línea sea el comienzo real de un
        # bloque textual.
        # ----------------------------------------------------

        if not is_plain_text_section_line(
            line,
            all_words,
        ):
            continue

        if not has_plain_text_block_following(
            lines,
            index,
            all_words,
        ):
            continue

        return line_doctop

    return None


# ============================================================
# ÚLTIMA FECHA — FALLBACK
# ============================================================

def find_last_movement_date_line(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
) -> Optional[
    List[
        Dict[str, Any]
    ]
]:
    """
    Encuentra la última línea que contiene una fecha en la
    columna FECHA.

    NOTA:

    Esta función se conserva para mantener la API y para el
    CASO 2.

    NO se utiliza para decidir el CASO 1 cuando existe una
    sección centrada, porque en ese layout podría seleccionar
    incorrectamente una fecha de una segunda tabla.
    """

    last_date_line: Optional[
        List[
            Dict[str, Any]
        ]
    ] = None

    for line in lines:

        if is_movement_date_line(
            line
        ):

            last_date_line = line

    return last_date_line


# ============================================================
# CASO 1 — ENCONTRAR CORTE DE SECCIÓN CENTRADA
# ============================================================

def find_centered_section_cutoff(
    lines: List[
        List[
            Dict[str, Any]
        ]
    ],
    words: List[
        Dict[str, Any]
    ],
    last_date_doctop: float,
) -> Optional[float]:
    """
    Implementación tradicional del CASO 1.

    Se conserva para mantener la API existente.

    IMPORTANTE:

    Respeta la misma estructura:

        CONTINUACIÓN
        PRODUCTO
        ...

    cuando la búsqueda ya se realiza desde una fecha conocida.

    Si encuentra el renglón CONTINUACIÓN, consume también el
    renglón siguiente y continúa.
    """

    skip_next_centered_product = False
    continuation_page: Optional[int] = None

    for index, line in enumerate(
        lines
    ):

        if not line:
            continue

        line_doctop = min(
            word_doctop(word)
            for word in line
        )

        if line_doctop <= last_date_doctop:
            continue

        current_page = word_page(
            line[0]
        )

        # ----------------------------------------------------
        # Consumir el producto asociado a CONTINUACIÓN.
        # ----------------------------------------------------

        if skip_next_centered_product:

            if (
                continuation_page is None
                or current_page
                == continuation_page
            ):

                skip_next_centered_product = False
                continuation_page = None

                continue

            skip_next_centered_product = False
            continuation_page = None

        # ----------------------------------------------------
        # Si ESTE MISMO renglón es CONTINUACIÓN:
        #
        # marcar que el siguiente renglón es el producto
        # asociado y NO cortar.
        # ----------------------------------------------------

        if is_continuation_line(
            line
        ):

            skip_next_centered_product = True
            continuation_page = current_page

            continue

        # ----------------------------------------------------
        # Detectar sección centrada.
        # ----------------------------------------------------

        if not is_centered_section_line(
            line,
            words,
        ):
            continue

        # ----------------------------------------------------
        # Este bloque centrado ya no pertenece a una pareja de
        # CONTINUACIÓN, por lo tanto es el corte.
        # ----------------------------------------------------

        return line_doctop

    return None


# ============================================================
# CORTE PRINCIPAL
# ============================================================

def remove_after_last_movement(
    words: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Corta absolutamente todo después de la sección que aparece
    inmediatamente después del último movimiento.

    PRIORIDAD:

        CASO 1
        --------
        recorrido físico completo del documento
             ↓
        fecha de movimiento
             ↓
        CONTINUACIÓN
             ↓
        PRODUCTO asociado
             ↓
        continuar movimientos
             ↓
        bloque centrado sin CONTINUACIÓN
             ↓
        CORTE ABSOLUTO

        CASO 2
        --------
        última fecha
             ↓
        bloque textual al margen izquierdo
             ↓
        CORTE

    IMPORTANTE:

    El CASO 1 NO obtiene primero la última fecha de todo el
    documento.

    El CASO 1 recorre las líneas en orden físico y mantiene
    cuál fue la última fecha antes del verdadero corte.

    Esto es indispensable porque puede haber otra tabla de
    movimientos después del punto que queremos eliminar.
    """

    if not words:
        return []

    # --------------------------------------------------------
    # 1. Agrupar palabras en líneas.
    # --------------------------------------------------------

    lines = group_words_into_lines(
        words
    )

    if not lines:
        return []

    # ========================================================
    # CASO 1 — PROCESO PRINCIPAL
    # ========================================================
    #
    # IMPORTANTE:
    #
    # Aquí NO buscamos primero la última fecha global.
    #
    # El propio detector mantiene internamente la última fecha
    # real encontrada antes del corte.
    # ========================================================

    centered_result = (
        find_centered_cutoff_and_last_movement(
            lines,
            words,
        )
    )

    if centered_result is not None:

        cutoff_doctop, _ = centered_result

        # ----------------------------------------------------
        # CORTE ABSOLUTO
        #
        # Se conserva todo lo anterior al encabezado del nuevo
        # producto y se elimina absolutamente todo lo posterior.
        # ----------------------------------------------------

        return [
            word
            for word in words
            if word_doctop(word)
            < cutoff_doctop
        ]

    # ========================================================
    # CASO 2 — FALLBACK
    # ========================================================
    #
    # Solamente si el CASO 1 no encontró absolutamente ningún
    # punto de corte.
    # ========================================================

    last_date_line = (
        find_last_movement_date_line(
            lines
        )
    )

    if last_date_line is None:
        return words

    last_date_doctop = max(
        word_doctop(word)
        for word in last_date_line
    )

    cutoff_doctop = (
        find_plain_text_section_cutoff(
            lines,
            words,
            last_date_doctop,
        )
    )

    # --------------------------------------------------------
    # Si ningún mecanismo encontró la sección posterior,
    # no destruimos información.
    # --------------------------------------------------------

    if cutoff_doctop is None:
        return words

    # --------------------------------------------------------
    # CORTE ABSOLUTO
    # --------------------------------------------------------

    return [
        word
        for word in words
        if word_doctop(word)
        < cutoff_doctop
    ]