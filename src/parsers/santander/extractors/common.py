from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


def normalized(text: str) -> str:
    # Mantener los índices del original al reconocer etiquetas con acentos.
    return text.upper().translate(str.maketrans("ÁÉÍÓÚÜ", "AEIOUU"))


@dataclass
class Line:
    page: int
    y: float
    words: list[dict]

    @property
    def text(self) -> str:
        return " ".join(str(w["text"]).strip() for w in self.words).strip()


def group_lines(words: list[dict]) -> list[Line]:
    """Ordenar copias de las cajas por página y centro; nunca modificar al reader."""
    pages: dict[int, list[dict]] = {}
    for word in words:
        if str(word.get("text") or "").strip():
            pages.setdefault(int(word.get("page") or 1), []).append(word)
    result = []
    for page, items in sorted(pages.items()):
        heights = [float(w.get("bottom", w["top"])) - float(w["top"]) for w in items]
        heights = [h for h in heights if h > 0]
        tolerance = statistics.median(heights) * 0.3 if heights else 3.0
        lines: list[Line] = []
        for word in sorted(items, key=lambda w: (center_y(w), float(w["x0"]))):
            y = center_y(word)
            nearby = [line for line in lines[-4:] if abs(line.y - y) <= tolerance]
            if nearby:
                line = min(nearby, key=lambda line: abs(line.y - y))
                line.words.append(word)
                line.y = statistics.mean(center_y(w) for w in line.words)
            else:
                lines.append(Line(page, y, [word]))
        for line in sorted(lines, key=lambda line: line.y):
            line.words.sort(key=lambda w: float(w["x0"]))
            result.append(line)
    return result


def center_y(word: dict) -> float:
    top = float(word["top"])
    return (top + float(word.get("bottom", top))) / 2


def center_x(word: dict) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2


MONEY = re.compile(r"(?<![\w.])[-−]?\s*\$?\s*\d[\d,]*\.\d{2}(?![\d%])")
DATE = re.compile(r"(\d{1,2})\s*[-/]\s*([A-Z0-9]{3}|\d{1,2})\s*[-/]\s*(\d{4})")
ACCOUNT = re.compile(r"\b\d{2}-\d{8}-\d\b")
MONTHS = dict(zip("ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC".split(), range(1, 13)))
MONTHS.update({"JAN": 1, "APR": 4, "AUG": 8, "DEC": 12, "SET": 9})


def parse_date(match: re.Match) -> str | None:
    day, month, year = match.groups()
    month = month.replace("0", "O") if not month.isdigit() else month
    try:
        month_number = int(month) if month.isdigit() else MONTHS[month]
        return date(int(year), month_number, int(day)).strftime("%d/%m/%Y")
    except (ValueError, KeyError):
        return None


def dates(text: str) -> list[str]:
    return [value for m in DATE.finditer(normalized(text)) if (value := parse_date(m))]


def money(text: str) -> float | None:
    value = text.strip().replace(" ", "").replace("$", "").replace(",", "").replace("−", "-")
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    if not re.fullmatch(r"-?\d+\.\d{2}", value):
        return None
    try:
        return float(Decimal(value) * (-1 if negative else 1))
    except InvalidOperation:
        return None


def amount_after_label(line: Line, pattern: str) -> float | None:
    match = re.search(pattern, normalized(line.text))
    if match:
        value = MONEY.search(line.text, match.end())
        if value:
            return money(value[0])
    return None
