"""Relectura acotada de celdas cuyo detector puede cortar dígitos iniciales."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable


def _text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.upper())
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def is_banamex_cover(words: list[dict]) -> bool:
    text = _text(" ".join(str(w.get("text", "")) for w in words))
    text = re.sub(r"\b[NM][UV][MN]ERO\b", "NUMERO", text)
    text = re.sub(r"\bGALDO\b", "SALDO", text)
    return "BANAMEX" in text and all(
        marker in text
        for marker in (
            "NUMERO DE CONTRATO",
            "NUMERO DE CUENTA DE CHEQUES",
            "CLABE",
            "SALDO AL CORTE",
        )
    )


def _amount(value: str) -> tuple[str, bool] | None:
    value = value.strip().replace(" ", "").replace("$", "").replace("−", "-")
    if not re.fullmatch(r"\(?-?(?:\d+|\d{1,3}(?:[.,]\d{3})+)[.,]\d{2}\)?-?", value):
        return None
    integer = re.sub(r"[^\d]", "", value[:-3])
    if not integer:
        return None
    digits = re.sub(r"\D", "", value)
    negative = value.startswith(("-", "(")) or value.endswith("-")
    return digits, negative


def rescue_money_cells(
    image,
    words: list[dict],
    page_width: float,
    recognize: Callable,
) -> tuple[list[dict], int]:
    """Reutiliza el reconocedor cargado: dos márgenes deben coincidir.

    Sólo acepta el mismo importe o dígitos iniciales visibles en ambos recortes.
    Nunca recibe saldos, totales esperados ni resultados de validaciones.
    """
    labels = [w for w in words if _text(str(w.get("text", ""))).strip(".: ") == "CONCEPTO"]
    header = None
    for concept in labels:
        cy = (float(concept["top"]) + float(concept["bottom"])) / 2
        height = max(float(concept["bottom"]) - float(concept["top"]), 1)
        matches = [
            w
            for w in words
            if _text(str(w.get("text", ""))).strip(".: ") in ("RETIROS", "DEPOSITOS", "SALDO")
            and abs((float(w["top"]) + float(w["bottom"])) / 2 - cy) < height * 3
        ]
        if len(matches) >= 2:
            header = (min(float(w["x0"]) for w in matches) - height, cy + height)
            break
    if header is None:
        return words, 0
    candidates = [
        w
        for w in words
        if float(w["x0"]) >= header[0]
        and float(w["top"]) > header[1]
        and _amount(str(w.get("text", "")))
    ]
    if not candidates:
        return words, 0
    scale = image.width / page_width
    crops = []
    for word in candidates:
        height = max(float(word["bottom"]) - float(word["top"]), 1)
        for margin in (0.45, 0.9):
            box = (
                max(0, int((float(word["x0"]) - height * margin) * scale)),
                max(0, int((float(word["top"]) - height * 0.4) * scale)),
                min(image.width, int((float(word["x1"]) + height * margin) * scale)),
                min(image.height, int((float(word["bottom"]) + height * 0.4) * scale)),
            )
            crops.append(image.crop(box))
    try:
        readings = list(recognize(crops))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return words, 0
    finally:
        for crop in crops:
            crop.close()
    if len(readings) != len(crops):
        return words, 0
    changes = {}
    for i, word in enumerate(candidates):
        first, second = readings[2 * i : 2 * i + 2]
        text = str(first[0]).strip()
        original, proposed = _amount(str(word["text"])), _amount(text)
        if (
            text != str(second[0]).strip()
            or min(float(first[1]), float(second[1])) < 0.97
            or proposed is None
            or original is None
            or proposed[1] != original[1]
        ):
            continue
        old_digits, new_digits = original[0], proposed[0]
        if not new_digits.endswith(old_digits) or not 0 < len(new_digits) - len(old_digits) <= 2:
            continue
        # La caja se amplía para que la capa PDF incluya el prefijo reconocido.
        height = float(word["bottom"]) - float(word["top"])
        changes[id(word)] = {
            **word,
            "text": text,
            "x0": max(0, float(word["x0"]) - height * 0.9),
            "width": float(word["x1"]) - max(0, float(word["x0"]) - height * 0.9),
            "confidence": min(float(first[1]), float(second[1])) * 100,
        }
    return [changes.get(id(w), w) for w in words], len(changes)
