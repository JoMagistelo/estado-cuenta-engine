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
    r"^[\s.,;:|_]*"
    r"(?P<day>0?[1-9]|[12]\d|3[01])"
    r"[\s.,;:|_]*$"
)

# En OCR deteriorado, el día puede quedar unido al primer token
# del concepto. El caso observado es ``30_1.S.R.``. Se limita el
# respaldo al guion bajo para no interpretar referencias, fechas
# u otros números del concepto como días de movimiento.
DAY_WITH_INLINE_CONCEPT_PATTERN = re.compile(
    r"^[\s.,;:|]*"
    r"(?P<day>0?[1-9]|[12]\d|3[01])"
    r"_+"
    r"(?P<concept>\S.*)$",
    re.IGNORECASE,
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
SPEI_OCR_DATE_PATTERN = re.compile(
    r"^(?P<day>[A-Z0-9]{1,4})"
    r"[/-]"
    r"(?P<month>\d{1,2})"
    r"[/-]"
    r"(?P<year>\d{4})$"
)
TRAILING_DIGITS_PATTERN = re.compile(r"(\d+)\D*$")

# Se usan únicamente como identidades alternativas de cruce. La
# Clave de Rastreo publicada y la Referencia / Serial original nunca
# se reescriben con estas equivalencias.
TRACKING_OCR_DIGIT_TRANSLATION = str.maketrans(
    {
        "B": "8",
        "C": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "O": "0",
        "Q": "0",
        "S": "5",
    }
)

# La cuenta puede venir fusionada con la primera palabra del
# concepto en un único token PDF, por ejemplo:
#
#     000000000000000000CONCEPTO
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
    tokens = re.findall(r"[A-Z0-9]+", normalized)

    # Tesseract puede perder el borde izquierdo de la primera letra:
    # ``DETALLE`` -> ``ETALLE`` o ``TALLE``. La segunda señal sigue
    # siendo el término completo MOVIMIENTOS, por lo que la relajación
    # no convierte textos generales de la carátula en una tabla.
    has_detail_token = any(
        token in ("DETALLE", "ETALLE", "TALLE")
        for token in tokens
    )

    return has_detail_token and "MOVIMIENTOS" in tokens


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


def is_generic_spei_period_header_line(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Detecta el título de una tabla SPEI aunque el OCR pierda su tipo.

    En el layout degradado se observó ``Info ... eriodo`` para
    Enviados y ``... durante el eriodo`` para Recibidos. Se exige una
    fecha completa, la raíz de PERIODO y evidencia de título; una
    línea de periodo del resumen, por sí sola, no activa esta ruta.
    """

    normalized = normalize_text(line_text(line))
    if "ERIODO" not in normalized:
        return False
    if DATE_PATTERN.search(line_text(line)) is None:
        return False

    return any(
        token in normalized
        for token in ("INFO", "DURANTE", "DURTE", "RECIB", "ENVI")
    )


def infer_spei_section_type(
    lines: Sequence[Sequence[Dict[str, Any]]],
) -> Optional[str]:
    """Clasifica una tabla sin depender de su título OCR."""

    tracking_parts = []
    participant_parts = []

    for line in lines:
        tracking_parts.append(
            text_from_spei_line_column(line, "clave_rastreo")
        )
        participant_parts.append(
            text_from_spei_line_column(line, "participante")
        )

    tracking = compact_tracking_key(" ".join(tracking_parts)) or ""
    participants = normalize_text(" ".join(participant_parts))

    has_sent_key = "HSBC" in tracking or "HSB" in tracking
    has_received_key = "MBAN" in tracking

    if has_sent_key and not has_received_key:
        return "enviados"
    if has_received_key and not has_sent_key:
        return "recibidos"

    if "*" in participants and "TRANSFERENCIA" in normalize_text(
        " ".join(line_text(line) for line in lines)
    ):
        return "enviados"

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
        HSBC0123 + 45 -> HSBC012345
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


def tracking_key_suffix(value: Optional[str]) -> Optional[str]:
    """
    Separa de forma no ambigua los prefijos ``HSB`` y ``HSBC``.

    ``HSBC`` se prueba primero porque contiene por completo a
    ``HSB``. El valor devuelto conserva todos los ceros y letras del
    identificador; se usa para generar identidades de cruce, no para
    modificar el campo publicado.
    """

    compact = compact_tracking_key(value)
    if not compact:
        return None

    if compact.startswith("HSBC"):
        return compact[4:] or None
    if compact.startswith("HSB"):
        return compact[3:] or None

    return compact


def normalize_numeric_tracking_identity(
    value: Optional[str],
) -> Optional[str]:
    """Normaliza relleno izquierdo sin alterar el valor original."""

    if value is None:
        return None

    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return None

    normalized = digits.lstrip("0")

    return normalized or "0"


def tracking_numeric_identities(
    value: Optional[str],
) -> Tuple[str, ...]:
    """
    Crea identidades numéricas tolerantes para el cruce SPEI.

    Además de extraer sólo los dígitos, genera una segunda candidata
    reemplazando confusiones OCR frecuentes. Así, por ejemplo,
    ``HSB00C4201`` puede cruzarse con ``004201`` o ``4201`` sin
    cambiar ninguno de los dos valores almacenados.
    """

    suffix = tracking_key_suffix(value)
    if not suffix:
        return ()

    candidates = (
        suffix,
        suffix.translate(TRACKING_OCR_DIGIT_TRANSLATION),
    )
    identities: List[str] = []

    for candidate in candidates:
        identity = normalize_numeric_tracking_identity(candidate)
        if identity and identity not in identities:
            identities.append(identity)

    return tuple(identities)


def normalize_spei_reference(value: Optional[str]) -> Optional[str]:
    """
    Reconstruye el Número de Referencia conservando sus ceros.

    Ejemplo:
        000000000000 + 00012345
        -> 00000000000000012345
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

    Ejemplo sintético:
        ABONO SPEI DEMO DC000000000 00012345
        -> 00012345
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

    Ejemplo sintético:
        00000001\n7654321 -> 7654321
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


def extract_movement_tracking_keys(
    movement_reference: Optional[str],
) -> Tuple[str, ...]:
    """
    Devuelve todas las candidatas útiles sin alterar la referencia.

    En OCR inclinado los dos renglones de Referencia / Serial pueden
    llegar invertidos. Cuando hay más de un renglón se descarta el
    componente serial de ocho dígitos y se prueban los demás; en el
    layout normal el resultado continúa siendo únicamente el renglón
    inferior histórico. La regla usa la estructura del campo y no un
    prefijo observado en una cuenta específica.
    """

    if movement_reference is None:
        return ()

    raw_values = [
        part.strip()
        for part in re.split(r"[\r\n]+", str(movement_reference))
        if part.strip()
    ]
    candidates: List[str] = []

    has_multiple_components = len(raw_values) > 1

    for raw_value in reversed(raw_values):
        compact = compact_tracking_key(raw_value)
        if not compact:
            continue
        if has_multiple_components and re.fullmatch(r"\d{8}", compact):
            continue

        normalized = normalize_tracking_key(compact)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    if candidates:
        return tuple(candidates)

    historical = extract_movement_tracking_key(movement_reference)

    return (historical,) if historical else ()


# ============================================================
# EXTRACTORES DE CAMPOS SPEI
# ============================================================

def normalize_spei_date_token(value: Any) -> Optional[str]:
    """Corrige únicamente confusiones OCR inequívocas del día."""

    token = normalize_text(value).replace(" ", "")
    token = re.sub(r"[^A-Z0-9/-]", "", token)
    match = SPEI_OCR_DATE_PATTERN.fullmatch(token)
    if match is None:
        return None

    raw_day = match.group("day")

    # Confusiones frecuentes limitadas a la celda de fecha. Las
    # formas 80/81 y B0/B1 corresponden a 30/31 por la silueta del
    # glifo 3; D/O/Q al inicio corresponden a un cero inicial.
    if (
        len(raw_day) == 2
        and raw_day[0] in ("8", "B")
        and raw_day[1] in ("0", "1")
    ):
        day_digits = "3" + raw_day[1]
    else:
        translated = raw_day.translate(
            str.maketrans(
                {
                    "D": "0",
                    "O": "0",
                    "P": "0",
                    "Q": "0",
                    "I": "1",
                    "L": "1",
                    "Z": "2",
                }
            )
        )
        day_digits = re.sub(r"\D", "", translated)

        if raw_day.isalpha() and len(day_digits) == 1:
            return None

    if not day_digits:
        return None

    # Una marca OCR puede quedar pegada a la izquierda, por ejemplo
    # ``123/12/2024`` para ``23/12/2024``. Sólo se descarta el prefijo
    # si los dos últimos dígitos forman un día calendario válido.
    day_candidates = [day_digits]
    if len(day_digits) > 2:
        day_candidates.append(day_digits[-2:])

    day_value: Optional[int] = None

    for candidate in day_candidates:
        value_int = int(candidate)
        if DAY_MIN <= value_int <= DAY_MAX:
            day_value = value_int
            break

    if day_value is None:
        return None

    try:
        parsed = date(
            int(match.group("year")),
            int(match.group("month")),
            day_value,
        )
    except ValueError:
        return None

    return parsed.strftime("%d/%m/%Y")


def extract_spei_date(row: SpeiRow) -> Optional[str]:
    value = text_from_spei_box(
        row,
        BOX_SPEI_FECHA,
        padding_x=5.0,
    )
    if not value:
        return None

    tokens = value.split()

    # Primero se prueba la celda completa. Esto recompone fechas que
    # el OCR separó dentro de la misma columna, por ejemplo
    # ``L1`` + ``7/12/2024`` o ``P2/1`` + ``2/2024``.
    normalized_compact = normalize_spei_date_token(
        "".join(tokens)
    )
    if normalized_compact:
        return normalized_compact

    for token in tokens:
        normalized = normalize_spei_date_token(token)
        if normalized:
            return normalized

    # El día también puede dividirse en dos words: ``L1`` +
    # ``7/12/2024``. Se reconstruye sólo dentro de la columna Fecha.
    for first, second in zip(tokens, tokens[1:]):
        first_digits = re.sub(r"\D", "", first)
        if not first_digits:
            continue

        normalized = normalize_spei_date_token(
            first_digits[-1] + second
        )
        if normalized:
            return normalized

    return None


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
    candidates: List[Tuple[Tuple[int, int, int], float]] = []

    for line in row.lines:
        for word in line:
            # Propiedad exclusiva de columna: un fragmento numérico
            # de Clave de Rastreo situado junto al borde (p. ej. 55)
            # no se concatena al importe 1,800.00.
            if primary_spei_column(word) != "monto":
                continue

            text = clean_word_text(word.get("text", ""))
            normalized = (
                text.replace(",", "").replace("$", "").strip()
            )
            if not re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
                continue

            try:
                parsed = float(normalized)
            except ValueError:
                continue

            score = (
                1 if "." in normalized else 0,
                1 if "," in text else 0,
                len(re.sub(r"\D", "", normalized)),
            )
            candidates.append((score, parsed))

    if not candidates:
        return 0.0

    candidates.sort(key=lambda item: item[0], reverse=True)

    return candidates[0][1]


def extract_received_date_from_tracking_key(
    value: Optional[str],
) -> Optional[str]:
    """Lee YYMMDD del segmento estable de una clave MBAN recibida."""

    compact = compact_tracking_key(value)
    if not compact or not compact.startswith("MBAN"):
        return None

    match = re.search(
        r"^MBAN[O0I1]{3,5}(?P<date>\d{6})",
        compact,
    )
    if match is None:
        return None

    raw_date = match.group("date")

    try:
        parsed = date(
            2000 + int(raw_date[:2]),
            int(raw_date[2:4]),
            int(raw_date[4:6]),
        )
    except ValueError:
        return None

    return parsed.strftime("%d/%m/%Y")


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

    if row.tipo == "recibidos":
        tracking_date = extract_received_date_from_tracking_key(
            row.clave_rastreo
        )
        if tracking_date:
            row.fecha = tracking_date


# ============================================================
# RECONSTRUCCIÓN DE FILAS SPEI
# ============================================================

def text_from_spei_line_column(
    line: Sequence[Dict[str, Any]],
    column_name: str,
) -> str:
    selected = [
        word
        for word in line
        if primary_spei_column(word) == column_name
    ]
    selected.sort(key=lambda word: safe_float(word.get("x0", 0.0)))

    return " ".join(
        clean_word_text(word.get("text", ""))
        for word in selected
        if clean_word_text(word.get("text", ""))
    ).strip()


def line_has_spei_row_structure(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Reconoce una fila aunque Tesseract dañe u omita su fecha.

    La combinación de hora, monto, clave y número de referencia es
    suficientemente específica para separar operaciones consecutivas
    sin interpretar como fila una línea de continuación.
    """

    time_text = text_from_spei_line_column(line, "hora")
    amount_text = text_from_spei_line_column(line, "monto")
    tracking_text = text_from_spei_line_column(line, "clave_rastreo")
    reference_text = text_from_spei_line_column(
        line,
        "numero_referencia",
    )
    account_text = text_from_spei_line_column(line, "cuenta")
    participant_text = text_from_spei_line_column(
        line,
        "participante",
    )

    has_time = any(
        TIME_PATTERN.fullmatch(token)
        for token in time_text.split()
    )
    has_amount = any(
        MONEY_PATTERN.fullmatch(token)
        for token in amount_text.split()
        if token != "$"
    )
    tracking_key = compact_tracking_key(tracking_text)
    reference_digits = re.sub(r"\D", "", reference_text)

    has_complete_tracking = (
        tracking_key is not None
        and len(tracking_key) >= 4
        and bool(re.search(r"\d", tracking_key))
    )
    has_strong_row_without_tracking = (
        len(re.sub(r"\D", "", account_text)) >= 10
        and bool(participant_text.strip())
    )

    return (
        has_time
        and has_amount
        and (has_complete_tracking or has_strong_row_without_tracking)
        and len(reference_digits) >= 4
    )


def line_starts_spei_row(
    line: Sequence[Dict[str, Any]],
) -> bool:
    date_text = text_from_spei_line_column(line, "fecha")
    if normalize_spei_date_token(date_text):
        return True

    for word in line:
        if not word_belongs_to_spei_column(
            word,
            BOX_SPEI_FECHA,
            padding_x=5.0,
        ):
            continue

        text = clean_word_text(word.get("text", ""))
        if normalize_spei_date_token(text):
            return True

    return line_has_spei_row_structure(line)


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


def line_has_spei_main_payload(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """Detecta datos principales desplazados antes de su fecha."""

    for word in line:
        owner = primary_spei_column(word)
        text = clean_word_text(word.get("text", ""))
        compact = compact_tracking_key(text) or ""
        digits = re.sub(r"\D", "", text)

        if owner == "cuenta" and len(digits) >= 10:
            return True
        if owner == "monto" and MONEY_PATTERN.fullmatch(text):
            return True
        if owner == "clave_rastreo" and compact.startswith(
            ("HSB", "MBAN")
        ):
            return True

    return False


def line_starts_degraded_spei_row(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """Reconoce una primera fila cuya fecha y clave perdieron prefijo."""

    participant = text_from_spei_line_column(line, "participante")
    account = text_from_spei_line_column(line, "cuenta")
    concept = text_from_spei_line_column(line, "concepto")
    amount = text_from_spei_line_column(line, "monto")

    return (
        "*" in participant
        and len(re.sub(r"\D", "", account)) >= 10
        and bool(concept.strip())
        and any(
            MONEY_PATTERN.fullmatch(token)
            for token in amount.split()
            if token != "$"
        )
    )


def split_spei_precursor_line(
    line: Sequence[Dict[str, Any]],
    has_current_row: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Separa columnas adelantadas de continuaciones de la fila previa.

    En OCR inclinado una misma línea lógica puede contener
    ``MEXICO Express`` de la fila anterior y cuenta/monto/clave de la
    siguiente. La propiedad exclusiva de columna permite dividirla.
    """

    if not has_current_row:
        return list(line), []

    precursor: List[Dict[str, Any]] = []
    continuation: List[Dict[str, Any]] = []

    for word in line:
        owner = primary_spei_column(word)
        normalized = normalize_text(word.get("text", ""))

        belongs_to_next = owner in (
            "cuenta",
            "concepto",
            "monto",
            "clave_rastreo",
            "numero_referencia",
        )

        if owner == "contraparte" and "TRANSFERENCIA" in normalized:
            belongs_to_next = True

        if belongs_to_next:
            precursor.append(word)
        else:
            continuation.append(word)

    return precursor, continuation


def split_page_into_spei_rows(
    lines: Sequence[Sequence[Dict[str, Any]]],
    section_type: str,
    recover_precursors: bool = False,
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
    pending_precursors: List[List[Dict[str, Any]]] = []

    for index, line in enumerate(lines):
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

        starts_row = line_starts_spei_row(line) or (
            recover_precursors and line_starts_degraded_spei_row(line)
        )

        if starts_row:
            if current_row is not None:
                populate_spei_row(current_row)
                rows.append(current_row)

            current_row = SpeiRow(
                tipo=section_type,
                page=safe_page(line[0]),
                lines=[*pending_precursors, list(line)],
            )
            pending_precursors = []
            continue

        if recover_precursors and line_has_spei_main_payload(line):
            next_line = next(
                (
                    candidate
                    for candidate in lines[index + 1:]
                    if candidate
                ),
                None,
            )

            if (
                next_line is not None
                and safe_page(next_line[0]) == safe_page(line[0])
                and line_starts_spei_row(next_line)
                and 0.0
                <= line_center_y(next_line) - line_center_y(line)
                <= 13.0
            ):
                precursor, continuation = split_spei_precursor_line(
                    line,
                    current_row is not None,
                )

                if current_row is not None and continuation:
                    current_row.lines.append(continuation)

                if precursor:
                    pending_precursors.append(precursor)
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

        if is_generic_spei_period_header_line(line):
            if current_type is not None and current_lines:
                sections.append((current_type, current_lines))

            current_type = "unknown"
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
        recover_precursors = section_type == "unknown"

        if section_type == "unknown":
            inferred_type = infer_spei_section_type(section_lines)
            if inferred_type is None:
                continue
            section_type = inferred_type

        rows.extend(
            split_page_into_spei_rows(
                section_lines,
                section_type,
                recover_precursors=recover_precursors,
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

    # Sólo se activa cuando existe evidencia estructural de una
    # fila real, pero Tesseract omitió alguno de sus campos. Los
    # movimientos normales conservan exactamente la ruta histórica.
    partial_recovery: bool = False
    movement_header_confirmed: bool = False

    referencia_serial_superior: Optional[str] = None
    referencia_serial_inferior: Optional[str] = None
    referencia_serial_completo: Optional[str] = None
    referencia_principal: Optional[str] = None


# ============================================================
# DÍA Y RECONSTRUCCIÓN DE MOVIMIENTOS
# ============================================================


def split_day_and_inline_concept(
    value: Any,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Separa el día y, si existe, el concepto unido por OCR.

    Tesseract puede conservar puntuación de la cuadrícula junto al
    número, por ejemplo ``11.`` o ``|14``. También puede producir
    ``30_1.S.R.``; en ese único formato se conserva ``1.S.R.`` como
    parte del concepto.
    """

    text = clean_word_text(value)
    if not text:
        return None, None

    match = DAY_OCR_PATTERN.fullmatch(text)
    inline_concept: Optional[str] = None

    if match is None:
        match = DAY_WITH_INLINE_CONCEPT_PATTERN.fullmatch(text)
        if match is None:
            return None, None

        inline_concept = clean_word_text(
            match.group("concept")
        ) or None

    try:
        day = int(match.group("day"))
    except (TypeError, ValueError):
        return None, None

    if not DAY_MIN <= day <= DAY_MAX:
        return None, None

    return day, inline_concept


def parse_day_token(value: Any) -> Optional[int]:
    day, _ = split_day_and_inline_concept(value)

    return day


def extract_day_from_line(
    line: Sequence[Dict[str, Any]],
) -> Optional[int]:
    day_words = sorted(
        (
            word
            for word in line
            if word_inside_box(
                word,
                BOX_DAY,
                padding_x=7.0,
                padding_y=3.0,
            )
            and safe_float(word.get("x1", 0.0)) <= 65.0
        ),
        key=lambda word: safe_float(word.get("x0", 0.0)),
    )

    # En páginas OCR degradadas HSBC puede entregar dos capas para
    # el día: una word ancha y corrupta y, encima, los dos dígitos
    # correctos por separado (``12`` + ``1`` + ``3``). Los dos
    # fragmentos unitarios situados más a la derecha son la lectura
    # más precisa de esa celda.
    single_digit_fragments: List[str] = []

    for word in day_words:
        raw = clean_word_text(word.get("text", ""))
        digits = re.sub(r"\D", "", raw)

        if len(digits) == 1:
            single_digit_fragments.append(digits)

    if len(single_digit_fragments) >= 2:
        composite = int("".join(single_digit_fragments[-2:]))
        if DAY_MIN <= composite <= DAY_MAX:
            return composite

    # Otra variante observada comprime el primer dígito en una word
    # diminuta como ``21``/``2!`` y conserva el segundo por separado.
    # Sólo se acepta cuando ambas cajas son contiguas en la columna
    # Día; no se toman números del concepto.
    if len(day_words) >= 2:
        for first, second in zip(day_words, day_words[1:]):
            first_digits = re.sub(
                r"\D",
                "",
                clean_word_text(first.get("text", "")),
            )
            second_digits = re.sub(
                r"\D",
                "",
                clean_word_text(second.get("text", "")),
            )
            gap = (
                safe_float(second.get("x0", 0.0))
                - safe_float(first.get("x1", 0.0))
            )
            first_width = (
                safe_float(first.get("x1", 0.0))
                - safe_float(first.get("x0", 0.0))
            )

            if (
                len(first_digits) == 2
                and len(second_digits) == 1
                and first_width <= 6.0
                and gap <= 2.5
            ):
                composite = int(first_digits[0] + second_digits)
                if DAY_MIN <= composite <= DAY_MAX:
                    return composite

    # ``E...7`` es una confusión localizada del glifo 2 en la celda
    # Día. Se exige un segundo dígito y estructura financiera real
    # para que esta equivalencia no se use sobre texto ordinario.
    for word in day_words:
        raw = normalize_text(word.get("text", ""))
        translated = raw.replace("E", "2")
        digits = re.sub(r"\D", "", translated)

        if (
            raw.startswith("E")
            and len(digits) == 2
            and line_has_transaction_amount(line)
        ):
            candidate = int(digits)
            if DAY_MIN <= candidate <= DAY_MAX:
                return candidate

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


def is_plausible_money_token(value: Any) -> bool:
    """
    Reconoce una word que puede representar un importe real.

    Los dígitos aislados que Tesseract genera sobre el borde derecho
    de la tabla (``3``, ``5``, ``8``) no se consideran dinero. Sí se
    conservan importes con decimales, separador de miles, símbolo de
    moneda o enteros de al menos dos dígitos.
    """

    text = clean_word_text(value)
    if not text or text == "$":
        return False

    normalized = (
        text
        .replace(",", "")
        .replace("$", "")
        .strip()
    )

    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
        return False

    digits = re.sub(r"\D", "", normalized)

    return (
        "." in normalized
        or "," in text
        or "$" in text
        or len(digits) >= 2
        or normalized == "0"
    )


def line_has_primary_money(
    line: Sequence[Dict[str, Any]],
    column_name: str,
) -> bool:
    return any(
        primary_movement_column(word) == column_name
        and is_plausible_money_token(
            word.get("text", "")
        )
        for word in line
    )


def line_has_transaction_amount(
    line: Sequence[Dict[str, Any]],
) -> bool:
    return (
        line_has_primary_money(line, "cargo")
        or line_has_primary_money(line, "abono")
    )


def line_has_balance_amount(
    line: Sequence[Dict[str, Any]],
) -> bool:
    return line_has_primary_money(line, "saldo")


def row_has_transaction_amount(row: MovementRow) -> bool:
    return any(
        line_has_transaction_amount(line)
        for line in row.lines
    )


def line_has_orphan_financial_evidence(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Detecta una fila financiera cuyo día/concepto desapareció.

    La señal es deliberadamente estricta: deben coexistir un importe
    de cargo/abono y el saldo. Así no se convierten referencias o
    números corruptos aislados en movimientos parciales.
    """

    if find_day_word_in_line(line) is not None:
        return False

    if not line_has_transaction_amount(line):
        return False

    return line_has_balance_amount(line)


def line_is_reference_continuation(
    line: Sequence[Dict[str, Any]],
) -> bool:
    return (
        find_day_word_in_line(line) is None
        and line_has_numeric_reference(line)
        and not line_has_transaction_amount(line)
        and not line_has_balance_amount(line)
    )


def line_is_low_information_noise(
    line: Sequence[Dict[str, Any]],
) -> bool:
    meaningful_tokens = [
        normalize_text(
            word.get("text", "")
        )
        for word in line
        if re.search(
            r"[A-Z0-9]{3,}",
            normalize_text(
                word.get("text", "")
            ),
        )
    ]

    return not meaningful_tokens


def line_is_concept_continuation(
    line: Sequence[Dict[str, Any]],
) -> bool:
    if (
        find_day_word_in_line(line) is not None
        or line_has_transaction_amount(line)
        or line_has_balance_amount(line)
    ):
        return False

    meaningful_words = [
        word
        for word in line
        if re.search(
            r"[A-Z0-9]{3,}",
            normalize_text(
                word.get("text", "")
            ),
        )
    ]

    if not meaningful_words:
        return False

    return all(
        primary_movement_column(word)
        in (
            "concepto",
            "referencia_serial",
            None,
        )
        for word in meaningful_words
    )


def should_attach_continuation_line(
    row: MovementRow,
    line: Sequence[Dict[str, Any]],
) -> bool:
    if not row.lines:
        return False

    vertical_gap = (
        line_center_y(line)
        - line_center_y(row.lines[0])
    )

    if vertical_gap < 0.0 or vertical_gap > MOVEMENT_ROW_MAX_GAP:
        return False

    if line_is_reference_continuation(line):
        return True

    # Algunos OCR separan el importe del renglón que contiene el día.
    if (
        not row_has_transaction_amount(row)
        and line_has_transaction_amount(line)
    ):
        return True

    return line_is_concept_continuation(line)


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

    for word in line:
        text = clean_word_text(
            word.get("text", "")
        )

        if not is_plausible_money_token(text):
            continue

        if primary_movement_column(word) in (
            "cargo",
            "abono",
            "saldo",
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


def line_confirms_movement_table(
    line: Sequence[Dict[str, Any]],
) -> bool:
    """
    Permite iniciar sin encabezado sólo ante una fila financiera real.

    Esto evita que el número de una dirección en la carátula active la
    tabla y que una línea posterior de RFC cierre la página antes del
    primer movimiento.
    """

    return (
        line_starts_movement(line)
        and line_has_numeric_reference(line)
        and line_has_transaction_amount(line)
        and line_has_balance_amount(line)
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
    pending_orphan_lines: List[List[Dict[str, Any]]] = []
    pending_orphan_page: Optional[int] = None
    table_started = False
    movement_header_confirmed = False

    def flush_current_row() -> None:
        nonlocal current_row

        if current_row is not None:
            rows.append(current_row)
            current_row = None

    def flush_pending_orphan() -> None:
        nonlocal pending_orphan_lines
        nonlocal pending_orphan_page

        if (
            pending_orphan_lines
            and movement_header_confirmed
        ):
            rows.append(
                MovementRow(
                    page=(
                        pending_orphan_page
                        if pending_orphan_page is not None
                        else 1
                    ),
                    lines=pending_orphan_lines,
                    partial_recovery=True,
                    movement_header_confirmed=(
                        movement_header_confirmed
                    ),
                )
            )

        pending_orphan_lines = []
        pending_orphan_page = None

    for line in lines:
        if not line:
            continue

        page = safe_page(line[0])

        if is_movement_header_line(line):
            flush_current_row()
            flush_pending_orphan()
            table_started = True
            movement_header_confirmed = True
            continue

        if is_column_header_line(line):
            table_started = True
            movement_header_confirmed = True
            continue

        if is_footer_like_line(line):
            if table_started:
                flush_current_row()
                flush_pending_orphan()
                break
            continue

        if table_started and (
            is_table_breaker_line(line)
            or is_spei_information_header_line(line)
        ):
            flush_current_row()
            flush_pending_orphan()
            break

        if line_starts_movement(line):
            if (
                not table_started
                and not line_confirms_movement_table(line)
            ):
                continue

            if not table_started:
                movement_header_confirmed = True

            if pending_orphan_lines:
                if (
                    line_has_transaction_amount(line)
                    or line_has_balance_amount(line)
                ):
                    # La fila pendiente ya contiene un movimiento
                    # financiero completo; el día actual pertenece
                    # al siguiente movimiento.
                    flush_pending_orphan()
                else:
                    # El OCR adelantó importe/saldo respecto al día.
                    # Se unen sin alterar el orden semántico: la línea
                    # con día queda al frente para construir la fecha.
                    flush_current_row()
                    current_row = MovementRow(
                        page=page,
                        lines=[
                            list(line),
                            *pending_orphan_lines,
                        ],
                        movement_header_confirmed=(
                            movement_header_confirmed
                        ),
                    )
                    pending_orphan_lines = []
                    pending_orphan_page = None
                    table_started = True
                    continue

            flush_current_row()

            current_row = MovementRow(
                page=page,
                lines=[list(line)],
                movement_header_confirmed=(
                    movement_header_confirmed
                ),
            )
            table_started = True
            continue

        if line_has_orphan_financial_evidence(line):
            if (
                current_row is not None
                and not row_has_transaction_amount(current_row)
            ):
                current_row.lines.append(list(line))
                continue

            flush_current_row()
            flush_pending_orphan()
            pending_orphan_lines = [list(line)]
            pending_orphan_page = page
            continue

        if not table_started:
            continue

        if pending_orphan_lines:
            vertical_gap = (
                line_center_y(line)
                - line_center_y(pending_orphan_lines[0])
            )

            if (
                0.0 <= vertical_gap <= MOVEMENT_ROW_MAX_GAP
                and (
                    line_is_reference_continuation(line)
                    or line_is_concept_continuation(line)
                )
            ):
                pending_orphan_lines.append(list(line))
                continue

            if line_is_low_information_noise(line):
                continue

            flush_pending_orphan()
            continue

        if current_row is not None:
            if should_attach_continuation_line(
                current_row,
                line,
            ):
                current_row.lines.append(list(line))
                continue

            if line_is_low_information_noise(line):
                continue

            # Una línea ajena ya no contamina el movimiento vigente.
            # La tabla permanece activa para que un día posterior pueda
            # iniciar otra fila en la misma página.
            flush_current_row()

    flush_current_row()
    flush_pending_orphan()

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
    parts = []

    # Se respeta primero el orden de renglones y después el orden X.
    # Ordenar todas las words por ``top`` mezclaba palabras de una
    # misma línea cuando el OCR las entregaba ligeramente inclinadas.
    ordered_lines = sorted(
        row.lines,
        key=line_center_y,
    )

    for line in ordered_lines:
        day_word = find_day_word_in_line(line)
        day_zone_words = {
            id(word)
            for word in line
            if (
                safe_float(word.get("x0", 0.0)) >= BOX_DAY[0] - 7.0
                and safe_float(word.get("x1", 0.0)) <= 65.0
            )
        }

        for word in sorted(
            line,
            key=lambda item: safe_float(
                item.get("x0", 0.0)
            ),
        ):
            if not word_inside_box(
                word,
                BOX_CONCEPTO,
                padding_x=5.0,
                padding_y=COLUMN_PADDING_Y,
            ):
                continue

            text = clean_word_text(
                word.get("text", "")
            )
            if not text:
                continue

            if id(word) in day_zone_words:
                if word is day_word:
                    _, inline_concept = (
                        split_day_and_inline_concept(text)
                    )

                    if inline_concept:
                        parts.append(inline_concept)

                continue

            if day_word is not None and word is day_word:
                _, inline_concept = (
                    split_day_and_inline_concept(text)
                )

                if inline_concept:
                    parts.append(inline_concept)

                continue

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

def movement_column_name_from_box(
    box: Tuple[float, float, float, float],
) -> Optional[str]:
    if box == BOX_CARGO:
        return "cargo"
    if box == BOX_ABONO:
        return "abono"
    if box == BOX_SALDO:
        return "saldo"

    return None


def parse_money_from_primary_line(
    line: Sequence[Dict[str, Any]],
    column_name: str,
) -> Optional[float]:
    candidates = []

    for word in line:
        if primary_movement_column(word) != column_name:
            continue

        text = clean_word_text(
            word.get("text", "")
        )

        if not is_plausible_money_token(text):
            continue

        normalized = (
            text
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

        try:
            value = float(normalized)
        except ValueError:
            continue

        digits = re.sub(r"\D", "", normalized)
        score = (
            1 if "." in normalized else 0,
            1 if "," in text else 0,
            1 if "$" in text else 0,
            len(digits),
        )

        candidates.append(
            (
                score,
                safe_float(
                    word.get("x0", 0.0)
                ),
                value,
            )
        )

    if not candidates:
        return None

    # Un importe con centavos y separador de miles tiene prioridad
    # sobre los dígitos espurios que aparecen al borde de la tabla.
    candidates.sort(
        key=lambda item: (
            item[0],
            -item[1],
        ),
        reverse=True,
    )

    return candidates[0][2]


def parse_money_words_optional(
    row: MovementRow,
    box: Tuple[float, float, float, float],
) -> Optional[float]:
    column_name = movement_column_name_from_box(box)
    if column_name is None:
        return None

    for line in sorted(
        row.lines,
        key=line_center_y,
    ):
        value = parse_money_from_primary_line(
            line,
            column_name,
        )

        if value is not None:
            return value

    return None


def parse_money_words(
    row: MovementRow,
    box: Tuple[float, float, float, float],
) -> float:
    value = parse_money_words_optional(
        row,
        box,
    )

    return value if value is not None else 0.0


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
    concepto = extract_concepto(row)
    raw_cargo = parse_money_words_optional(
        row,
        BOX_CARGO,
    )
    raw_abono = parse_money_words_optional(
        row,
        BOX_ABONO,
    )
    raw_saldo = parse_money_words_optional(
        row,
        BOX_SALDO,
    )

    referencia_principal = extract_referencia(row)
    referencia_completa = extract_referencia_completa(row)
    referencia_modelo = (
        referencia_completa
        or referencia_principal
        or None
    )

    # Un movimiento con día, concepto y referencia es recuperable
    # aunque Tesseract haya omitido por completo sus importes. Esta
    # vía exige que el encabezado real de movimientos haya sido visto,
    # por lo que no afecta renglones numéricos del resumen financiero.
    if (
        row.movement_header_confirmed
        and day is not None
        and concepto
        and referencia_modelo
        and raw_cargo is None
        and raw_abono is None
    ):
        row.partial_recovery = True

    if row.partial_recovery:
        fecha_operacion = (
            build_operation_date(
                day,
                periodo_inicio,
            )
            if day is not None
            else None
        )
        concepto_modelo = concepto or None
        cargo = raw_cargo
        abono = raw_abono
        saldo_operacion = raw_saldo
    else:
        fecha_operacion = build_operation_date(
            day,
            periodo_inicio,
        )
        concepto_modelo = concepto
        cargo = (
            raw_cargo
            if raw_cargo is not None
            else 0.0
        )
        abono = (
            raw_abono
            if raw_abono is not None
            else 0.0
        )
        saldo_operacion = (
            raw_saldo
            if raw_saldo is not None
            else 0.0
        )

    return Movimiento(
        fecha_operacion=fecha_operacion,
        fecha_liquidacion=None,
        concepto=concepto_modelo,
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
        concepto_original=concepto_modelo,
    )


def is_valid_movement(
    movement: Movimiento,
    allow_partial: bool = False,
) -> bool:
    if allow_partial:
        has_financial_data = any(
            value is not None
            for value in (
                movement.cargo,
                movement.abono,
                movement.saldo_operacion,
            )
        )

        has_complete_identity = all(
            (
                movement.fecha_operacion,
                movement.concepto,
                movement.referencia,
            )
        )

        has_any_identity = any(
            (
                movement.fecha_operacion,
                movement.concepto,
                movement.referencia,
            )
        )

        return (
            has_complete_identity
            or (
                has_financial_data
                and has_any_identity
            )
        )

    if not movement.fecha_operacion:
        return False
    if not movement.concepto:
        return False
    if movement.cargo == 0.0 and movement.abono == 0.0:
        return False

    return True


def movement_accounting_delta(
    movement: Movimiento,
) -> Optional[float]:
    """Devuelve Abono - Cargo cuando el sentido es recuperable."""

    cargo = movement.cargo
    abono = movement.abono

    if cargo is None and abono is None:
        return None

    return float(abono or 0.0) - float(cargo or 0.0)


def extract_statement_opening_balance(
    words: Sequence[Dict[str, Any]],
) -> Optional[float]:
    """
    Recupera el saldo inicial como frontera contable del primer
    movimiento.

    Se exige el ancla completa SALDO + INICIAL y un importe en la
    columna derecha. La función no depende de una página o altura
    fija y sólo se usa para comprobar filas parciales del detalle.
    """

    candidates: List[Tuple[int, float, float]] = []

    for line in group_words_into_lines(words):
        normalized = normalize_text(line_text(line))
        if "SALDO" not in normalized or "INICIAL" not in normalized:
            continue

        value = parse_money_from_primary_line(line, "saldo")
        if value is None:
            continue

        candidates.append(
            (
                safe_page(line[0]),
                line_center_y(line),
                value,
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))

    return candidates[0][2]


def malformed_money_token_matches_expected(
    row: MovementRow,
    column_name: str,
    expected_amount: float,
) -> bool:
    """
    Detecta únicamente el OCR anómalo con cuatro dígitos después de
    la coma de miles, por ejemplo ``1,6563.20``.

    No corrige por formato solamente: el valor esperado debe poder
    obtenerse eliminando exactamente un único dígito OCR del entero,
    conservando intactos los centavos.
    """

    expected_text = f"{abs(expected_amount):.2f}"
    expected_integer, expected_fraction = expected_text.split(".")

    pattern = re.compile(
        r"^\$?\s*(\d{1,3}),(\d{4})\.(\d{2})$"
    )

    for line in row.lines:
        for word in line:
            if primary_movement_column(word) != column_name:
                continue

            match = pattern.fullmatch(
                clean_word_text(word.get("text", ""))
            )
            if match is None:
                continue

            raw_integer = match.group(1) + match.group(2)

            if match.group(3) != expected_fraction:
                continue
            if len(raw_integer) != len(expected_integer) + 1:
                continue

            if any(
                raw_integer[:index] + raw_integer[index + 1:]
                == expected_integer
                for index in range(len(raw_integer))
            ):
                return True

    return False


def repair_malformed_transaction_amounts(
    movements: Sequence[Movimiento],
    rows: Sequence[MovementRow],
) -> None:
    """
    Repara un importe sólo cuando coinciden tres evidencias:

      1. el token monetario tiene la agrupación OCR imposible;
      2. los saldos anterior/actual determinan el importe correcto;
      3. el movimiento siguiente confirma independientemente el saldo
         actual.

    Los importes con formato válido conservan la ruta histórica.
    """

    limit = min(len(movements), len(rows))

    for index in range(1, limit - 1):
        movement = movements[index]
        previous = movements[index - 1]
        following = movements[index + 1]

        if (
            movement.saldo_operacion is None
            or previous.saldo_operacion is None
            or following.saldo_operacion is None
        ):
            continue

        try:
            current_balance = float(movement.saldo_operacion)
            previous_balance = float(previous.saldo_operacion)
            cargo = float(movement.cargo or 0.0)
            abono = float(movement.abono or 0.0)
        except (TypeError, ValueError):
            continue

        if cargo > 0.0 and abono == 0.0:
            column_name = "cargo"
            expected_amount = round(
                previous_balance - current_balance,
                2,
            )
        elif abono > 0.0 and cargo == 0.0:
            column_name = "abono"
            expected_amount = round(
                current_balance - previous_balance,
                2,
            )
        else:
            continue

        if expected_amount <= 0.0:
            continue

        if not malformed_money_token_matches_expected(
            rows[index],
            column_name,
            expected_amount,
        ):
            continue

        following_delta = movement_accounting_delta(following)
        if following_delta is None:
            continue

        try:
            confirmed_current_balance = round(
                float(following.saldo_operacion) - following_delta,
                2,
            )
        except (TypeError, ValueError):
            continue

        if abs(confirmed_current_balance - current_balance) >= 0.01:
            continue

        if column_name == "cargo":
            movement.cargo = expected_amount
        else:
            movement.abono = expected_amount


def balance_is_obviously_truncated(
    observed: float,
    expected: float,
) -> bool:
    """
    Detecta únicamente pérdidas claras de uno o más dígitos.

    No se corrigen diferencias ordinarias con una sola evidencia;
    se exige que ambos saldos difieran por más de un orden práctico
    de magnitud (menos de 20 % o más de cinco veces).
    """

    if abs(expected) < 0.01:
        return False

    ratio = abs(observed) / abs(expected)

    return ratio < 0.20 or ratio > 5.0


def repair_partial_movement_financials(
    movements: Sequence[Movimiento],
    rows: Sequence[MovementRow],
    opening_balance: Optional[float],
) -> None:
    """
    Completa únicamente filas marcadas como recuperación parcial.

    Una corrección requiere dos fronteras independientes: el saldo
    anterior (o el saldo inicial impreso) y el saldo del movimiento
    siguiente junto con su importe. Esto permite recuperar la fila
    inicial aun cuando Tesseract haya omitido cargo y saldo, y una
    fila interna cuyos importes hayan perdido varios dígitos.
    """

    limit = min(len(movements), len(rows))

    for index in range(limit):
        row = rows[index]
        if not row.partial_recovery:
            continue

        movement = movements[index]
        previous_balance: Optional[float] = None

        if index == 0:
            previous_balance = opening_balance
        else:
            previous = movements[index - 1].saldo_operacion
            if previous is not None:
                try:
                    previous_balance = float(previous)
                except (TypeError, ValueError):
                    pass

        expected_current: Optional[float] = None

        if index + 1 < limit:
            following = movements[index + 1]
            following_delta = movement_accounting_delta(following)

            if (
                following.saldo_operacion is not None
                and following_delta is not None
            ):
                try:
                    expected_current = round(
                        float(following.saldo_operacion)
                        - following_delta,
                        2,
                    )
                except (TypeError, ValueError):
                    pass

        observed_balance: Optional[float] = None
        if movement.saldo_operacion is not None:
            try:
                observed_balance = float(movement.saldo_operacion)
            except (TypeError, ValueError):
                pass

        if expected_current is not None and (
            observed_balance is None
            or balance_is_obviously_truncated(
                observed_balance,
                expected_current,
            )
        ):
            movement.saldo_operacion = expected_current
            observed_balance = expected_current

        if previous_balance is None or observed_balance is None:
            continue

        expected_delta = round(
            observed_balance - previous_balance,
            2,
        )
        if abs(expected_delta) < 0.01:
            continue

        observed_delta = movement_accounting_delta(movement)
        should_replace_amount = observed_delta is None

        if observed_delta is not None and expected_current is not None:
            same_direction = observed_delta * expected_delta > 0.0
            should_replace_amount = (
                same_direction
                and abs(observed_delta) < abs(expected_delta) * 0.20
            )

        if not should_replace_amount:
            continue

        if expected_delta < 0.0:
            movement.cargo = abs(expected_delta)
            movement.abono = 0.0
        else:
            movement.cargo = 0.0
            movement.abono = expected_delta


def repair_missing_operation_dates(
    movements: Sequence[Movimiento],
) -> None:
    """Completa una fecha ausente sólo si ambos vecinos coinciden."""

    for index in range(1, len(movements) - 1):
        movement = movements[index]
        if movement.fecha_operacion:
            continue

        previous_date = movements[index - 1].fecha_operacion
        following_date = movements[index + 1].fecha_operacion

        if previous_date and previous_date == following_date:
            movement.fecha_operacion = previous_date


def repair_corrupted_balances(
    movements: Sequence[Movimiento],
) -> None:
    """
    Repara un saldo OCR sólo cuando la contabilidad lo demuestra.

    - Si el saldo anterior y el posterior producen exactamente el
      mismo valor, ambas evidencias permiten corregir centavos OCR.
    - Con una sola evidencia, únicamente se corrige un saldo que
      perdió claramente varios dígitos.
    - Nunca se inventa el saldo de un movimiento parcial sin valor.
    """

    for index, movement in enumerate(movements):
        observed = movement.saldo_operacion
        if observed is None:
            continue

        try:
            observed_value = float(observed)
        except (TypeError, ValueError):
            continue

        expected_values: List[float] = []
        current_delta = movement_accounting_delta(movement)

        if index > 0 and current_delta is not None:
            previous_balance = movements[
                index - 1
            ].saldo_operacion

            if previous_balance is not None:
                try:
                    expected_values.append(
                        round(
                            float(previous_balance)
                            + current_delta,
                            2,
                        )
                    )
                except (TypeError, ValueError):
                    pass

        if index + 1 < len(movements):
            next_movement = movements[index + 1]
            next_balance = next_movement.saldo_operacion
            next_delta = movement_accounting_delta(
                next_movement
            )

            if (
                next_balance is not None
                and next_delta is not None
            ):
                try:
                    expected_values.append(
                        round(
                            float(next_balance)
                            - next_delta,
                            2,
                        )
                    )
                except (TypeError, ValueError):
                    pass

        if not expected_values:
            continue

        replacement: Optional[float] = None

        if (
            len(expected_values) >= 2
            and abs(
                expected_values[0]
                - expected_values[1]
            ) < 0.01
        ):
            replacement = expected_values[0]
        elif len(expected_values) == 1:
            candidate = expected_values[0]

            if balance_is_obviously_truncated(
                observed_value,
                candidate,
            ):
                replacement = candidate

        if (
            replacement is not None
            and abs(
                observed_value - replacement
            ) >= 0.01
        ):
            movement.saldo_operacion = replacement


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
    sent_by_numeric_tracking_key: Dict[str, List[SpeiRow]]
    received_by_reference: Dict[str, List[SpeiRow]]


def build_spei_match_indexes(
    spei_rows: Sequence[SpeiRow],
) -> SpeiMatchIndexes:
    sent_by_tracking_key: Dict[str, List[SpeiRow]] = {}
    sent_by_numeric_tracking_key: Dict[str, List[SpeiRow]] = {}
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

            for numeric_key in tracking_numeric_identities(
                row.clave_rastreo
            ):
                sent_by_numeric_tracking_key.setdefault(
                    numeric_key,
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
        sent_by_numeric_tracking_key=(
            sent_by_numeric_tracking_key
        ),
        received_by_reference=received_by_reference,
    )


def movement_amounts(movement: Movimiento) -> List[float]:
    amounts = []

    if movement.cargo:
        amounts.append(float(movement.cargo))
    if movement.abono:
        amounts.append(float(movement.abono))

    return amounts


def normalized_concept_identity(value: Optional[str]) -> str:
    if not value:
        return ""

    normalized = normalize_text(value)
    normalized = re.sub(r"\b\d{4,}\b\s*$", "", normalized)

    return re.sub(r"[^A-Z0-9]", "", normalized)


def meaningful_concept_tokens(value: Optional[str]) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Z0-9]+", normalize_text(value))
        if (
            (len(token) >= 2 or token.isdigit())
            and (not token.isdigit() or len(token) <= 2)
            and token not in {"CGO", "RRA", "ARRA"}
        )
    }


def spei_concept_match_score(
    movement: Movimiento,
    candidate: SpeiRow,
) -> int:
    movement_concept = normalized_concept_identity(movement.concepto)
    spei_concept = normalized_concept_identity(candidate.concepto)

    if not movement_concept or not spei_concept:
        return 0
    if movement_concept == spei_concept:
        return 3
    if (
        spei_concept in movement_concept
        or movement_concept in spei_concept
    ):
        return 2

    movement_tokens = meaningful_concept_tokens(movement.concepto)
    spei_tokens = meaningful_concept_tokens(candidate.concepto)
    if movement_tokens and spei_tokens:
        if spei_tokens.issubset(movement_tokens):
            return 2

        overlap = len(movement_tokens.intersection(spei_tokens))
        if overlap / max(len(movement_tokens), len(spei_tokens)) >= 0.6:
            return 2

    return 0


def choose_spei_candidate(
    movement: Movimiento,
    candidates: Sequence[SpeiRow],
) -> Optional[SpeiRow]:
    if not candidates:
        return None

    amounts = movement_amounts(movement)

    amount_matches = [
        candidate
        for candidate in candidates
        if (
            candidate.monto <= 0.0
            or not amounts
            or any(
                abs(candidate.monto - amount) < 0.01
                for amount in amounts
            )
        )
    ]

    # Una clave correcta con importe incompatible es evidencia de
    # que el OCR desplazó Referencia / Serial a la fila vecina. No se
    # enriquece esa fila; la reconciliación bidireccional posterior
    # podrá resolver ambas por monto, sentido y fecha.
    if not amount_matches:
        return None
    if len(amount_matches) == 1:
        return amount_matches[0]

    concept_scores = [
        (spei_concept_match_score(movement, candidate), candidate)
        for candidate in amount_matches
    ]
    best_concept_score = max(score for score, _ in concept_scores)

    if best_concept_score > 0:
        best_concept_candidates = [
            candidate
            for score, candidate in concept_scores
            if score == best_concept_score
        ]
        if len(best_concept_candidates) == 1:
            return best_concept_candidates[0]

    for candidate in amount_matches:
        for amount in amounts:
            if abs(candidate.monto - amount) < 0.01:
                return candidate

    return amount_matches[0]


def unique_spei_rows(
    rows: Sequence[SpeiRow],
) -> List[SpeiRow]:
    result: List[SpeiRow] = []
    seen: set[int] = set()

    for row in rows:
        identity = id(row)
        if identity in seen:
            continue

        seen.add(identity)
        result.append(row)

    return result


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

    keys = extract_movement_tracking_keys(movement.referencia)
    if not keys:
        return None

    exact_candidates: List[SpeiRow] = []

    for key in keys:
        exact_candidates.extend(
            indexes.sent_by_tracking_key.get(key, [])
        )

    candidates = unique_spei_rows(exact_candidates)

    if candidates:
        exact_match = choose_spei_candidate(movement, candidates)
        if exact_match is not None:
            return exact_match

    # Respaldo para variantes HSB/HSBC, relleno con ceros a la
    # izquierda y letras OCR intercaladas. El campo original no se
    # modifica; estas identidades existen únicamente para el cruce.
    numeric_candidates: List[SpeiRow] = []

    for key in keys:
        for numeric_key in tracking_numeric_identities(key):
            numeric_candidates.extend(
                indexes.sent_by_numeric_tracking_key.get(
                    numeric_key,
                    [],
                )
            )

    return choose_spei_candidate(
        movement,
        unique_spei_rows(numeric_candidates),
    )


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
            ... DC000000000 00012345

        Número de Referencia SPEI:
            000000000000 + 00012345

        Identidad común:
            12345

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


def parse_model_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None

    try:
        day_value, month_value, year_value = value.split("/")
        return date(
            int(year_value),
            int(month_value),
            int(day_value),
        )
    except (AttributeError, TypeError, ValueError):
        return None


def infer_spei_date_from_reference(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> Optional[str]:
    """
    Recupera DDMMYY del extremo derecho sólo con validación cruzada.

    El Número de Referencia no siempre codifica la fecha, por eso el
    respaldo se acepta exclusivamente cuando la fecha resultante
    queda a no más de dos días de la operación ya extraída.
    """

    reference = normalize_spei_reference(spei_row.numero_referencia)
    movement_date = parse_model_date(movement.fecha_operacion)
    if not reference or len(reference) < 6 or movement_date is None:
        return None

    suffix = reference[-6:]

    try:
        candidate = date(
            2000 + int(suffix[4:6]),
            int(suffix[2:4]),
            int(suffix[:2]),
        )
    except ValueError:
        return None

    if abs((movement_date - candidate).days) > 2:
        return None

    return candidate.strftime("%d/%m/%Y")


def reconcile_spei_date_with_movement(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> Optional[str]:
    """Recupera la decena del día sólo cuando el OCR la omitió."""

    parsed_spei_date = parse_model_date(spei_row.fecha)
    movement_date = parse_model_date(movement.fecha_operacion)
    if parsed_spei_date is None or movement_date is None:
        return spei_row.fecha
    if abs((movement_date - parsed_spei_date).days) <= 2:
        return spei_row.fecha
    if spei_concept_match_score(movement, spei_row) < 2:
        return spei_row.fecha

    raw_date = text_from_spei_box(
        spei_row,
        BOX_SPEI_FECHA,
        padding_x=5.0,
    ) or ""
    raw_match = re.search(r"(?<!\d)(\d)[/-]\d{1,2}[/-]\d{4}", raw_date)
    if raw_match is None:
        return spei_row.fecha

    if (
        movement_date.month != parsed_spei_date.month
        or movement_date.year != parsed_spei_date.year
    ):
        return spei_row.fecha

    base_day = int(raw_match.group(1))
    candidates = []

    for prefix in (10, 20):
        try:
            candidate = date(
                parsed_spei_date.year,
                parsed_spei_date.month,
                base_day + prefix,
            )
        except ValueError:
            continue

        if abs((movement_date - candidate).days) <= 2:
            candidates.append(candidate)

    if len(candidates) != 1:
        return spei_row.fecha

    return candidates[0].strftime("%d/%m/%Y")


def fallback_spei_pair_is_compatible(
    movement: Movimiento,
    spei_row: SpeiRow,
) -> bool:
    """
    Valida un cruce de respaldo por sentido, importe y fecha.

    Se usa sólo en la reconciliación uno-a-uno. Nunca basta el monto
    aislado: para enviados se exige además evidencia conceptual de
    transferencia; cuando ambas fechas existen no pueden diferir más
    de dos días calendario.
    """

    amounts = movement_amounts(movement)
    if spei_row.monto <= 0.0 or not any(
        abs(spei_row.monto - amount) < 0.01
        for amount in amounts
    ):
        return False

    if spei_row.tipo == "enviados":
        if not movement.cargo or movement.abono:
            return False

        normalized_concept = normalize_text(movement.concepto)
        reference_parts = [
            compact_tracking_key(part)
            for part in re.split(
                r"[\r\n]+",
                movement.referencia or "",
            )
            if part.strip()
        ]
        has_serial_pair = (
            len(reference_parts) > 1
            and any(
                part is not None and re.fullmatch(r"\d{8}", part)
                for part in reference_parts
            )
        )
        has_transfer_evidence = any(
            token in normalized_concept
            for token in ("CGO", "SPEI", "TANDA", "PAGO")
        ) or has_serial_pair

        if not has_transfer_evidence:
            return False
    elif spei_row.tipo == "recibidos":
        if not movement.abono or movement.cargo:
            return False
    else:
        return False

    movement_date = parse_model_date(movement.fecha_operacion)
    spei_date = parse_model_date(spei_row.fecha)

    if spei_date is None and spei_concept_match_score(
        movement,
        spei_row,
    ) < 2:
        return False

    if movement_date is not None and spei_date is not None:
        date_distance = abs((movement_date - spei_date).days)
        has_strong_concept_match = (
            spei_concept_match_score(movement, spei_row) >= 2
            and len(meaningful_concept_tokens(spei_row.concepto)) >= 2
        )

        if date_distance > 2 and not has_strong_concept_match:
            return False

    return True


def resolve_unique_spei_fallbacks(
    movements: Sequence[Movimiento],
    spei_rows: Sequence[SpeiRow],
    resolved_matches: List[Optional[SpeiRow]],
) -> None:
    """Resuelve pares únicos en ambas direcciones, sin reutilizarlos."""

    used_rows = {
        id(match)
        for match in resolved_matches
        if match is not None
    }

    while True:
        candidate_rows_by_movement: Dict[int, List[SpeiRow]] = {}
        candidate_movements_by_row: Dict[int, List[int]] = {}

        for movement_index, movement in enumerate(movements):
            if resolved_matches[movement_index] is not None:
                continue

            for spei_row in spei_rows:
                if id(spei_row) in used_rows:
                    continue
                if not fallback_spei_pair_is_compatible(
                    movement,
                    spei_row,
                ):
                    continue

                candidate_rows_by_movement.setdefault(
                    movement_index,
                    [],
                ).append(spei_row)
                candidate_movements_by_row.setdefault(
                    id(spei_row),
                    [],
                ).append(movement_index)

        resolved_any = False

        for movement_index, candidates in candidate_rows_by_movement.items():
            if len(candidates) != 1:
                continue

            candidate = candidates[0]
            if len(candidate_movements_by_row.get(id(candidate), [])) != 1:
                continue

            resolved_matches[movement_index] = candidate
            used_rows.add(id(candidate))
            resolved_any = True

        if not resolved_any:
            break


def remove_ambiguous_spei_reuse(
    movements: Sequence[Movimiento],
    resolved_matches: List[Optional[SpeiRow]],
) -> None:
    """Impide publicar una misma operación SPEI en dos movimientos."""

    matches_by_row: Dict[int, List[int]] = {}

    for index, match in enumerate(resolved_matches):
        if match is None:
            continue
        matches_by_row.setdefault(id(match), []).append(index)

    for indexes in matches_by_row.values():
        if len(indexes) <= 1:
            continue

        match = resolved_matches[indexes[0]]
        if match is None:
            continue

        match_date = parse_model_date(match.fecha)
        scored = []

        for index in indexes:
            movement_date = parse_model_date(
                movements[index].fecha_operacion
            )
            exact_date = int(
                match_date is not None and movement_date == match_date
            )
            scored.append((exact_date, index))

        best_score = max(score for score, _ in scored)
        best_indexes = [
            index
            for score, index in scored
            if score == best_score
        ]

        keep_index = best_indexes[0] if len(best_indexes) == 1 else None

        for index in indexes:
            if index != keep_index:
                resolved_matches[index] = None


def recover_operation_date_from_spei(
    movements: Sequence[Movimiento],
    index: int,
    spei_row: SpeiRow,
) -> None:
    """Usa la fecha SPEI sólo cuando queda acotada por ambos vecinos."""

    movement = movements[index]
    if movement.fecha_operacion or not spei_row.fecha:
        return
    if index == 0 or index + 1 >= len(movements):
        return

    previous_date = parse_model_date(
        movements[index - 1].fecha_operacion
    )
    following_date = parse_model_date(
        movements[index + 1].fecha_operacion
    )
    candidate_date = parse_model_date(spei_row.fecha)

    if (
        previous_date is not None
        and following_date is not None
        and candidate_date is not None
        and previous_date <= candidate_date <= following_date
    ):
        movement.fecha_operacion = spei_row.fecha


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
        if re.fullmatch(r"\d{18}", cuenta_ordenante):
            movement.clabe_beneficiario = cuenta_ordenante
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
        if re.fullmatch(r"\d{18}", spei_row.cuenta_beneficiaria):
            movement.clabe_beneficiario = spei_row.cuenta_beneficiaria
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

    # La fecha de liquidación proviene de la fila SPEI confirmada,
    # tanto para enviados como para recibidos. No se copia la fecha
    # del movimiento ni se completa cuando el OCR de la tabla no
    # aportó una fecha calendario válida.
    liquidation_date = (
        reconcile_spei_date_with_movement(movement, spei_row)
        or infer_spei_date_from_reference(movement, spei_row)
    )
    if liquidation_date:
        movement.fecha_liquidacion = liquidation_date

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

    # Si la tabla conservó únicamente un sufijo muy corto (``73``),
    # el pareo único ya confirmado permite completar sólo la parte
    # numérica desde Referencia / Serial. No se inventa HSB/HSBC,
    # porque ese prefijo no puede deducirse de forma determinista.
    if (
        spei_row.tipo == "enviados"
        and tracking_key
        and len(tracking_key) < 4
    ):
        for candidate in extract_movement_tracking_keys(
            movement.referencia
        ):
            compact_candidate = compact_tracking_key(candidate)
            if (
                compact_candidate
                and len(compact_candidate) >= 4
                and compact_candidate.endswith(tracking_key)
            ):
                tracking_key = compact_candidate
                break

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

    remove_ambiguous_spei_reuse(
        movements,
        resolved_matches,
    )

    resolve_unique_spei_fallbacks(
        movements,
        spei_rows,
        resolved_matches,
    )

    for index, (movement, spei_match) in enumerate(
        zip(movements, resolved_matches)
    ):
        if spei_match is None:
            continue

        recover_operation_date_from_spei(
            movements,
            index,
            spei_match,
        )
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
    accepted_rows: List[MovementRow] = []

    for row in movement_rows:
        movement = movement_row_to_model(
            row,
            periodo_inicio,
        )

        if is_valid_movement(
            movement,
            allow_partial=row.partial_recovery,
        ):
            movements.append(movement)
            accepted_rows.append(row)

    opening_balance = extract_statement_opening_balance(
        filtered_words
    )

    repair_partial_movement_financials(
        movements,
        accepted_rows,
        opening_balance,
    )

    repair_malformed_transaction_amounts(
        movements,
        accepted_rows,
    )

    repair_corrupted_balances(movements)
    repair_missing_operation_dates(movements)

    enrich_movements_from_spei(
        movements,
        spei_rows,
    )

    return movements
