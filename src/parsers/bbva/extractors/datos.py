import re
from typing import List, Dict, Any, Optional

from models.datos_cuenta import DatosCuenta


# ============================================================
# CONFIGURACIÓN ESPACIAL — DATOS DE CUENTA BBVA
# ============================================================
#
# Estas coordenadas corresponden directamente a los valores
# observados en el PDF BBVA proporcionado.
#
# NO se utilizan etiquetas para localizar los datos.
# El extractor únicamente lee lo que exista dentro de
# cada región espacial.
# ============================================================


# ------------------------------------------------------------
# PRODUCTO PRINCIPAL
#
# Libretón Básico Cuenta Digital
#
# x0 = 459.9866
# x1 = 598.2236
# top = 16.6544
# bottom = 27.6544
# ------------------------------------------------------------

# Coordenadas ajustadas según estado_bbva2.pdf
BOX_PRODUCTO_PRINCIPAL = (
    459.0,  # x0
    599.0,  # x1
    16.0,   # top
    28.0,   # bottom
)


# ------------------------------------------------------------
# PERIODO INICIAL
#
# 27/06/2022
#
# x0 = 498.9133
# x1 = 539.9533
# top = 48.3818
# bottom = 58.3818
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_PERIODO_INICIO = (
    498.0,  # x0
    540.0,  # x1
    48.0,   # top
    59.0,   # bottom
)


# ------------------------------------------------------------
# PERIODO FINAL
#
# 26/07/2022
#
# x0 = 554.5433
# x1 = 595.5833
# top = 48.3818
# bottom = 58.3818
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_PERIODO_FIN = (
    554.0,  # x0
    596.0,  # x1
    48.0,   # top
    59.0,   # bottom
)


# ------------------------------------------------------------
# FECHA DE CORTE
#
# 26/07/2022
#
# x0 = 554.5433
# x1 = 595.5833
# top = 63.4054
# bottom = 73.4054
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_FECHA_CORTE = (
    554.0,  # x0
    596.0,  # x1
    63.0,   # top
    74.0,   # bottom
)


# ------------------------------------------------------------
# NÚMERO DE CUENTA
#
# 1563369348
#
# x0 = 549.9833
# x1 = 595.5833
# top = 78.4290
# bottom = 88.4290
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_NUMERO_CUENTA = (
    549.0,  # x0
    596.0,  # x1
    78.0,   # top
    89.0,   # bottom
)


# ------------------------------------------------------------
# NÚMERO DE CLIENTE
#
# C8715220
#
# x0 = 558.1933
# x1 = 595.5833
# top = 93.4526
# bottom = 103.4526
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_NUMERO_CLIENTE = (
    558.0,  # x0
    596.0,  # x1
    93.0,   # top
    104.0,  # bottom
)


# ------------------------------------------------------------
# RFC
#
# FASS770615SN6
# NADJ951003-9I2
#
# x0 = 530.8533
# x1 = 595.5833
# top = 108.4762
# bottom = 118.4762
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_RFC = (
    530.0,  # x0
    596.0,  # x1
    108.0,  # top
    119.0,  # bottom
)


# ------------------------------------------------------------
# CLABE
#
# 012 180 01546750943 2
# 012 680 01563369348 1
# x0 = 506.6633 ... 595.5833
# top = 123.4999
# bottom = 133.4999
#
# Los fragmentos deben concatenarse:
#
# 012 + 180 + 01546750943 + 2
#
# = 012180015467509432
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_CLABE = (
    500.0,  # x0
    602.0,  # x1
    123.0,  # top
    143.0,  # bottom
)


# ------------------------------------------------------------
# NOMBRE DEL CLIENTE
#
# JONATHAN NAVA DIONICIO
#
# x0 = 40.8888 ... 145.6888
# top = 101.9564
# bottom = 111.9564
# ------------------------------------------------------------
# Coordenadas ajustadas según estado_bbva2.pdf
BOX_NOMBRE_CLIENTE = (
    40.0,   # x0
    300.0,  # x1 (ampliado para nombres largos)
    101.0,  # top
    112.0,  # bottom
)


OCR_LINE_TOLERANCE = 3.0

FULL_DATE_PATTERN = re.compile(
    r"^(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/\d{4}$"
)
ACCOUNT_NUMBER_PATTERN = re.compile(r"^\d{10}$")
CLIENT_NUMBER_PATTERN = re.compile(r"^[A-Z]\d{7}$")
RFC_PATTERN = re.compile(r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$")


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def word_inside_box(
    word: Dict[str, Any],
    box: tuple[float, float, float, float],
) -> bool:
    """
    Determina si una palabra pertenece a una región espacial.

    box:

        (
            xmin,
            xmax,
            ymin,
            ymax
        )

    Se utiliza el centro de la palabra para evitar problemas
    con palabras que se encuentren parcialmente sobre el
    límite de una región.
    """
    # Todos los datos de la cuenta están en la primera página.
    # Ignoramos cualquier palabra que no sea de la página 1.
    page = word.get("page", 1)
    if page != 1:
        return False

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)

    top = word.get("top", 0)
    bottom = word.get("bottom", 0)

    xmin, xmax, ymin, ymax = box

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return (
        xmin <= center_x <= xmax
        and ymin <= center_y <= ymax
    )


def words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> List[Dict[str, Any]]:
    """
    Devuelve las palabras que se encuentran dentro de
    una región espacial.

    Las palabras se ordenan de izquierda a derecha.
    """

    result = [
        word
        for word in words
        if word_inside_box(word, box)
    ]

    return words_in_reading_order(result)


def group_words_into_lines(
    words: List[Dict[str, Any]],
    tolerance: float = OCR_LINE_TOLERANCE,
) -> List[List[Dict[str, Any]]]:
    """Agrupa words conservando el orden visual de lectura.

    En texto digital todas las palabras de una línea suelen compartir ``top``.
    OCR introduce pequeñas variaciones verticales; ordenar únicamente por
    ``top`` invierte textos como "Libretón Básico Cuenta Digital" y también los
    fragmentos de la CLABE.
    """

    ordered = sorted(
        words,
        key=lambda word: (
            word.get("page", 1),
            word.get("top", 0),
            word.get("x0", 0),
        ),
    )
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_page: int | None = None
    current_top: float | None = None

    for word in ordered:
        page = int(word.get("page", 1))
        top = float(word.get("top", 0))

        if (
            current_top is None
            or (page == current_page and abs(top - current_top) <= tolerance)
        ):
            current.append(word)
            if current_top is None:
                current_top = top
                current_page = page
            continue

        current.sort(key=lambda item: item.get("x0", 0))
        lines.append(current)
        current = [word]
        current_top = top
        current_page = page

    if current:
        current.sort(key=lambda item: item.get("x0", 0))
        lines.append(current)

    return lines


def words_in_reading_order(
    words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aplana las palabras ordenadas por línea y luego de izquierda a derecha."""

    return [
        word
        for line in group_words_into_lines(words)
        for word in line
    ]


def normalized_compact_text(value: str) -> str:
    """Normaliza separadores sin corregir de forma agresiva texto libre."""

    return re.sub(r"[\s-]+", "", value.strip().upper())


def find_header_token(
    words: List[Dict[str, Any]],
    pattern: re.Pattern[str],
    *,
    first_page_only: bool = False,
) -> Optional[str]:
    """Busca un identificador en la zona derecha de encabezados BBVA.

    Cuenta y cliente se repiten en las páginas de movimientos; esa repetición
    permite recuperar un valor omitido por OCR en la primera página.
    """

    candidates = sorted(
        words,
        key=lambda word: (
            word.get("page", 1),
            word.get("top", 0),
            word.get("x0", 0),
        ),
    )

    for word in candidates:
        page = int(word.get("page", 1))
        top = float(word.get("top", 0))
        x0 = float(word.get("x0", 0))

        if first_page_only and page != 1:
            continue

        if x0 < 450 or top > 160:
            continue

        value = normalized_compact_text(word.get("text", ""))

        if pattern.fullmatch(value):
            return value

    return None


def find_header_dates(
    words: List[Dict[str, Any]],
) -> List[str]:
    """Obtiene las fechas completas del periodo y corte en orden visual."""

    dates: List[str] = []

    for word in words_in_reading_order(
        [
            word
            for word in words
            if word.get("page", 1) == 1
            and float(word.get("x0", 0)) >= 430
            and float(word.get("top", 0)) <= 100
        ]
    ):
        value = normalized_compact_text(word.get("text", "")).replace("O", "0")

        if FULL_DATE_PATTERN.fullmatch(value):
            dates.append(value)

    return dates


def find_customer_name(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """Recupera la primera línea del bloque postal, donde BBVA imprime al titular."""

    candidates = [
        word
        for word in words
        if word.get("page", 1) == 1
        and 20 <= (word.get("x0", 0) + word.get("x1", 0)) / 2 <= 300
        and 90 <= float(word.get("top", 0)) <= 140
    ]

    for line in group_words_into_lines(candidates):
        values = [word.get("text", "").strip() for word in line]
        values = [value for value in values if value]

        if line and min(float(word.get("top", 0)) for word in line) > 121.5:
            continue

        if len(values) < 2 or any(any(char.isdigit() for char in value) for value in values):
            continue

        if values[0].upper().rstrip(".") in {"AND", "AV", "CALLE", "COL"}:
            continue

        text = " ".join(values).strip()

        if text:
            return text

    return None


def text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> Optional[str]:
    """
    Extrae y concatena el texto contenido dentro de una
    región espacial.

    No busca etiquetas.
    No interpreta el contenido.
    Simplemente devuelve lo que existe dentro de la caja.
    """

    selected = words_in_box(
        words,
        box,
    )

    values = []

    for word in selected:

        text = word.get("text", "").strip()

        if text:
            values.append(text)

    if not values:
        return None

    return " ".join(values).strip()


def numeric_text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> Optional[str]:
    """
    Extrae los fragmentos numéricos contenidos en una
    región espacial y los concatena.

    Se utiliza específicamente para la CLABE, donde BBVA
    puede entregar el valor dividido en varias palabras.
    """

    selected = words_in_box(
        words,
        box,
    )

    parts = []

    for word in selected:

        text = word.get("text", "").strip()

        if text.isdigit():
            parts.append(text)

    if not parts:
        return None

    return "".join(parts)


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_producto_principal(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente el producto principal desde
    su coordenada espacial.

    Ejemplo:

        Libretón Básico Cuenta Digital
    """

    return text_from_box(
        words,
        BOX_PRODUCTO_PRINCIPAL,
    )


def extract_periodo_inicio(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente la fecha inicial del periodo.

    Ejemplo:

        05/05/2026
    """

    value = text_from_box(
        words,
        BOX_PERIODO_INICIO,
    )

    normalized = normalized_compact_text(value or "").replace("O", "0")

    if FULL_DATE_PATTERN.fullmatch(normalized):
        return normalized

    dates = find_header_dates(words)
    return dates[0] if dates else value


def extract_periodo_fin(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente la fecha final del periodo.

    Ejemplo:

        04/06/2026
    """

    value = text_from_box(
        words,
        BOX_PERIODO_FIN,
    )

    normalized = normalized_compact_text(value or "").replace("O", "0")

    if FULL_DATE_PATTERN.fullmatch(normalized):
        return normalized

    dates = find_header_dates(words)
    return dates[1] if len(dates) >= 2 else value


def extract_fecha_corte(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente la fecha de corte desde
    su coordenada espacial.

    Ejemplo:

        04/06/2026
    """

    value = text_from_box(
        words,
        BOX_FECHA_CORTE,
    )

    normalized = normalized_compact_text(value or "").replace("O", "0")

    if FULL_DATE_PATTERN.fullmatch(normalized):
        return normalized

    dates = find_header_dates(words)
    return dates[2] if len(dates) >= 3 else value


def extract_numero_cuenta(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente el número de cuenta desde
    su coordenada espacial.

    Ejemplo:

        1546750943
    """

    value = normalized_compact_text(
        text_from_box(words, BOX_NUMERO_CUENTA) or ""
    )

    if ACCOUNT_NUMBER_PATTERN.fullmatch(value):
        return value

    return find_header_token(
        words,
        ACCOUNT_NUMBER_PATTERN,
    )


def extract_numero_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente el número de cliente desde
    su coordenada espacial.

    Ejemplo:

        A0289423
    """

    value = normalized_compact_text(
        text_from_box(words, BOX_NUMERO_CLIENTE) or ""
    )

    if CLIENT_NUMBER_PATTERN.fullmatch(value):
        return value

    return find_header_token(
        words,
        CLIENT_NUMBER_PATTERN,
    )


def extract_rfc(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente el RFC desde su coordenada
    espacial.

    Ejemplo:

        FASS770615SN6
    """

    value = normalized_compact_text(text_from_box(
        words,
        BOX_RFC,
    ) or "")

    if RFC_PATTERN.fullmatch(value):
        return value

    return find_header_token(
        words,
        RFC_PATTERN,
        first_page_only=True,
    )


def extract_clabe(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente la CLABE desde su coordenada
    espacial.

    BBVA puede entregar la CLABE como varios words:

        012
        180
        01546750943
        2

    El extractor los concatena para obtener:

        012180015467509432
    """

    value = numeric_text_from_box(
        words,
        BOX_CLABE,
    )

    if value is None:
        return None

    if len(value) != 18:
        return None

    return value


def extract_nombre_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae directamente el nombre del cliente desde
    su coordenada espacial.

    Ejemplo:

        SELVA FRANCO SANCHEZ
    """

    direct = text_from_box(
        words,
        BOX_NOMBRE_CLIENTE,
    )

    fallback = find_customer_name(words)

    if not direct:
        return fallback

    if fallback and len(fallback.split()) > len(direct.split()):
        return fallback

    return direct


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_datos_cuenta_words(
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extractor espacial de datos generales de cuenta BBVA.

    Este extractor NO utiliza etiquetas del documento para
    encontrar los campos.

    Cada dato se obtiene exclusivamente desde la región
    espacial previamente identificada en el PDF.

    Campos extraídos:

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

    producto_principal = extract_producto_principal(
        words
    )

    periodo_inicio = extract_periodo_inicio(
        words
    )

    periodo_fin = extract_periodo_fin(
        words
    )

    fecha_corte = extract_fecha_corte(
        words
    )

    numero_cuenta = extract_numero_cuenta(
        words
    )

    numero_cliente = extract_numero_cliente(
        words
    )

    rfc = extract_rfc(
        words
    )

    clabe = extract_clabe(
        words
    )

    nombre_cliente = extract_nombre_cliente(
        words
    )

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
