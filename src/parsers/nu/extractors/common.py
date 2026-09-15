from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

SpatialWord = Dict[str, Any]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_page(word: SpatialWord) -> int:
    try:
        return int(word.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def word_center_y(word: SpatialWord) -> float:
    return (safe_float(word.get("top")) + safe_float(word.get("bottom"))) / 2.0


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def normalize_upper(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.upper()


def compact_text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_upper(value))


def clean_word_text(value: Any) -> str:
    text = normalize_text(value)
    if not text or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9$+%-]", text):
        return ""
    return text.strip(" _—–|¦")


@dataclass(slots=True)
class SpatialLine:
    page: int
    words: List[SpatialWord]

    @property
    def center_y(self) -> float:
        return sum(word_center_y(word) for word in self.words) / len(self.words)

    @property
    def doctop(self) -> float:
        values = [safe_float(word.get("doctop"), self.center_y) for word in self.words]
        return sum(values) / len(values)

    @property
    def text(self) -> str:
        return " ".join(
            value
            for value in (clean_word_text(word.get("text", "")) for word in self.words)
            if value
        ).strip()


def _line_tolerance(page_words: Sequence[SpatialWord]) -> float:
    heights = [
        safe_float(word.get("bottom")) - safe_float(word.get("top"))
        for word in page_words
    ]
    heights = [height for height in heights if 0.1 <= height <= 28.0]
    if not heights:
        return 2.5
    return max(1.5, min(4.5, statistics.median(heights) * 0.42))


def group_words_into_lines(words: Sequence[SpatialWord]) -> List[SpatialLine]:
    pages: Dict[int, List[SpatialWord]] = {}
    for word in words:
        if clean_word_text(word.get("text", "")):
            pages.setdefault(safe_page(word), []).append(word)

    result: List[SpatialLine] = []
    for page in sorted(pages):
        page_words = pages[page]
        tolerance = _line_tolerance(page_words)
        groups: List[List[SpatialWord]] = []
        centers: List[float] = []

        for word in sorted(
            page_words,
            key=lambda item: (word_center_y(item), safe_float(item.get("x0"))),
        ):
            center_y = word_center_y(word)
            candidate: Optional[int] = None
            candidate_delta = float("inf")
            for index in range(max(0, len(groups) - 8), len(groups)):
                delta = abs(center_y - centers[index])
                if delta <= tolerance and delta < candidate_delta:
                    candidate = index
                    candidate_delta = delta

            if candidate is None:
                groups.append([word])
                centers.append(center_y)
            else:
                groups[candidate].append(word)
                centers[candidate] = sum(word_center_y(item) for item in groups[candidate]) / len(
                    groups[candidate]
                )

        for group in groups:
            group.sort(key=lambda item: safe_float(item.get("x0")))
            result.append(SpatialLine(page=page, words=group))

    result.sort(key=lambda line: (line.page, line.center_y))
    return result


def parse_money(value: Any) -> Optional[float]:
    text = normalize_text(value)
    if not text or not re.search(r"\d", text):
        return None
    negative = "-" in text or ("(" in text and ")" in text)
    compact = re.sub(r"[^0-9.,]", "", text)
    if not compact:
        return None

    if compact.count(".") > 1 and "," not in compact:
        parts = compact.split(".")
        compact = "".join(parts[:-1]) + "." + parts[-1]
    compact = compact.replace(",", "")
    try:
        result = float(compact)
    except ValueError:
        return None
    return -result if negative else result
