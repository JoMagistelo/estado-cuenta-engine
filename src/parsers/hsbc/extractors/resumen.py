from typing import List, Dict, Any, Optional
import re

from models.resumen_financiero import ResumenFinanciero


# ============================================================
# REFERENCIAS DE LAYOUT
# ============================================================

# Caso NORMAL:
# "Saldo" / "Promedio" aparecen en este top.
SALDO_PROMEDIO_NORMAL_TOP = 259.197338

# Caso PREMIUM:
# "Saldo" / "Promedio" aparecen en este top.
SALDO_PROMEDIO_PREMIUM_TOP = 246.123783


# ============================================================
# CONFIGURACIÓN ESPACIAL — RESUMEN FINANCIERO BBVA
# ============================================================
#
# Estas coordenadas corresponden directamente a los valores
# observados en el PDF BBVA proporcionado, dentro del bloque
# "Información Financiera" (Rendimiento, Comisiones y
# Comportamiento del periodo).
#
# NO se utilizan etiquetas para localizar los datos.
# El extractor únicamente lee lo que exista dentro de
# cada región espacial.
#
# El bloque se organiza en dos columnas sobre el mismo
# renglón (mismo "top"):
#
#   Columna izquierda -> Rendimiento / Comisiones
#   Columna derecha   -> Comportamiento
# ============================================================


# ------------------------------------------------------------
# RENDIMIENTO — SALDO PROMEDIO
BOX_SALDO_PROMEDIO = (
    260.0,  # x0
    296.0,  # x1
    259.0,  # top
    270.0,  # bottom
)


# ------------------------------------------------------------
# RENDIMIENTO — DÍAS DEL PERIODO
BOX_DIAS_PERIODO = (
    285.0,  # x0
    296.0,  # x1
    273.0,  # top
    284.0,  # bottom
)


# ------------------------------------------------------------
# RENDIMIENTO — TASA BRUTA ANUAL
# Nota: el símbolo "%" se imprime aparte, en x0 ≈ 184.67,
# dentro del mismo renglón. No forma parte del valor
# numérico y por lo tanto se deja fuera de la caja de forma
# deliberada.
BOX_TASA_BRUTA_ANUAL = (
    273.0,  # x0
    296.0,  # x1
    287.0,  # top
    298.0,  # bottom
)


# ------------------------------------------------------------
# RENDIMIENTO — SALDO PROMEDIO GRAVABLE
BOX_SALDO_PROMEDIO_GRAVABLE = (
    278.0,  # x0
    296.0,  # x1
    301.0,  # top
    312.0,  # bottom
)


# ------------------------------------------------------------
# RENDIMIENTO — INTERESES A FAVOR (+)
BOX_INTERESES_A_FAVOR = (
    278.0,  # x0
    296.0,  # x1
    315.0,  # top
    326.0,  # bottom
)


# ------------------------------------------------------------
# RENDIMIENTO — ISR RETENIDO (-)
BOX_ISR_RETENIDO = (
    278.0,  # x0
    296.0,  # x1
    330.0,  # top
    341.0,  # bottom
)


# ------------------------------------------------------------
# COMISIONES — CHEQUES PAGADOS (conteo)
# Nota: en el mismo renglón existe además un importe
# ("0.00" en x0 ≈ 277.85) que no forma parte del modelo,
# ya que cheques_pagados es un conteo (int), no un importe.
# Se deja fuera de la caja de forma deliberada.
BOX_CHEQUES_PAGADOS = (
    184.0,  # x0
    190.0,  # x1
    358.0,  # top
    369.0,  # bottom
)


# ------------------------------------------------------------
# COMISIONES — MANEJO DE CUENTA (importe)
BOX_MANEJO_CUENTA = (
    277.0,  # x0
    296.0,  # x1
    372.0,  # top
    383.0,  # bottom
)


# ------------------------------------------------------------
# TOTAL COMISIONES — CARGOS OBJETADOS (importe)
# Nota: en el mismo renglón existe además un conteo
# ("0" en x0 ≈ 184.55) que no se usa aquí: el modelo define
# cargos_objetados como float (importe), no como conteo.
BOX_CARGOS_OBJETADOS = (
    278.0,  # x0
    296.0,  # x1
    400.0,  # top
    411.0,  # bottom
)


# ------------------------------------------------------------
# TOTAL COMISIONES — ABONOS OBJETADOS (importe)
# Nota: igual que en cargos_objetados, se ignora el conteo
# ("0" en x0 ≈ 184.55) y se toma el importe.
BOX_ABONOS_OBJETADOS = (
    278.0,  # x0
    296.0,  # x1
    415.0,  # top
    426.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — SALDO ANTERIOR
BOX_SALDO_ANTERIOR = (
    547.0,  # x0
    583.0,  # x1
    259.0,  # top
    270.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — DEPÓSITOS / ABONOS (+) (importe)
# Nota: en el mismo renglón existe además un conteo de
# movimientos ("215" en x0 ≈ 460.11) que no se usa aquí:
# el modelo define depositos_abonos como float (importe),
# no como conteo.
BOX_DEPOSITOS_ABONOS = (
    542.0,  # x0
    583.0,  # x1
    273.0,  # top
    284.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — RETIROS / CARGOS (-) (importe)
# Nota: igual que en depósitos_abonos, se ignora el conteo
# ("68" en x0 ≈ 465.24) y se toma el importe.
BOX_RETIROS_CARGOS = (
    542.0,  # x0
    583.0,  # x1
    287.0,  # top
    298.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — SALDO FINAL
BOX_SALDO_FINAL = (
    547.0,  # x0
    583.0,  # x1
    298.0,  # top
    309.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — SALDO PROMEDIO MÍNIMO MENSUAL
BOX_SALDO_PROMEDIO_MINIMO_MENSUAL = (
    564.0,  # x0
    583.0,  # x1
    312.0,  # top
    323.0,  # bottom
)


# ------------------------------------------------------------
# COMPORTAMIENTO — SALDO GLOBAL
# La etiqueta "Saldo Global" se encuentra a la izquierda
# (x0 ≈ 319), pero el valor numérico está alineado a la
# derecha con el resto de los importes de la sección
# "Comportamiento".
# La caja se define para capturar únicamente el valor numérico
# y su posible signo de moneda ($), que es lo que nos interesa.
BOX_SALDO_GLOBAL = (
    510.0,  # x0 (Desde el signo '$' para incluirlo)
    583.0,  # x1 (Alineado con el resto de la columna)
    456.0,  # top (Ajustado para ser más preciso)
    467.0,  # bottom (Con margen de tolerancia)
)

# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def get_delta_y(
    words: List[Dict[str, Any]],
) -> float:
    """
    Detecta si el documento utiliza el layout normal
    o el layout premium y devuelve el desplazamiento vertical.

    Normal:
        delta_y = 0

    Premium:
        delta_y = PREMIUM_TOP - NORMAL_TOP
    """

    found_normal = False
    found_premium = False

    for word in words:

        if word.get("page", 1) != 1:
            continue

        text = word.get("text", "").strip().lower()

        if text not in {"saldo", "promedio"}:
            continue

        top = word.get("top")

        if top is None:
            continue

        if abs(top - SALDO_PROMEDIO_NORMAL_TOP) <= 2.0:
            found_normal = True
            break

        if abs(top - SALDO_PROMEDIO_PREMIUM_TOP) <= 2.0:
            found_premium = True

    if found_normal:
        return 0.0

    if found_premium:
        return (
            SALDO_PROMEDIO_PREMIUM_TOP
            - SALDO_PROMEDIO_NORMAL_TOP
        )

    # Por defecto, asumimos el layout normal si no se
    # encuentra una referencia clara.
    return 0.0


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
    # Todo el resumen financiero está en la primera página.
    # Ignoramos cualquier palabra que no sea de la página 1.
    page = word.get("page", 1)
    if page != 1:
        return False

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)

    top = word.get("top", 0)
    bottom = word.get("bottom", 0)

    box_xmin, box_xmax, box_ymin, box_ymax = box

    # Comprueba si hay superposición entre la caja de la palabra y la caja de búsqueda.
    # Esto es más robusto que usar el centro, especialmente para palabras en los bordes.
    x_overlap = x0 < box_xmax and x1 > box_xmin
    y_overlap = top < box_ymax and bottom > box_ymin

    return x_overlap and y_overlap


def words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> List[Dict[str, Any]]:
    """
    Devuelve las palabras que pertenecen a la caja,
    aplicando únicamente el desplazamiento vertical
    correspondiente al layout detectado.
    """

    delta_y = get_delta_y(words)

    box_xmin, box_xmax, box_ymin, box_ymax = box

    adjusted_box = (
        box_xmin,
        box_xmax,
        box_ymin + delta_y,
        box_ymax + delta_y,
    )

    result = [
        word
        for word in words
        if word_inside_box(word, adjusted_box)
    ]

    result.sort(
        key=lambda word: (
            word.get("page", 1),
            word.get("top", 0),
            word.get("x0", 0),
        )
    )

    return result


def text_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> Optional[str]:
    """
    Extrae y concatena el texto contenido dentro de una
    región espacial.
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


def extract_numeric_amount_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> Optional[float]:
    """
    Extrae un importe monetario desde una región espacial.
    
    Ignora símbolos monetarios y busca un token numérico,
    soportando separadores de miles. Es robusto contra la
    fragmentación de palabras del OCR (ej. "$" y "6,341.00"
    como palabras separadas).
    """

    selected = words_in_box(
        words,
        box,
    )

    # Patrón monetario.
    # Soporta números con o sin decimales y comas de miles.
    amount_pattern = re.compile(
        r"""
        ^[+-]?
        (?:
            \d{1,3}(?:,\d{3})+
            |
            \d+
        )
        (?:\.\d{2,})?
        $
        """,
        re.VERBOSE,
    )

    # Buscar únicamente palabras que sean importes.
    for word in selected:

        text = word.get("text", "").strip()

        if not text or not amount_pattern.fullmatch(text):
            continue

        try:
            return float(text.replace(",", ""))
        except (ValueError, TypeError):
            continue

    return None

# ============================================================
# UTILIDADES NUMÉRICAS
# ============================================================


def parse_amount(value: Optional[str]) -> float:
    """
    Convierte un texto numérico (posiblemente con comas de
    miles) a float.

    Devuelve 0.0 si el valor es None, vacío, o no puede
    convertirse.
    """

    if not value:
        return 0.0

    value = (
        value
        .replace(",", "")
        .replace(" ", "")
        .strip()
    )

    try:
        return float(value)

    except (ValueError, TypeError):

        return 0.0


def parse_amount_optional(value: Optional[str]) -> Optional[float]:
    """
    Igual que parse_amount, pero preserva None cuando no se
    encontró texto dentro de la caja.
    """

    if not value:
        return None

    value = (
        value
        .replace(",", "")
        .replace(" ", "")
        .strip()
    )

    try:
        return float(value)

    except (ValueError, TypeError):

        return None


def parse_int(value: Optional[str]) -> int:
    """
    Convierte un texto entero (posiblemente con comas de
    miles) a int.

    Devuelve 0 si el valor es None, vacío, o no puede
    convertirse.
    """

    if not value:
        return 0

    value = (
        value
        .replace(",", "")
        .replace(" ", "")
        .strip()
    )

    try:
        return int(float(value))

    except (ValueError, TypeError):

        return 0


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_saldo_promedio(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae directamente el saldo promedio (Rendimiento)
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_SALDO_PROMEDIO,
    )

    return parse_amount_optional(texto)


def extract_dias_periodo(
    words: List[Dict[str, Any]],
) -> int:
    """
    Extrae directamente los días del periodo desde su
    coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_DIAS_PERIODO,
    )

    return parse_int(texto)


def extract_tasa_bruta_anual(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente la tasa bruta anual (%) desde su
    coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_TASA_BRUTA_ANUAL,
    )

    return parse_amount(texto)


def extract_saldo_promedio_gravable(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el saldo promedio gravable desde
    su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_SALDO_PROMEDIO_GRAVABLE,
    )

    return parse_amount(texto)


def extract_intereses_a_favor(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente los intereses a favor (+) desde
    su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_INTERESES_A_FAVOR,
    )

    return parse_amount(texto)


def extract_isr_retenido(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el ISR retenido (-) desde su
    coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_ISR_RETENIDO,
    )

    return parse_amount(texto)


def extract_cheques_pagados(
    words: List[Dict[str, Any]],
) -> int:
    """
    Extrae directamente el número de cheques pagados desde
    su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_CHEQUES_PAGADOS,
    )

    return parse_int(texto)


def extract_manejo_cuenta(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el importe de manejo de cuenta
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_MANEJO_CUENTA,
    )

    return parse_amount(texto)


def extract_cargos_objetados(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el importe de cargos objetados
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_CARGOS_OBJETADOS,
    )

    return parse_amount(texto)


def extract_abonos_objetados(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el importe de abonos objetados
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_ABONOS_OBJETADOS,
    )

    return parse_amount(texto)


def extract_saldo_anterior(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el saldo anterior (Comportamiento)
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_SALDO_ANTERIOR,
    )

    return parse_amount(texto)


def extract_depositos_abonos(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el importe de depósitos / abonos (+)
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_DEPOSITOS_ABONOS,
    )

    return parse_amount(texto)


def extract_retiros_cargos(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el importe de retiros / cargos (-)
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_RETIROS_CARGOS,
    )

    return parse_amount(texto)


def extract_saldo_final(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el saldo final (Comportamiento)
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_SALDO_FINAL,
    )

    return parse_amount(texto)


def extract_saldo_promedio_minimo_mensual(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae directamente el saldo promedio mínimo mensual
    desde su coordenada espacial.
    """

    texto = text_from_box(
        words,
        BOX_SALDO_PROMEDIO_MINIMO_MENSUAL,
    )

    return parse_amount(texto)


def extract_saldo_global(
    words: List[Dict[str, Any]],
) -> float:
    """
    Extrae el saldo global exclusivamente mediante coordenadas
    espaciales.

    La función NO utiliza la etiqueta "Saldo Global", solo la
    caja de coordenadas definida en `BOX_SALDO_GLOBAL`.
    """
    value = extract_numeric_amount_from_box(
        words,
        BOX_SALDO_GLOBAL,
    )
    return value if value is not None else 0.0


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_resumen_financiero_words(
    words: List[Dict[str, Any]],
) -> ResumenFinanciero:
    """
    Extractor espacial del resumen financiero BBVA.

    Este extractor NO utiliza etiquetas del documento para
    encontrar los campos.

    Cada dato se obtiene exclusivamente desde la región
    espacial previamente identificada en el PDF, dentro del
    bloque "Información Financiera".

    Campos extraídos:

        Rendimiento
            - saldo_promedio
            - dias_periodo
            - tasa_bruta_anual
            - saldo_promedio_gravable
            - intereses_a_favor
            - isr_retenido

        Comisiones
            - cheques_pagados
            - manejo_cuenta

        Total Comisiones
            - cargos_objetados
            - abonos_objetados

        Comportamiento
            - saldo_anterior
            - depositos_abonos
            - retiros_cargos
            - saldo_final
            - saldo_promedio_minimo_mensual
            - saldo_global (coordenada estimada, ver
              BOX_SALDO_GLOBAL)
    """

    saldo_promedio = extract_saldo_promedio(
        words
    )

    dias_periodo = extract_dias_periodo(
        words
    )

    tasa_bruta_anual = extract_tasa_bruta_anual(
        words
    )

    saldo_promedio_gravable = extract_saldo_promedio_gravable(
        words
    )

    intereses_a_favor = extract_intereses_a_favor(
        words
    )

    isr_retenido = extract_isr_retenido(
        words
    )

    cheques_pagados = extract_cheques_pagados(
        words
    )

    manejo_cuenta = extract_manejo_cuenta(
        words
    )

    cargos_objetados = extract_cargos_objetados(
        words
    )

    abonos_objetados = extract_abonos_objetados(
        words
    )

    saldo_anterior = extract_saldo_anterior(
        words
    )

    depositos_abonos = extract_depositos_abonos(
        words
    )

    retiros_cargos = extract_retiros_cargos(
        words
    )

    saldo_final = extract_saldo_final(
        words
    )

    saldo_promedio_minimo_mensual = extract_saldo_promedio_minimo_mensual(
        words
    )

    saldo_global = extract_saldo_global(
        words
    )

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,

        dias_periodo=dias_periodo,

        tasa_bruta_anual=tasa_bruta_anual,

        saldo_promedio_gravable=saldo_promedio_gravable,

        intereses_a_favor=intereses_a_favor,

        isr_retenido=isr_retenido,

        cheques_pagados=cheques_pagados,

        manejo_cuenta=manejo_cuenta,

        cargos_objetados=cargos_objetados,

        abonos_objetados=abonos_objetados,

        saldo_anterior=saldo_anterior,

        depositos_abonos=depositos_abonos,

        retiros_cargos=retiros_cargos,

        saldo_final=saldo_final,

        saldo_promedio_minimo_mensual=saldo_promedio_minimo_mensual,

        saldo_global=saldo_global,
    )