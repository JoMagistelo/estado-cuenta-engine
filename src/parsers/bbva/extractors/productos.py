# parsers/bbva/extractors/otros_productos_words.py

from typing import List, Dict, Any, Optional

from models.otros_productos import OtrosProductos


# ============================================================
# REFERENCIAS DE LAYOUT
# ============================================================

# Caso NORMAL:
# La fila de "Otros Productos" (con "N/A") aparece en este top.
OTROS_PRODUCTOS_NORMAL_TOP = 419.622538

# Caso PREMIUM:
# La fila de "Otros Productos" (con "N/A") aparece en este top.
OTROS_PRODUCTOS_PREMIUM_TOP = 367.877793

# El delta es aprox. -51.74


# ============================================================
# CONFIGURACIÓN ESPACIAL — OTROS PRODUCTOS BBVA
# ============================================================

# Valores observados directamente en el PDF BBVA.
#
# Contrato:
# x ≈ 325
#
# Producto:
# x ≈ 371
#
# Tasa de interés anual:
# x ≈ 414
#
# GAT nominal:
# x ≈ 461
#
# GAT real:
# x ≈ 507
#
# Total de comisiones:
# x ≈ 558
#
# Los valores aparecen aproximadamente en:
# top ≈ 419.62
# bottom ≈ 429.62
#
# En el estado de cuenta proporcionado:
#
# N/A | N/A | N/A | N/A | N/A | N/A
#
# IMPORTANTE:
# Se conserva literalmente el valor mostrado en el PDF.
# Por lo tanto, "N/A" NO se convierte a None.


BOX_CONTRATO = (
    307.0,
    356.0,
    416.0,
    433.0,
)


BOX_PRODUCTO = (
    356.0,
    402.0,
    416.0,
    433.0,
)


BOX_TASA_INTERES_ANUAL = (
    402.0,
    445.0,
    416.0,
    433.0,
)


BOX_GAT_NOMINAL_ANUAL = (
    445.0,
    495.0,
    416.0,
    433.0,
)


BOX_GAT_REAL_ANUAL = (
    495.0,
    532.0,
    416.0,
    433.0,
)


BOX_TOTAL_COMISIONES = (
    532.0,
    590.0,
    416.0,
    433.0,
)


# ============================================================
# UTILIDADES ESPACIALES
# ============================================================

def get_delta_y(
    words: List[Dict[str, Any]],
) -> float:
    """
    Detecta si el documento utiliza el layout normal
    o el layout premium para la sección "Otros Productos"
    y devuelve el desplazamiento vertical.

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

        # Usamos "N/A" como ancla, ya que es el valor presente
        # en los ejemplos para esta sección.
        text = word.get("text", "").strip()
        if text != "N/A":
            continue

        top = word.get("top")
        if top is None:
            continue

        if abs(top - OTROS_PRODUCTOS_NORMAL_TOP) <= 2.0:
            found_normal = True
            break

        if abs(top - OTROS_PRODUCTOS_PREMIUM_TOP) <= 2.0:
            found_premium = True

    if found_normal:
        return 0.0

    if found_premium:
        return (
            OTROS_PRODUCTOS_PREMIUM_TOP
            - OTROS_PRODUCTOS_NORMAL_TOP
        )

    # Por defecto, asumimos el layout normal.
    return 0.0

def word_inside_box(
    word: Dict[str, Any],
    box: tuple[float, float, float, float],
) -> bool:
    """
    Determina si el centro de una palabra se encuentra
    dentro de una región espacial.
    """

    # La sección observada corresponde a la página 1.
    if word.get("page", 1) != 1:
        return False

    x0 = word.get("x0", 0)
    x1 = word.get("x1", 0)

    top = word.get("top", 0)
    bottom = word.get("bottom", 0)

    box_xmin, box_xmax, box_ymin, box_ymax = box

    word_center_x = (x0 + x1) / 2
    word_center_y = (top + bottom) / 2

    return (
        box_xmin <= word_center_x <= box_xmax
        and
        box_ymin <= word_center_y <= box_ymax
    )


def words_in_box(
    words: List[Dict[str, Any]],
    box: tuple[float, float, float, float],
) -> List[Dict[str, Any]]:
    """
    Devuelve las palabras que pertenecen a la caja,
    aplicando el desplazamiento vertical correspondiente
    al layout detectado.
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
    Extrae literalmente el texto encontrado dentro de
    una caja espacial.

    No transforma N/A en None.
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


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_contrato(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente el contrato.
    """

    return text_from_box(
        words,
        BOX_CONTRATO,
    )


def extract_producto(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente el producto.
    """

    return text_from_box(
        words,
        BOX_PRODUCTO,
    )


def extract_tasa_interes_anual(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente la tasa de interés anual.

    Ejemplo:
        N/A -> "N/A"
    """

    return text_from_box(
        words,
        BOX_TASA_INTERES_ANUAL,
    )


def extract_gat_nominal_anual(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente el GAT nominal anual.
    """

    return text_from_box(
        words,
        BOX_GAT_NOMINAL_ANUAL,
    )


def extract_gat_real_anual(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente el GAT real anual.
    """

    return text_from_box(
        words,
        BOX_GAT_REAL_ANUAL,
    )


def extract_total_comisiones(
    words: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae literalmente el total de comisiones.
    """

    return text_from_box(
        words,
        BOX_TOTAL_COMISIONES,
    )


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_otros_productos_words(
    words: List[Dict[str, Any]],
) -> OtrosProductos:
    """
    Extractor espacial de Otros Productos BBVA.

    La extracción se realiza exclusivamente mediante
    coordenadas espaciales.

    Los valores se conservan literalmente como aparecen
    en el estado de cuenta.

    Ejemplo:

        N/A

    permanece como:

        "N/A"

    Campos:

        - contrato
        - producto
        - tasa_interes_anual
        - gat_nominal_anual
        - gat_real_anual
        - total_comisiones
    """

    contrato = extract_contrato(
        words
    )

    producto = extract_producto(
        words
    )

    tasa_interes_anual = extract_tasa_interes_anual(
        words
    )

    gat_nominal_anual = extract_gat_nominal_anual(
        words
    )

    gat_real_anual = extract_gat_real_anual(
        words
    )

    total_comisiones = extract_total_comisiones(
        words
    )

    return OtrosProductos(
        contrato=contrato,
        producto=producto,
        tasa_interes_anual=tasa_interes_anual,
        gat_nominal_anual=gat_nominal_anual,
        gat_real_anual=gat_real_anual,
        total_comisiones=total_comisiones,
    )