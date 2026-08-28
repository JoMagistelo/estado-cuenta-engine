from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from statistics import median
from typing import Any, Dict, List, Optional

from models.movimiento import Movimiento
from parsers.banamex.utils.words_grafico_filter import (
    remove_after_grafico_transaccional,
)
from parsers.banamex.utils.words_header_filter import (
    remove_banamex_header,
)


# ============================================================
# CONFIGURACIÓN GENERAL — MOVIMIENTOS BANAMEX
# ============================================================
#
# Tabla esperada:
#
#     FECHA | CONCEPTO | RETIROS | DEPOSITOS | SALDO
#
# A diferencia de Datos de Cuenta y Resumen Financiero, la
# tabla de movimientos declara su geometría mediante la propia
# cabecera. Por eso el mecanismo principal no necesita cajas
# rígidas por producto:
#
#     1. detecta la cabecera en cada página;
#     2. construye columnas iniciales;
#     3. calibra las columnas monetarias con los x1 reales de
#        los importes observados;
#     4. propaga la última configuración a páginas de
#        continuación sin cabecera.
#
# DEFAULT_COLUMN_BOUNDS se conserva como fallback compatible
# para MiCuenta y documentos donde falte la cabecera.
#
# ============================================================


PAGE_MOVIMIENTOS = 2

LINE_Y_TOLERANCE = 3.5
COLUMN_TOLERANCE = 6.0


DEFAULT_COLUMN_BOUNDS = {
    "FECHA": (8.0, 52.0),
    "CONCEPTO": (52.0, 255.0),
    "RETIROS": (255.0, 324.0),
    "DEPOSITOS": (324.0, 408.0),
    "SALDO": (408.0, 490.0),
}


HEADER_ALIASES = {
    "FECHA": {"FECHA"},
    "CONCEPTO": {"CONCEPTO", "DESCRIPCION"},
    "RETIROS": {"RETIROS", "CARGOS"},
    "DEPOSITOS": {"DEPOSITOS", "ABONOS"},
    "SALDO": {"SALDO"},
}

HEADER_NAMES = set(HEADER_ALIASES)

MONTH_NAMES = {
    "ENE",
    "FEB",
    "MAR",
    "ABR",
    "MAY",
    "JUN",
    "JUL",
    "AGO",
    "SEP",
    "OCT",
    "NOV",
    "DIC",
}

SKIP_LINE_MARKERS = (
    "DETALLE DE OPERACIONES",
    "OPERACIONES REALIZADAS",
    "ESTADO DE CUENTA",
    "CENTRO DE ATENCION TELEFONICA",
)

TERMINAL_LINE_MARKERS = (
    "GRAFICO TRANSACCIONAL",
    "ESTE DOCUMENTO ES UNA REPRESENTACION IMPRESA SIN VALIDEZ FISCAL",
    "INFORMACION IMPORTANTE",
)


# ============================================================
# REGEX
# ============================================================


DATE_PATTERN = re.compile(
    r"""
    ^
    (?:
        \d{1,2}\s+[A-Z]{3,9}
        |
        \d{1,2}/[A-Z]{3,9}
        |
        \d{1,2}-[A-Z]{3,9}
        |
        \d{1,2}\s+[A-Z]{3,9}\s+\d{4}
        |
        \d{1,2}/[A-Z]{3,9}/\d{4}
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


MONEY_PATTERN = re.compile(
    r"""
    ^
    \(?
    [+-]?
    \$?
    (?:
        \d{1,3}(?:,\d{3})+
        |
        \d+
    )
    (?:\.\d{2})?
    \)?
    -?
    $
    """,
    re.VERBOSE,
)


RFC_PATTERN = re.compile(
    r"""
    \b
    (
        [A-Z&Ñ]{3,4}
        \s?
        \d{6}
        \s?
        [A-Z0-9]{3}
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


TIME_PATTERN = re.compile(
    r"\b([01]?\d|2[0-3]):[0-5]\d\b"
)


AUTH_PATTERN = re.compile(
    r"""
    \b
    AUT(?:ORIZACION)?
    \.?
    \s*[:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


SUC_PATTERN = re.compile(
    r"""
    \b
    SUC(?:URSAL)?
    \.?
    \s*[:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CAJA_PATTERN = re.compile(
    r"""
    \b
    CAJA
    \.?
    \s*[:#-]?
    \s*
    ([A-Z0-9]+)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


RASTREO_PATTERN = re.compile(
    r"""
    \b
    (?:
        CLAVE
        \s+
        (?:DE\s+)?
    )?
    RASTREO
    \.?
    \s*[:#-]?
    \s*
    ([A-Z0-9][A-Z0-9_-]*)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CLABE_PATTERN = re.compile(
    r"(?<!\d)(\d{18})(?!\d)"
)


# ============================================================
# ESTRUCTURA DE CONFIGURACIÓN
# ============================================================


@dataclass(frozen=True, slots=True)
class ColumnConfig:
    """
    Límites espaciales de las cinco columnas.

    FECHA y CONCEPTO se evalúan por centro X.
    RETIROS, DEPÓSITOS y SALDO se evalúan por x1 porque los
    importes están alineados por su borde derecho.
    """

    fecha: tuple[float, float]
    concepto: tuple[float, float]
    retiros: tuple[float, float]
    depositos: tuple[float, float]
    saldo: tuple[float, float]


# ============================================================
# NORMALIZACIÓN
# ============================================================


def normalize_text(value: Any) -> str:
    """Normaliza espacios preservando el texto visible."""

    if value is None:
        return ""

    normalized = (
        str(value)
        .replace("\xa0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def normalize_upper(value: Any) -> str:
    """Normaliza para comparación sin depender de acentos."""

    normalized = unicodedata.normalize(
        "NFD",
        normalize_text(value),
    )

    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )

    return normalized.upper()


# ============================================================
# COORDENADAS
# ============================================================


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def word_page(word: Dict[str, Any]) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def word_center_x(word: Dict[str, Any]) -> float:
    x0 = _safe_float(word.get("x0", 0))
    x1 = _safe_float(word.get("x1", x0), x0)

    return (x0 + x1) / 2.0


def word_center_y(word: Dict[str, Any]) -> float:
    top = _safe_float(word.get("top", 0))
    bottom = _safe_float(word.get("bottom", top), top)

    return (top + bottom) / 2.0


def word_height(word: Dict[str, Any]) -> float:
    top = _safe_float(word.get("top", 0))
    bottom = _safe_float(word.get("bottom", top), top)

    return abs(bottom - top)


def word_x1(word: Dict[str, Any]) -> float:
    return _safe_float(
        word.get("x1", word.get("x0", 0))
    )


# ============================================================
# AGRUPACIÓN DE LÍNEAS
# ============================================================


def group_words_into_lines(
    words: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Agrupa palabras por página y cercanía vertical."""

    if not words:
        return []

    ordered = sorted(
        words,
        key=lambda word: (
            word_page(word),
            word_center_y(word),
            _safe_float(word.get("x0", 0)),
        ),
    )

    heights = sorted(
        word_height(word)
        for word in ordered
        if word_height(word) > 0
    )

    typical_height = (
        heights[len(heights) // 2]
        if heights
        else 0.0
    )

    tolerance = max(
        LINE_Y_TOLERANCE,
        typical_height * 0.45,
    )

    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_page: Optional[int] = None
    current_y: Optional[float] = None

    for word in ordered:
        page = word_page(word)
        center_y = word_center_y(word)

        if (
            current_y is None
            or page != current_page
            or abs(center_y - current_y) > tolerance
        ):
            if current:
                current.sort(
                    key=lambda item: _safe_float(
                        item.get("x0", 0)
                    )
                )
                lines.append(current)

            current = [word]
            current_page = page
            current_y = center_y
            continue

        current.append(word)
        current_y = sum(
            word_center_y(item)
            for item in current
        ) / len(current)

    if current:
        current.sort(
            key=lambda item: _safe_float(item.get("x0", 0))
        )
        lines.append(current)

    return lines


def line_text(line: List[Dict[str, Any]]) -> str:
    values = [
        normalize_text(word.get("text", ""))
        for word in sorted(
            line,
            key=lambda item: _safe_float(item.get("x0", 0)),
        )
        if normalize_text(word.get("text", ""))
    ]

    return " ".join(values).strip()


def line_center_y(line: List[Dict[str, Any]]) -> float:
    if not line:
        return 0.0

    return sum(
        word_center_y(word)
        for word in line
    ) / len(line)


# ============================================================
# CABECERA DE TABLA
# ============================================================


def find_word(
    line: List[Dict[str, Any]],
    expected: str,
) -> Optional[Dict[str, Any]]:
    canonical = normalize_upper(expected)
    aliases = HEADER_ALIASES.get(canonical, {canonical})

    for word in line:
        if normalize_upper(word.get("text", "")) in aliases:
            return word

    return None


def is_movements_header(line: List[Dict[str, Any]]) -> bool:
    found = sum(
        1
        for name in HEADER_NAMES
        if find_word(line, name) is not None
    )

    return found >= 4


def detect_header(
    line: List[Dict[str, Any]],
) -> Optional[Dict[str, Dict[str, float]]]:
    if not is_movements_header(line):
        return None

    result: Dict[str, Dict[str, float]] = {}

    for name in HEADER_NAMES:
        word = find_word(line, name)

        if word is None:
            continue

        x0 = _safe_float(word.get("x0", 0))
        x1 = _safe_float(word.get("x1", x0), x0)

        result[name] = {
            "x0": x0,
            "x1": x1,
            "center": (x0 + x1) / 2.0,
        }

    return result


# ============================================================
# IMPORTES
# ============================================================


def is_money(text: str) -> bool:
    return bool(
        MONEY_PATTERN.fullmatch(normalize_text(text))
    )


def parse_amount(text: str) -> float:
    """Convierte importes, incluyendo paréntesis y signo final."""

    if not text:
        return 0.0

    value = normalize_text(text)
    negative = False

    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1].strip()

    if value.endswith("-"):
        negative = True
        value = value[:-1].strip()

    value = (
        value.replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        amount = float(value)
    except (ValueError, TypeError):
        return 0.0

    if negative:
        return -abs(amount)

    return amount


# ============================================================
# CONSTRUCCIÓN Y CALIBRACIÓN DE COLUMNAS
# ============================================================


def build_default_config() -> ColumnConfig:
    return ColumnConfig(
        fecha=DEFAULT_COLUMN_BOUNDS["FECHA"],
        concepto=DEFAULT_COLUMN_BOUNDS["CONCEPTO"],
        retiros=DEFAULT_COLUMN_BOUNDS["RETIROS"],
        depositos=DEFAULT_COLUMN_BOUNDS["DEPOSITOS"],
        saldo=DEFAULT_COLUMN_BOUNDS["SALDO"],
    )


def build_config_from_header(
    header: Dict[str, Dict[str, float]],
) -> ColumnConfig:
    """
    Construye una primera configuración desde la cabecera.

    Los límites financieros se calculan entre los centros de
    RETIROS/DEPÓSITOS/SALDO. Después serán calibrados con los
    bordes x1 reales de los importes de la página.
    """

    fallback = build_default_config()

    fecha = fallback.fecha
    concepto = fallback.concepto
    retiros = fallback.retiros
    depositos = fallback.depositos
    saldo = fallback.saldo

    fecha_header = header.get("FECHA")
    concepto_header = header.get("CONCEPTO")
    retiros_header = header.get("RETIROS")
    depositos_header = header.get("DEPOSITOS")
    saldo_header = header.get("SALDO")

    if fecha_header is not None:
        header_width = max(
            fecha_header["x1"] - fecha_header["x0"],
            10.0,
        )
        fecha = (
            max(0.0, fecha_header["x0"] - header_width * 0.35),
            fecha_header["x1"],
        )

    if (
        fecha_header is not None
        and retiros_header is not None
    ):
        concepto = (
            fecha_header["x1"] + 5.0,
            retiros_header["x0"] - 5.0,
        )
    elif concepto_header is not None:
        concepto = (
            fecha[1],
            fallback.concepto[1],
        )

    if (
        retiros_header is not None
        and depositos_header is not None
        and saldo_header is not None
    ):
        retiro_center = retiros_header["center"]
        deposito_center = depositos_header["center"]
        saldo_center = saldo_header["center"]

        if retiro_center < deposito_center < saldo_center:
            retiro_deposito_boundary = (
                retiro_center + deposito_center
            ) / 2.0
            deposito_saldo_boundary = (
                deposito_center + saldo_center
            ) / 2.0

            left_spacing = deposito_center - retiro_center
            right_spacing = saldo_center - deposito_center

            financial_left = max(
                concepto[1],
                retiro_center - left_spacing / 2.0,
            )
            financial_right = (
                saldo_center + right_spacing / 2.0
            )

            retiros = (
                financial_left,
                retiro_deposito_boundary,
            )
            depositos = (
                retiro_deposito_boundary,
                deposito_saldo_boundary,
            )
            saldo = (
                deposito_saldo_boundary,
                financial_right,
            )

    return ColumnConfig(
        fecha=fecha,
        concepto=concepto,
        retiros=retiros,
        depositos=depositos,
        saldo=saldo,
    )


def money_word_inside_column(
    word: Dict[str, Any],
    column: tuple[float, float],
) -> bool:
    """Evalúa la columna monetaria mediante el borde x1."""

    xmin, xmax = column
    edge = word_x1(word)

    return xmin <= edge <= xmax


def _calibrate_config_from_amounts(
    page_lines: List[List[Dict[str, Any]]],
    config: ColumnConfig,
    header_y: float,
) -> ColumnConfig:
    """
    Ajusta fronteras con las alineaciones x1 observadas.

    La calibración solo se aplica cuando aparecen candidatos en
    las tres columnas, evitando inferencias agresivas en páginas
    incompletas.
    """

    candidates: Dict[str, List[float]] = {
        "retiros": [],
        "depositos": [],
        "saldo": [],
    }

    for line in page_lines:
        if line_center_y(line) <= header_y + LINE_Y_TOLERANCE:
            continue

        for word in line:
            text = normalize_text(word.get("text", ""))

            if not is_money(text):
                continue

            for column_name in (
                "retiros",
                "depositos",
                "saldo",
            ):
                column = getattr(config, column_name)

                if money_word_inside_column(word, column):
                    candidates[column_name].append(word_x1(word))
                    break

    if not all(candidates.values()):
        return config

    retiro_anchor = float(median(candidates["retiros"]))
    deposito_anchor = float(median(candidates["depositos"]))
    saldo_anchor = float(median(candidates["saldo"]))

    if not (
        retiro_anchor < deposito_anchor < saldo_anchor
    ):
        return config

    retiro_deposito_boundary = (
        retiro_anchor + deposito_anchor
    ) / 2.0
    deposito_saldo_boundary = (
        deposito_anchor + saldo_anchor
    ) / 2.0

    financial_left = min(
        config.retiros[0],
        retiro_anchor
        - (deposito_anchor - retiro_anchor) / 2.0,
    )
    financial_right = max(
        config.saldo[1],
        saldo_anchor
        + (saldo_anchor - deposito_anchor) / 2.0,
    )

    return ColumnConfig(
        fecha=config.fecha,
        concepto=config.concepto,
        retiros=(
            financial_left,
            retiro_deposito_boundary,
        ),
        depositos=(
            retiro_deposito_boundary,
            deposito_saldo_boundary,
        ),
        saldo=(
            deposito_saldo_boundary,
            financial_right,
        ),
    )


def build_page_configs(
    lines: List[List[Dict[str, Any]]],
) -> Dict[int, ColumnConfig]:
    """Construye y propaga configuración para todas las páginas."""

    if not lines:
        return {}

    page_lines: Dict[int, List[List[Dict[str, Any]]]] = {}

    for line in lines:
        if line:
            page_lines.setdefault(word_page(line[0]), []).append(line)

    detected: Dict[int, ColumnConfig] = {}

    for page, current_lines in page_lines.items():
        for line in current_lines:
            header = detect_header(line)

            if header is None:
                continue

            initial = build_config_from_header(header)
            detected[page] = _calibrate_config_from_amounts(
                page_lines=current_lines,
                config=initial,
                header_y=line_center_y(line),
            )
            break

    pages = sorted(page_lines)

    if not detected:
        default = build_default_config()
        return {page: default for page in pages}

    result: Dict[int, ColumnConfig] = {}
    previous: Optional[ColumnConfig] = None

    for page in pages:
        if page in detected:
            previous = detected[page]
            result[page] = previous
            continue

        if previous is not None:
            result[page] = previous
            continue

        next_page = next(
            (
                candidate
                for candidate in sorted(detected)
                if candidate > page
            ),
            None,
        )

        result[page] = (
            detected[next_page]
            if next_page is not None
            else build_default_config()
        )

    return result


def get_config(
    page: int,
    configs: Dict[int, ColumnConfig],
) -> ColumnConfig:
    if page in configs:
        return configs[page]

    previous_pages = [
        candidate
        for candidate in configs
        if candidate <= page
    ]

    if previous_pages:
        return configs[max(previous_pages)]

    if configs:
        return configs[min(configs)]

    return build_default_config()


# ============================================================
# PERTENENCIA Y EXTRACCIÓN DE COLUMNAS
# ============================================================


def word_inside_column(
    word: Dict[str, Any],
    column: tuple[float, float],
) -> bool:
    center = word_center_x(word)
    xmin, xmax = column

    return (
        xmin - COLUMN_TOLERANCE
        <= center
        <= xmax + COLUMN_TOLERANCE
    )


def words_in_column(
    line: List[Dict[str, Any]],
    column: tuple[float, float],
) -> List[Dict[str, Any]]:
    result = [
        word
        for word in line
        if word_inside_column(word, column)
    ]

    result.sort(
        key=lambda item: _safe_float(item.get("x0", 0))
    )

    return result


def column_text(
    line: List[Dict[str, Any]],
    column: tuple[float, float],
) -> str:
    values = [
        normalize_text(word.get("text", ""))
        for word in words_in_column(line, column)
        if normalize_text(word.get("text", ""))
    ]

    return " ".join(values).strip()


def extract_fecha_operacion(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> str:
    return column_text(line, config.fecha)


def extract_concepto(
    block: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> str:
    result: List[str] = []

    for line in block:
        if not line:
            continue

        config = get_config(word_page(line[0]), configs)
        text = column_text(line, config.concepto)

        if text:
            result.append(text)

    return "\n".join(result).strip()


def extract_amount_from_block(
    block: List[List[Dict[str, Any]]],
    column_name: str,
    configs: Dict[int, ColumnConfig],
) -> float:
    """Extrae el último importe válido de la columna indicada."""

    candidates: List[tuple[int, Dict[str, Any]]] = []

    for line_index, line in enumerate(block):
        if not line:
            continue

        config = get_config(word_page(line[0]), configs)
        current_column = getattr(config, column_name)

        for word in line:
            text = normalize_text(word.get("text", ""))

            if (
                is_money(text)
                and money_word_inside_column(
                    word,
                    current_column,
                )
            ):
                candidates.append((line_index, word))

    if not candidates:
        return 0.0

    _, word = candidates[-1]

    return parse_amount(word.get("text", ""))


def extract_cargo(
    block: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> float:
    return extract_amount_from_block(
        block,
        "retiros",
        configs,
    )


def extract_abono(
    block: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> float:
    return extract_amount_from_block(
        block,
        "depositos",
        configs,
    )


def extract_saldo(
    block: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> float:
    return extract_amount_from_block(
        block,
        "saldo",
        configs,
    )


# ============================================================
# FECHA Y BLOQUES
# ============================================================


def is_date_text(text: str) -> bool:
    normalized = normalize_upper(text)

    if not normalized:
        return False

    if DATE_PATTERN.fullmatch(normalized):
        return True

    parts = normalized.split()

    if len(parts) != 2:
        return False

    day = parts[0]
    month = parts[1][:3]

    return (
        day.isdigit()
        and month in MONTH_NAMES
        and 1 <= int(day) <= 31
    )


def is_start_movement(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> bool:
    return is_date_text(
        extract_fecha_operacion(line, config)
    )


def is_saldo_anterior(
    line: List[Dict[str, Any]],
    config: ColumnConfig,
) -> bool:
    concepto = normalize_upper(
        column_text(line, config.concepto)
    )

    return "SALDO ANTERIOR" in concepto


def is_terminal_line(line: List[Dict[str, Any]]) -> bool:
    text = normalize_upper(line_text(line))

    return any(
        marker in text
        for marker in TERMINAL_LINE_MARKERS
    )


def should_skip_line(line: List[Dict[str, Any]]) -> bool:
    if not line:
        return True

    text = normalize_upper(line_text(line))

    if not text:
        return True

    if is_movements_header(line):
        return True

    return any(
        marker in text
        for marker in SKIP_LINE_MARKERS
    )


def build_blocks(
    lines: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> List[List[List[Dict[str, Any]]]]:
    blocks: List[List[List[Dict[str, Any]]]] = []
    current: List[List[Dict[str, Any]]] = []

    for line in lines:
        if is_terminal_line(line):
            break

        if should_skip_line(line):
            continue

        config = get_config(word_page(line[0]), configs)

        if is_start_movement(line, config):
            if current:
                blocks.append(current)

            current = [line]
            continue

        if current:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


# ============================================================
# CONCEPTO → DATOS ESTRUCTURADOS
# ============================================================


def extract_referencia_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    patterns = (
        r"\bREFERENCIA\.?\s*[:#-]?\s*([A-Z0-9*_-]+)",
        r"\bREF\.?\s*[:#-]?\s*([A-Z0-9*_-]+)",
    )

    for pattern in patterns:
        match = re.search(pattern, concepto, re.IGNORECASE)

        if match:
            value = match.group(1).strip()

            if value:
                return value

    match = re.search(
        r"(?<!\S)(\*{2,}[A-Z0-9_-]+)",
        concepto,
        re.IGNORECASE,
    )

    return match.group(1) if match else None


def extract_auth_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    match = AUTH_PATTERN.search(concepto)

    return match.group(1).strip() if match else None


def extract_hora_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    explicit = re.search(
        r"\bHORA\.?\s*[:#-]?\s*([01]?\d|2[0-3]):[0-5]\d\b",
        concepto,
        re.IGNORECASE,
    )

    if explicit:
        match = TIME_PATTERN.search(explicit.group(0))
        return match.group(0) if match else None

    match = TIME_PATTERN.search(concepto)

    return match.group(0) if match else None


def extract_rfc_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    match = RFC_PATTERN.search(concepto)

    if not match:
        return None

    return match.group(1).replace(" ", "").upper()


def extract_banco_interbancario_from_concepto(
    concepto: str,
) -> Optional[str]:
    """
    Extrae la institución asociada a un PAGO INTERBANCARIO.

    Ejemplo:

        PAGO INTERBANCARIO A Mercado
        Pago W AL BENEF.
        PATRICIA,...

    Devuelve:

        Mercado Pago W
    """

    if not concepto:
        return None

    match = re.search(
        r"""
        \b
        PAGO
        \s+
        INTERBANCARIO
        \s+
        A
        \s+
        (.+?)
        (?=
            \s+
            AL
            \s+
            BENEF(?:ICIARIO)?
            \.?
            (?:\s|$)
        )
        """,
        concepto,
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )

    if not match:
        return None

    value = normalize_text(match.group(1))

    return value if value else None


def extract_sucursal_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    banco_interbancario = (
        extract_banco_interbancario_from_concepto(concepto)
    )

    if banco_interbancario:
        return banco_interbancario

    match = SUC_PATTERN.search(concepto)

    return match.group(1).strip() if match else None


def extract_caja_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    match = CAJA_PATTERN.search(concepto)

    return match.group(1).strip() if match else None


def extract_clave_rastreo_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    match = RASTREO_PATTERN.search(concepto)

    return match.group(1).strip() if match else None


def extract_clabe_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    labelled_patterns = (
        r"\bCLABE\.?\s*[:#-]?\s*(\d{18})\b",
        r"\bCTA\.?\s*BENEFICIARIO\s*[:#-]?\s*(\d{18})\b",
    )

    for pattern in labelled_patterns:
        match = re.search(
            pattern,
            concepto,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    match = CLABE_PATTERN.search(concepto)

    return match.group(1) if match else None


def extract_cuenta_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    patterns = (
        r"\bCTA\.?\s*BENEFICIARIO\s*[:#-]?\s*(\d{4,20})\b",
        r"\bCUENTA\.?\s*[:#-]?\s*(\d{4,20})\b",
        r"\bCTA\.?\s*[:#-]?\s*(\d{4,20})\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            concepto,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def extract_beneficiario_from_concepto(
    concepto: str,
) -> Optional[str]:
    if not concepto:
        return None

    patterns = (
        r"""
        \bAL\s+BENEF(?:ICIARIO)?\.?
        \s*[:#-]?\s*
        (.+?)
        (?=
            \s*\(DATO\b
            |
            \n\s*(?:CTA\.?\s*BENEFICIARIO|CLABE|CLAVE|RASTREO|REF\.?)\b
            |
            \Z
        )
        """,
        r"""
        \bBENEFICIARIO\.?
        \s*[:#-]?\s*
        (.+?)
        (?=
            \s*\(DATO\b
            |
            \n\s*(?:CTA\.?\s*BENEFICIARIO|CLABE|CLAVE|RASTREO|REF\.?)\b
            |
            \Z
        )
        """,
        r"\bA\s+FAVOR\s+DE\s+(.+)",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            concepto,
            re.IGNORECASE | re.VERBOSE | re.DOTALL,
        )

        if not match:
            continue

        value = normalize_text(match.group(1))

        if value:
            return value

    return None


# ============================================================
# TIPO DE OPERACIÓN Y CONSTRUCTOR
# ============================================================


def extract_tipo_operacion(
    cargo: float,
    abono: float,
    concepto: str,
) -> Optional[str]:
    if cargo != 0.0:
        return "CARGO"

    if abono != 0.0:
        return "ABONO"

    text = normalize_upper(concepto)

    if any(
        marker in text
        for marker in (
            "DEPOSITO",
            "ABONO",
            "TRANSFERENCIA RECIBIDA",
            "TRASPASO RECIBIDO",
        )
    ):
        return "ABONO"

    if any(
        marker in text
        for marker in (
            "RETIRO",
            "CARGO",
            "PAGO",
            "TRANSFERENCIA ENVIADA",
            "TRASPASO ENVIADO",
        )
    ):
        return "CARGO"

    return None


def build_movimiento(
    block: List[List[Dict[str, Any]]],
    configs: Dict[int, ColumnConfig],
) -> Optional[Movimiento]:
    if not block:
        return None

    first_line = block[0]
    first_page = word_page(first_line[0])
    config = get_config(first_page, configs)

    if is_saldo_anterior(first_line, config):
        return None

    concepto = extract_concepto(block, configs)
    cargo = extract_cargo(block, configs)
    abono = extract_abono(block, configs)
    saldo = extract_saldo(block, configs)

    return Movimiento(
        fecha_operacion=extract_fecha_operacion(
            first_line,
            config,
        ),
        fecha_liquidacion=None,
        concepto=concepto,
        tipo_operacion=extract_tipo_operacion(
            cargo,
            abono,
            concepto,
        ),
        cargo=cargo,
        abono=abono,
        referencia=extract_referencia_from_concepto(concepto),
        autorizacion=extract_auth_from_concepto(concepto),
        beneficiario=extract_beneficiario_from_concepto(concepto),
        cuenta_beneficiario=(
            extract_cuenta_beneficiario_from_concepto(concepto)
        ),
        clabe_beneficiario=(
            extract_clabe_beneficiario_from_concepto(concepto)
        ),
        rfc=extract_rfc_from_concepto(concepto),
        sucursal=extract_sucursal_from_concepto(concepto),
        caja=extract_caja_from_concepto(concepto),
        hora_operacion=extract_hora_from_concepto(concepto),
        clave_rastreo=extract_clave_rastreo_from_concepto(concepto),
        saldo_operacion=saldo,
        saldo_liquidacion=0.0,
        concepto_original=concepto,
    )


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================


def extract_movimientos_words(
    words: List[Dict[str, Any]],
) -> List[Movimiento]:
    """Extrae movimientos Banamex de forma multi-layout."""

    if not words:
        return []

    filtered_words = remove_after_grafico_transaccional(words)
    filtered_words = remove_banamex_header(filtered_words)

    lines = group_words_into_lines(filtered_words)

    if not lines:
        return []

    configs = build_page_configs(lines)
    blocks = build_blocks(lines, configs)

    movimientos: List[Movimiento] = []

    for block in blocks:
        movimiento = build_movimiento(block, configs)

        if movimiento is None:
            continue

        if (
            movimiento.cargo == 0.0
            and movimiento.abono == 0.0
            and movimiento.saldo_operacion == 0.0
        ):
            continue

        movimientos.append(movimiento)

    return movimientos