from typing import List, Dict, Any, Optional

from models.datos_cuenta import DatosCuenta


# ============================================================
# CONFIGURACIÓN ESPACIAL — DATOS DE CUENTA BANAMEX
# ============================================================
#
# Este extractor trabaja exclusivamente mediante coordenadas
# espaciales.
#
# NO utiliza etiquetas para localizar los valores.
#
# Las cajas están definidas pensando en la CELDA / COLUMNA
# donde vive cada dato, y no únicamente alrededor de las
# palabras actualmente observadas.
#
# Esto permite tolerar:
#
#   - nombres de producto más largos
#   - nombres de cliente más largos
#   - pequeñas variaciones de espaciado
#   - cambios menores en el ancho del texto
#
# ============================================================


# ============================================================
# PÁGINAS
# ============================================================

PAGE_GENERAL = 1
PAGE_CLIENTE = 2


# ============================================================
# PRODUCTO PRINCIPAL
# ============================================================
#
# Fila:
#
#     PRODUCTO/SERVICIO | CONTRATO | ...
#
# Valor observado:
#
#     MiCuenta
#
# Coordenada observada:
#
#     x0 = 18.3
#     x1 = 56.811
#     top = 392.463
#     bottom = 401.463
#
# IMPORTANTE:
#
# La caja NO se limita a x1 = 56.811.
#
# Se utiliza prácticamente todo el ancho de la columna
# PRODUCTO/SERVICIO, hasta antes de la columna CONTRATO.
#
# ============================================================

BOX_PRODUCTO_PRINCIPAL = (
    17.0,   # x0
    178.0,  # x1
    389.0,  # top
    405.0,  # bottom
)


# ============================================================
# NÚMERO DE CUENTA / CONTRATO
# ============================================================
#
# Coordenada observada:
#
#     x0 = 187.8
#     x1 = 232.836
#     top = 392.463
#     bottom = 401.463
#
# La columna CONTRATO comienza aproximadamente en x=181.8
# y termina antes de la columna de SALDO ANTERIOR.
#
# ============================================================

BOX_NUMERO_CUENTA = (
    178.0,  # x0
    249.0,  # x1
    389.0,  # top
    405.0,  # bottom
)


# ============================================================
# PERIODO INICIAL
# ============================================================
#
# Texto:
#
#     RESUMEN DEL 09/ENE/2026 AL 08/FEB/2026
#
# Valor:
#
#     09/ENE/2026
#
# Coordenada observada:
#
#     x0 = 101.411
#     x1 = 166.839
#
# La caja deja margen a ambos lados para que una variación
# razonable del texto no provoque pérdida.
#
# ============================================================

BOX_PERIODO_INICIO = (
    98.0,   # x0
    170.0,  # x1
    453.0,  # top
    471.0,  # bottom
)


# ============================================================
# PERIODO FINAL
# ============================================================
#
# Valor:
#
#     08/FEB/2026
#
# Coordenada observada:
#
#     x0 = 189.466
#     x1 = 253.673
#
# ============================================================

BOX_PERIODO_FIN = (
    186.0,  # x0
    257.0,  # x1
    453.0,  # top
    471.0,  # bottom
)


# ============================================================
# FECHA DE CORTE
# ============================================================
#
# En la tabla RESUMEN GENERAL aparece:
#
#     SALDO AL 06/FEB/2026
#
# La fecha está ubicada en:
#
#     x0 = 409.821
#     x1 = 462.354
#
# La caja se limita a la celda de la fecha, NO a toda la
# expresión "SALDO AL".
#
# ============================================================

BOX_FECHA_CORTE = (
    406.0,  # x0
    467.0,  # x1
    377.0,  # top
    393.0,  # bottom
)


# ============================================================
# NÚMERO DE CLIENTE
# ============================================================
#
# Coordenada:
#
#     x0 = 424.5
#     x1 = 479.544
#     top = 20.677
#     bottom = 31.677
#
# Se utiliza la zona derecha del encabezado.
#
# ============================================================

BOX_NUMERO_CLIENTE = (
    420.0,  # x0
    482.0,  # x1
    17.0,   # top
    35.0,   # bottom
)


# ============================================================
# NOMBRE DEL CLIENTE
# ============================================================
#
# La caja cubre la zona completa donde aparece el nombre,
# permitiendo que aparezcan nombres más largos.
#
# ============================================================

BOX_NOMBRE_CLIENTE = (
    18.0,   # x0
    280.0,  # x1
    40.0,   # top
    58.0,   # bottom
)


# ============================================================
# RFC
# ============================================================
#
#
# Coordenada:
#
#     x0 = 397.2
#     x1 = 480.965
#     top = 32.077
#     bottom = 43.077
#
# La etiqueta "Registro Federal de Contribuyentes" está
# aproximadamente entre x=189 y x=363.
#
# El valor comienza aproximadamente en x=397.
#
# ============================================================

BOX_RFC = (
    392.0,  # x0
    483.0,  # x1
    28.0,   # top
    47.0,   # bottom
)


# ============================================================
# CLABE
# ============================================================
#
#
# Coordenada:
#
#     x0 = 137.7
#     x1 = 227.772
#     top = 403.863
#     bottom = 412.863
#
# La etiqueta:
#
#     CLABE Interbancaria
#
# ocupa aproximadamente x=18.3 hasta x=102.837.
#
# Por eso la caja empieza después de la etiqueta y deja
# espacio suficiente hacia la derecha.
#
# ============================================================

BOX_CLABE = (
    133.0,  # x0
    250.0,  # x1
    400.0,  # top
    417.0,  # bottom
)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def word_inside_box(
    word: Dict[str, Any],
    box: tuple[float, float, float, float],
    page_number: int,
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

    A diferencia del extractor BBVA, aquí la página se recibe
    explícitamente porque los datos generales de Banamex se
    encuentran distribuidos entre página 1 y página 2.
    """

    page = word.get("page", 1)

    if page != page_number:
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
    page_number: int,
) -> List[Dict[str, Any]]:
    """
    Devuelve las palabras que se encuentran dentro de una
    región espacial determinada.

    Las palabras se ordenan:

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
            word.get("page", page_number),
            word.get("top", 0),
            word.get("x0", 0),
        )
    )

    return result


def text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int,
) -> Optional[str]:
    """
    Extrae y concatena el texto contenido dentro de una
    región espacial.

    No busca etiquetas.

    No interpreta el contenido.

    Simplemente devuelve las palabras existentes dentro
    de la caja.
    """

    selected = words_in_box(
        words,
        box,
        page_number,
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
    page_number: int,
) -> Optional[str]:
    """
    Extrae los fragmentos numéricos contenidos dentro de
    una región espacial y los concatena.

    Se utiliza para valores como la CLABE.
    """

    selected = words_in_box(
        words,
        box,
        page_number,
    )

    parts = []

    for word in selected:

        text = word.get("text", "").strip()

        # Permitimos únicamente fragmentos completamente
        # numéricos.
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
    Extrae el producto principal.

    Ejemplo:

        MiCuenta
    """

    return text_from_box(
        words,
        BOX_PRODUCTO_PRINCIPAL,
        PAGE_GENERAL,
    )


def extract_periodo_inicio(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha inicial del periodo.

    Ejemplo:

        09/ENE/2026
    """

    return text_from_box(
        words,
        BOX_PERIODO_INICIO,
        PAGE_GENERAL,
    )


def extract_periodo_fin(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha final del periodo.

    Ejemplo:

        08/FEB/2026
    """

    return text_from_box(
        words,
        BOX_PERIODO_FIN,
        PAGE_GENERAL,
    )


def extract_fecha_corte(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la fecha de corte.

    Ejemplo:

        06/FEB/2026
    """

    return text_from_box(
        words,
        BOX_FECHA_CORTE,
        PAGE_GENERAL,
    )


def extract_numero_cuenta(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el número de cuenta / contrato.

    """

    return text_from_box(
        words,
        BOX_NUMERO_CUENTA,
        PAGE_GENERAL,
    )


def extract_numero_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el número de cliente.

    Ejemplo:
    """

    return text_from_box(
        words,
        BOX_NUMERO_CLIENTE,
        PAGE_CLIENTE,
    )


def extract_rfc(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el RFC.

    Ejemplo:

    """

    value = text_from_box(
        words,
        BOX_RFC,
        PAGE_GENERAL,
    )

    if value is None:
        return None

    return value.replace(" ", "")


def extract_clabe(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae la CLABE interbancaria.

    """

    value = numeric_text_from_box(
        words,
        BOX_CLABE,
        PAGE_GENERAL,
    )

    if value is None:
        return None

    # Una CLABE mexicana tiene 18 dígitos.
    if len(value) != 18:
        return None

    return value


def extract_nombre_cliente(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el nombre completo del cliente.

    """

    return text_from_box(
        words,
        BOX_NOMBRE_CLIENTE,
        PAGE_CLIENTE,
    )


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_datos_cuenta_words(
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extractor espacial de datos generales de cuenta BANAMEX.

    Este extractor NO utiliza etiquetas del documento para
    encontrar los campos.

    Cada dato se obtiene exclusivamente desde la región
    espacial previamente identificada.

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