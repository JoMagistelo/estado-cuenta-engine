from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import date


def normalized(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).upper()


@dataclass
class Line:
    page: int
    y: float
    words: list[dict]

    @property
    def text(self) -> str:
        return " ".join(str(w["text"]).strip() for w in self.words).strip()


def group_lines(words: list[dict]) -> list[Line]:
    """Agrupa por centro vertical, sin depender del DPI ni del orden del OCR."""
    pages: dict[int, list[dict]] = {}
    for word in words:
        if str(word.get("text") or "").strip():
            pages.setdefault(int(word.get("page") or 1), []).append(word)
    result = []
    for page, page_words in sorted(pages.items()):
        heights = [float(w.get("bottom", w["top"])) - float(w["top"]) for w in page_words]
        heights = [h for h in heights if h > 0]
        tolerance = statistics.median(heights) * 0.30 if heights else 3.0
        lines: list[Line] = []
        for word in sorted(page_words, key=lambda w: (_center(w), float(w["x0"]))):
            y = _center(word)
            candidates = [line for line in lines[-4:] if abs(line.y - y) <= tolerance]
            if candidates:
                line = min(candidates, key=lambda line: abs(line.y - y))
                line.words.append(word)
                line.y = sum(_center(w) for w in line.words) / len(line.words)
            else:
                lines.append(Line(page, y, [word]))
        for line in sorted(lines, key=lambda line: line.y):
            line.words.sort(key=lambda w: float(w["x0"]))
            result.append(line)
    return result


def _center(word: dict) -> float:
    top = float(word["top"])
    return (top + float(word.get("bottom", top))) / 2


MONEY = re.compile(r"\$\s*([\d,]+\.\d{2})(?!\d)")
MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
LONG_DATE = re.compile(r"(\d{1,2})\s+DE\s+(\w+)\s+(?:DE\s+)?(\d{4})")


def long_dates(text: str) -> list[date]:
    dates = []
    for day, month, year in LONG_DATE.findall(normalized(text)):
        try:
            dates.append(date(int(year), MONTHS[month], int(day)))
        except (KeyError, ValueError):
            continue
    return dates


def amount_for_label(lines: list[Line], pattern: str) -> float | None:
    for line in lines:
        if re.search(pattern, normalized(line.text)):
            match = MONEY.search(line.text)
            if match:
                return float(match[1].replace(",", ""))
    return None
