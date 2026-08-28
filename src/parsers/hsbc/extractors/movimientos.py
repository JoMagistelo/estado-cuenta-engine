from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.movimiento import Movimiento
from parsers.hsbc.utils.words_footer_filter import filter_hsbc_footer_words


# ============================================================
# CONFIGURACIÓN ESPACIAL — MOVIMIENTOS HSBC
# ============================================================

BOX_DAY = (35.0, 60.0, 0.0, 900.0)
BOX_CONCEPTO = (55.0, 278.0, 0.0, 900.0)
BOX_REFERENCIA_SERIAL = (280.0, 345.0, 0.0, 900.0)

# Compatibilidad semántica con código existente/futuro.
BOX_SERIAL = (290.0, 345.0, 0.0, 900.0)
BOX_REFERENCIA = (280.0, 345.0, 0.0, 900.0)

BOX_CARGO = (345.0, 415.0, 0.0, 900.0)
BOX_ABONO = (420.0, 505.0, 0.0, 900.0)
BOX_SALDO = (515.0, 575.0, 0.0, 900.0)

MOVEMENT_DATA_COLUMNS: Tuple[
    Tuple[str, Tuple[float, float, float, float]],
    ...,
] = (
    ("dia", BOX_DAY),
    ("concepto", BOX_CONCEPTO),
    ("referencia_serial", BOX_REFERENCIA_SERIAL),
    ("cargo", BOX_CARGO),
    ("abono", BOX_ABONO),
    ("saldo", BOX_SALDO),
)


# ============================================================
# CONFIGURACIÓN ESPACIAL — TABLAS SPEI
# ============================================================

BOX_SPEI_FECHA = (35.0, 80.0, 0.0, 900.0)
BOX_SPEI_HORA = (80.0, 120.0, 0.0, 900.0)
BOX_SPEI_PARTICIPANTE = (120.0, 188.0, 0.0, 900.0)
BOX_SPEI_BENEFICIARIO = (188.0, 246.0, 0.0, 900.0)
BOX_SPEI_CUENTA_BENEFICIARIA = (245.0, 337.0, 0.0, 900.0)
BOX_SPEI_CONCEPTO = (337.0, 395.0, 0.0, 900.0)
BOX_SPEI_MONTO = (395.0, 465.0, 0.0, 900.0)
BOX_SPEI_CLAVE_RASTREO = (465.0, 514.0, 0.0, 900.0)
BOX_SPEI_NUMERO_REFERENCIA = (514.0, 575.0, 0.0, 900.0)

SPEI_DATA_COLUMNS: Tuple[
    Tuple[str, Tuple[float, float, float, float]],
    ...,
] = (
    ("fecha", BOX_SPEI_FECHA),
    ("hora", BOX_SPEI_HORA),
    ("participante", BOX_SPEI_PARTICIPANTE),
    ("contraparte", BOX_SPEI_BENEFICIARIO),
    ("cuenta", BOX_SPEI_CUENTA_BENEFICIARIA),
    ("concepto", BOX_SPEI_CONCEPTO),
    ("monto", BOX_SPEI_MONTO),
    ("clave_rastreo", BOX_SPEI_CLAVE_RASTREO),
    ("numero_referencia", BOX_SPEI_NUMERO_REFERENCIA),
)


# ============================================================
# TOLERANCIAS
# ============================================================

LINE_Y_TOLERANCE = 5.0
MOVEMENT_ROW_MAX_GAP = 22.0
COLUMN_PADDING_X = 8.0
COLUMN_PADDING_Y = 4.0

# Impide que el padding de una columna SPEI capture palabras
# pertenecientes a la columna vecina.
SPEI_MIN_HORIZONTAL_OVERLAP_RATIO = 0.55

DAY_MIN = 1
DAY_MAX = 31


# ============================================================
# PATRONES
# ============================================================

DAY_PATTERN = re.compile(r"^(?:0?[1-9]|[12]\d|3[01])$")

# Tesseract puede conservar puntuación de la cuadrícula junto al
# día, por ejemplo ``11.`` o ``14|``. La puntuación es tolerable
# únicamente en la columna Día y nunca se incorpora al concepto.
DAY_OCR_PATTERN = re.compile(
    r"^[\s.,;:|]*"
    r"(?P<day>0?[1-9]|[12]\d|3[01])"
    r"[\s.,;:|]*$"
)

# HSBC puede imprimir día y mes con uno o dos dígitos. El patrón
# conserva tres grupos: día, mes y año.
DATE_PATTERN = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])"
    r"[/-]"
    r"(0?[1-9]|1[0-2])"
    r"[/-]"
    r"(\d{4})\b"
)

MONEY_PATTERN = re.compile(r"^\$?\s*[\d,]+(?:\.\d{1,2})?$")
REFERENCE_PATTERN = re.compile(
    r"^[A-Z0-9Ñ&./_-]+$",
    re.IGNORECASE,
)
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}$")
SPEI_DATE_PATTERN = re.compile(
    r"^(?:0?[1-9]|[12]\d|3[01])"
    r"[/-]"
    r"(?:0?[1-9]|1[0-2])"
    r"[/-]"
    r"\d{4}$"
)
TRAILING_DIGITS_PATTERN = re.compile(r"(\d+)\D*$")

# La cuenta puede venir fusionada con la primera palabra del
# concepto en un único token PDF, por ejemplo:
#
#     00001180228001000108HACIENDA
#
# El patrón separa la secuencia numérica inicial del texto que
# pertenece a la columna Concepto del pago.
ACCOUNT_WITH_INLINE_CONCEPT_PATTERN = re.compile(
    r"^(?P<account>\d{10,22})(?P<concept>.*)$"
)


# ============================================================
# UTILIDADES GENERALES
# ============================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1))
    except (TypeError, ValueError):
        return 1


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    text = text.upper()
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_word_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# GEOMETRÍA
# ============================================================

def word_bounds(
    word: Dict[str, Any],
) -> Tuple[float, float, float, float]:
    x0 = safe_float(word.get("x0", 0.0))
    x1 = safe_float(word.get("x1", x0))
    top = safe_float(word.get("top", 0.0))
    bottom = safe_float(word.get("bottom", top))

    return x0, x1, top, bottom


def word_center(word: Dict[str, Any]) -> Tuple[float, float]:
    x0, x1, top, bottom = word_bounds(word)

    return (x0 + x1) / 2.0, (top + bottom) / 2.0


def word_inside_box(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding_x: float = 0.0,
    padding_y: float = 0.0,
) -> bool:
    """
    Determina si una word se solapa con una caja espacial.

    Se conserva el criterio de solapamiento para tolerar
    pequeñas variaciones de coordenadas en PDF digital y OCR.
    """

    xmin, xmax, ymin, ymax = box
    word_x0, word_x1, word_top, word_bottom = word_bounds(word)

    box_xmin = xmin - padding_x
    box_xmax = xmax + padding_x
    box_ymin = ymin - padding_y
    box_ymax = ymax + padding_y

    overlaps_x = word_x1 >= box_xmin and word_x0 <= box_xmax
    overlaps_y = word_bottom >= box_ymin and word_top <= box_ymax

    return overlaps_x and overlaps_y


def horizontal_overlap_width(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding_x: float = 0.0,
) -> float:
    xmin, xmax, _, _ = box
    word_x0, word_x1, _, _ = word_bounds(word)

    box_xmin = xmin - padding_x
    box_xmax = xmax + padding_x

    return max(
        0.0,
        min(word_x1, box_xmax) - max(word_x0, box_xmin),
    )


def horizontal_overlap_ratio(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding_x: float = 0.0,
) -> float:
    """
    Calcula qué proporción horizontal de la word pertenece
    realmente a la caja.

    Esto permite mantener tolerancia espacial sin aceptar una
    palabra vecina que únicamente roza el padding de la caja.
    """

    word_x0, word_x1, _, _ = word_bounds(word)
    overlap = horizontal_overlap_width(
        word,
        box,
        padding_x=padding_x,
    )
    word_width = max(word_x1 - word_x0, 0.001)

    return overlap / word_width


def word_belongs_to_spei_column(
    word: Dict[str, Any],
    box: Tuple[float, float, float, float],
    padding_x: float,
) -> bool:
    """
    Asigna una word a una columna SPEI solamente cuando existe
    solapamiento vertical y una parte mayoritaria de la word
    pertenece horizontalmente a esa columna.
    """

    if not word_inside_box(
        word,
        box,
        padding_x=padding_x,
        padding_y=COLUMN_PADDING_Y,
    ):
        return False

    return (
        horizontal_overlap_ratio(
            word,
            box,
            padding_x=padding_x,
        )
        >= SPEI_MIN_HORIZONTAL_OVERLAP_RATIO
    )


def primary_spei_column(
    word: Dict[str, Any],
) -> Optional[str]:
    """
    Determina la columna SPEI propietaria de una word usando el
    mayor solapamiento horizontal real, sin padding.

    Esta asignación disjunta se utiliza al reconstruir SPEI
    recibidos. Evita que una palabra cercana a un límite sea
    duplicada en dos columnas y permite detectar tokens que
    contienen datos fusionados de Cuenta y Concepto.
    """

    best_name: Optional[str] = None
    best_overlap = 0.0

    for column_name, box in SPEI_DATA_COLUMNS:
        overlap = horizontal_overlap_width(word, box)

        if overlap > best_overlap:
            best_name = column_name
            best_overlap = overlap

    return best_name


def primary_movement_column(
    word: Dict[str, Any],
) -> Optional[str]:
    """
    Determina la columna principal de una word del detalle de
    movimientos mediante el mayor solapamiento horizontal real.

    Referencia / Serial se reconstruye con esta propiedad exclusiva
    para impedir que una palabra de Descripción o Retiro/Cargo que
    roce el límite invalide el renglón completo de referencia.
    """

    best_name: Optional[str] = None
    best_overlap = 0.0

    for column_name, box in MOVEMENT_DATA_COLUMNS:
        overlap = horizontal_overlap_width(word, box)

        if overlap > best_overlap:
            best_name = column_name
            best_overlap = overlap

    return best_name


# ============================================================
# RENGLONES
# ============================================================

def line_bounds(
    line: Sequence[Dict[str, Any]],
) -> Tuple[float, float, float, float]:
    if not line:
        return 0.0, 0.0, 0.0, 0.0

    return (
        min(safe_float(word.get("x0", 0.0)) for word in line),
        max(safe_float(word.get("x1", 0.0)) for word in line),
        min(safe_float(word.get("top", 0.0)) for word in line),
        max(safe_float(word.get("bottom", 0.0)) for word in line),
    )


def line_center_y(line: Sequence[Dict[str, Any]]) -> float:
    _, _, ymin, ymax = line_bounds(line)

    return (ymin + ymax) / 2.0


def line_text(line: Sequence[Dict[str, Any]]) -> str:
    parts = []

    for word in line:
        text = clean_word_text(word.get("text", ""))
        if text:
            parts.append(text)

    return " ".join(parts).strip()


def group_words_into_lines(
    words: Sequence[Dict[str, Any]],
    y_tolerance: float = LINE_Y_TOLERANCE,
) -> List[List[Dict[str, Any]]]:
    """
    Agrupa words en renglones lógicos sin mezclar páginas.
    """

    valid_words = [
        word
        for word in words
        if clean_word_text(word.get("text", ""))
    ]
    valid_words.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    lines_by_page: Dict[int, List[List[Dict[str, Any]]]] = {}

    for word in valid_words:
        page = safe_page(word)
        center_y = word_center(word)[1]
        page_lines = lines_by_page.setdefault(page, [])

        best_line: Optional[List[Dict[str, Any]]] = None
        best_distance = float("inf")

        for line in reversed(page_lines):
            current_line_y = line_center_y(line)
            distance = abs(center_y - current_line_y)

            if distance <= y_tolerance and distance < best_distance:
                best_distance = distance
                best_line = line

            if current_line_y < center_y - y_tolerance:
                break

        if best_line is None:
            page_lines.append([word])
        else:
            best_line.append(word)

    result: List[List[Dict[str, Any]]] = []

    for page in sorted(lines_by_page):
        page_lines = lines_by_page[page]
        page_lines.sort(key=line_center_y)

        for line in page_lines:
            line.sort(
                key=lambda word: safe_float(word.get("x0", 0.0))
            )
            result.append(line)

    return result


# ============================================================
# PERIODO
# ============================================================

def extract_period_from_words(
    words: Sequence[Dict[str, Any]],
) -> Tuple[Optional[date], Optional[date]]:
    lines = group_words_into_lines(words)
    candidates = []

    for line in lines:
        if "PERIODO" not in normalize_text(line_text(line)):
            continue

        matches = DATE_PATTERN.findall(line_text(line))
        if len(matches) < 2:
            continue

        try:
            first = date(
                int(matches[0][2]),
                int(matches[0][1]),
                int(matches[0][0]),
            )
            second = date(
                int(matches[1][2]),
                int(matches[1][1]),
                int(matches[1][0]),
            )
        except ValueError:
            continue

        candidates.append(
            (
                first,
                second,
                safe_page(line[0]),
                line_center_y(line),
            )
        )

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: (item[2], item[3]))

    return candidates[0][0], candidates[0][1]


# ============================================================
# ENCABEZADOS DE MOVIMIENTOS
# ============================================================

def is_movement_header_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))

    return "DETALLE" in normalized and "MOVIMIENTOS" in normalized


def is_column_header_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))
    score = 0

    if "DIA" in normalized:
        score += 1
    if "DESCRIPCION" in normalized:
        score += 1
    if "RETIRO/CARGO" in normalized:
        score += 1
    if "DEPOSITO/ABONO" in normalized:
        score += 1
    if "SALDO" in normalized:
        score += 1

    return score >= 3


# ============================================================
# DETECCIÓN DE TABLAS SPEI
# ============================================================

def spei_section_type(
    line: Sequence[Dict[str, Any]],
) -> Optional[str]:
    normalized = normalize_text(line_text(line))

    if "SPEI" not in normalized:
        return None
    if "ENVIADOS" in normalized:
        return "enviados"
    if "RECIBIDOS" in normalized:
        return "recibidos"

    return None


def is_spei_column_header_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))
    compact = re.sub(r"\s+", "", normalized)
    score = 0

    if "FECHADE" in compact:
        score += 1
    if "HORADE" in compact:
        score += 1
    if "PARTICIPANTE" in compact:
        score += 1
    if "BENEFICIARIO" in compact:
        score += 1
    if (
        "CUENTABENEFICIARIA" in compact
        or "CUENTAORDENANTE" in compact
    ):
        score += 1
    if "MONTODELPAGO" in compact:
        score += 1
    if "CLAVEDE" in compact:
        score += 1
    if "RASTREO" in compact:
        score += 1
    if "NUMERODE" in compact:
        score += 1

    return score >= 3


def is_spei_table_breaker_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Detecta el texto que cierra físicamente una tabla SPEI.

    Debe ejecutarse antes de agregar la línea a la última fila
    para evitar que las notas y CoDi contaminen sus columnas.
    """

    normalized = normalize_text(line_text(line))

    if not normalized:
        return False
    if "DATO NO VERIFICADO" in normalized:
        return True
    if normalized.startswith("CODI"):
        return True
    if "OPERACION PROCESADA POR CODI" in normalized:
        return True
    if "EMITIDO POR" in normalized:
        return True
    if "PASEO DE LA REFORMA" in normalized:
        return True

    return False


# ============================================================
# DATO AUXILIAR SPEI
# ============================================================

@dataclass
class SpeiRow:
    tipo: str
    page: int
    lines: List[List[Dict[str, Any]]]

    fecha: Optional[str] = None
    hora: Optional[str] = None
    participante: Optional[str] = None
    beneficiario: Optional[str] = None
    cuenta_beneficiaria: Optional[str] = None

    # Semántica explícita para SPEI recibidos. Se conservan
    # también los campos genéricos para mantener compatibilidad.
    nombre_ordenante: Optional[str] = None
    cuenta_ordenante: Optional[str] = None

    concepto: Optional[str] = None
    monto: float = 0.0
    clave_rastreo: Optional[str] = None
    numero_referencia: Optional[str] = None


# ============================================================
# UTILIDADES ESPACIALES PARA SPEI
# ============================================================

def words_from_spei_row_in_box(
    row: SpeiRow,
    box: Tuple[float, float, float, float],
    padding_x: float = COLUMN_PADDING_X,
) -> List[Dict[str, Any]]:
    selected = []

    for line in row.lines:
        for word in line:
            if word_belongs_to_spei_column(
                word,
                box,
                padding_x=padding_x,
            ):
                selected.append(word)

    selected.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    return selected


def text_from_spei_box(
    row: SpeiRow,
    box: Tuple[float, float, float, float],
    padding_x: float = COLUMN_PADDING_X,
) -> Optional[str]:
    words = words_from_spei_row_in_box(
        row,
        box,
        padding_x=padding_x,
    )
    parts = []

    for word in words:
        text = clean_word_text(word.get("text", ""))
        if text:
            parts.append(text)

    if not parts:
        return None

    return " ".join(parts).strip()


def text_from_primary_spei_column(
    row: SpeiRow,
    column_name: str,
) -> Optional[str]:
    """
    Reconstruye una columna usando propiedad espacial exclusiva.

    Se utiliza en SPEI recibidos para impedir que el padding de una
    columna capture palabras cortas de la columna contigua. Por
    ejemplo, ``LA`` de ``TESORERIA DE LA FEDERACION`` no debe formar
    parte de Participante Emisor.
    """

    selected: List[Dict[str, Any]] = []

    for line in row.lines:
        for word in line:
            if primary_spei_column(word) == column_name:
                selected.append(word)

    selected.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    parts = [
        clean_word_text(word.get("text", ""))
        for word in selected
        if clean_word_text(word.get("text", ""))
    ]

    if not parts:
        return None

    return " ".join(parts).strip()


def split_account_and_inline_concept(
    value: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Separa una cuenta numérica y el texto del concepto cuando el
    PDF entrega ambos dentro de un solo token.

    La separación se basa en la semántica estable de la columna:
    Cuenta Ordenante inicia con el identificador numérico y todo
    texto posterior pertenece a Concepto del pago.
    """

    compact = re.sub(r"\s+", "", value)
    if not compact:
        return None, None

    match = ACCOUNT_WITH_INLINE_CONCEPT_PATTERN.fullmatch(compact)
    if not match:
        return None, None

    account = match.group("account") or None
    inline_concept = match.group("concept") or None

    return account, inline_concept


def extract_received_account_and_concept(
    row: SpeiRow,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Reconstruye Cuenta Ordenante y Concepto del pago de un SPEI
    recibido con propiedad exclusiva de columnas.

    Cada word se asigna primero a la columna con mayor solapamiento
    real. Si el lector PDF fusionó la cuenta con la primera palabra
    del concepto, se separan ambos componentes y se conserva su
    orden natural dentro del renglón.
    """

    account_candidates: List[str] = []
    concept_lines: List[str] = []

    for line in row.lines:
        account_parts: List[str] = []
        concept_parts: List[str] = []

        for word in sorted(
            line,
            key=lambda item: safe_float(item.get("x0", 0.0)),
        ):
            text = clean_word_text(word.get("text", ""))
            if not text:
                continue

            owner = primary_spei_column(word)

            if owner == "cuenta":
                account_parts.append(text)
            elif owner == "concepto":
                concept_parts.append(text)

        inline_concept: Optional[str] = None

        if account_parts:
            account_text = "".join(account_parts)
            account, inline_concept = split_account_and_inline_concept(
                account_text
            )

            if account:
                account_candidates.append(account)

        line_concept_parts: List[str] = []

        if inline_concept:
            line_concept_parts.append(inline_concept)

        line_concept_parts.extend(concept_parts)

        if line_concept_parts:
            concept_lines.append(
                " ".join(line_concept_parts).strip()
            )

    account_value: Optional[str] = None

    if account_candidates:
        # Si existen varias candidatas, la más larga representa el
        # identificador completo; el orden original resuelve empates.
        account_value = max(account_candidates, key=len)

    concept_value = (
        " ".join(concept_lines).strip()
        if concept_lines
        else None
    )

    return account_value, concept_value


# ============================================================
# NORMALIZACIÓN DE IDENTIFICADORES SPEI
# ============================================================

def compact_tracking_key(value: Optional[str]) -> Optional[str]:
    """
    Reconstruye la Clave de Rastreo conservando el prefijo.

    Ejemplo:
        HSBC2285 + 77 -> HSBC228577
    """

    if value is None:
        return None

    compact = re.sub(
        r"[^A-Z0-9]",
        "",
        normalize_text(value),
    )

    return compact or None


def normalize_tracking_key(value: Optional[str]) -> Optional[str]:
    """
    Genera la clave utilizada exclusivamente para el cruce.

    Tolera HSBC, HSB o la clave sin prefijo.
    """

    compact = compact_tracking_key(value)
    if not compact:
        return None

    if compact.startswith("HSBC"):
        compact = compact[4:]
    elif compact.startswith("HSB"):
        compact = compact[3:]

    return compact or None


def normalize_spei_reference(value: Optional[str]) -> Optional[str]:
    """
    Reconstruye el Número de Referencia conservando sus ceros.

    Ejemplo:
        000000000000 + 00110014
        -> 00000000000000110014
    """

    if value is None:
        return None

    digits = re.sub(r"\D", "", value)

    return digits or None


def normalize_account_identifier(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    compact = re.sub(r"\s+", "", value).strip()

    return compact or None


def normalize_reference_for_right_match(
    value: Optional[str],
) -> Optional[str]:
    """
    Convierte una referencia numérica a su identidad leída desde
    la derecha.

    Solamente se eliminan ceros de relleno situados a la izquierda.
    No se eliminan ni modifican dígitos significativos.
    """

    if value is None:
        return None

    digits = re.sub(r"\D", "", value)
    if not digits:
        return None

    normalized = digits.lstrip("0")

    return normalized or "0"


def numeric_references_match_from_right(
    first: Optional[str],
    second: Optional[str],
) -> bool:
    """
    Compara dos referencias desde su extremo derecho, ignorando
    exclusivamente los ceros de relleno a la izquierda.
    """

    first_normalized = normalize_reference_for_right_match(first)
    second_normalized = normalize_reference_for_right_match(second)

    if not first_normalized or not second_normalized:
        return False

    return first_normalized == second_normalized


def extract_received_reference_from_concept(
    concept: Optional[str],
) -> Optional[str]:
    """
    Extrae la referencia numérica situada al extremo derecho del
    concepto del movimiento.

    Esta es la única referencia del movimiento utilizada para
    cruzar SPEI recibidos. Referencia / Serial pertenece a otra
    columna y no interviene en esta estrategia.

    Caso observado:
        HACIENDA TE DEVUELVE DC252600004 0110014
        -> 0110014
    """

    if not concept:
        return None

    match = TRAILING_DIGITS_PATTERN.search(concept)
    if not match:
        return None

    return match.group(1)


def extract_movement_tracking_key(
    movement_reference: Optional[str],
) -> Optional[str]:
    """
    Obtiene la referencia importante de un movimiento enviado.

    Cuando Referencia / Serial contiene dos renglones, el valor
    inferior es el que se cruza con Clave de Rastreo. El valor
    completo permanece conservado en Movimiento.referencia si no
    existe coincidencia SPEI.

    Ejemplo:
        08045209\n6116115 -> 6116115
    """

    if movement_reference is None:
        return None

    values = [
        part.strip()
        for part in re.split(
            r"[\r\n]+",
            str(movement_reference),
        )
        if part.strip()
    ]

    if not values:
        return None

    return normalize_tracking_key(values[-1])


# ============================================================
# EXTRACTORES DE CAMPOS SPEI
# ============================================================

def extract_spei_date(row: SpeiRow) -> Optional[str]:
    value = text_from_spei_box(
        row,
        BOX_SPEI_FECHA,
        padding_x=5.0,
    )
    if not value:
        return None

    match = DATE_PATTERN.search(value)

    return match.group(0) if match else None


def extract_spei_time(row: SpeiRow) -> Optional[str]:
    value = text_from_spei_box(
        row,
        BOX_SPEI_HORA,
        padding_x=5.0,
    )
    if not value:
        return None

    for token in value.split():
        if TIME_PATTERN.fullmatch(token):
            return token

    return None


def parse_spei_amount(row: SpeiRow) -> float:
    words = words_from_spei_row_in_box(
        row,
        BOX_SPEI_MONTO,
        padding_x=8.0,
    )
    if not words:
        return 0.0

    parts = []

    for word in words:
        text = clean_word_text(word.get("text", ""))
        if not text:
            continue

        normalized = (
            text
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

        if re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
            parts.append(normalized)

    if not parts:
        return 0.0

    value = "".join(parts)
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        return 0.0

    try:
        return float(value)
    except ValueError:
        return 0.0


def populate_spei_row(row: SpeiRow) -> None:
    row.fecha = extract_spei_date(row)
    row.hora = extract_spei_time(row)

    generic_participant = text_from_spei_box(
        row,
        BOX_SPEI_PARTICIPANTE,
        padding_x=5.0,
    )

    nombre_contraparte = text_from_spei_box(
        row,
        BOX_SPEI_BENEFICIARIO,
        padding_x=5.0,
    )
    row.beneficiario = nombre_contraparte

    raw_account = text_from_spei_box(
        row,
        BOX_SPEI_CUENTA_BENEFICIARIA,
        padding_x=6.0,
    )
    generic_account = normalize_account_identifier(raw_account)

    generic_concept = text_from_spei_box(
        row,
        BOX_SPEI_CONCEPTO,
        padding_x=5.0,
    )

    if row.tipo == "recibidos":
        received_participant = text_from_primary_spei_column(
            row,
            "participante",
        )
        received_counterparty = text_from_primary_spei_column(
            row,
            "contraparte",
        )
        received_account, received_concept = (
            extract_received_account_and_concept(row)
        )

        row.participante = (
            received_participant
            or generic_participant
        )
        row.nombre_ordenante = (
            received_counterparty
            or nombre_contraparte
        )
        row.beneficiario = row.nombre_ordenante
        row.cuenta_ordenante = received_account or generic_account

        # Se conservan los campos genéricos con el mismo valor para
        # compatibilidad con consumidores existentes.
        row.cuenta_beneficiaria = row.cuenta_ordenante
        row.concepto = received_concept or generic_concept
    else:
        row.participante = generic_participant
        row.cuenta_beneficiaria = generic_account
        row.concepto = generic_concept

    row.monto = parse_spei_amount(row)

    raw_tracking_key = text_from_spei_box(
        row,
        BOX_SPEI_CLAVE_RASTREO,
        padding_x=5.0,
    )
    row.clave_rastreo = compact_tracking_key(raw_tracking_key)

    raw_reference = text_from_spei_box(
        row,
        BOX_SPEI_NUMERO_REFERENCIA,
        padding_x=6.0,
    )
    row.numero_referencia = normalize_spei_reference(raw_reference)


# ============================================================
# RECONSTRUCCIÓN DE FILAS SPEI
# ============================================================

def line_starts_spei_row(
    line: Sequence[Dict[str, Any]],
) -> bool:
    for word in line:
        if not word_belongs_to_spei_column(
            word,
            BOX_SPEI_FECHA,
            padding_x=5.0,
        ):
            continue

        text = clean_word_text(word.get("text", ""))
        if SPEI_DATE_PATTERN.fullmatch(text):
            return True

    return False


def is_valid_spei_data_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))

    if not normalized:
        return False
    if is_spei_column_header_line(line):
        return False
    if is_spei_table_breaker_line(line):
        return False

    return True


def split_page_into_spei_rows(
    lines: Sequence[Sequence[Dict[str, Any]]],
    section_type: str,
) -> List[SpeiRow]:
    """
    Reconstruye operaciones SPEI de una o varias líneas.

    Una fecha con día o mes de uno o dos dígitos inicia una nueva
    operación. Las líneas posteriores, incluida la continuación de
    Clave de Rastreo o Número de Referencia, permanecen dentro de
    la misma SpeiRow.
    """

    rows: List[SpeiRow] = []
    current_row: Optional[SpeiRow] = None

    for line in lines:
        if not line:
            continue

        if is_spei_table_breaker_line(line):
            if current_row is not None:
                populate_spei_row(current_row)
                rows.append(current_row)
                current_row = None
            break

        if is_spei_column_header_line(line):
            continue

        if line_starts_spei_row(line):
            if current_row is not None:
                populate_spei_row(current_row)
                rows.append(current_row)

            current_row = SpeiRow(
                tipo=section_type,
                page=safe_page(line[0]),
                lines=[list(line)],
            )
            continue

        if current_row is None:
            continue
        if not is_valid_spei_data_line(line):
            continue
        if safe_page(line[0]) != current_row.page:
            continue

        gap = (
            line_center_y(line)
            - line_center_y(current_row.lines[-1])
        )

        if 0.0 <= gap <= MOVEMENT_ROW_MAX_GAP:
            current_row.lines.append(list(line))

    if current_row is not None:
        populate_spei_row(current_row)
        rows.append(current_row)

    return rows


def extract_spei_rows(
    words: Sequence[Dict[str, Any]],
) -> List[SpeiRow]:
    """
    Extrae de forma independiente todas las tablas de SPEI
    enviados y recibidos del estado de cuenta.
    """

    lines = group_words_into_lines(words)
    sections: List[
        Tuple[str, List[Sequence[Dict[str, Any]]]]
    ] = []

    current_type: Optional[str] = None
    current_lines: List[Sequence[Dict[str, Any]]] = []

    for line in lines:
        detected_type = spei_section_type(line)

        if detected_type is not None:
            if current_type is not None and current_lines:
                sections.append((current_type, current_lines))

            current_type = detected_type
            current_lines = []
            continue

        if current_type is None:
            continue

        if is_spei_table_breaker_line(line):
            if current_lines:
                sections.append((current_type, current_lines))

            current_type = None
            current_lines = []
            continue

        current_lines.append(line)

    if current_type is not None and current_lines:
        sections.append((current_type, current_lines))

    rows: List[SpeiRow] = []

    for section_type, section_lines in sections:
        rows.extend(
            split_page_into_spei_rows(
                section_lines,
                section_type,
            )
        )

    return rows


# ============================================================
# FILA LÓGICA — MOVIMIENTO PRINCIPAL
# ============================================================

@dataclass
class MovementRow:
    page: int
    lines: List[List[Dict[str, Any]]]

    referencia_serial_superior: Optional[str] = None
    referencia_serial_inferior: Optional[str] = None
    referencia_serial_completo: Optional[str] = None
    referencia_principal: Optional[str] = None


# ============================================================
# DÍA Y RECONSTRUCCIÓN DE MOVIMIENTOS
# ============================================================


def parse_day_token(value: Any) -> Optional[int]:
    """
    Convierte un token de la columna Día a entero.

    Tesseract puede conservar puntuación de la cuadrícula junto al
    número, por ejemplo ``11.`` o ``|14``. Solo se toleran signos
    externos; nunca se eliminan letras ni dígitos adicionales.
    """

    text = clean_word_text(value)
    if not text:
        return None

    match = DAY_OCR_PATTERN.fullmatch(text)
    if match is None:
        return None

    try:
        day = int(match.group("day"))
    except (TypeError, ValueError):
        return None

    if not DAY_MIN <= day <= DAY_MAX:
        return None

    return day


def extract_day_from_line(
    line: Sequence[Dict[str, Any]],
) -> Optional[int]:
    day_word = find_day_word_in_line(line)
    if day_word is None:
        return None

    return parse_day_token(
        day_word.get("text", "")
    )


def find_day_word_in_line(
    line: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Devuelve el word que representa el día del movimiento.

    Conservar la identidad del word permite excluir exactamente ese
    elemento de Descripción cuando las cajas se solapan, sin eliminar
    otros números legítimos del concepto.
    """

    for word in line:
        if not word_inside_box(
            word,
            BOX_DAY,
            padding_x=7.0,
            padding_y=3.0,
        ):
            continue

        day = parse_day_token(
            word.get("text", "")
        )

        if day is not None:
            return word

    return None


def line_has_movement_amount(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Confirma que el renglón contiene un importe dentro de las
    columnas financieras del detalle.

    Se usa únicamente para validar días con puntuación OCR. Los días
    que ya cumplían DAY_PATTERN conservan exactamente la conducta
    anterior del parser.
    """

    financial_boxes = (
        BOX_CARGO,
        BOX_ABONO,
        BOX_SALDO,
    )

    for word in line:
        text = clean_word_text(
            word.get("text", "")
        )

        if not text or text == "$":
            continue

        if not MONEY_PATTERN.fullmatch(text):
            continue

        if any(
            word_inside_box(
                word,
                box,
                padding_x=8.0,
                padding_y=COLUMN_PADDING_Y,
            )
            for box in financial_boxes
        ):
            return True

    return False


def line_has_numeric_reference(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Busca evidencia numérica en Referencia / Serial.

    Esta segunda señal evita interpretar ``1.``, ``2.`` o ``3.`` de
    listas informativas como días de movimientos.
    """

    for word in line:
        if primary_movement_column(word) != "referencia_serial":
            continue

        digits = re.sub(
            r"\D",
            "",
            clean_word_text(
                word.get("text", "")
            ),
        )

        if len(digits) >= 4:
            return True

    return False


def line_starts_movement(
    line: Sequence[Dict[str, Any]],
) -> bool:
    day_word = find_day_word_in_line(line)
    if day_word is None:
        return False

    raw_day = clean_word_text(
        day_word.get("text", "")
    )

    # Ruta histórica: no cambia absolutamente nada para un día
    # limpio que el parser original ya reconocía.
    if DAY_PATTERN.fullmatch(raw_day):
        return True

    # Ruta nueva y limitada: un día como ``11.`` solamente inicia
    # movimiento cuando el mismo renglón tiene la estructura mínima
    # de una fila financiera real.
    return (
        line_has_movement_amount(line)
        and
        line_has_numeric_reference(line)
    )


def is_footer_like_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))

    if "EMITIDO POR" in normalized:
        return True
    if "PASEO DE LA REFORMA" in normalized:
        return True
    if "RFC:" in normalized:
        return True

    return False


def is_table_breaker_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    normalized = normalize_text(line_text(line))

    if not normalized:
        return False
    if normalized.startswith("CODI"):
        return True
    if "OPERACION PROCESADA POR CODI" in normalized:
        return True
    if normalized.startswith("CIFRAS EXPRESADAS"):
        return True

    return False


def is_spei_information_header_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Detecta el encabezado real que inicia una sección informativa
    SPEI después del detalle de movimientos.

    Exigir ``INFORMACION`` y ``PERIODO`` evita confundir este cierre
    estructural con el concepto ordinario de un movimiento SPEI.
    """

    normalized = normalize_text(line_text(line))

    return (
        "INFORMACION" in normalized
        and "SPEI" in normalized
        and "PERIODO" in normalized
        and (
            "ENVIADOS" in normalized
            or "RECIBIDOS" in normalized
        )
    )


def split_page_into_movement_rows(
    words: Sequence[Dict[str, Any]],
) -> List[MovementRow]:
    if not words:
        return []

    lines = group_words_into_lines(words)
    rows: List[MovementRow] = []
    current_row: Optional[MovementRow] = None
    table_started = False

    for line in lines:
        if not line:
            continue

        page = safe_page(line[0])

        if is_movement_header_line(line):
            table_started = True
            continue

        if is_column_header_line(line):
            table_started = True
            continue

        if is_footer_like_line(line):
            if current_row is not None:
                rows.append(current_row)
                current_row = None
            break

        if table_started and (
            is_table_breaker_line(line)
            or is_spei_information_header_line(line)
        ):
            if current_row is not None:
                rows.append(current_row)
                current_row = None
            break

        if line_starts_movement(line):
            if current_row is not None:
                rows.append(current_row)

            current_row = MovementRow(
                page=page,
                lines=[list(line)],
            )
            table_started = True
            continue

        if not table_started:
            continue

        if current_row is not None:
            # La siguiente línea con día delimita la próxima fila.
            # Mientras no aparezca ese inicio ni un cierre explícito
            # de tabla, toda línea pertenece al movimiento actual.
            #
            # No se usa una distancia vertical máxima: HSBC puede
            # imprimir Referencia y Serial con separaciones variables.
            current_row.lines.append(list(line))

    if current_row is not None:
        rows.append(current_row)

    return rows


# ============================================================
# EXTRACCIÓN DE COLUMNAS DEL MOVIMIENTO
# ============================================================

def words_from_rows_in_box(
    row: MovementRow,
    box: Tuple[float, float, float, float],
    padding_x: float = COLUMN_PADDING_X,
) -> List[Dict[str, Any]]:
    selected = []

    for line in row.lines:
        for word in line:
            if word_inside_box(
                word,
                box,
                padding_x=padding_x,
                padding_y=COLUMN_PADDING_Y,
            ):
                selected.append(word)

    selected.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    return selected


def text_from_box(
    row: MovementRow,
    box: Tuple[float, float, float, float],
    padding_x: float = COLUMN_PADDING_X,
) -> str:
    words = words_from_rows_in_box(
        row,
        box,
        padding_x=padding_x,
    )

    return " ".join(
        clean_word_text(word.get("text", ""))
        for word in words
        if clean_word_text(word.get("text", ""))
    ).strip()


def extract_concepto(row: MovementRow) -> str:
    words = words_from_rows_in_box(
        row,
        BOX_CONCEPTO,
        padding_x=5.0,
    )
    parts = []

    day_word = (
        find_day_word_in_line(row.lines[0])
        if row.lines
        else None
    )

    for word in words:
        if day_word is not None and word is day_word:
            continue

        text = clean_word_text(word.get("text", ""))
        if text:
            parts.append(text)

    return " ".join(parts).strip()


# ============================================================
# REFERENCIA / SERIAL
# ============================================================

def is_reference_word_candidate(
    word: Dict[str, Any],
) -> bool:
    """
    Valida una word individual antes de reconstruir los renglones
    de Referencia / Serial.

    Un símbolo monetario situado exactamente sobre el límite con
    Retiro/Cargo no debe invalidar una referencia legítima que
    comparte su misma coordenada vertical.
    """

    text = clean_word_text(word.get("text", ""))
    if not text:
        return False

    compact = re.sub(r"\s+", "", text)
    if not compact or compact in ("$", "-"):
        return False

    return bool(REFERENCE_PATTERN.fullmatch(compact))


def reference_serial_words(
    row: MovementRow,
) -> List[Dict[str, Any]]:
    selected = [
        word
        for line in row.lines
        for word in line
        if primary_movement_column(word) == "referencia_serial"
        and is_reference_word_candidate(word)
    ]

    selected.sort(
        key=lambda word: (
            safe_page(word),
            safe_float(word.get("top", 0.0)),
            safe_float(word.get("x0", 0.0)),
        )
    )

    return selected


def reference_serial_lines(
    row: MovementRow,
) -> List[List[Dict[str, Any]]]:
    words = reference_serial_words(row)
    if not words:
        return []

    lines = group_words_into_lines(
        words,
        y_tolerance=LINE_Y_TOLERANCE,
    )
    lines.sort(key=line_center_y)

    return lines


def valid_reference_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    text = line_text(line)
    if not text:
        return False

    compact = re.sub(r"\s+", "", text)
    if not compact or compact in ("$", "-"):
        return False

    return bool(REFERENCE_PATTERN.fullmatch(compact))


def compact_reference_line(
    line: Sequence[Dict[str, Any]],
) -> Optional[str]:
    if not valid_reference_line(line):
        return None

    parts = []

    for word in line:
        text = clean_word_text(word.get("text", ""))
        if not text:
            continue

        cleaned = re.sub(
            r"[^A-Z0-9Ñ&./_-]",
            "",
            text.upper(),
        )
        if cleaned:
            parts.append(cleaned)

    value = "".join(parts)

    return value or None


def extract_referencia_serial(
    row: MovementRow,
) -> Tuple[Optional[str], Optional[str]]:
    lines = reference_serial_lines(row)
    if not lines:
        return None, None

    valid_values = []

    for line in lines:
        value = compact_reference_line(line)
        if value:
            valid_values.append(value)

    if not valid_values:
        return None, None

    referencia_superior = valid_values[0]
    referencia_inferior = (
        valid_values[1]
        if len(valid_values) >= 2
        else None
    )

    return referencia_superior, referencia_inferior


def build_referencia_serial_completo(
    referencia_superior: Optional[str],
    referencia_inferior: Optional[str],
) -> Optional[str]:
    values = []

    if referencia_superior:
        values.append(referencia_superior)
    if referencia_inferior:
        values.append(referencia_inferior)

    if not values:
        return None

    return "\n".join(values)


def populate_reference_serial_data(row: MovementRow) -> None:
    (
        referencia_superior,
        referencia_inferior,
    ) = extract_referencia_serial(row)

    row.referencia_serial_superior = referencia_superior
    row.referencia_serial_inferior = referencia_inferior
    row.referencia_serial_completo = build_referencia_serial_completo(
        referencia_superior,
        referencia_inferior,
    )

    # La referencia inferior es la variable semántica de cruce
    # exclusiva de los SPEI enviados.
    row.referencia_principal = (
        referencia_inferior
        or referencia_superior
    )


def extract_referencia(row: MovementRow) -> Optional[str]:
    if (
        row.referencia_serial_superior is None
        and row.referencia_serial_inferior is None
        and row.referencia_serial_completo is None
    ):
        populate_reference_serial_data(row)

    return row.referencia_principal


def extract_referencia_completa(
    row: MovementRow,
) -> Optional[str]:
    if (
        row.referencia_serial_superior is None
        and row.referencia_serial_inferior is None
        and row.referencia_serial_completo is None
    ):
        populate_reference_serial_data(row)

    return row.referencia_serial_completo


# ============================================================
# IMPORTE
# ============================================================

def parse_money_words(
    row: MovementRow,
    box: Tuple[float, float, float, float],
) -> float:
    words = words_from_rows_in_box(
        row,
        box,
        padding_x=8.0,
    )
    if not words:
        return 0.0

    parts = []

    for word in words:
        text = clean_word_text(word.get("text", ""))
        if not text or text == "$":
            continue

        normalized = (
            text
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

        if re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
            parts.append(normalized)

    if not parts:
        return 0.0

    value = "".join(parts)
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        return 0.0

    try:
        return float(value)
    except ValueError:
        return 0.0


# ============================================================
# FECHA Y TIPO DE OPERACIÓN
# ============================================================

def extract_day_from_row(row: MovementRow) -> Optional[int]:
    if not row.lines:
        return None

    return extract_day_from_line(row.lines[0])


def build_operation_date(
    day: Optional[int],
    periodo_inicio: Optional[date],
) -> str:
    if day is None:
        return ""

    if periodo_inicio is None:
        return f"{day:02d}"

    try:
        return date(
            periodo_inicio.year,
            periodo_inicio.month,
            day,
        ).strftime("%d/%m/%Y")
    except ValueError:
        return f"{day:02d}"


def extract_tipo_operacion(concepto: str) -> Optional[str]:
    normalized = normalize_text(concepto)

    if normalized.startswith("RETIRO"):
        return "Retiro"
    if normalized.startswith("DEPOSITO"):
        return "Depósito"
    if normalized.startswith("ABONO"):
        return "Abono"

    return None


# ============================================================
# FILA → MODELO
# ============================================================

def movement_row_to_model(
    row: MovementRow,
    periodo_inicio: Optional[date],
) -> Movimiento:
    populate_reference_serial_data(row)

    day = extract_day_from_row(row)
    fecha_operacion = build_operation_date(day, periodo_inicio)
    concepto = extract_concepto(row)
    cargo = parse_money_words(row, BOX_CARGO)
    abono = parse_money_words(row, BOX_ABONO)
    saldo_operacion = parse_money_words(row, BOX_SALDO)

    referencia_principal = extract_referencia(row)
    referencia_completa = extract_referencia_completa(row)
    referencia_modelo = (
        referencia_completa
        or referencia_principal
        or None
    )

    return Movimiento(
        fecha_operacion=fecha_operacion,
        fecha_liquidacion=None,
        concepto=concepto,
        tipo_operacion=None,
        cargo=cargo,
        abono=abono,
        referencia=referencia_modelo,
        clave_rastreo=None,
        autorizacion=None,
        beneficiario=None,
        cuenta_beneficiario=None,
        clabe_beneficiario=None,
        rfc=None,
        sucursal=None,
        caja=None,
        hora_operacion=None,
        saldo_operacion=saldo_operacion,
        saldo_liquidacion=0.0,
        concepto_original=concepto,
    )


def is_valid_movement(movement: Movimiento) -> bool:
    if not movement.fecha_operacion:
        return False
    if not movement.concepto:
        return False
    if movement.cargo == 0.0 and movement.abono == 0.0:
        return False

    return True


# ============================================================
# ÍNDICES Y DESEMPATE SPEI
# ============================================================

@dataclass
class SpeiMatchIndexes:
    """
    Índices separados por la semántica real de cada tabla.

    Enviados:
        Referencia / Serial inferior -> Clave de Rastreo

    Recibidos:
        Referencia final del concepto -> Número de Referencia
    """

    sent_by_tracking_key: Dict[str, List[SpeiRow]]
    received_by_reference: Dict[str, List[SpeiRow]]


def build_spei_match_indexes(
    spei_rows: Sequence[SpeiRow],
) -> SpeiMatchIndexes:
    sent_by_tracking_key: Dict[str, List[SpeiRow]] = {}
    received_by_reference: Dict[str, List[SpeiRow]] = {}

    for row in spei_rows:
        if row.tipo == "enviados":
            tracking_key = normalize_tracking_key(
                row.clave_rastreo
            )
            if tracking_key:
                sent_by_tracking_key.setdefault(
                    tracking_key,
                    [],
                ).append(row)
            continue

        if row.tipo != "recibidos":
            continue

        reference_key = normalize_reference_for_right_match(
            row.numero_referencia
        )
        tracking_key = compact_tracking_key(row.clave_rastreo)

        # La Clave de Rastreo es obligatoria para considerar válida
        # la fila SPEI y posteriormente almacenarla en el movimiento
        # cuando se confirme la coincidencia.
        if not reference_key or not tracking_key:
            continue

        received_by_reference.setdefault(
            reference_key,
            [],
        ).append(row)

    return SpeiMatchIndexes(
        sent_by_tracking_key=sent_by_tracking_key,
        received_by_reference=received_by_reference,
    )


def movement_amounts(movement: Movimiento) -> List[float]:
    amounts = []

    if movement.cargo:
        amounts.append(float(movement.cargo))
    if movement.abono:
        amounts.append(float(movement.abono))

    return amounts


def choose_spei_candidate(
    movement: Movimiento,
    candidates: Sequence[SpeiRow],
) -> Optional[SpeiRow]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    amounts = movement_amounts(movement)

    for candidate in candidates:
        for amount in amounts:
            if abs(candidate.monto - amount) < 0.01:
                return candidate

    return candidates[0]


# ============================================================
# MATCH SPEI ENVIADOS
# ============================================================

def find_spei_sent_match(
    movement: Movimiento,
    indexes: SpeiMatchIndexes,
) -> Optional[SpeiRow]:
    """
    Cruza:
        referencia inferior del movimiento
        <->
        Clave de Rastreo de cualquier SPEI enviado

    Ejemplo:
        08045209\n6116115
        <->
        HSB61161 + 15
    """

    key = extract_movement_tracking_key(movement.referencia)
    if not key:
        return None

    candidates = indexes.sent_by_tracking_key.get(key, [])

    return choose_spei_candidate(movement, candidates)


# ============================================================
# MATCH SPEI RECIBIDOS
# ============================================================

def find_spei_received_match(
    movement: Movimiento,
    indexes: SpeiMatchIndexes,
) -> Optional[SpeiRow]:
    """
    Cruza exclusivamente:
        referencia numérica al final del concepto del movimiento
        <->
        Número de Referencia de la fila SPEI recibida

    La comparación parte del extremo derecho y solamente ignora
    ceros de relleno a la izquierda.

    Caso observado:
        Concepto del movimiento:
            ... DC252600004 0110014

        Número de Referencia SPEI:
            000000000000 + 00110014

        Identidad común:
            110014

    Referencia / Serial del movimiento no interviene en este cruce.
    """

    movement_reference = extract_received_reference_from_concept(
        movement.concepto
    )
    if not movement_reference:
        return None

    reference_key = normalize_reference_for_right_match(
        movement_reference
    )
    if not reference_key:
        return None

    candidates = indexes.received_by_reference.get(
        reference_key,
        [],
    )

    # La verificación explícita documenta y garantiza que el índice
    # representa la misma comparación numérica desde la derecha.
    valid_candidates = [
        candidate
        for candidate in candidates
        if numeric_references_match_from_right(
            movement_reference,
            candidate.numero_referencia,
        )
    ]

    return choose_spei_candidate(movement, valid_candidates)


def find_spei_match(
    movement: Movimiento,
    indexes: SpeiMatchIndexes,
) -> Optional[SpeiRow]:
    """
    Ejecuta las dos estrategias sin mezclar sus identificadores.

    Si ambas producen candidato, el sentido contable resuelve la
    ambigüedad. En ausencia de esa señal se conserva la prioridad
    histórica de SPEI enviados.
    """

    sent_match = find_spei_sent_match(movement, indexes)
    received_match = find_spei_received_match(movement, indexes)

    if sent_match is None:
        return received_match
    if received_match is None:
        return sent_match

    if movement.abono and not movement.cargo:
        return received_match
    if movement.cargo and not movement.abono:
        return sent_match

    return sent_match


# ============================================================
# ENRIQUECIMIENTO DE MOVIMIENTOS
# ============================================================

def enrich_movement_from_received_spei(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> None:
    """
    Mapeo semántico exclusivo de SPEI recibidos.

    Nombre del Ordenante  -> Beneficiario
    Cuenta Ordenante      -> Cuenta del Beneficiario
    Concepto del pago     -> Concepto Original
    """

    nombre_ordenante = (
        spei_row.nombre_ordenante
        or spei_row.beneficiario
    )
    cuenta_ordenante = (
        spei_row.cuenta_ordenante
        or spei_row.cuenta_beneficiaria
    )

    if nombre_ordenante:
        movement.beneficiario = nombre_ordenante
    if cuenta_ordenante:
        movement.cuenta_beneficiario = cuenta_ordenante
    if spei_row.concepto:
        movement.concepto_original = spei_row.concepto


def enrich_movement_from_sent_spei(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> None:
    """
    Mapeo estable de SPEI enviados.
    """

    if spei_row.beneficiario:
        movement.beneficiario = spei_row.beneficiario
    if spei_row.cuenta_beneficiaria:
        movement.cuenta_beneficiario = spei_row.cuenta_beneficiaria
    if spei_row.concepto:
        movement.concepto_original = spei_row.concepto


def enrich_movement_from_spei(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> None:
    """
    Enriquece únicamente después de confirmar una coincidencia.

    La Referencia / Serial original del movimiento se conserva
    siempre intacta.

    La Clave de Rastreo obtenida de la tabla SPEI se almacena
    exclusivamente en Movimiento.clave_rastreo.

    Si no hay coincidencia, esta función no se invoca y tanto
    la Referencia / Serial como el resto de los datos originales
    permanecen intactos.
    """

    if spei_row.tipo == "recibidos":
        enrich_movement_from_received_spei(
            movement,
            spei_row,
        )
    else:
        enrich_movement_from_sent_spei(
            movement,
            spei_row,
        )

    if spei_row.hora:
        movement.hora_operacion = (
            spei_row.hora
        )

    # Participante Emisor para recibidos y Participante Receptor
    # para enviados comparten la misma posición espacial.
    if spei_row.participante:
        movement.sucursal = (
            spei_row.participante
        )

    # --------------------------------------------------------
    # CLAVE DE RASTREO
    # --------------------------------------------------------
    #
    # La Clave de Rastreo se obtiene de la fila SPEI que ya fue
    # confirmada mediante las reglas de cruce existentes.
    #
    # IMPORTANTE:
    #
    # NO se modifica movement.referencia.
    #
    # Referencia / Serial pertenece al movimiento original y
    # debe conservarse exactamente como fue reconstruida desde
    # la tabla de movimientos.
    # --------------------------------------------------------

    tracking_key = compact_tracking_key(
        spei_row.clave_rastreo
    )

    if tracking_key:
        movement.clave_rastreo = tracking_key


def enrich_movements_from_spei(
    movements: List[Movimiento],
    spei_rows: Sequence[SpeiRow],
) -> None:
    if not movements or not spei_rows:
        return

    indexes = build_spei_match_indexes(spei_rows)

    # Primero se resuelven todas las coincidencias sobre el estado
    # original e inmutable del lote. Después se aplican los mapeos.
    # Así, el enriquecimiento de un movimiento nunca puede influir
    # en la resolución de ningún movimiento posterior.
    resolved_matches = [
        find_spei_match(movement, indexes)
        for movement in movements
    ]

    for movement, spei_match in zip(
        movements,
        resolved_matches,
    ):
        if spei_match is None:
            continue

        enrich_movement_from_spei(movement, spei_match)


# ============================================================
# FUNCIÓN PRINCIPAL PÚBLICA
# ============================================================

def extract_movimientos_words(
    words: List[Dict[str, Any]],
) -> List[Movimiento]:
    """
    Extrae movimientos HSBC y los enriquece con las tablas SPEI.

    Flujo:
        WORDS
          -> filtro de footer
          -> extracción independiente de tablas SPEI
          -> reconstrucción de movimientos
          -> cruce global contra todas las filas SPEI
          -> enriquecimiento de los modelos coincidentes

    Los movimientos sin coincidencia permanecen intactos.
    """

    if not words:
        return []

    filtered_words = filter_hsbc_footer_words(words)
    if not filtered_words:
        return []

    periodo_inicio, _ = extract_period_from_words(filtered_words)

    # Las tablas SPEI se extraen de todo el documento antes de
    # realizar cualquier cruce con los movimientos.
    spei_rows = extract_spei_rows(filtered_words)

    pages: Dict[int, List[Dict[str, Any]]] = {}

    for word in filtered_words:
        pages.setdefault(safe_page(word), []).append(word)

    movement_rows: List[MovementRow] = []

    for page in sorted(pages):
        movement_rows.extend(
            split_page_into_movement_rows(pages[page])
        )

    if not movement_rows:
        return []

    movements: List[Movimiento] = []

    for row in movement_rows:
        movement = movement_row_to_model(
            row,
            periodo_inicio,
        )

        if is_valid_movement(movement):
            movements.append(movement)

    enrich_movements_from_spei(
        movements,
        spei_rows,
    )

    return movements
