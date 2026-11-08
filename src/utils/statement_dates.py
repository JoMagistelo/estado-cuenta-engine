"""Calendar dates shared by Excel normalization and the CEP workflow.

Yearless bank dates are resolved against the statement interval, never today's
year. Explicit years are retained, including dates outside the reported period.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta


MONTHS = {
    name: number
    for number, names in enumerate((
        ("ENE", "ENERO", "JAN", "JANUARY"),
        ("FEB", "FEBRERO", "FEBRUARY"),
        ("MAR", "MARZO", "MARCH"),
        ("ABR", "ABRIL", "APR", "APRIL"),
        ("MAY", "MAYO"),
        ("JUN", "JUNIO", "JUNE"),
        ("JUL", "JULIO", "JULY"),
        ("AGO", "AGOSTO", "AUG", "AUGUST"),
        ("SEP", "SEPT", "SET", "SEPTIEMBRE", "SETIEMBRE", "SEPTEMBER"),
        ("OCT", "OCTUBRE", "OCTOBER"),
        ("NOV", "NOVIEMBRE", "NOVEMBER"),
        ("DIC", "DICIEMBRE", "DEC", "DECEMBER"),
    ), 1)
    for name in names
}


def text_key(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in value if not unicodedata.combining(c)).upper().strip()


@dataclass(frozen=True)
class DateResolution:
    value: date | None
    status: str
    detail: str = ""


def date_parts(value: object) -> tuple[int, int | None, int | None] | None:
    """Read the actual formats emitted by the bank parsers (day first)."""
    if isinstance(value, datetime):
        return value.day, value.month, value.year
    if isinstance(value, date):
        return value.day, value.month, value.year
    if not isinstance(value, str):
        return None
    s = re.sub(r"\bDE[L]?\b", " ", text_key(value)).strip(" *|_")
    s = re.sub(r"^(?:(?:FECHA\s+(?:CORTE|CIERRE)|AL|CORTE|PERIODO)\s*[:#-]?\s*)+", "", s)
    s = re.sub(r"\s*\$.*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    iso = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T]00:00:00)?", s)
    compact = re.fullmatch(r"(20\d{2})(\d{2})(\d{2})", s)
    if iso or compact:
        y, m, d = map(int, (iso or compact).groups())
        return d, m, y
    if re.fullmatch(r"\d{1,2}", s):
        return int(s), None, None
    match = re.fullmatch(
        r"(\d{1,2})\s*[/ .-]?\s*([A-Z]+|\d{1,2})"
        r"(?:\s*[/ .-]?\s*(\d{4}|\d{2}))?", s
    )
    if match:
        d, month, year = match.groups()
        m = int(month) if month.isdigit() else MONTHS.get(month)
        if m is None:
            return None
        y = int(year) if year else None
        if y is not None and y < 100:
            y += 2000 if y < 70 else 1900
        return int(d), m, y
    if re.fullmatch(r"\d{1,2}", s):
        return int(s), None, None
    return None


def full_date(value: object) -> date | None:
    parts = date_parts(value)
    if parts and parts[1] is not None and parts[2] is not None:
        try:
            return date(parts[2], parts[1], parts[0])
        except ValueError:
            pass
    return None


def _candidates(parts, years, months=range(1, 13)) -> list[date]:
    day, month, _year = parts
    result = []
    for year in sorted(set(years)):
        for candidate_month in ([month] if month else months):
            try:
                result.append(date(year, candidate_month, day))
            except ValueError:
                continue
    return result


def statement_interval(start: object, end: object, cutoff: object = None):
    """Complete partial period endpoints only when anchored by a full date."""
    first, last, cut = full_date(start), full_date(end), full_date(cutoff)
    last = last or cut
    if first is None and last and date_parts(start):
        options = [d for d in _candidates(date_parts(start), (last.year - 1, last.year))
                   if 0 <= (last - d).days <= 370]
        if len(options) == 1:
            first = options[0]
    if full_date(end) is None and first and date_parts(end):
        options = [d for d in _candidates(date_parts(end), (first.year, first.year + 1))
                   if 0 <= (d - first).days <= 370]
        if len(options) == 1:
            last = options[0]
    return first, last, cut


def resolve_date(
    value: object,
    start: object = None,
    end: object = None,
    cutoff: object = None,
    *,
    filename: str = "",
    settlement: bool = False,
) -> DateResolution:
    if value is None or value == "":
        return DateResolution(None, "VACIA")
    parts = date_parts(value)
    if not parts:
        return DateResolution(None, "REVISAR", "Formato de fecha no reconocido")
    first, last, cut = statement_interval(start, end, cutoff)
    if parts[2] is not None:
        parsed = full_date(value)
        if not parsed:
            return DateResolution(None, "REVISAR", "Fecha de calendario inválida")
        if first and last and not first <= parsed <= last + timedelta(days=7 if settlement else 0):
            return DateResolution(parsed, "FUERA_DE_PERIODO", "Se conserva el año explícito")
        return DateResolution(parsed, "EXPLICITA")
    if first and last:
        if first > last:
            return DateResolution(None, "REVISAR", "Periodo de inicio posterior al fin")
        options = [d for d in _candidates(parts, range(first.year, last.year + 1))
                   if first <= d <= last]
        if not options and settlement:
            options = [d for d in _candidates(parts, range(first.year, last.year + 2))
                       if first - timedelta(days=3) <= d <= last + timedelta(days=7)]
        if len(options) == 1:
            return DateResolution(options[0], "POR_PERIODO")
        return DateResolution(None, "REVISAR", "Fecha sin año fuera del periodo o ambigua")
    if last:
        # A cutoff is an end date, not the label/month on a renamed PDF.
        # In January, December belongs to the preceding year.
        options = [d for d in _candidates(parts, (last.year - 1, last.year, last.year + 1))
                   if last - timedelta(days=62) <= d <= last + timedelta(days=7 if settlement else 0)]
        if len(options) == 1:
            return DateResolution(options[0], "POR_CORTE", "Sólo hay fecha final; ventana de 62 días")
    if first and not last:
        options = [d for d in _candidates(parts, (first.year, first.year + 1))
                   if first <= d <= first + timedelta(days=62)]
        if len(options) == 1:
            return DateResolution(options[0], "POR_INICIO")
    # Filename is a last resort, restricted to its explicit month. A filename
    # labelled December cannot establish whether its period closes in January.
    label = text_key(filename)
    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    match = re.search(rf"\b({month_names})[ _.-]+(20\d{{2}})\b", label)
    if not first and not last and match and parts[1] == MONTHS[match[1]]:
        try:
            return DateResolution(date(int(match[2]), parts[1], parts[0]), "POR_ARCHIVO",
                                  "Año y mes explícitos del nombre; revisar")
        except ValueError:
            pass
    return DateResolution(None, "REVISAR", "No hay evidencia suficiente para asignar el año")
