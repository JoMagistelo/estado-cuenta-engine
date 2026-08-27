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
# A diferencia de BBVA, estas coordenadas NO se consideran
# absolutas.
#
# Se utilizan como:
#
#   1. referencia espacial;
#   2. guía para localizar el dato;
#   3. criterio de proximidad;
#   4. fallback cuando el OCR desplaza ligeramente las
#      palabras.
#
# La validación definitiva se realiza mediante texto y
# estructura del estado de cuenta.
#
# El extractor funciona con:
#
#   - PDF digital leído mediante words;
#   - PDF procesado mediante OCR;
#   - desplazamientos moderados de X/Y;
#   - palabras separadas;
#   - páginas iniciales ausentes.
#
# ============================================================


# ------------------------------------------------------------
# COORDENADAS DE REFERENCIA
# ------------------------------------------------------------
#
# Estas son las coordenadas observadas en el JSON proporcionado.
#
# Página de referencia:
#
#     página 2
#
# del documento original proporcionado.
#
# El extractor NO depende de que la página sea exactamente 2.
# ------------------------------------------------------------


# ------------------------------------------------------------
# PRODUCTO PRINCIPAL
#
# Texto observado:
#
#     CUENTA PREMIER
#
# Coordenadas aproximadas:
#
#     CUENTA   x=257..302
#     PREMIER  x=306..355
#     top      ~=25
# ------------------------------------------------------------

BOX_PRODUCTO_PRINCIPAL = (
    240.0,
    370.0,
    15.0,
    55.0,
)


# ------------------------------------------------------------
# NOMBRE DEL CLIENTE
#
# Texto observado:
#
#     JUAN ANTONIO GARCIA CARRADA
#
# Coordenadas:
#
#     x = 43..176
#     top ~= 110
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
#     NUMERO
#     DE
#     CUENTA
#
# Valor:
#
#     6270638192
#
# Coordenadas del valor:
#
#     x = 43..86
#     top ~= 227
# ------------------------------------------------------------

BOX_NUMERO_CUENTA = (
    35.0,
    150.0,
    220.0,
    245.0,
)


# ------------------------------------------------------------
# CLABE
#
# Etiqueta:
#
#     CLABE
#     INTERBANCARIA
#
# Valor observado dividido en words:
#
#     021905062706381
#     925
#
# Resultado:
#
#     021905062706381925
#
# Coordenadas:
#
#     x = 182..260
#     top ~= 227
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
#
# Coordenadas:
#
#     x = 43..77
#     top ~= 248
# ------------------------------------------------------------

BOX_NUMERO_CLIENTE = (
    35.0,
    150.0,
    235.0,
    265.0,
)


# ------------------------------------------------------------
# RFC
#
# Valor:
#
#     GACJ700226PP2
#
# Coordenadas:
#
#     x = 43..105
#     top ~= 267
# ------------------------------------------------------------

BOX_RFC = (
    35.0,
    160.0,
    250.0,
    280.0,
)


# ------------------------------------------------------------
# PERIODO
#
# Texto observado:
#
#     Periodo del 01/06/2026 al 30/06/2026
#
# Las palabras aparecen dentro de una tabla.
#
# Coordenadas aproximadas:
#
#     top ~= 277
#
# Este extractor NO depende de coordenadas exactas para este
# campo: primero identifica la línea que contiene "Periodo"
# y después valida las dos fechas.
# ------------------------------------------------------------

BOX_PERIODO = (
    350.0,
    560.0,
    265.0,
    295.0,
)


# ------------------------------------------------------------
# FECHA DE CORTE
#
# En el formato HSBC proporcionado, la fecha final del periodo
# corresponde al cierre del estado.
#
# Fallback:
#
#     fecha_corte = periodo_fin
#
# ------------------------------------------------------------


# ============================================================
# CONSTANTES DE TOLERANCIA
# ============================================================

# Tolerancia vertical para considerar palabras pertenecientes
# al mismo renglón.
LINE_Y_TOLERANCE = 5.0

# Tolerancia espacial para boxes durante OCR.
BOX_PADDING_X = 12.0
BOX_PADDING_Y = 10.0

# Distancia máxima en Y entre etiqueta y valor.
VALUE_MAX_VERTICAL_DISTANCE = 45.0

# Número máximo de páginas que se consideran al localizar
# inicialmente la zona de datos.
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


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================


def normalize_text(value: Any) -> str:
    """
    Normaliza texto para comparación semántica.

    Se eliminan:

        - acentos;
        - diferencias de mayúsculas/minúsculas;
        - espacios repetidos.

    Ejemplo:

        "Número de Cuenta"

    se convierte en:

        "NUMERO DE CUENTA"
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


def clean_word_text(value: Any) -> str:
    """
    Limpia el texto individual de una word.
    """

    if value is None:
        return ""

    return str(value).strip()


def normalized_word_text(word: Dict[str, Any]) -> str:
    """
    Devuelve el texto normalizado de una word.
    """

    return normalize_text(
        word.get("text", "")
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
        word.get("x0", 0.0)
    )

    x1 = float(
        word.get("x1", x0)
    )

    top = float(
        word.get("top", 0.0)
    )

    bottom = float(
        word.get("bottom", top)
    )

    return (
        (x0 + x1) / 2,
        (top + bottom) / 2,
    )


def word_inside_box(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding_x: float = 0.0,
    padding_y: float = 0.0,
) -> bool:
    """
    Determina si el centro de una palabra se encuentra
    dentro de una región espacial.

    A diferencia del extractor BBVA, aquí se permite
    padding para tolerar desplazamientos producidos por OCR.
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
    words: Sequence[Dict[str, Any]],
    box: Tuple[float, float, float, float],
    padding_x: float = BOX_PADDING_X,
    padding_y: float = BOX_PADDING_Y,
) -> List[Dict[str, Any]]:
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
            int(word.get("page", 1)),
            float(word.get("top", 0.0)),
            float(word.get("x0", 0.0)),
        )
    )

    return selected


def box_center(
    box: Tuple[float, float, float, float],
) -> Tuple[float, float]:
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
    words: Sequence[Dict[str, Any]],
    y_tolerance: float = LINE_Y_TOLERANCE,
) -> List[List[Dict[str, Any]]]:
    """
    Agrupa palabras que pertenecen al mismo renglón.

    Esto es especialmente importante para OCR porque el reader
    entrega palabras individuales y no oraciones.

    El algoritmo utiliza el centro Y de cada palabra y después
    ordena cada renglón de izquierda a derecha.
    """

    valid_words = [
        word
        for word in words
        if clean_word_text(
            word.get("text", "")
        )
    ]

    valid_words = sorted(
        valid_words,
        key=lambda word: (
            int(word.get("page", 1)),
            float(word.get("top", 0.0)),
            float(word.get("x0", 0.0)),
        ),
    )

    lines: List[List[Dict[str, Any]]] = []

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

            if abs(center_y - line_center_y) <= y_tolerance:

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
                float(word.get("x0", 0.0))
            )
        )

    return lines


def line_text(
    line: Sequence[Dict[str, Any]],
) -> str:
    """
    Concatena las palabras de un renglón.
    """

    values = []

    for word in line:

        text = clean_word_text(
            word.get("text", "")
        )

        if text:
            values.append(
                text
            )

    return " ".join(values).strip()


def normalized_line_text(
    line: Sequence[Dict[str, Any]],
) -> str:
    """
    Devuelve el texto normalizado de un renglón.
    """

    return normalize_text(
        line_text(line)
    )


def line_bounds(
    line: Sequence[Dict[str, Any]],
) -> Tuple[float, float, float, float]:
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
        float(word.get("x0", 0.0))
        for word in line
    )

    xmax = max(
        float(word.get("x1", 0.0))
        for word in line
    )

    ymin = min(
        float(word.get("top", 0.0))
        for word in line
    )

    ymax = max(
        float(word.get("bottom", 0.0))
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
    line: Sequence[Dict[str, Any]],
    tokens: Sequence[str],
) -> bool:
    """
    Determina si un renglón contiene todos los tokens indicados.

    Ejemplo:

        ["NUMERO", "DE", "CUENTA"]

    coincide con:

        "NUMERO DE CUENTA"
    """

    normalized = normalized_line_text(
        line
    )

    return all(
        normalize_text(token) in normalized
        for token in tokens
    )


def find_lines_containing_tokens(
    lines: Sequence[Sequence[Dict[str, Any]]],
    tokens: Sequence[str],
) -> List[List[Dict[str, Any]]]:
    """
    Busca todos los renglones que contengan un conjunto
    determinado de tokens.
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
    lines: Sequence[Sequence[Dict[str, Any]]],
    tokens: Sequence[str],
    expected_box: Optional[
        Tuple[float, float, float, float]
    ] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Busca la mejor coincidencia textual y espacial.

    Primero exige coincidencia textual.

    Después utiliza la posición esperada únicamente para
    decidir cuál coincidencia es la más probable.
    """

    candidates = find_lines_containing_tokens(
        lines,
        tokens,
    )

    if not candidates:
        return None

    if expected_box is None:
        return candidates[0]

    expected_x, expected_y = box_center(
        expected_box
    )

    best_line = None
    best_score = float("inf")

    for line in candidates:

        xmin, xmax, ymin, ymax = line_bounds(
            line
        )

        center_x = (xmin + xmax) / 2
        center_y = (ymin + ymax) / 2

        distance = (
            abs(center_x - expected_x)
            +
            abs(center_y - expected_y)
        )

        if distance < best_score:

            best_score = distance
            best_line = line

    return best_line


# ============================================================
# PÁGINA DE DATOS HSBC
# ============================================================


def page_groups(
    words: Sequence[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Agrupa words por número de página.
    """

    result: Dict[
        int,
        List[Dict[str, Any]]
    ] = {}

    for word in words:

        try:
            page = int(
                word.get("page", 1)
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
    words: Sequence[Dict[str, Any]],
) -> int:
    """
    Calcula qué tan probable es que una página sea la página
    principal de datos de cuenta HSBC.

    Se utilizan varias señales independientes.
    """

    score = 0

    lines = group_words_into_lines(
        words
    )

    normalized_lines = [
        normalized_line_text(line)
        for line in lines
    ]

    joined = " ".join(
        normalized_lines
    )

    # --------------------------------------------------------
    # Señales fuertes
    # --------------------------------------------------------

    if (
        "NUMERO DE CUENTA"
        in joined
    ):
        score += 10

    if (
        "CLABE"
        in joined
    ):
        score += 7

    if (
        "NUMERO DE CLIENTE"
        in joined
    ):
        score += 7

    if (
        re.search(
            r"\bRFC\b",
            joined,
        )
    ):
        score += 6

    if (
        "RESUMEN DE CUENTAS"
        in joined
    ):
        score += 5

    # --------------------------------------------------------
    # Señales adicionales
    # --------------------------------------------------------

    if (
        "PERIODO"
        in joined
    ):
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
    words: Sequence[Dict[str, Any]],
) -> Optional[int]:
    """
    Encuentra automáticamente la página que contiene los
    datos generales de la cuenta.

    No asume que la página 2 exista.

    Esto resuelve tanto:

        documento con hoja inicial
        documento sin hoja inicial
        documento OCR
        documento digital
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
# UTILIDADES PARA VALORES POSTERIORES A UNA ETIQUETA
# ============================================================


def line_center_y(
    line: Sequence[Dict[str, Any]],
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
    line: Sequence[Dict[str, Any]],
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


def candidate_lines_after_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
    anchor: Sequence[Dict[str, Any]],
    max_vertical_distance: float = VALUE_MAX_VERTICAL_DISTANCE,
) -> List[List[Dict[str, Any]]]:
    """
    Devuelve renglones cercanos que aparecen después de una
    etiqueta.
    """

    anchor_y = line_center_y(
        anchor
    )

    result = []

    for line in lines:

        y = line_center_y(
            line
        )

        delta_y = y - anchor_y

        if (
            0.0
            <= delta_y
            <= max_vertical_distance
        ):
            result.append(
                list(line)
            )

    result.sort(
        key=lambda line: (
            line_center_y(line)
        )
    )

    return result


def extract_candidate_words_from_lines(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> List[str]:
    """
    Extrae las palabras de varias líneas.
    """

    result = []

    for line in lines:

        for word in line:

            text = clean_word_text(
                word.get("text", "")
            )

            if text:
                result.append(
                    text
                )

    return result


# ============================================================
# EXTRACTOR DE CUENTA
# ============================================================


def extract_account_from_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    """
    Extrae número de cuenta usando:

        NUMERO DE CUENTA

    y después busca un valor numérico cercano.

    La posición esperada actúa como restricción espacial.
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

    candidates = candidate_lines_after_anchor(
        lines,
        anchor,
    )

    best_value = None
    best_distance = float("inf")

    for line in candidates:

        text = line_text(
            line
        )

        compact = re.sub(
            r"\D",
            "",
            text,
        )

        if not ACCOUNT_PATTERN.match(
            compact
        ):
            continue

        distance = abs(
            line_center_y(line)
            -
            line_center_y(anchor)
        )

        if distance < best_distance:

            best_distance = distance
            best_value = compact

    return best_value


# ============================================================
# EXTRACTOR DE CLABE
# ============================================================


def extract_clabe_from_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    """
    Extrae la CLABE a partir de la etiqueta:

        CLABE INTERBANCARIA

    La CLABE puede venir dividida en varias words.

    Ejemplo:

        021905062706381
        925

    Se concatena hasta obtener:

        021905062706381925
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

    candidates = candidate_lines_after_anchor(
        lines,
        anchor,
    )

    for line in candidates:

        parts = []

        for word in line:

            text = clean_word_text(
                word.get("text", "")
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

        candidate = "".join(
            parts
        )

        if CLABE_PATTERN.match(
            candidate
        ):
            return candidate

    # --------------------------------------------------------
    # Fallback:
    #
    # La OCR puede separar la CLABE en más de un renglón.
    # --------------------------------------------------------

    accumulated = ""

    for line in candidates:

        for word in line:

            text = clean_word_text(
                word.get("text", "")
            )

            digits = re.sub(
                r"\D",
                "",
                text,
            )

            if not digits:
                continue

            accumulated += digits

            if len(accumulated) == 18:
                return accumulated

            if len(accumulated) > 18:
                return None

    return None


# ============================================================
# EXTRACTOR DE CLIENTE
# ============================================================


def extract_numero_cliente_from_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    """
    Extrae el número de cliente desde:

        NUMERO DE CLIENTE
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

    candidates = candidate_lines_after_anchor(
        lines,
        anchor,
    )

    for line in candidates:

        value = re.sub(
            r"\D",
            "",
            line_text(line),
        )

        if CLIENT_PATTERN.match(
            value
        ):
            return value

    return None


# ============================================================
# EXTRACTOR RFC
# ============================================================


def extract_rfc_from_anchor(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    """
    Extrae RFC desde la etiqueta RFC.

    La validación evita confundir el RFC con números cercanos.
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

    candidates = candidate_lines_after_anchor(
        lines,
        anchor,
    )

    for line in candidates:

        raw = line_text(
            line
        )

        candidate = re.sub(
            r"[^A-Z0-9Ñ&]",
            "",
            raw.upper(),
        )

        if RFC_PATTERN.match(
            candidate
        ):
            return candidate

    return None


# ============================================================
# EXTRACTOR DE PERIODO
# ============================================================


def extract_dates(
    text: str,
) -> List[str]:
    """
    Extrae fechas dd/mm/yyyy o dd-mm-yyyy.
    """

    return DATE_PATTERN.findall(
        text
    )


def normalize_date(
    value: str,
) -> str:
    """
    Normaliza separador de fecha a '/'.
    """

    return value.replace(
        "-",
        "/",
    )


def extract_periodo(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Tuple[
    Optional[str],
    Optional[str],
]:
    """
    Busca la línea que representa:

        Periodo del 01/06/2026 al 30/06/2026

    No depende de coordenadas exactas.

    Primero utiliza el texto "Periodo".

    Después exige dos fechas.
    """

    candidates = []

    for line in lines:

        normalized = normalized_line_text(
            line
        )

        if "PERIODO" not in normalized:
            continue

        dates = extract_dates(
            line_text(line)
        )

        if len(dates) >= 2:

            candidates.append(
                (
                    line,
                    dates[:2],
                )
            )

    if not candidates:
        return (
            None,
            None,
        )

    # Preferimos la línea más cercana a la coordenada
    # de referencia del documento original.
    best_line = None
    best_dates = None
    best_distance = float("inf")

    expected_y = 277.0

    for line, dates in candidates:

        y = line_center_y(
            line
        )

        distance = abs(
            y - expected_y
        )

        if distance < best_distance:

            best_distance = distance
            best_line = line
            best_dates = dates

    if best_line is None or best_dates is None:
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
# EXTRACTOR DEL PRODUCTO
# ============================================================


def extract_producto_principal(
    words: Sequence[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el producto principal.

    En el formato proporcionado, la información aparece como:

        CUENTA PREMIER

    Se busca primero por texto y posteriormente se utiliza la
    coordenada como criterio de preferencia.
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
            "CUENTA" in normalized
            and
            "PREMIER" in normalized
        ):
            candidates.append(
                line
            )

    if candidates:

        expected_x, expected_y = box_center(
            BOX_PRODUCTO_PRINCIPAL
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

        # ----------------------------------------------------
        # Nos interesa el nombre del producto y no el resto
        # del encabezado.
        # ----------------------------------------------------

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
    # Fallback espacial
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
        "CUENTA" in normalized
        and
        "PREMIER" in normalized
    ):
        return "Cuenta Premier"

    return None


# ============================================================
# EXTRACTOR NOMBRE DEL CLIENTE
# ============================================================


def is_probable_person_name(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Determina si un renglón parece corresponder a un nombre
    de cliente.

    Se evitan textos comerciales y etiquetas.
    """

    text = line_text(
        line
    )

    normalized = normalize_text(
        text
    )

    if not text:
        return False

    # --------------------------------------------------------
    # El nombre debe contener únicamente contenido textual
    # razonable.
    # --------------------------------------------------------

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
    words: Sequence[Dict[str, Any]],
) -> Optional[str]:
    """
    Extrae el nombre del cliente.

    En el documento proporcionado aparece aproximadamente:

        JUAN ANTONIO GARCIA CARRADA

    El extractor usa:

        1. coordenada esperada;
        2. agrupación en renglón;
        3. validación textual;
        4. descarte de encabezados comerciales.
    """

    lines = group_words_into_lines(
        words
    )

    candidate_lines = [
        list(line)
        for line in lines
        if word_inside_box(
            {
                "x0": (
                    line_bounds(line)[0]
                ),
                "x1": (
                    line_bounds(line)[1]
                ),
                "top": (
                    line_bounds(line)[2]
                ),
                "bottom": (
                    line_bounds(line)[3]
                ),
                "page": (
                    line[0].get(
                        "page",
                        1,
                    )
                    if line
                    else 1
                ),
            },
            BOX_NOMBRE_CLIENTE,
            padding_x=25.0,
            padding_y=20.0,
        )
    ]

    candidates = [
        line
        for line in candidate_lines
        if is_probable_person_name(line)
    ]

    if candidates:

        expected_x, expected_y = box_center(
            BOX_NOMBRE_CLIENTE
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
    # Fallback:
    #
    # buscar palabras dentro de la región y reconstruirlas.
    # --------------------------------------------------------

    selected = words_in_box(
        words,
        BOX_NOMBRE_CLIENTE,
        padding_x=30.0,
        padding_y=25.0,
    )

    if not selected:
        return None

    selected_lines = group_words_into_lines(
        selected
    )

    for line in selected_lines:

        if is_probable_person_name(
            line
        ):
            return line_text(
                line
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
    Valida CLABE mexicana.

    Por ahora la validación estructural se limita a:

        exactamente 18 dígitos.

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
    Valida formato dd/mm/yyyy.
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
    words: List[Dict[str, Any]],
) -> DatosCuenta:
    """
    Extractor robusto de datos generales de cuenta HSBC.

    El extractor utiliza una estrategia híbrida:

        TEXTO
            +
        COORDENADAS
            +
        ESTRUCTURA DEL DOCUMENTO

    Los campos extraídos son:

        - producto_principal
        - periodo_inicio
        - periodo_fin
        - fecha_corte
        - numero_cuenta
        - numero_cliente
        - rfc
        - clabe
        - nombre_cliente

    ========================================================
    FLUJO
    ========================================================

    1. Se agrupan las words por página.

    2. Se identifica automáticamente la página con mayor
       evidencia de ser la página de datos.

    3. Se reconstruyen renglones a partir de las words.

    4. Las etiquetas localizan la información:

           NUMERO DE CUENTA
           CLABE
           NUMERO DE CLIENTE
           RFC
           PERIODO

    5. Las coordenadas ayudan a seleccionar la coincidencia
       correcta cuando una palabra o etiqueta aparece varias
       veces.

    6. Los valores se validan por formato.

    7. Si la hoja inicial no existe, el algoritmo continúa
       funcionando porque no depende del número absoluto
       de página.

    ========================================================
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

    # --------------------------------------------------------
    # Si no encontramos una página claramente identificable,
    # utilizamos todas las words como fallback.
    # --------------------------------------------------------

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
    # 2. RECONSTRUIR RENGLONES
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
    # 4. NOMBRE DEL CLIENTE
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
            lines
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
            lines
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
            lines
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
    # En el layout HSBC proporcionado, el periodo es:
    #
    #     Periodo del 01/06/2026 al 30/06/2026
    #
    # Por lo tanto el cierre corresponde a la fecha final.
    #
    # Si posteriormente encontramos otro layout HSBC que
    # contenga una etiqueta específica "Fecha de corte", esta
    # función puede ampliarse sin modificar el resto del
    # extractor.
    # ========================================================

    fecha_corte = periodo_fin

    # ========================================================
    # 11. DEVOLVER MODELO
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
