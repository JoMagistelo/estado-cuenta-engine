from __future__ import annotations

import re
import unicodedata

from typing import List, Dict, Any, Optional


from models.otros_productos import OtrosProductos


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
#
# BANAMEX
#
# Actualmente no se dispone de un layout espacial definido
# para la sección de Otros Productos / Productos Financieros.
#
# Mientras no exista una definición espacial específica para
# Banamex, todos los campos se conservan como:
#
#     "N/A"
#
# IMPORTANTE:
#
# Se mantienen las funciones individuales de extracción
# preparadas para que posteriormente puedan sustituirse
# por extracción mediante coordenadas sin modificar la
# función pública ni el modelo de datos.
#
# ============================================================


NA_VALUE = "N/A"


# ============================================================
# TIPO DE DATOS DE ENTRADA
# ============================================================

SpatialWord = Dict[str, Any]


# ============================================================
# UTILIDAD GENERAL
# ============================================================


def na_value() -> str:
    """
    Devuelve el valor por defecto utilizado por Banamex.

    Actualmente todos los campos de Otros Productos se
    representan como "N/A".
    """

    return NA_VALUE



# ============================================================
# FORTALECIMIENTO — PRODUCTO SECUNDARIO CUENTA PRIORITY
# ============================================================


PRODUCT_LINE_Y_TOLERANCE = 4.0


def normalize_product_text(value: Any) -> str:
    normalized = unicodedata.normalize(
        "NFD",
        str(value or ""),
    )
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    normalized = normalized.upper()
    normalized = re.sub(r"[^A-Z0-9%.-]+", " ", normalized)
    return " ".join(normalized.split())


def _word_center_y(word: SpatialWord) -> float:
    top = float(word.get("top", 0) or 0)
    bottom = float(word.get("bottom", top) or top)
    return (top + bottom) / 2.0


def _group_product_lines(
    words: List[SpatialWord],
) -> List[List[SpatialWord]]:
    ordered = sorted(
        words,
        key=lambda word: (
            int(word.get("page", 1) or 1),
            _word_center_y(word),
            float(word.get("x0", 0) or 0),
        ),
    )

    lines: List[List[SpatialWord]] = []
    current: List[SpatialWord] = []
    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:
        page = int(word.get("page", 1) or 1)
        center_y = _word_center_y(word)

        if (
            current_y is None
            or page != current_page
            or abs(center_y - current_y)
            > PRODUCT_LINE_Y_TOLERANCE
        ):
            if current:
                current.sort(
                    key=lambda item: float(
                        item.get("x0", 0) or 0
                    )
                )
                lines.append(current)

            current = [word]
            current_page = page
            current_y = center_y
            continue

        current.append(word)
        current_y = sum(
            _word_center_y(item)
            for item in current
        ) / len(current)

    if current:
        current.sort(
            key=lambda item: float(item.get("x0", 0) or 0)
        )
        lines.append(current)

    return lines


def _product_line_text(
    line: List[SpatialWord],
) -> str:
    return normalize_product_text(
        " ".join(
            str(word.get("text", "")).strip()
            for word in line
            if str(word.get("text", "")).strip()
        )
    )


def _priority_product_page(
    words: List[SpatialWord],
) -> Optional[int]:
    """
    Localiza la primera línea cuyo contenido completo es
    ``AHORRO FACIL``.

    La igualdad exacta evita confundir el producto real con las
    menciones promocionales de Ahorro Fácil de la página 1.
    """

    for line in _group_product_lines(words):
        if not line:
            continue

        if _product_line_text(line) == "AHORRO FACIL":
            page = int(line[0].get("page", 1) or 1)

            if page > 1:
                return page

    return None


def _line_on_product_page(
    words: List[SpatialWord],
    required_tokens: tuple[str, ...],
) -> Optional[List[SpatialWord]]:
    product_page = _priority_product_page(words)

    if product_page is None:
        return None

    required = {
        normalize_product_text(token)
        for token in required_tokens
    }

    for line in _group_product_lines(words):
        if not line:
            continue

        if int(line[0].get("page", 1) or 1) != product_page:
            continue

        tokens = set(_product_line_text(line).split())

        if required.issubset(tokens):
            return line

    return None


def _rightmost_matching_text(
    line: Optional[List[SpatialWord]],
    pattern: re.Pattern[str],
) -> Optional[str]:
    if not line:
        return None

    candidates = [
        str(word.get("text", "")).strip()
        for word in line
        if pattern.fullmatch(
            str(word.get("text", "")).strip()
        )
    ]

    if not candidates:
        return None

    return candidates[-1]


_PERCENT_PATTERN = re.compile(r"[+-]?\d+(?:\.\d+)?%")
_CONTRACT_PATTERN = re.compile(r"\d{8,12}")


# ============================================================
# EXTRACTORES INDIVIDUALES
# ============================================================


def extract_contrato(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el contrato del producto financiero.

    Actualmente Banamex no utiliza extracción espacial para
    esta sección, por lo que devuelve "N/A".

    La función queda preparada para reemplazarse posteriormente
    por una extracción basada en coordenadas.
    """

    line = _line_on_product_page(
        words,
        ("CONTRATO",),
    )
    value = _rightmost_matching_text(
        line,
        _CONTRACT_PATTERN,
    )

    return value if value is not None else na_value()


def extract_producto(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el nombre del producto financiero.

    Actualmente devuelve "N/A".

    Posteriormente puede reemplazarse por extracción espacial
    sin modificar la interfaz pública del extractor.
    """

    if _priority_product_page(words) is not None:
        return "AHORRO FACIL"

    return na_value()


def extract_tasa_interes_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae la tasa de interés anual.

    Actualmente devuelve "N/A".
    """

    line = _line_on_product_page(
        words,
        ("TASA", "DE", "INTERES", "NETA"),
    )

    if line:
        annual_candidates = [
            str(word.get("text", "")).strip()
            for word in line
            if (
                float(word.get("x0", 0) or 0) >= 240.0
                and _PERCENT_PATTERN.fullmatch(
                    str(word.get("text", "")).strip()
                )
            )
        ]

        if annual_candidates:
            return annual_candidates[-1]

    return na_value()


def extract_gat_nominal_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el GAT nominal anual.

    Actualmente devuelve "N/A".
    """

    line = _line_on_product_page(
        words,
        ("GAT", "NOMINAL"),
    )
    value = _rightmost_matching_text(
        line,
        _PERCENT_PATTERN,
    )

    return value if value is not None else na_value()


def extract_gat_real_anual(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el GAT real anual.

    Actualmente devuelve "N/A".
    """

    line = _line_on_product_page(
        words,
        ("GAT", "REAL"),
    )
    value = _rightmost_matching_text(
        line,
        _PERCENT_PATTERN,
    )

    return value if value is not None else na_value()


def extract_total_comisiones(
    words: List[SpatialWord],
) -> Optional[str]:
    """
    Extrae el total de comisiones.

    Actualmente devuelve "N/A".
    """

    line = _line_on_product_page(
        words,
        ("COMISIONES", "EFECTIVAMENTE", "COBRADAS"),
    )

    if line:
        text = _product_line_text(line)

        if "NO APLICA" in text:
            return "No Aplica"

        # Conserva literalmente cualquier valor monetario que
        # llegue a declararse en este mismo renglón.
        for word in reversed(line):
            value = str(word.get("text", "")).strip()

            if value and normalize_product_text(value) not in {
                "COMISIONES",
                "EFECTIVAMENTE",
                "COBRADAS",
            }:
                return value

    return na_value()


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================


def extract_otros_productos_words(
    words: List[SpatialWord],
) -> OtrosProductos:
    """
    Extractor de Otros Productos para Banamex.

    Actualmente Banamex no tiene implementada una extracción
    espacial específica para esta sección.

    Por ello todos los campos se devuelven literalmente como:

        "N/A"

    La estructura queda preparada para implementar
    posteriormente coordenadas específicas de Banamex.

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

    tasa_interes_anual = (
        extract_tasa_interes_anual(
            words
        )
    )

    gat_nominal_anual = (
        extract_gat_nominal_anual(
            words
        )
    )

    gat_real_anual = (
        extract_gat_real_anual(
            words
        )
    )

    total_comisiones = (
        extract_total_comisiones(
            words
        )
    )

    return OtrosProductos(
        contrato=contrato,
        producto=producto,
        tasa_interes_anual=tasa_interes_anual,
        gat_nominal_anual=gat_nominal_anual,
        gat_real_anual=gat_real_anual,
        total_comisiones=total_comisiones,
    )