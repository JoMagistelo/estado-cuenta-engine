from typing import List, Dict, Any


# ============================================================
# CONFIGURACION ENCABEZADO PREMIUM BBVA
# ============================================================

# REFERENCIA en PREMIUM:
# x0 ~= 219
PREMIUM_REFERENCIA_XMIN = 215.0
PREMIUM_REFERENCIA_XMAX = 225.0


# REFERENCIA en NORMAL:
# x0 ~= 321
# Si se encuentra aquí, el documento NO es PREMIUM.
NORMAL_REFERENCIA_XMIN = 318.0
NORMAL_REFERENCIA_XMAX = 325.0


# ------------------------------------------------------------
# Coordenadas X de las palabras del encabezado PREMIUM.
#
# Se utilizan para eliminar únicamente las palabras que
# pertenecen al encabezado, no cualquier palabra que caiga
# dentro de una franja vertical.
# ------------------------------------------------------------

PREMIUM_HEADER_COLUMNS = {
    "FECHA": (30.0, 70.0),
    "SALDO": (510.0, 550.0),

    "OPER": (15.0, 50.0),
    "LIQ": (55.0, 80.0),
    "DESCRIPCION": (80.0, 150.0),
    "REFERENCIA": (215.0, 275.0),
    "CARGOS": (365.0, 415.0),
    "ABONOS": (425.0, 470.0),
    "OPERACION": (470.0, 535.0),
    "LIQUIDACION": (535.0, 605.0),
}


# El encabezado Premium tiene dos líneas.
#
# Línea 1:
#     FECHA / SALDO
#
# Línea 2:
#     OPER / LIQ / DESCRIPCIÓN / REFERENCIA / ...
#
# Las coordenadas reales proporcionadas son:
#
#     línea 1 -> top ~= 521
#     línea 2 -> top ~= 532
#
# Permitimos una tolerancia vertical pequeña.
HEADER_LINE_TOLERANCE = 3.0


# Distancia máxima entre la primera y segunda línea
# del encabezado.
HEADER_SECOND_LINE_OFFSET = 15.0


# ============================================================
# UTILIDADES
# ============================================================

def normalize_header_text(
    text: str
) -> str:
    """
    Normaliza texto de encabezado para comparar
    DESCRIPCIÓN / DESCRIPCION
    OPERACIÓN / OPERACION
    LIQUIDACIÓN / LIQUIDACION
    """

    return (
        text
        .strip()
        .upper()
        .replace("Ó", "O")
        .replace("É", "E")
    )


def x_in_range(
    x0: float,
    xmin: float,
    xmax: float
) -> bool:
    """
    Determina si x0 cae dentro del rango horizontal.
    """

    return xmin <= x0 <= xmax


# ============================================================
# DETECCION DE LAYOUT
# ============================================================

def is_premium_layout(
    words: List[Dict[str, Any]]
) -> bool:
    """
    Detecta exclusivamente el layout PREMIUM.

    PREMIUM:
        REFERENCIA x0 ~= 219

    NORMAL:
        REFERENCIA x0 ~= 321

    Si aparece REFERENCIA en la coordenada NORMAL,
    devuelve False.

    En consecuencia, el layout NORMAL queda completamente
    intacto.
    """

    premium_found = False

    for word in words:

        text = (
            word.get("text", "")
            .strip()
            .upper()
        )

        if text != "REFERENCIA":
            continue

        x0 = float(
            word.get("x0", 0)
        )

        if (
            PREMIUM_REFERENCIA_XMIN
            <= x0
            <= PREMIUM_REFERENCIA_XMAX
        ):
            premium_found = True
            break

        if (
            NORMAL_REFERENCIA_XMIN
            <= x0
            <= NORMAL_REFERENCIA_XMAX
        ):
            return False

    return premium_found


# ============================================================
# DETECTAR CADA ENCABEZADO PREMIUM
# ============================================================

def find_premium_headers(
    words: List[Dict[str, Any]]
) -> List[Dict[str, float]]:
    """
    Busca cada encabezado Premium utilizando como ancla
    la palabra REFERENCIA en su coordenada X conocida.

    Retorna:

        [
            {
                "page": 1,
                "top": 532.66
            },
            {
                "page": 3,
                "top": 531.91
            },
            ...
        ]

    Cada aparición de REFERENCIA Premium representa
    un encabezado candidato.
    """

    headers = []

    for word in words:

        text = (
            word.get("text", "")
            .strip()
            .upper()
        )

        if text != "REFERENCIA":
            continue

        x0 = float(
            word.get("x0", 0)
        )

        if not (
            PREMIUM_REFERENCIA_XMIN
            <= x0
            <= PREMIUM_REFERENCIA_XMAX
        ):
            continue

        headers.append(
            {
                "page": int(
                    word.get("page", 1)
                ),
                "top": float(
                    word.get("top", 0)
                )
            }
        )

    headers.sort(
        key=lambda header: (
            header["page"],
            header["top"]
        )
    )

    return headers


# ============================================================
# VALIDAR QUE REALMENTE SEA ENCABEZADO
# ============================================================

def is_header_word(
    word: Dict[str, Any],
    header_page: int,
    header_top: float
) -> bool:
    """
    Determina si una palabra pertenece al encabezado
    Premium detectado.

    Se validan simultáneamente:

    - página
    - posición vertical
    - texto
    - posición horizontal correspondiente a la columna
      del encabezado.

    Esto evita eliminar palabras ajenas al encabezado.
    """

    page = int(
        word.get("page", 1)
    )

    if page != header_page:
        return False

    top = float(
        word.get("top", 0)
    )

    # El encabezado comienza en la primera línea:
    #
    # FECHA / SALDO
    #
    # y continúa en la segunda:
    #
    # OPER / LIQ / DESCRIPCIÓN / ...
    #
    # La palabra ancla REFERENCIA está en la segunda línea.
    #
    # Por eso permitimos:
    #
    # header_top - ~15 -> primera línea
    # header_top        -> segunda línea
    #

    first_line_top = (
        header_top
        - HEADER_SECOND_LINE_OFFSET
    )

    if not (
        first_line_top - HEADER_LINE_TOLERANCE
        <= top
        <= header_top + HEADER_LINE_TOLERANCE
    ):
        return False

    text = normalize_header_text(
        word.get("text", "")
    )

    if not text:
        return False

    x0 = float(
        word.get("x0", 0)
    )

    # --------------------------------------------------------
    # Determinar si la palabra corresponde a alguna
    # columna conocida del encabezado Premium.
    # --------------------------------------------------------

    for header_name, (
        xmin,
        xmax
    ) in PREMIUM_HEADER_COLUMNS.items():

        if text == normalize_header_text(
            header_name
        ):

            if x_in_range(
                x0,
                xmin,
                xmax
            ):
                return True

    return False


# ============================================================
# REMOVER ENCABEZADOS PREMIUM DUPLICADOS
# ============================================================

def remove_duplicate_premium_headers(
    words: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Elimina únicamente los encabezados repetidos del
    layout PREMIUM.

    Comportamiento:

    NORMAL:
        No modifica nada.

    PREMIUM con un encabezado:
        No modifica nada.

    PREMIUM con varios encabezados:
        Conserva únicamente el primero.
        Elimina exclusivamente las palabras que pertenecen
        a los encabezados posteriores.

    Ninguna otra palabra es modificada.
    """

    # --------------------------------------------------------
    # 1. NORMAL -> no tocar absolutamente nada.
    # --------------------------------------------------------

    if not is_premium_layout(words):
        return words


    # --------------------------------------------------------
    # 2. Buscar encabezados Premium.
    # --------------------------------------------------------

    headers = find_premium_headers(
        words
    )


    # --------------------------------------------------------
    # 3. Uno o ninguno -> no hay nada que eliminar.
    # --------------------------------------------------------

    if len(headers) <= 1:
        return words


    # --------------------------------------------------------
    # 4. El primero se conserva.
    #    Los demás son duplicados.
    # --------------------------------------------------------

    duplicate_headers = headers[1:]


    # --------------------------------------------------------
    # 5. Filtrar únicamente las palabras pertenecientes
    #    a esos encabezados duplicados.
    # --------------------------------------------------------

    cleaned = []

    for word in words:

        remove = False

        for header in duplicate_headers:

            if is_header_word(
                word,
                header["page"],
                header["top"]
            ):
                remove = True
                break

        if not remove:
            cleaned.append(
                word
            )


    return cleaned