from __future__ import annotations

import re
from typing import Any, Iterable


# ============================================================
# NORMALIZACIÓN BÁSICA
# ============================================================

def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def merge_split_dates(text: str) -> str:
    """
    Une fechas partidas por extracción espacial, por ejemplo:
    27/06/20 22 -> 27/06/2022
    """
    text = re.sub(r"(\d{2}/\d{2}/\d{2})\s+(\d{2})", r"\1\2", text)
    text = re.sub(r"(\d{2}/[A-Z]{3})\s+(\d{2})", r"\1\2", text, flags=re.I)
    return text


def normalize_fragmented_text(text: str) -> str:
    return normalize_whitespace(merge_split_dates(text))


# ============================================================
# CELDAS / FILAS / TABLAS
# ============================================================

def cell_text(cell: Any) -> str:
    if cell is None:
        return ""
    return normalize_whitespace(str(cell).replace("\n", " "))


def compact_row(row: list[Any]) -> list[str]:
    return [
        cell_text(cell)
        for cell in row
        if cell_text(cell)
    ]


def compact_table(table: list[list[Any]]) -> list[list[str]]:
    result: list[list[str]] = []

    for row in table:
        new_row = compact_row(row)
        if new_row:
            result.append(new_row)

    return result


def row_text(row: list[Any]) -> str:
    return normalize_whitespace(" ".join(cell_text(cell) for cell in row if cell_text(cell)))


def table_text(table: list[list[Any]]) -> str:
    return "\n".join(
        row_text(row)
        for row in table
        if row_text(row)
    )


def table_contains_keywords(
    table: list[list[Any]],
    keywords: str | Iterable[str],
    all_keywords: bool = True,
) -> bool:
    if isinstance(keywords, str):
        keywords = [keywords]

    text = table_text(table).casefold()

    if all_keywords:
        return all(keyword.casefold() in text for keyword in keywords)

    return any(keyword.casefold() in text for keyword in keywords)


def find_table(
    tables: list[list[list[Any]]],
    keywords: str | Iterable[str],
    all_keywords: bool = True,
) -> list[list[str]] | None:
    """
    Devuelve la primera tabla que cumpla el criterio.
    La tabla se devuelve compactada (sin celdas vacías).
    """
    for table in tables:
        if table_contains_keywords(table, keywords, all_keywords=all_keywords):
            return compact_table(table)
    return None


def find_row(
    table: list[list[Any]],
    keyword: str,
) -> list[str] | None:
    keyword_cf = keyword.casefold()

    for row in table:
        if keyword_cf in row_text(row).casefold():
            return compact_row(row)

    return None


def find_row_value(
    table: list[list[Any]] | None,
    keyword: str,
) -> str | None:
    if not table:
        return None

    row = find_row(table, keyword)
    if not row:
        return None

    return row[-1] if row else None


def extract_digits(text: str | None) -> str | None:
    if not text:
        return None

    digits = "".join(re.findall(r"\d", text))
    return digits or None


# ============================================================
# PARSEO DE NÚMEROS
# ============================================================

def parse_amount(value: Any) -> float:
    if value is None:
        return 0.0

    text = normalize_whitespace(str(value))
    text = text.replace("$", "").replace(",", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0

    return 0.0


def parse_int(value: Any) -> int:
    if value is None:
        return 0

    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else 0


# ============================================================
# HELPERS BBVA
# ============================================================

def extract_clabe_from_table(table: list[list[Any]]) -> str | None:
    for row in table:
        text = row_text(row)
        if "CLABE" in text.casefold():
            digits = extract_digits(text)
            if digits and len(digits) >= 18:
                return digits[:18]
    return None


def extract_value_after_label_from_text(
    text: str,
    pattern: str,
    flags: int = re.IGNORECASE | re.DOTALL,
) -> str | None:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return normalize_whitespace(m.group(1))