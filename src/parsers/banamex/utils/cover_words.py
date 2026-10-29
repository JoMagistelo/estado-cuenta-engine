"""Alineación por cabeceras para las tablas de la portada etiquetada."""

from __future__ import annotations

import re
import unicodedata
from statistics import mean


def _label(word: dict) -> str:
    text = unicodedata.normalize("NFD", str(word.get("text", "")).upper())
    return re.sub(r"[^A-Z]", "", text)


def align_table_words(words: list[dict]) -> list[dict]:
    pages: dict[int, list[dict]] = {}
    for word in words:
        pages.setdefault(int(word.get("page") or 1), []).append(word)
    slopes = {}
    aliases = {"FECHA", "CONCEPTO", "DESCRIPCION", "RETIROS", "DEPOSITOS", "SALDO"}
    for page, items in pages.items():
        for concept in items:
            if _label(concept) not in ("CONCEPTO", "DESCRIPCION"):
                continue
            cy = (float(concept["top"]) + float(concept["bottom"])) / 2
            height = max(float(concept["bottom"]) - float(concept["top"]), 1)
            anchors = {}
            for word in items:
                label = _label(word)
                y = (float(word["top"]) + float(word["bottom"])) / 2
                if label in aliases and abs(y - cy) < height * 3:
                    if label not in anchors or abs(y - cy) < abs(anchors[label][1] - cy):
                        anchors[label] = ((float(word["x0"]) + float(word["x1"])) / 2, y)
            if len(anchors) < 4 or not {"RETIROS", "DEPOSITOS"}.issubset(anchors):
                continue
            points = list(anchors.values())
            mx, my = mean(p[0] for p in points), mean(p[1] for p in points)
            denominator = sum((x - mx) ** 2 for x, y in points)
            if not denominator:
                continue
            slope = sum((x - mx) * (y - my) for x, y in points) / denominator
            residual = max(abs(y - my - slope * (x - mx)) for x, y in points)
            if 0.003 <= abs(slope) <= 0.06 and residual <= height * 0.4:
                slopes[page] = (slope, mx)
            break
    if not slopes:
        return words
    result = []
    for word in words:
        page = int(word.get("page") or 1)
        if page not in slopes:
            result.append(word)
            continue
        slope, origin = slopes[page]
        delta = slope * ((float(word["x0"]) + float(word["x1"])) / 2 - origin)
        result.append(
            {
                **word,
                "top": float(word["top"]) - delta,
                "bottom": float(word["bottom"]) - delta,
                **({"doctop": float(word["doctop"]) - delta} if "doctop" in word else {}),
            }
        )
    return result
