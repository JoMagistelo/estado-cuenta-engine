from __future__ import annotations

import re
from math import hypot
from typing import Any, Dict, List, Optional

from models.resumen_financiero import ResumenFinanciero


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
#
# Este extractor trabaja EXCLUSIVAMENTE mediante coordenadas
# espaciales.
#
# NO depende de que las palabras vengan agrupadas.
#
# Cada elemento obtenido por pdfplumber representa una palabra
# independiente con sus propias coordenadas:
#
#     {
#         "text": "...",
#         "x0": ...,
#         "x1": ...,
#         "top": ...,
#         "bottom": ...,
#         "page": ...
#     }
#
# Por lo tanto, las cajas se definen alrededor de la CELDA
# donde vive el valor y no alrededor de una frase completa.
#
# La estructura está diseñada para tolerar:
#
#   - pequeños desplazamientos verticales
#   - pequeños desplazamientos horizontales
#   - cambios ligeros de espaciado
#   - cambios ligeros en el ancho de las palabras
#   - diferencias pequeñas entre estados
#
# Los campos que no fueron observados en las coordenadas
# suministradas se retornan como "N/A".
#
# ============================================================


PAGE_GENERAL = 1

NA_VALUE = "N/A"


# ============================================================
# TOLERANCIAS ESPACIALES
# ============================================================
#
# Las coordenadas proporcionadas corresponden a un documento
# concreto.
#
# No queremos depender de coincidencias exactas.
#
# Por eso las cajas se expanden mediante estas tolerancias.
#
# Una modificación pequeña del PDF no debería romper el
# extractor.
#
# ============================================================

TOLERANCE_X = 6.0
TOLERANCE_Y = 4.0


# ============================================================
# CAJAS ESPACIALES
# ============================================================
#
# Todas las coordenadas provienen del estado de cuenta
# proporcionado.
#
# La caja NO intenta representar únicamente la palabra.
#
# Representa la región/celda donde vive el valor.
#
# ============================================================


# ------------------------------------------------------------
# SALDO ANTERIOR
# ------------------------------------------------------------
#
# Valor observado:
#
#     $65.68
#
# Coordenadas observadas:
#
#     x0 = 289.500
#     x1 = 317.022
#     top = 481.563
#     bottom = 490.563
#
# ------------------------------------------------------------

BOX_SALDO_ANTERIOR = (
    260.0,   # x0
    335.0,   # x1
    476.0,   # top
    497.0,   # bottom
)


# ------------------------------------------------------------
# DEPÓSITOS / ABONOS
# ------------------------------------------------------------
#
# Valor observado:
#
#     $61,105.00
#
# Coordenadas:
#
#     x0 = 270.000
#     x1 = 315.036
#     top = 492.963
#     bottom = 501.963
#
# ------------------------------------------------------------

BOX_DEPOSITOS_ABONOS = (
    250.0,   # x0
    335.0,   # x1
    487.0,   # top
    506.0,   # bottom
)


# ------------------------------------------------------------
# RETIROS / CARGOS
# ------------------------------------------------------------
#
# Valor observado:
#
#     $59,970.68
#
# Coordenadas:
#
#     x0 = 270.000
#     x1 = 315.036
#     top = 504.363
#     bottom = 513.363
#
# ------------------------------------------------------------

BOX_RETIROS_CARGOS = (
    250.0,   # x0
    335.0,   # x1
    498.0,   # top
    519.0,   # bottom
)


# ------------------------------------------------------------
# SALDO FINAL
# ------------------------------------------------------------
#
# Valor observado:
#
#     $1,200.00
#
# Coordenadas:
#
#     x0 = 275.700
#     x1 = 324.628
#     top = 515.677
#     bottom = 526.677
#
# ------------------------------------------------------------

BOX_SALDO_FINAL = (
    255.0,   # x0
    340.0,   # x1
    509.0,   # top
    534.0,   # bottom
)


# ------------------------------------------------------------
# SALDO PROMEDIO
# ------------------------------------------------------------
#
# Valor observado:
#
#     $1,676.00
#
# Coordenadas:
#
#     x0 = 191.400
#     x1 = 231.432
#     top = 541.263
#     bottom = 550.263
#
# ------------------------------------------------------------

BOX_SALDO_PROMEDIO = (
    175.0,   # x0
    250.0,   # x1
    535.0,   # top
    560.0,   # bottom
)


# ------------------------------------------------------------
# DÍAS DEL PERIODO
# ------------------------------------------------------------
#
# Valor observado:
#
#     31
#
# Coordenadas:
#
#     x0 = 224.700
#     x1 = 234.708
#     top = 552.663
#     bottom = 561.663
#
# ------------------------------------------------------------

BOX_DIAS_PERIODO = (
    205.0,   # x0
    250.0,   # x1
    546.0,   # top
    568.0,   # bottom
)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================


def _expand_box(
    box: tuple[float, float, float, float],
    tolerance_x: float = TOLERANCE_X,
    tolerance_y: float = TOLERANCE_Y,
) -> tuple[float, float, float, float]:
    """
    Expande ligeramente una caja espacial.

    Esto permite tolerar pequeños cambios de coordenadas entre
    estados de cuenta sin tener que modificar inmediatamente
    cada caja.
    """

    xmin, xmax, ymin, ymax = box

    return (
        xmin - tolerance_x,
        xmax + tolerance_x,
        ymin - tolerance_y,
        ymax + tolerance_y,
    )


def word_inside_box(
    word: Dict[str, Any],
    box: tuple[float, float, float, float],
    page_number: int,
) -> bool:
    """
    Determina si una palabra pertenece a una región espacial.

    Se utiliza el CENTRO de la palabra, no solamente x0/x1.

    Esto es importante porque las palabras son elementos
    independientes y pueden desplazarse ligeramente dentro
    de su celda.
    """

    page = word.get("page", 1)

    if page != page_number:
        return False

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)

    top = word.get("top", 0)
    bottom = word.get("bottom", 0)

    xmin, xmax, ymin, ymax = _expand_box(box)

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return (
        xmin <= center_x <= xmax
        and ymin <= center_y <= ymax
    )


def words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int = PAGE_GENERAL,
) -> List[Dict[str, Any]]:
    """
    Devuelve todas las palabras pertenecientes a una región.

    Las palabras se ordenan por:

        1. posición vertical
        2. posición horizontal
    """

    result = [
        word
        for word in words
        if word_inside_box(
            word=word,
            box=box,
            page_number=page_number,
        )
    ]

    result.sort(
        key=lambda word: (
            word.get("top", 0),
            word.get("x0", 0),
        )
    )

    return result


def _parse_amount(value: Optional[str]) -> Optional[float]:
    """
    Convierte un texto numérico (posiblemente con comas y
    símbolo de moneda) a float.

    Devuelve None si el valor es None, vacío, o no puede
    convertirse.
    """

    if value is None or value == NA_VALUE:
        return None

    cleaned_value = (
        value.replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(cleaned_value)
    except (ValueError, TypeError):
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    """
    Convierte un texto numérico a int.

    Devuelve None si el valor es None, vacío, o no puede
    convertirse.
    """

    if value is None or value == NA_VALUE:
        return None

    cleaned_value = (
        value.strip()
    )

    try:
        # Se convierte a float primero para manejar "31.0"
        return int(float(cleaned_value))
    except (ValueError, TypeError):
        return None


# ============================================================
# UTILIDADES DE TEXTO / NÚMEROS
# ============================================================


_MONEY_PATTERN = re.compile(
    r"""
    ^

    # signo opcional
    [-+]?

    # símbolo monetario opcional
    \$?

    # número
    \d{1,3}

    # grupos opcionales de miles
    (?:,\d{3})*

    # decimales opcionales
    (?:\.\d{2})?

    $

    """,
    re.VERBOSE,
)


def is_money_text(text: str) -> bool:
    """
    Determina si un fragmento de texto representa una cantidad
    monetaria.

    Ejemplos válidos:

        $65.68
        $61,105.00
        $59,970.68
        $1,200.00
        $1,676.00
    """

    if not text:
        return False

    value = text.strip()

    return bool(_MONEY_PATTERN.fullmatch(value))


def is_integer_text(text: str) -> bool:
    """
    Determina si el texto es un entero simple.
    """

    if not text:
        return False

    return bool(re.fullmatch(r"\d{1,3}", text.strip()))


def _candidate_distance(
    word: Dict[str, Any],
    target_x: float,
    target_y: float,
) -> float:
    """
    Calcula la distancia entre el centro de una palabra y un
    punto esperado.

    Se utiliza para elegir el candidato más cercano cuando una
    región contiene más de una palabra válida.
    """

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)

    top = word.get("top", 0)
    bottom = word.get("bottom", 0)

    center_x = (x0 + x1) / 2
    center_y = (top + bottom) / 2

    return hypot(
        center_x - target_x,
        center_y - target_y,
    )


def _box_center(
    box: tuple[float, float, float, float],
) -> tuple[float, float]:
    """
    Obtiene el centro geométrico de una caja.
    """

    xmin, xmax, ymin, ymax = box

    return (
        (xmin + xmax) / 2,
        (ymin + ymax) / 2,
    )


def extract_value_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    validator,
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """
    Extrae el candidato válido más cercano al centro esperado
    de una caja.

    Esto hace que el extractor no dependa de que exista
    exactamente una palabra en una coordenada fija.

    Si existen varias palabras válidas dentro de la región,
    se selecciona la más cercana al centro de la celda.
    """

    selected = words_in_box(
        words=words,
        box=box,
        page_number=page_number,
    )

    candidates: List[Dict[str, Any]] = []

    for word in selected:

        text = str(
            word.get("text", "")
        ).strip()

        if not text:
            continue

        if validator(text):
            candidates.append(word)

    if not candidates:
        return None

    target_x, target_y = _box_center(box)

    candidates.sort(
        key=lambda word: _candidate_distance(
            word=word,
            target_x=target_x,
            target_y=target_y,
        )
    )

    value = str(
        candidates[0].get("text", "")
    ).strip()

    return value or None


def extract_money_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """
    Extrae una cantidad monetaria de una región.
    """

    return extract_value_from_box(
        words=words,
        box=box,
        validator=is_money_text,
        page_number=page_number,
    )


def extract_integer_from_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
    page_number: int = PAGE_GENERAL,
) -> Optional[str]:
    """
    Extrae un entero de una región.
    """

    return extract_value_from_box(
        words=words,
        box=box,
        validator=is_integer_text,
        page_number=page_number,
    )


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_saldo_promedio(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae:

        Saldo Promedio

    Valor observado:

        $1,676.00
    """

    value = extract_money_from_box(
        words=words,
        box=BOX_SALDO_PROMEDIO,
        page_number=PAGE_GENERAL,
    )

    return _parse_amount(value)


def extract_dias_periodo(
    words: List[Dict[str, Any]],
) -> Optional[int]:
    """
    Extrae:

        Días Transcurridos

    Valor observado:

        31
    """

    value = extract_integer_from_box(
        words=words,
        box=BOX_DIAS_PERIODO,
        page_number=PAGE_GENERAL,
    )

    return _parse_int(value)


def extract_saldo_anterior(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae:

        Saldo Anterior

    Valor observado:

        $65.68
    """

    value = extract_money_from_box(
        words=words,
        box=BOX_SALDO_ANTERIOR,
        page_number=PAGE_GENERAL,
    )

    return _parse_amount(value)


def extract_depositos_abonos(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae:

        Depósitos

    Valor observado:

        $61,105.00
    """

    value = extract_money_from_box(
        words=words,
        box=BOX_DEPOSITOS_ABONOS,
        page_number=PAGE_GENERAL,
    )

    return _parse_amount(value)


def extract_retiros_cargos(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae:

        Retiros

    Valor observado:

        $59,970.68
    """

    value = extract_money_from_box(
        words=words,
        box=BOX_RETIROS_CARGOS,
        page_number=PAGE_GENERAL,
    )

    return _parse_amount(value)


def extract_saldo_final(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Extrae:

        Saldo al 06 de febrero de 2026

    Valor observado:

        $1,200.00
    """

    value = extract_money_from_box(
        words=words,
        box=BOX_SALDO_FINAL,
        page_number=PAGE_GENERAL,
    )

    return _parse_amount(value)


# ============================================================
# CAMPOS NO DISPONIBLES EN LAS COORDENADAS PROPORCIONADAS
# ============================================================
#
# Estos campos forman parte del modelo ResumenFinanciero, pero
# no aparecen en las coordenadas suministradas.
#
# Por indicación expresa:
#
#     -> se retorna N/A
#
# NO se intenta inferirlos.
#
# ============================================================


def extract_tasa_bruta_anual(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Tasa Bruta Anual no fue
    proporcionada.
    """

    return None


def extract_saldo_promedio_gravable(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Saldo Promedio Gravable no
    fue proporcionada.
    """

    return None


def extract_intereses_a_favor(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Intereses a Favor no fue
    proporcionada.
    """

    return None


def extract_isr_retenido(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a ISR Retenido no fue
    proporcionada.
    """

    return None


def extract_cheques_pagados(
    words: List[Dict[str, Any]],
) -> Optional[int]:
    """
    La coordenada correspondiente a Cheques Pagados no fue
    proporcionada.
    """

    return None


def extract_manejo_cuenta(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Manejo de Cuenta no fue
    proporcionada.
    """

    return None


def extract_cargos_objetados(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Cargos Objetados no fue
    proporcionada.
    """

    return None


def extract_abonos_objetados(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Abonos Objetados no fue
    proporcionada.
    """

    return None


def extract_saldo_promedio_minimo_mensual(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Saldo Promedio Mínimo
    Mensual no fue proporcionada.
    """

    return None


def extract_saldo_global(
    words: List[Dict[str, Any]],
) -> Optional[float]:
    """
    La coordenada correspondiente a Saldo Global no fue
    proporcionada.
    """

    return None


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_resumen_financiero_words(
    words: List[Dict[str, Any]],
) -> ResumenFinanciero:
    """
    Extractor espacial del RESUMEN FINANCIERO BANAMEX.

    El extractor utiliza exclusivamente coordenadas
    espaciales.

    No depende de que las palabras de una etiqueta estén
    agrupadas.

    Ejemplo:

        "Saldo Anterior"

    llega como:

        "Saldo"
        "Anterior"

    en dos objetos independientes.

    Lo mismo sucede con:

        "Días Transcurridos"

    y cualquier otro texto del PDF.

    Campos actualmente disponibles mediante las coordenadas
    proporcionadas:

        - saldo_promedio
        - dias_periodo
        - saldo_anterior
        - depositos_abonos
        - retiros_cargos
        - saldo_final

    Campos sin coordenadas proporcionadas:

        - tasa_bruta_anual
        - saldo_promedio_gravable
        - intereses_a_favor
        - isr_retenido
        - cheques_pagados
        - manejo_cuenta
        - cargos_objetados
        - abonos_objetados
        - saldo_promedio_minimo_mensual
        - saldo_global
    
    Estos últimos retornan None.
    """

    # --------------------------------------------------------
    # CAMPOS OBSERVADOS
    # --------------------------------------------------------

    saldo_promedio = extract_saldo_promedio(
        words
    )

    dias_periodo = extract_dias_periodo(
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

    # --------------------------------------------------------
    # CAMPOS NO OBSERVADOS
    # --------------------------------------------------------

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

    saldo_promedio_minimo_mensual = (
        extract_saldo_promedio_minimo_mensual(
            words
        )
    )

    saldo_global = extract_saldo_global(
        words
    )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

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