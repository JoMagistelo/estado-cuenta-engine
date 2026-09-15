from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from statistics import median
from typing import Any, Callable


SpatialWord = dict[str, Any]

_MIN_SCALE = 0.80
_MAX_SCALE = 1.30
_BASE_LINE_TOLERANCE = 3.5

# Espacio canónico de los extractores Banamex. La tabla de movimientos es
# común a los layouts observados; la fila de producto de MiCuenta conserva el
# eje Y de su perfil histórico (Cuenta Base tiene otra altura en página 1).
_CANONICAL_TITLE_Y = 15.01
_CANONICAL_PAGE_LINE_Y = 39.16
_CANONICAL_MICUENTA_PRODUCT_ROW_Y = 397.0
_CANONICAL_MOVEMENTS_HEADER_Y = 96.2
_CANONICAL_MOVEMENTS_HEADER_X = {
    "FECHA": 35.53,
    "CONCEPTO": 157.87,
    "RETIROS": 293.24,
    "DEPOSITOS": 365.76,
    "SALDO": 441.51,
}

_MONEY_PATTERN = re.compile(r"^\(?[-+]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?\)?-?$")


@dataclass(frozen=True, slots=True)
class AffineTransform:
    """Transformación afín conservadora para cajas OCR axis-aligned.

    ``x`` corrige escala y traslación horizontal. ``y`` incorpora además una
    componente de ``x`` para retirar la inclinación observada en los renglones.
    """

    scale_x: float = 1.0
    offset_x: float = 0.0
    skew_y_from_x: float = 0.0
    scale_y: float = 1.0
    offset_y: float = 0.0

    def apply_x(self, value: float) -> float:
        return self.scale_x * value + self.offset_x

    def apply_y(self, x: float, y: float) -> float:
        return self.skew_y_from_x * x + self.scale_y * y + self.offset_y


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _word_page(word: SpatialWord) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _word_center_x(word: SpatialWord) -> float:
    x0 = _safe_float(word.get("x0", 0))
    x1 = _safe_float(word.get("x1", x0), x0)
    return (x0 + x1) / 2.0


def _word_center_y(word: SpatialWord) -> float:
    top = _safe_float(word.get("top", 0))
    bottom = _safe_float(word.get("bottom", top), top)
    return (top + bottom) / 2.0


def _word_height(word: SpatialWord) -> float:
    top = _safe_float(word.get("top", 0))
    bottom = _safe_float(word.get("bottom", top), top)
    return abs(bottom - top)


def _normalize_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized.upper())
    return " ".join(normalized.split())


def _group_words_into_lines(words: list[SpatialWord]) -> list[list[SpatialWord]]:
    if not words:
        return []

    ordered = sorted(
        words,
        key=lambda word: (
            _word_page(word),
            _word_center_y(word),
            _safe_float(word.get("x0", 0)),
        ),
    )
    heights = sorted(_word_height(word) for word in ordered if _word_height(word) > 0)
    typical_height = median(heights) if heights else 0.0
    tolerance = max(_BASE_LINE_TOLERANCE, typical_height * 0.45)

    lines: list[list[SpatialWord]] = []
    current: list[SpatialWord] = []
    current_page: int | None = None
    current_y: float | None = None

    for word in ordered:
        page = _word_page(word)
        center_y = _word_center_y(word)

        if current_y is None or page != current_page or abs(center_y - current_y) > tolerance:
            if current:
                current.sort(key=lambda item: _safe_float(item.get("x0", 0)))
                lines.append(current)
            current = [word]
            current_page = page
            current_y = center_y
            continue

        current.append(word)
        current_y = sum(_word_center_y(item) for item in current) / len(current)

    if current:
        current.sort(key=lambda item: _safe_float(item.get("x0", 0)))
        lines.append(current)

    return lines


def _line_text(line: list[SpatialWord]) -> str:
    return " ".join(
        str(word.get("text", "")).strip() for word in line if str(word.get("text", "")).strip()
    )


def _line_tokens(line: list[SpatialWord]) -> set[str]:
    return set(_normalize_text(_line_text(line)).split())


def _is_legacy_micuenta(words: list[SpatialWord]) -> bool:
    page_one_text = _normalize_text(
        " ".join(str(word.get("text", "")) for word in words if _word_page(word) == 1)
    )
    compact = page_one_text.replace(" ", "")

    return (
        "MICUENTA" in compact
        and "CUENTABASEBANAMEX" not in compact
        and "CUENTAPRIORITY" not in compact
    )


def _is_title_line(line: list[SpatialWord]) -> bool:
    return {"ESTADO", "DE", "CUENTA", "AL"}.issubset(_line_tokens(line))


def _is_page_line(line: list[SpatialWord]) -> bool:
    return "PAGINA" in _line_tokens(line)


def _is_micuenta_product_row(line: list[SpatialWord]) -> bool:
    compact = _normalize_text(_line_text(line)).replace(" ", "")
    money_count = sum(
        bool(_MONEY_PATTERN.fullmatch(str(word.get("text", "")).strip())) for word in line
    )
    return "MICUENTA" in compact and money_count >= 2


def _movement_header_words(line: list[SpatialWord]) -> dict[str, SpatialWord] | None:
    aliases = {
        "FECHA": {"FECHA"},
        "CONCEPTO": {"CONCEPTO", "DESCRIPCION"},
        "RETIROS": {"RETIROS", "CARGOS"},
        "DEPOSITOS": {"DEPOSITOS", "ABONOS"},
        "SALDO": {"SALDO"},
    }
    found: dict[str, SpatialWord] = {}

    for word in line:
        token = _normalize_text(word.get("text", ""))
        for canonical, options in aliases.items():
            if token in options and canonical not in found:
                found[canonical] = word
                break

    if set(found) == set(aliases):
        return found
    return None


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    """Resuelve un sistema pequeño por eliminación de Gauss con pivoteo."""

    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]

    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-9:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]

        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]

        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row], augmented[column])
            ]

    return [augmented[row][-1] for row in range(size)]


def _least_squares(
    rows: list[tuple[float, ...]],
    targets: list[float],
) -> list[float] | None:
    if not rows or len(rows) != len(targets):
        return None

    width = len(rows[0])
    normal_matrix = [
        [sum(row[left] * row[right] for row in rows) for right in range(width)]
        for left in range(width)
    ]
    normal_vector = [
        sum(row[column] * target for row, target in zip(rows, targets)) for column in range(width)
    ]
    return _solve_linear_system(normal_matrix, normal_vector)


def _fit_vertical_affine(
    first_line: list[SpatialWord],
    first_target_y: float,
    second_line: list[SpatialWord],
    second_target_y: float,
) -> tuple[float, float, float] | None:
    rows: list[tuple[float, float, float]] = []
    targets: list[float] = []

    for line, target_y in (
        (first_line, first_target_y),
        (second_line, second_target_y),
    ):
        for word in line:
            rows.append((_word_center_x(word), _word_center_y(word), 1.0))
            targets.append(target_y)

    coefficients = _least_squares(rows, targets)
    if coefficients is None:
        return None

    skew_y_from_x, scale_y, offset_y = coefficients
    if not _MIN_SCALE <= scale_y <= _MAX_SCALE:
        return None
    if abs(skew_y_from_x) > 0.08:
        return None
    return skew_y_from_x, scale_y, offset_y


def _fit_horizontal_transform(
    header_words: dict[str, SpatialWord],
) -> tuple[float, float] | None:
    source = [_word_center_x(header_words[name]) for name in _CANONICAL_MOVEMENTS_HEADER_X]
    target = [_CANONICAL_MOVEMENTS_HEADER_X[name] for name in _CANONICAL_MOVEMENTS_HEADER_X]
    source_mean = sum(source) / len(source)
    target_mean = sum(target) / len(target)
    denominator = sum((value - source_mean) ** 2 for value in source)
    if denominator < 1e-9:
        return None

    scale = (
        sum(
            (source_value - source_mean) * (target_value - target_mean)
            for source_value, target_value in zip(source, target)
        )
        / denominator
    )
    offset = target_mean - scale * source_mean

    if not _MIN_SCALE <= scale <= _MAX_SCALE:
        return None
    return scale, offset


def _find_line(
    lines: list[list[SpatialWord]],
    predicate: Callable[[list[SpatialWord]], bool],
) -> list[SpatialWord] | None:
    return next((line for line in lines if predicate(line)), None)


def _page_transforms(words: list[SpatialWord]) -> dict[int, AffineTransform]:
    by_page: dict[int, list[list[SpatialWord]]] = {}
    for line in _group_words_into_lines(words):
        by_page.setdefault(_word_page(line[0]), []).append(line)

    transforms: dict[int, AffineTransform] = {}

    for page, lines in by_page.items():
        title = _find_line(lines, _is_title_line)
        if title is None:
            continue

        header_line = _find_line(lines, lambda line: _movement_header_words(line) is not None)

        if page == 1:
            second_line = _find_line(lines, _is_micuenta_product_row)
            second_target_y = _CANONICAL_MICUENTA_PRODUCT_ROW_Y
        elif header_line is not None:
            second_line = header_line
            second_target_y = _CANONICAL_MOVEMENTS_HEADER_Y
        else:
            second_line = _find_line(lines, _is_page_line)
            second_target_y = _CANONICAL_PAGE_LINE_Y

        if second_line is None:
            continue

        vertical = _fit_vertical_affine(
            title,
            _CANONICAL_TITLE_Y,
            second_line,
            second_target_y,
        )
        if vertical is None:
            continue

        scale_x = 1.0
        offset_x = 0.0
        if header_line is not None:
            header_words = _movement_header_words(header_line)
            if header_words is not None:
                horizontal = _fit_horizontal_transform(header_words)
                if horizontal is not None:
                    scale_x, offset_x = horizontal

        transforms[page] = AffineTransform(
            scale_x=scale_x,
            offset_x=offset_x,
            skew_y_from_x=vertical[0],
            scale_y=vertical[1],
            offset_y=vertical[2],
        )

    return transforms


def _transform_word(word: SpatialWord, transform: AffineTransform) -> SpatialWord:
    item = dict(word)
    x0 = _safe_float(word.get("x0", 0))
    x1 = _safe_float(word.get("x1", x0), x0)
    top = _safe_float(word.get("top", 0))
    bottom = _safe_float(word.get("bottom", top), top)
    doctop_offset = _safe_float(word.get("doctop", top), top) - top

    transformed_x = sorted((transform.apply_x(x0), transform.apply_x(x1)))
    transformed_y = [transform.apply_y(x, y) for x in (x0, x1) for y in (top, bottom)]

    item["x0"], item["x1"] = transformed_x
    item["top"] = min(transformed_y)
    item["bottom"] = max(transformed_y)
    item["doctop"] = doctop_offset + item["top"]
    item["width"] = item["x1"] - item["x0"]
    item["height"] = item["bottom"] - item["top"]
    return item


def _snap_transformed_line_baselines(
    words: list[SpatialWord],
    transformed_pages: set[int],
) -> None:
    """Elimina residuos subpíxel para conservar el orden izquierda-derecha."""

    for line in _group_words_into_lines(words):
        if _word_page(line[0]) not in transformed_pages:
            continue

        target_top = float(median(_safe_float(word.get("top", 0)) for word in line))
        target_bottom = float(median(_safe_float(word.get("bottom", target_top)) for word in line))
        for word in line:
            delta = target_top - _safe_float(word.get("top", 0))
            word["top"] = target_top
            word["bottom"] = target_bottom
            word["doctop"] = _safe_float(word.get("doctop", target_top)) + delta
            word["height"] = target_bottom - target_top


def normalize_banamex_words(words: list[SpatialWord]) -> list[SpatialWord]:
    """Alinea MiCuenta OCR con el espacio canónico del parser Banamex.

    ``statement_processor`` invoca este módulo únicamente para documentos OCR.
    Aun así, el normalizador exige señales inequívocas de MiCuenta y dos anclas
    por página. Cuenta Base, Priority y páginas sin registro confiable conservan
    exactamente sus objetos y coordenadas originales.
    """

    if not words or not _is_legacy_micuenta(words):
        return words

    transforms = _page_transforms(words)
    if not transforms:
        return words

    normalized = [
        _transform_word(word, transforms[_word_page(word)])
        if _word_page(word) in transforms
        else word
        for word in words
    ]
    _snap_transformed_line_baselines(normalized, set(transforms))
    return normalized


def normalize_words(words: list[SpatialWord]) -> list[SpatialWord]:
    """Alias compatible con el contrato genérico de normalizadores."""

    return normalize_banamex_words(words)
