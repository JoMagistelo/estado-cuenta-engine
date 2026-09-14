"""Recuperación localizada de importes Scotiabank omitidos por Tesseract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output


SpatialWord = dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_page(word: SpatialWord) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _center_y(word: SpatialWord) -> float:
    return (_safe_float(word.get("top")) + _safe_float(word.get("bottom"))) / 2.0


def _upper(word: SpatialWord) -> str:
    return str(word.get("text", "") or "").strip().upper()


def _normalize_summary_money(value: Any) -> str | None:
    """Devuelve un importe canónico sólo cuando el OCR conserva sus dígitos.

    Scotiabank imprime dos decimales en ``Resumen de Saldos``. El segundo pase
    puede adherir bordes de celda al importe o perder separadores, pero no se
    completan dígitos ausentes. Por ejemplo, ``$4790456`` se normaliza a
    ``$47,904.56`` porque conserva todos los dígitos impresos.
    """

    raw = str(value or "").strip()
    if not raw or not re.search(r"\d", raw):
        return None

    normalized = (
        raw.replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace(" ", "")
        .strip("[]{}|!;:")
    )
    accounting_negative = normalized.startswith("(") and normalized.endswith(")")
    normalized = normalized.strip("()")
    negative = (
        normalized.startswith("-")
        or normalized.endswith("-")
        or accounting_negative
    )
    normalized = normalized.strip("-")
    currency_hint = "$" in normalized
    numeric = re.sub(r"[^0-9.,]", "", normalized)
    if not numeric:
        return None

    amount: float | None = None
    if "," in numeric and "." in numeric:
        decimal_sep = "." if numeric.rfind(".") > numeric.rfind(",") else ","
        left, right = numeric.rsplit(decimal_sep, 1)
        if len(right) == 2:
            digits_left = re.sub(r"[.,]", "", left)
            if digits_left:
                amount = float(f"{digits_left}.{right}")
    elif numeric.count(",") == 1 and "." not in numeric:
        left, right = numeric.split(",", 1)
        if len(right) == 2 and left.isdigit():
            amount = float(f"{left}.{right}")
        elif 1 <= len(left) <= 3 and len(right) == 5 and (left + right).isdigit():
            digits = left + right
            amount = float(f"{digits[:-2]}.{digits[-2:]}")
    elif numeric.count(".") == 1 and "," not in numeric:
        left, right = numeric.split(".", 1)
        if len(right) == 2 and left.isdigit():
            amount = float(f"{left}.{right}")
    elif numeric.isdigit() and currency_hint and len(numeric) >= 3:
        amount = float(f"{numeric[:-2]}.{numeric[-2:]}")

    if amount is None:
        return None
    if negative:
        amount = -amount
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def _summary_title(
    page_words: Sequence[SpatialWord],
    page_width: float,
) -> SpatialWord | None:
    for word in page_words:
        if _upper(word) != "RESUMEN" or _safe_float(word.get("x0")) >= page_width * 0.35:
            continue
        if any(
            "SALDOS" in _upper(candidate)
            and _safe_float(candidate.get("x0")) > _safe_float(word.get("x0"))
            and abs(_center_y(candidate) - _center_y(word)) <= 8.0
            for candidate in page_words
        ):
            return word
    return None


def _summary_structure_score(
    page_words: Sequence[SpatialWord],
    page_width: float,
    title_y: float,
) -> int:
    left_words = [
        _upper(word)
        for word in page_words
        if page_width * 0.05 <= _safe_float(word.get("x0")) < page_width * 0.31
        and title_y < _center_y(word) < title_y + 150.0
    ]
    joined = " ".join(left_words)
    return sum(
        marker in joined
        for marker in ("INTERES", "RETIRO", "COMISION", "IMPUEST", "SALDO")
    )


def _core_money_count(
    page_words: Sequence[SpatialWord],
    page_width: float,
    title_y: float,
) -> int:
    left = page_width * 0.30
    right = page_width * 0.405
    return sum(
        _normalize_summary_money(word.get("text")) is not None
        for word in page_words
        if left <= _safe_float(word.get("x0")) < right
        and title_y < _center_y(word) < title_y + 145.0
    )


def _find_summary_candidate(
    words: Sequence[SpatialWord],
) -> tuple[int, list[SpatialWord], float, float] | None:
    pages: dict[int, list[SpatialWord]] = {}
    for word in words:
        pages.setdefault(_safe_page(word), []).append(word)

    candidates: list[tuple[int, int, list[SpatialWord], float, float]] = []

    for page, page_words in sorted(pages.items()):
        page_width = max(
            612.0,
            max((_safe_float(word.get("x1")) for word in page_words), default=0.0) + 18.0,
        )
        title = _summary_title(page_words, page_width)
        if title is None:
            continue
        title_y = _center_y(title)
        structure = _summary_structure_score(page_words, page_width, title_y)
        page_has_bank_mark = any(
            "SCOTIABANK" in _upper(word)
            for word in page_words
        )
        layout_mark = (
            any("COMPORTAMIENTO" in _upper(word) for word in page_words)
            and any("SOBREGIRO" in _upper(word) for word in page_words)
        )
        if structure < 3 or not (page_has_bank_mark or layout_mark):
            continue
        candidates.append((structure, -page, page_words, page_width, title_y))

    if not candidates:
        return None
    _, negative_page, page_words, width, title_y = max(
        candidates,
        key=lambda item: (item[0], item[1]),
    )
    return -negative_page, page_words, width, title_y


def recover_scotiabank_summary_page(
    image: Image.Image,
    page_words: Sequence[SpatialWord],
    logical_page: int,
    page_width: float,
    doctop_offset: float,
    *,
    title_y: float | None = None,
) -> list[SpatialWord]:
    """Relee únicamente la columna monetaria de un resumen Scotiabank incompleto."""

    if title_y is None:
        title = _summary_title(page_words, page_width)
        if title is None:
            return []
        title_y = _center_y(title)
    if _summary_structure_score(page_words, page_width, title_y) < 3:
        return []
    if _core_money_count(page_words, page_width, title_y) >= 4:
        return []

    left = page_width * 0.30
    right = page_width * 0.405
    top = max(0.0, title_y - 1.0)
    bottom = title_y + 215.0
    pixel_to_pdf = page_width / image.width
    if pixel_to_pdf <= 0:
        return []

    px0 = max(0, int(left / pixel_to_pdf))
    py0 = max(0, int(top / pixel_to_pdf))
    px1 = min(image.width, int(right / pixel_to_pdf))
    py1 = min(image.height, int(bottom / pixel_to_pdf))
    if px1 <= px0 or py1 <= py0:
        return []

    try:
        data = pytesseract.image_to_data(
            image.crop((px0, py0, px1, py1)),
            lang="spa",
            config="--oem 3 --psm 11",
            output_type=Output.DICT,
            timeout=30,
        )
    except (RuntimeError, pytesseract.TesseractError):
        return []

    extra: list[SpatialWord] = []
    for index, raw_text in enumerate(data.get("text", [])):
        canonical = _normalize_summary_money(raw_text)
        if canonical is None:
            continue
        try:
            x0 = (px0 + float(data["left"][index])) * pixel_to_pdf
            y0 = (py0 + float(data["top"][index])) * pixel_to_pdf
            width = float(data["width"][index]) * pixel_to_pdf
            height = float(data["height"][index]) * pixel_to_pdf
            confidence = float(data["conf"][index])
        except (KeyError, IndexError, TypeError, ValueError):
            continue

        if any(
            abs(_safe_float(word.get("x0")) - x0) <= 8.0
            and abs(_safe_float(word.get("top")) - y0) <= 5.0
            and _normalize_summary_money(word.get("text")) == canonical
            for word in page_words
        ):
            continue

        extra.append(
            {
                "text": canonical,
                "x0": x0,
                "x1": x0 + width,
                "top": y0,
                "bottom": y0 + height,
                "doctop": doctop_offset + y0,
                "width": width,
                "height": height,
                "upright": True,
                "direction": "ltr",
                "page": logical_page,
                "confidence": confidence,
                "source": "scotiabank_summary_tesseract_retry",
            }
        )

    recovered_core = [
        word
        for word in extra
        if title_y < _center_y(word) < title_y + 145.0
    ]
    return extra if len(recovered_core) >= 2 else []


def recover_scotiabank_summary_words(
    file_path: str | Path,
    words: Sequence[SpatialWord],
    *,
    start_page: int = 0,
) -> list[SpatialWord]:
    """Recupera importes impresos que PSM 3 omitió, sin calcularlos."""

    candidate = _find_summary_candidate(words)
    if candidate is None:
        return []
    logical_page, page_words, _, title_y = candidate
    if _core_money_count(page_words, max(612.0, max(
        (_safe_float(word.get("x1")) for word in page_words), default=0.0
    ) + 18.0), title_y) >= 4:
        return []

    path = Path(file_path).expanduser()
    if not path.is_file():
        return []

    physical_index = int(start_page or 0) + logical_page - 1
    try:
        pdf = pdfium.PdfDocument(str(path))
        if physical_index < 0 or physical_index >= len(pdf):
            return []
        page = pdf[physical_index]
        page_width, _ = page.get_size()
        bitmap = page.render(scale=300 / 72)
        image = ImageOps.autocontrast(bitmap.to_pil().convert("L"))
        doctop_offset = 0.0
        if page_words:
            first = page_words[0]
            doctop_offset = _safe_float(first.get("doctop")) - _safe_float(first.get("top"))
        return recover_scotiabank_summary_page(
            image,
            page_words,
            logical_page,
            page_width,
            doctop_offset,
            title_y=title_y,
        )
    except (OSError, RuntimeError, ValueError, pytesseract.TesseractError):
        return []
