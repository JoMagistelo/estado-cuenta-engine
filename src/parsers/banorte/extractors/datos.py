from __future__ import annotations

from typing import List, Dict, Any, Optional
import re

from models.datos_cuenta import DatosCuenta


# ============================================================
# EXTRACTOR ESPACIAL — DATOS DE CUENTA BANORTE
# ============================================================
#
# Este extractor trabaja exclusivamente con coordenadas.
#
# NO utiliza etiquetas para localizar campos.
#
# Cada dato se obtiene desde una región espacial previamente
# identificada dentro del layout BANORTE.
#
# Características:
#
#   - Todo el bloque general está en página 1.
#   - Las columnas se modelan mediante cajas espaciales.
#   - Se utiliza solapamiento espacial horizontal.
#   - La pertenencia vertical se determina mediante la
#     coordenada TOP de la palabra.
#   - Los valores pueden estar fragmentados en varias palabras.
#   - La lógica de negocio se mantiene separada de la lógica
#     espacial.
#
# ============================================================


# ============================================================
# PÁGINAS
# ============================================================

PAGE_DATOS = 1


# ============================================================
# CONFIGURACIÓN GENERAL DE TOLERANCIA
# ============================================================

# Una palabra puede tocar parcialmente una caja y seguir
# perteneciendo a ella horizontalmente.
#
# Esto permite tolerar:
#
#   - pequeñas variaciones de x
#   - pequeñas variaciones de renderizado
#
# IMPORTANTE:
#
# La tolerancia vertical NO se utiliza para determinar la
# pertenencia a un renglón.
#
# En este layout BANORTE los renglones se distinguen
# correctamente mediante "top".
#
SPATIAL_TOLERANCE_X = 1.5
SPATIAL_TOLERANCE_Y = 1.5


# ============================================================
# TOLERANCIA PARA AGRUPAR PALABRAS DEL MISMO RENGLÓN
# ============================================================
#
# Se utiliza exclusivamente cuando un campo puede aparecer
# en más de un renglón vertical dentro de la misma caja.
#
# En el nuevo layout BANORTE tenemos:
#
#     Primer renglón:
#         top ≈ 220.899
#
#     Segundo renglón:
#         top ≈ 230.859
#
# La diferencia es ≈ 9.96 puntos.
#
# Por lo tanto podemos considerar como pertenecientes al
# mismo renglón palabras cuyo TOP difiera muy poco.
#
# Esto NO reemplaza la lógica espacial general.
# Solamente se utiliza para seleccionar un renglón concreto.
# ============================================================

ROW_TOP_TOLERANCE = 1.5


# ============================================================
# PRODUCTO PRINCIPAL
# ============================================================
#
# Fila observada:
#
#     NOMINA BANORTE SIN CHEQUERA
#
# Coordenadas:
#
#     NOMINA       x=53.784 - 79.488
#     BANORTE      x=80.919 - 109.647
#     SIN          x=111.078 - 121.500
#     CHEQUERA     x=122.931 - 155.394
#
# Y:
#
#     top    ≈ 220.899
#     bottom ≈ 229.899
#
# Se deja margen suficiente para variaciones.
# ============================================================

BOX_PRODUCTO_PRINCIPAL = (
    49.0,    # x0
    160.0,   # x1
    217.5,   # top
    233.0,   # bottom
)


# ============================================================
# NÚMERO DE CUENTA
# ============================================================
#
# Valor observado en el nuevo layout:
#
#     Primer renglón:
#
#         1098973139
#
#     Segundo renglón:
#
#         1109382534
#
# Coordenadas:
#
#     x0 = 216.588
#     x1 = 251.238
#
# Y primer renglón:
#
#     top    = 220.899
#     bottom = 229.899
#
# Y segundo renglón:
#
#     top    = 230.859
#     bottom = 239.859
#
# IMPORTANTE:
#
# La caja continúa cubriendo el área original completa para
# no modificar el comportamiento espacial existente.
#
# La selección del PRIMER RENGLÓN se hace posteriormente
# mediante "_first_row_words_in_box".
# ============================================================

BOX_NUMERO_CUENTA = (
    211.0,
    256.0,
    217.5,
    233.0,
)


# ============================================================
# NÚMERO DE CLIENTE
# ============================================================
#
# Valor observado:
#
#     13128904
#
# Coordenadas:
#
#     x0 = 95.130
#     x1 = 122.850
#
# Y:
#
#     top    = 138.354
#     bottom = 147.354
#
# ============================================================

BOX_NUMERO_CLIENTE = (
    95.1,   # x0
    122.9,  # x1
    137.0,  # top
    140.0,  # bottom
)


# ============================================================
# RFC
# ============================================================
#
# Valor observado:
#
#     ROOM770801B36
#
# Coordenadas:
#
#     x0 = 63.702
#     x1 = 112.266
#
# Y:
#
#     top    = 146.368
#     bottom = 155.368
#
# ============================================================

BOX_RFC = (
    63.7,   # x0
    112.3,  # x1
    146.0,  # top
    156.0,  # bottom
)


# ============================================================
# NOMBRE DEL CLIENTE
# ============================================================
#
# Nombre observado:
#
#     MIGUEL ANGEL RODRIGUEZ OLMOS
#
# Coordenadas:
#
#     MIGUEL
#         x = 50.400 - 71.901
#
#     ANGEL
#         x = 73.314 - 91.620
#
#     RODRIGUEZ
#         x = 93.033 - 124.650
#
#     OLMOS
#         x = 126.063 - 145.827
#
# Todos en:
#
#     top    ≈ 63.426
#     bottom ≈ 72.426
#
# IMPORTANTE:
#
# La siguiente línea contiene DIRECCIÓN y comienza en
# top ≈ 71.136.
#
# Por eso NO debemos ampliar demasiado verticalmente la caja.
#
# La extensión horizontal sí puede ser amplia para soportar
# nombres más largos.
# ============================================================

BOX_NOMBRE_CLIENTE = (
    47.0,
    230.0,
    59.0,
    69.5,
)


# ============================================================
# PERIODO — INICIO
# ============================================================
#
# Valor observado:
#
#     01/Junio/2025
#
# Coordenadas:
#
#     x0 = 423.355
#     x1 = 468.139
#
# Y:
#
#     top    = 105.450
#     bottom = 114.450
#
# ============================================================

BOX_PERIODO_INICIO = (
    420.0,
    472.0,
    102.5,
    117.5,
)


# ============================================================
# PERIODO — FIN
# ============================================================
#
# Valor observado:
#
#     30/Junio/2025
#
# Coordenadas:
#
#     x0 = 476.824
#     x1 = 521.608
#
# Y:
#
#     top    = 105.450
#     bottom = 114.450
#
# ============================================================

BOX_PERIODO_FIN = (
    473.0,
    525.0,
    102.5,
    117.5,
)


# ============================================================
# FECHA DE CORTE
# ============================================================
#
# Valor observado dentro de la palabra:
#
#     corte30/Junio/2025
#
# Coordenadas:
#
#     x0 = 393.506
#     x1 = 456.493
#
# Y:
#
#     top    = 117.300
#     bottom = 126.300
#
# IMPORTANTE:
#
# El extractor espacial obtiene toda la palabra, pero
# posteriormente extraemos exclusivamente la fecha mediante
# expresión regular.
#
# ============================================================

BOX_FECHA_CORTE = (
    393.0,   # x0
    457.0,   # x1
    117.0,   # top
    127.0,   # bottom
)


# ============================================================
# CLABE
# ============================================================
#
# En el nuevo layout la CLABE aparece fragmentada en el
# PRIMER RENGLÓN:
#
#     072
#     853
#     01098973139
#     3
#
# Coordenadas:
#
#     072
#         x = 284.236 - 294.631
#
#     853
#         x = 296.044 - 306.439
#
#     01098973139
#         x = 307.852 - 345.967
#
#     3
#         x = 347.380 - 350.845
#
# Todas en:
#
#     top    ≈ 220.899
#
# La segunda cuenta aparece en el SEGUNDO RENGLÓN con los
# mismos rangos X pero:
#
#     top ≈ 230.859
#
# La caja permanece amplia para conservar la lógica original.
#
# La extracción posteriormente seleccionará únicamente
# el PRIMER RENGLÓN.
# ============================================================

BOX_CLABE = (
    281.0,
    354.5,
    217.5,
    233.0,
)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte un valor espacial a float de forma segura.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(
    value: Optional[str],
) -> Optional[str]:
    """
    Normaliza espacios de un texto.

    No altera el contenido semántico.
    """

    if value is None:
        return None

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value or None


def word_inside_box(
    word: Dict[str, Any],
    box: tuple[float, float, float, float],
    page_number: int,
) -> bool:
    """
    Determina si una palabra pertenece a una región espacial.

    IMPORTANTE:

    Las palabras PDF son unidades discretas con coordenadas
    propias.

    Para BANORTE NO debemos decidir la pertenencia vertical
    mediante intersección de rectángulos porque dos renglones
    consecutivos pueden tener unos puntos de solapamiento
    físico debido al renderizado.

    Ejemplo real:

        CLIENTE
            top    = 138.354
            bottom = 147.354

        RFC
            top    = 146.368
            bottom = 155.368

    Los rectángulos se intersectan ligeramente.

    Sin embargo, son DOS RENGLEONES distintos.

    Por ello:

        - X  -> solapamiento espacial
        - Y  -> posición TOP de la palabra

    Esto respeta la naturaleza del documento:

        cada palabra pertenece al renglón definido por su TOP.
    """

    page = word.get(
        "page",
        1,
    )

    if page != page_number:
        return False

    x0 = _safe_float(
        word.get("x0")
    )

    x1 = _safe_float(
        word.get("x1")
    )

    top = _safe_float(
        word.get("top")
    )

    xmin, xmax, ymin, ymax = box

    # ========================================================
    # TOLERANCIA HORIZONTAL
    # ========================================================

    xmin -= SPATIAL_TOLERANCE_X
    xmax += SPATIAL_TOLERANCE_X

    # ========================================================
    # SOLAPAMIENTO HORIZONTAL
    # ========================================================
    #
    # Seguimos permitiendo pequeñas variaciones de X.
    #
    # Esto permite que una palabra que toque parcialmente
    # la región siga perteneciendo a ella.
    # ========================================================

    horizontal_overlap = (
        min(x1, xmax)
        - max(x0, xmin)
    )

    if horizontal_overlap <= 0:
        return False

    # ========================================================
    # POSICIÓN VERTICAL
    # ========================================================
    #
    # NO usamos:
    #
    #     top/bottom del word
    #
    # contra:
    #
    #     ymin/ymax
    #
    # mediante intersección.
    #
    # Usamos directamente TOP.
    #
    # Así un word pertenece al renglón si su TOP cae dentro
    # del rango vertical configurado.
    #
    # Esto evita mezclar:
    #
    #     13128904
    #
    # con:
    #
    #     ROOM770801B36
    #
    # aunque sus rectángulos físicos lleguen a tocarse.
    # ========================================================

    ymin -= SPATIAL_TOLERANCE_Y
    ymax += SPATIAL_TOLERANCE_Y

    if top < ymin:
        return False

    if top > ymax:
        return False

    return True


def words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> List[Dict[str, Any]]:
    """
    Devuelve las palabras que se encuentran dentro de una
    región espacial.

    Orden:

        página
        posición vertical
        posición horizontal
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
            word.get(
                "page",
                page_number,
            ),
            _safe_float(
                word.get("top")
            ),
            _safe_float(
                word.get("x0")
            ),
        )
    )

    return result


def _first_row_words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> List[Dict[str, Any]]:
    """
    Devuelve únicamente las palabras pertenecientes al
    PRIMER RENGLÓN encontrado dentro de la caja espacial.

    Esta función existe para layouts BANORTE donde una misma
    caja horizontal puede contener varios registros verticales.

    Ejemplo del nuevo layout:

        top = 220.899  -> primer renglón
        top = 230.859  -> segundo renglón

    Se toma el menor TOP existente y se conservan todas las
    palabras cuyo TOP esté suficientemente cerca de ese valor.

    IMPORTANTE:

    Esto NO cambia la extracción espacial general.

    Solo permite resolver campos específicos que tienen más
    de un renglón dentro de la misma región.
    """

    selected = words_in_box(
        words,
        box,
        page_number,
    )

    if not selected:
        return []

    # ========================================================
    # PRIMER TOP REAL EN LA CAJA
    # ========================================================

    first_top = min(
        _safe_float(
            word.get("top")
        )
        for word in selected
    )

    # ========================================================
    # CONSERVAR SOLO LAS PALABRAS DEL PRIMER RENGLÓN
    # ========================================================
    #
    # Todas las palabras pertenecientes al mismo renglón
    # normalmente tienen el mismo TOP.
    #
    # La pequeña tolerancia permite resistir diferencias
    # mínimas de renderizado.
    # ========================================================

    first_row = [
        word
        for word in selected
        if abs(
            _safe_float(
                word.get("top")
            ) - first_top
        ) <= ROW_TOP_TOLERANCE
    ]

    first_row.sort(
        key=lambda word: (
            _safe_float(
                word.get("x0")
            )
        )
    )

    return first_row


def text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> Optional[str]:
    """
    Extrae texto de una caja espacial.

    No busca etiquetas.
    No depende de palabras específicas.

    Simplemente concatena el contenido localizado
    espacialmente.
    """

    selected = words_in_box(
        words,
        box,
        page_number,
    )

    values: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if text:
            values.append(text)

    if not values:
        return None

    return _normalize_text(
        " ".join(values)
    )


def numeric_text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> Optional[str]:
    """
    Extrae todos los fragmentos numéricos encontrados en una
    caja y los concatena.

    Esto es especialmente importante para BANORTE porque la
    CLABE aparece físicamente fragmentada.

    Ejemplo:

        072
        580
        01260110302
        0

    Resultado:

        072580012601103020
    """

    selected = words_in_box(
        words,
        box,
        page_number,
    )

    parts: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        # Conservamos únicamente caracteres numéricos.
        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:
            parts.append(digits)

    if not parts:
        return None

    return "".join(parts)


def numeric_text_from_first_row(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> Optional[str]:
    """
    Extrae únicamente los fragmentos numéricos del PRIMER
    RENGLÓN encontrado dentro de una caja.

    Se utiliza para campos como CLABE cuando la misma región
    horizontal contiene varios registros.

    Ejemplo:

        PRIMER RENGLÓN
            072
            853
            01098973139
            3

        SEGUNDO RENGLÓN
            072
            853
            01109382534
            3

    Resultado:

        072853010989731393

    Importante:

    Si el layout antiguo solo tiene un renglón, se comporta
    exactamente como numeric_text_from_box().
    """

    selected = _first_row_words_in_box(
        words,
        box,
        page_number,
    )

    parts: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        digits = re.sub(
            r"\D",
            "",
            text,
        )

        if digits:
            parts.append(digits)

    if not parts:
        return None

    return "".join(parts)


def text_from_first_row(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> Optional[str]:
    """
    Extrae texto únicamente del PRIMER RENGLÓN encontrado
    dentro de una caja.

    Si solamente existe un renglón, funciona exactamente igual
    que text_from_box().
    """

    selected = _first_row_words_in_box(
        words,
        box,
        page_number,
    )

    values: List[str] = []

    for word in selected:

        text = str(
            word.get(
                "text",
                "",
            )
        ).strip()

        if text:
            values.append(text)

    if not values:
        return None

    return _normalize_text(
        " ".join(values)
    )


# ============================================================
# UTILIDADES DE VALIDACIÓN
# ============================================================


def normalize_rfc(
    value: Optional[str],
) -> Optional[str]:
    """
    Normaliza un RFC eliminando espacios y el prefijo "RFC:".
    """

    if value is None:
        return None

    # Elimina cualquier instancia de "RFC" y dos puntos,
    # con o sin espacios.
    # Ejemplo: "RFC: RFC: ROOM770801B36" -> "ROOM770801B36"
    cleaned_value = re.sub(
        r"(?:RFC\s*:?\s*)+",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s+",
        "",
        cleaned_value.upper(),
    )

    return value or None


def normalize_account(
    value: Optional[str],
) -> Optional[str]:
    """
    Normaliza un número de cuenta.

    Se conservan únicamente dígitos.
    """

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return digits or None


def normalize_customer_number(
    value: Optional[str],
) -> Optional[str]:
    """
    Normaliza el número de cliente.
    """

    if value is None:
        return None

    # Conservamos únicamente dígitos para el número de cliente.
    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return digits or None


def normalize_clabe(
    value: Optional[str],
) -> Optional[str]:
    """
    Valida y normaliza una CLABE.

    Debe contener exactamente 18 dígitos.
    """

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if len(digits) != 18:
        return None

    return digits


def extract_date_from_text(
    value: Optional[str],
) -> Optional[str]:
    """
    Extrae una fecha desde una cadena espacial.

    Soporta:

        01/Junio/2025
        30/Junio/2025

    e incluso casos donde la palabra está pegada a texto:

        corte30/Junio/2025
    """

    if value is None:
        return None

    match = re.search(
        r"\d{1,2}/[A-Za-zÁÉÍÓÚáéíóúÑñ]+/\d{4}\b",
        value,
    )

    if not match:
        return None

    return match.group(0)


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_producto_principal(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el producto principal.

    Ejemplo:

        NOMINA BANORTE SIN CHEQUERA
    """

    value = text_from_box(
        words,
        BOX_PRODUCTO_PRINCIPAL,
        PAGE_DATOS,
    )

    return _normalize_text(value)


def extract_numero_cuenta(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el número de cuenta.

    En layouts donde la misma caja contiene varios renglones,
    se toma exclusivamente el PRIMER RENGLÓN.

    Esto evita concatenar:

        1098973139
        1109382534

    y obtener incorrectamente:

        10989731391109382534

    En layouts anteriores con un solo renglón, el comportamiento
    permanece igual.
    """

    value = text_from_first_row(
        words,
        BOX_NUMERO_CUENTA,
        PAGE_DATOS,
    )

    return normalize_account(value)


def extract_numero_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el número de cliente.

    Ejemplo:

        13128904
    """

    value = text_from_box(
        words,
        BOX_NUMERO_CLIENTE,
        PAGE_DATOS,
    )

    return normalize_customer_number(value)


def extract_rfc(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae y normaliza el RFC.

    Ejemplo:

        ROOM770801B36
    """

    value = text_from_box(
        words,
        BOX_RFC,
        PAGE_DATOS,
    )

    return normalize_rfc(value)


def extract_nombre_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el nombre del cliente.

    La caja está limitada verticalmente para evitar capturar
    la línea inmediatamente inferior correspondiente a la
    dirección.

    Ejemplo:

        MIGUEL ANGEL RODRIGUEZ OLMOS
    """

    value = text_from_box(
        words,
        BOX_NOMBRE_CLIENTE,
        PAGE_DATOS,
    )

    return _normalize_text(value)


def extract_periodo_inicio(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha inicial del periodo.

    Ejemplo:

        01/Junio/2025
    """

    value = text_from_box(
        words,
        BOX_PERIODO_INICIO,
        PAGE_DATOS,
    )

    return extract_date_from_text(value)


def extract_periodo_fin(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha final del periodo.

    Ejemplo:

        30/Junio/2025
    """

    value = text_from_box(
        words,
        BOX_PERIODO_FIN,
        PAGE_DATOS,
    )

    return extract_date_from_text(value)


def extract_fecha_corte(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha de corte.

    La palabra observada por el PDF puede venir como:

        corte30/Junio/2025

    por lo que primero se localiza espacialmente y después
    se extrae únicamente la fecha.
    """

    value = text_from_box(
        words,
        BOX_FECHA_CORTE,
        PAGE_DATOS,
    )

    return extract_date_from_text(value)


def extract_clabe(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la CLABE.

    BANORTE puede fragmentarla visualmente en varios bloques.

    En el nuevo layout existen DOS renglones dentro de la misma
    región espacial.

    Por eso se toma exclusivamente el PRIMER RENGLÓN.

    Esto conserva el comportamiento anterior cuando solamente
    existe un renglón.
    """

    value = numeric_text_from_first_row(
        words,
        BOX_CLABE,
        PAGE_DATOS,
    )

    return normalize_clabe(value)


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_datos_cuenta_words(
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extractor espacial de datos generales de cuenta BANORTE.

    NO depende de etiquetas.

    Todos los campos se obtienen mediante coordenadas.

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