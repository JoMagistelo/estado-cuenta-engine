"""Reconocimiento por celdas de la tabla MiCuenta en papel escaneado."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import product
from statistics import median
from typing import Literal

from PIL import Image, ImageFilter, ImageOps


def _runs(mask: list[bool], gap: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = None
    for pos, enabled in enumerate([*mask, False]):
        if enabled and start is None:
            start = pos
        elif not enabled and start is not None:
            if runs and start - runs[-1][1] <= gap:
                start = runs.pop()[0]
            runs.append((start, pos))
            start = None
    return runs


@dataclass(frozen=True, slots=True)
class TableGrid:
    top: int
    bottom: int
    dividers: tuple[int, int, int, int]
    first_center: float
    pitch: float

    @classmethod
    def detect(cls, gray: Image.Image) -> TableGrid | None:
        width, height = gray.size
        projection = (
            gray.crop((0, round(height * 0.13), width, round(height * 0.152)))
            .filter(ImageFilter.MinFilter(3))
            .resize((width, 1), Image.Resampling.BOX)
            .tobytes()
        )
        dividers = []
        # Buscar las reglas, no el centro de los rótulos. Los intervalos sólo
        # limitan la búsqueda a la distribución de las cinco columnas.
        for left, right in ((0.065, 0.16), (0.40, 0.55), (0.55, 0.69), (0.70, 0.83)):
            x = min(range(int(left * width), int(right * width)), key=projection.__getitem__)
            if projection[x] > 148:
                return None
            dividers.append(x)
        a, b, c, d = dividers
        if b - a < 2 * (c - b) or not 0.78 < (d - c) / (c - b) < 1.45:
            return None

        margin = round(width * 0.024)
        counts = [0] * height
        for x in dividers:
            span = gray.crop((x - margin, 0, x + margin, height))
            pixels, stride = span.tobytes(), span.width
            for y in range(height):
                counts[y] += min(pixels[y * stride : (y + 1) * stride]) < 44
        ruled = [
            (a, b)
            for a, b in _runs([n >= 3 for n in counts], round(height * 0.005))
            if height * 0.08 < a < height * 0.23 and b - a > height * 0.023
        ]
        if not ruled:
            return None
        top, bottom = max(ruled, key=lambda run: run[1] - run[0])
        if bottom >= 0.98 * height:
            return None

        tone = gray.crop((b + 8, 0, d - 8, height)).resize((1, height), Image.Resampling.BOX)
        bands = [
            (u, v)
            for u, v in _runs([p < 235 for p in tone.tobytes()], round(height * 0.003))
            if top - 12 < u < bottom and height * 0.009 < v - u < height * 0.023
        ]
        gaps = [
            v[0] - u[0]
            for u, v in zip(bands, bands[1:])
            if height * 0.025 < v[0] - u[0] < height * 0.037
        ]
        if not gaps and bottom - top > 0.115 * height:
            return None
        pitch = median(gaps) / 2 if gaps else height / 64
        first = top + 1.5 * pitch
        observed = [(u + v) / 2 for u, v in bands if (u + v) / 2 > top + pitch]
        if observed:
            first += median((y - first + pitch / 2) % pitch - pitch / 2 for y in observed)
            anchors = [
                (round((y - first) / pitch), y)
                for y in observed
                if abs((y - first + pitch / 2) % pitch - pitch / 2) < 0.28 * pitch
            ]
            if len(anchors) >= 3:
                mx = sum(i for i, y in anchors) / len(anchors)
                my = sum(y for i, y in anchors) / len(anchors)
                spread = sum((i - mx) ** 2 for i, y in anchors)
                if spread:
                    pitch = sum((i - mx) * (y - my) for i, y in anchors) / spread
                    first = my - mx * pitch
        return cls(top, bottom, tuple(dividers), first - pitch * 0.055, pitch)

    def metadata(self, scale: float) -> dict:
        return {
            "first_center": self.first_center * scale,
            "pitch": self.pitch * scale,
            "bottom": self.bottom * scale,
            "dividers": [x * scale for x in self.dividers],
        }


@dataclass(frozen=True, slots=True)
class Cell:
    row: int
    column: int
    box: tuple[int, int, int, int]
    image: Image.Image
    alternate: Image.Image | None = None


def _clear_dithering(gray: Image.Image, pitch: float) -> Image.Image:
    smooth = gray.filter(ImageFilter.GaussianBlur(pitch / 41))
    return smooth.point([max(0, min(255, (i - 65) * 6)) for i in range(256)])


def _numeric_extent(ink: Image.Image, pitch: float) -> tuple[int, int, int, int] | None:
    """Busca los trazos de los dígitos sin la regla horizontal de la tabla."""
    profile = ink.resize((ink.width, 1), Image.Resampling.BOX).tobytes()
    strong = [i for i, value in enumerate(profile) if value * ink.height >= 255 * pitch * 0.15]
    if not strong:
        return None
    left = max(0, strong[0] - round(pitch * 0.18))
    right = min(ink.width, strong[-1] + round(pitch * 0.09))
    extent = ink.crop((left, 0, right, ink.height)).getbbox()
    if extent is None:
        return None
    x0, y0, x1, y1 = extent
    return x0 + left, y0, x1 + left, y1


def _cells(gray: Image.Image, grid: TableGrid) -> list[Cell]:
    clean = _clear_dithering(gray, grid.pitch)
    alternate = gray.filter(ImageFilter.GaussianBlur(grid.pitch / 58)).point(
        [max(0, min(255, (i - 78) * 5)) for i in range(256)]
    )
    pad = max(2, round(grid.pitch * 0.09))
    a, b, c, d = grid.dividers
    left = max(0, int(a - (b - a) * 0.29))
    right = min(gray.width, d + int((d - c) * 1.11))
    cells = []
    center = grid.first_center
    row = 0
    while center < grid.bottom:
        top = max(grid.top, round(center - grid.pitch * 0.51))
        bottom = min(grid.bottom, round(center + grid.pitch * 0.51))
        if bottom - top < grid.pitch * 0.5:
            break
        # La inclinación de las reglas verticales varía entre páginas. La
        # proyección local evita que una regla entre en la imagen de la celda.
        trace = (
            gray.crop((0, top, gray.width, bottom))
            .resize((gray.width, 1), Image.Resampling.BOX)
            .tobytes()
        )
        radius = round(gray.width * 0.021)
        boundaries = [
            left,
            *(min(range(x - radius, x + radius + 1), key=trace.__getitem__) for x in grid.dividers),
            right,
        ]
        for col, (x0, x1) in enumerate(zip(boundaries, boundaries[1:])):
            margin = pad if col < 2 else round(grid.pitch * 0.15)
            box = (x0 + margin, top, x1 - margin, bottom)
            cell = clean.crop(box)
            ink = ImageOps.invert(cell.point([0 if i < 162 else 255 for i in range(256)]))
            if col >= 2:
                # Una regla impresa ocupa casi todo el ancho de la celda;
                # una cifra o un signo menos sólo ocupa parte del renglón.
                rows = ink.resize((1, ink.height), Image.Resampling.BOX).tobytes()
                for y, coverage in enumerate(rows):
                    if coverage >= 210:
                        cell.paste(255, (0, y, cell.width, y + 1))
                        ink.paste(0, (0, y, ink.width, y + 1))
                extent = _numeric_extent(ink, grid.pitch)
            else:
                extent = ink.getbbox()
            if (
                extent is None
                or extent[2] - extent[0] < 0.17 * grid.pitch
                or extent[3] - extent[1] < 0.23 * grid.pitch
            ):
                continue
            if ink.histogram()[255] < grid.pitch**2 * 0.035:
                continue
            ix0, iy0, ix1, iy1 = extent
            trimmed = cell.crop(extent)
            ink_box = (box[0] + ix0, top + iy0, box[0] + ix1, top + iy1)
            context_box = (
                max(box[0], ink_box[0] - pad),
                top,
                min(box[2], ink_box[2] + pad),
                bottom,
            )
            cells.append(
                Cell(row, col, ink_box, trimmed, alternate.crop(context_box) if col != 1 else None)
            )
        center += grid.pitch
        row += 1
    return cells


def _select_money(
    cells: list[Cell],
    readings: list[tuple[str, float]],
    alternatives: list[list[tuple[str, float]]],
    previous: int | None,
) -> tuple[int | None, set[int]]:
    """El saldo sólo desambigua lecturas del OCR; nunca genera un importe."""
    from parsers.banamex.extractors.tabular_movements import _money

    choices = {}
    unresolved = set()
    for i, (cell, options) in enumerate(zip(cells, alternatives)):
        if cell.column < 2:
            continue
        values = {}
        for text, score in options:
            cents = _money(text)
            if cents is not None:
                old = values.get(cents)
                if old is None or score > old[1]:
                    values[cents] = (text, score)
        if values:
            choices[i] = [(amount, text, score) for amount, (text, score) in values.items()]
            readings[i] = max(values.values(), key=lambda pair: pair[1])
        elif any(re.search(r"\d{2}", text) for text, _ in options):
            unresolved.add(i)

    entries = []
    pending = {}
    for i, cell in enumerate(cells):
        if cell.column == 0 and _date_key(readings[i][0], 1) is not None:
            pending = {}
        if i not in choices:
            continue
        pending[cell.column] = i
        if cell.column == 4:
            entries.append(tuple(pending.get(col) for col in (2, 3, 4)))
            pending = {}
    if not entries:
        return previous, unresolved

    states = {previous: ((0, 0.0), [])}
    empty = [(0, "", 0.0)]
    for entry in entries:
        next_states = {}
        for cargo, abono, saldo in product(*(choices.get(i, empty) for i in entry)):
            for opening, (points, path) in states.items():
                agrees = opening is not None and opening + abono[0] - cargo[0] == saldo[0]
                rating = (
                    points[0] + int(agrees),
                    points[1] + sum(v[2] for v in (cargo, abono, saldo)),
                )
                candidate = next_states.get(saldo[0])
                if candidate is None or rating > candidate[0]:
                    next_states[saldo[0]] = (rating, path + list(zip(entry, (cargo, abono, saldo))))
        states = next_states
    ending, (_, path) = max(states.items(), key=lambda item: item[1][0])
    opening_index = None
    for i in range(0, len(path), 3):
        (ci, c), (ai, a), (si, s) = path[i : i + 3]
        if previous is not None and previous + a[0] - c[0] != s[0]:
            unresolved.update(k for k in (opening_index, ci, ai, si) if k is not None)
        previous, opening_index = s[0], si
    for i, (_, text, confidence) in path:
        if i is not None:
            readings[i] = (text, confidence)
    return ending, unresolved


def _date_key(value: str, first_month: int) -> int | None:
    from parsers.banamex.extractors.tabular_cover import MONTH_ABBREVIATIONS
    from parsers.banamex.extractors.tabular_movements import _date

    normalized = _date(value)
    if normalized:
        day, month = normalized.split()
        return ((MONTH_ABBREVIATIONS[month] - first_month) % 12) * 32 + int(day)
    return None


def _select_dates(cells, readings, alternatives, start_month, previous):
    indexes = [i for i, cell in enumerate(cells) if cell.column == 0]
    states = {previous: ((0, 0.0), [])}
    for i in indexes:
        options = [
            (day, text, score)
            for text, score in alternatives[i]
            if (day := _date_key(text, start_month)) is not None
        ]
        next_states = {}
        for last, (points, path) in states.items():
            for day, text, score in [(last, "", 0.0), *options]:
                if last is not None and day < last:
                    continue
                rating = (points[0] + int(bool(text)), points[1] + score)
                if day not in next_states or rating > next_states[day][0]:
                    next_states[day] = (rating, path + [(text, score)])
        states = next_states
    ending, (_, path) = max(states.items(), key=lambda item: item[1][0])
    retry = set()
    for i, pair in zip(indexes, path):
        readings[i] = pair
        votes = {
            day for text, _ in alternatives[i] if (day := _date_key(text, start_month)) is not None
        }
        if len(votes) > 1 or not pair[0]:
            if any(
                re.search(r"\d|ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC", value, re.I)
                for value, _ in alternatives[i]
            ):
                retry.add(i)
    return ending, retry


def _native_cells(words, grid, scale) -> dict[tuple[int, int], tuple[str, float]]:
    grouped = defaultdict(list)
    for word in words:
        y = (word["top"] + word["bottom"]) / (2 * scale)
        row = round((y - grid.first_center) / grid.pitch)
        if row < 0 or y >= grid.bottom:
            continue
        x = (word["x0"] + word["x1"]) / (2 * scale)
        column = bisect_right(grid.dividers, x)
        if column != 1:
            grouped[row, column].append(word)
    return {
        key: (
            " ".join(w["text"] for w in sorted(items, key=lambda w: w["x0"])),
            min(float(w.get("confidence", 0.0)) for w in items),
        )
        for key, items in grouped.items()
    }


def _retry_cell(gray: Image.Image, cell: Cell, pitch: float, clean: bool) -> Cell:
    x0, y0, x1, y1 = cell.box
    dx, dy = round(pitch * 0.18), round(pitch * 0.13)
    crop = gray.crop(
        (max(0, x0 - dx), max(0, y0 - dy), min(gray.width, x1 + dx), min(gray.height, y1 + dy))
    )
    crop = _clear_dithering(crop, pitch) if clean else ImageOps.autocontrast(crop)
    return replace(
        cell,
        image=crop.resize(
            (round(crop.width * 1.6), round(crop.height * 1.6)), Image.Resampling.LANCZOS
        ),
    )


def _identifier_crop(gray: Image.Image, cell: Cell, pitch: float, blur_divisor: int) -> Cell:
    # La ampliación se hace después de atenuar la trama para conservar los
    # trazos de los dígitos. El recorte izquierdo evita volver a incluir la regla.
    x0, y0, x1, y1 = cell.box
    pad = max(2, round(pitch * 0.065))
    crop = gray.crop((x0, max(0, y0 - pad), min(gray.width, x1 + pad), min(gray.height, y1 + pad)))
    clean = crop.filter(ImageFilter.GaussianBlur(pitch / blur_divisor)).point(
        [max(0, min(255, (value - 72) * 5)) for value in range(256)]
    )
    return replace(
        cell, image=clean.resize((clean.width * 3, clean.height * 3), Image.Resampling.LANCZOS)
    )


def _identifier_cells(cells, readings, awaiting):
    from parsers.banamex.extractors.tabular_movements import ACCOUNT_LABEL, TRACKING_LABEL

    targets = []
    for i, cell in enumerate(cells):
        if cell.column != 1:
            continue
        text = readings[i][0]
        if awaiting:
            targets.append((i, awaiting))
            awaiting = None
        if re.search(TRACKING_LABEL, text, re.I):
            tail = re.split(TRACKING_LABEL, text, flags=re.I)[-1]
            if re.search(r"\d{3}", tail):
                targets.append((i, "tracking_label"))
            else:
                awaiting = "tracking_value"
        elif re.search(ACCOUNT_LABEL + r"\s*[:.]?\s*$", text, re.I):
            awaiting = "account"
    return targets, awaiting


def _identifier_value(kind, text):
    from parsers.banamex.extractors.tabular_movements import ACCOUNT_NUMBER, _tracking

    if kind == "account":
        number = re.match(r"^\s*" + ACCOUNT_NUMBER, text)
        return re.sub(r"\D", "", number[1]) if number else None
    return _tracking(text if kind == "tracking_label" else "RASTREO " + text)


def _best_identifier_reading(kind, options, authorization):
    from cep.catalog import valid_clabe

    values = defaultdict(list)
    for text, score in options:
        if key := _identifier_value(kind, text):
            values[key].append((text, score))
    if not values:
        return options[0]

    def rank(key):
        length_matches = (key.isdigit() and len(key) in (10, 18)) or (
            len(key) == 24 and (key.endswith("TEF") or key.startswith("MBAN"))
        )
        matches_auth = (
            kind != "account"
            and len(key) == 18
            and key.isdigit()
            and key[4:11].zfill(8) == authorization
        )
        strength = valid_clabe(key) if kind == "account" else length_matches
        return matches_auth, strength, len(values[key]), max(score for _, score in values[key])

    return max(values[max(values, key=rank)], key=lambda pair: pair[1])


def _account_digit_crop(gray: Image.Image, cell: Cell, pitch: float) -> Cell | None:
    raw = gray.crop(cell.box)
    ink = raw.filter(ImageFilter.GaussianBlur(pitch / 85)).point(
        [255 if value < 122 else 0 for value in range(256)]
    )
    columns = ink.resize((ink.width, 1), Image.Resampling.BOX).tobytes()
    # Una separación mayor que la de los dígitos marca el inicio de la
    # referencia o del texto que sigue al número en la misma línea.
    group = next(
        (
            (left, right)
            for left, right in _runs([value > 30 for value in columns], round(pitch / 5))
            if left < pitch * 0.35 and right - left >= pitch * 2.5
        ),
        None,
    )
    if group is None:
        return None
    left, right = group
    crop = raw.crop((max(0, left - 2), 0, min(raw.width, right + 2), raw.height))
    images = []
    for divisor in (115, 65):
        clean = crop.filter(ImageFilter.GaussianBlur(pitch / divisor)).point(
            [max(0, min(255, (value - 72) * 5)) for value in range(256)]
        )
        images.append(clean.resize((clean.width * 2, clean.height * 2), Image.Resampling.LANCZOS))
    return replace(cell, image=images[0], alternate=images[1])


def _recover_tesseract_clabes(gray, cells, targets, readings, pitch, recognize):
    from cep.catalog import valid_clabe
    from parsers.banamex.extractors.tabular_movements import ACCOUNT_NUMBER

    pending = []
    for i, kind in targets:
        if kind != "account":
            continue
        text = readings[i][0]
        match = re.match(r"^\s*" + ACCOUNT_NUMBER, text)
        if not match:
            continue
        account = re.sub(r"\D", "", match[1])
        if len(account) < 17 or valid_clabe(account):
            continue
        if crop := _account_digit_crop(gray, cells[i], pitch):
            pending.append((i, text[match.end() :].strip(), crop))
    if pending:
        crops = [crop for _, _, crop in pending]
        first = recognize(crops, local=True, digits=True)
        second = recognize(crops, local=True, alternate=True, digits=True)
        for (i, suffix, _), (number, score), (other, other_score) in zip(pending, first, second):
            if number == other and valid_clabe(number):
                readings[i] = (f"{number} {suffix}".rstrip(), min(score, other_score))


class BanamexTabularOCR:
    """Estado de lectura local a un PDF, compartido por ambos motores OCR."""

    def __init__(self, engine: Literal["paddleocr", "tesseract"] = "paddleocr"):
        self._engine = engine
        self.eligible = False
        self.pages: dict[int, dict] = {}
        self.previous_balance: int | None = None
        self.previous_date: int | None = None
        self.first_month = 1
        self.awaiting_identifier: str | None = None

    def grid(self, image: Image.Image) -> TableGrid | None:
        return TableGrid.detect(image.convert("L")) if self.eligible else None

    def observe_cover(self, words: list[dict]) -> None:
        from parsers.banamex.extractors.anchored_header import is_cover_page
        from parsers.banamex.extractors.tabular_cover import TabularCover

        if cover := TabularCover.detect(words):
            self.eligible = True
            self.previous_balance = None
            self.previous_date = None
            self.awaiting_identifier = None
            start, _ = cover.period_dates()
            self.first_month = int(start.split("/")[1]) if start else 1
        elif self.eligible and is_cover_page(words):
            self.eligible = False

    def read_table(
        self,
        image: Image.Image,
        grid: TableGrid,
        words: list[dict],
        *,
        page: int,
        page_width: float,
        doctop: float,
        recognize: Callable[..., list[tuple[str, float]]],
    ) -> list[dict]:
        """Relee exclusivamente el cuerpo delimitado por las reglas del papel."""
        gray = image.convert("L")
        cells = _cells(gray, grid)
        readings = recognize(cells)
        if len(readings) != len(cells) or not any(text for text, score in readings):
            return words
        numeric = [i for i, cell in enumerate(cells) if cell.alternate is not None]
        second = recognize([cells[i] for i in numeric], alternate=True)
        alternatives = [[reading] for reading in readings]
        for i, reading in zip(numeric, second):
            alternatives[i].append(reading)
        scale = page_width / image.width
        native = _native_cells(words, grid, scale)
        for i in numeric:
            cell = cells[i]
            if reading := native.get((cell.row, cell.column)):
                alternatives[i].append(reading)
        ending_date, date_retry = _select_dates(
            cells,
            readings,
            alternatives,
            self.first_month,
            self.previous_date,
        )
        ending, money_retry = _select_money(cells, readings, alternatives, self.previous_balance)
        retry = sorted(date_retry | money_retry)
        if retry:
            for clean in (True, False):
                candidates = recognize(
                    [_retry_cell(gray, cells[i], grid.pitch, clean) for i in retry], local=True
                )
                for i, reading in zip(retry, candidates):
                    alternatives[i].append(reading)
            ending_date, _ = _select_dates(
                cells, readings, alternatives, self.first_month, self.previous_date
            )
            ending, _ = _select_money(cells, readings, alternatives, self.previous_balance)
        self.previous_date, self.previous_balance = ending_date, ending
        targets, self.awaiting_identifier = _identifier_cells(
            cells, readings, self.awaiting_identifier
        )
        if targets:
            primary = [readings[i] for i, _ in targets]
            blur_divisor = 94 if self._engine == "tesseract" else 85
            focused = recognize(
                [_identifier_crop(gray, cells[i], grid.pitch, blur_divisor) for i, _ in targets],
                local=True,
            )
            raw = recognize(
                [_retry_cell(gray, cells[i], grid.pitch, False) for i, _ in targets], local=True
            )
            weak_tracking = []
            for (i, kind), *options in zip(targets, primary, focused, raw):
                authorization = next(
                    (
                        m[1]
                        for text, _ in readings[i + 1 : i + 25]
                        if (m := re.search(r"\bAUT\s+(\d{8})\b", text)) and int(m[1])
                    ),
                    None,
                )
                readings[i] = _best_identifier_reading(kind, options, authorization)
                if self._engine == "tesseract" and kind != "account":
                    key = _identifier_value(kind, readings[i][0])
                    if (
                        not key
                        or (key.isdigit() and len(key) not in (10, 18))
                        or (key.endswith("TEF") and len(key) != 24)
                    ):
                        weak_tracking.append((i, kind, options, authorization))
            if weak_tracking:
                recovered = recognize(
                    [_retry_cell(gray, cells[i], grid.pitch, True) for i, *_ in weak_tracking],
                    local=True,
                )
                for (i, kind, options, authorization), candidate in zip(weak_tracking, recovered):
                    readings[i] = _best_identifier_reading(
                        kind, [*options, candidate], authorization
                    )
            if self._engine == "tesseract":
                _recover_tesseract_clabes(gray, cells, targets, readings, grid.pitch, recognize)
        data_top = grid.first_center - grid.pitch * 0.52
        top, bottom = data_top * scale, grid.bottom * scale
        result = [w for w in words if not top <= (w["top"] + w["bottom"]) / 2 < bottom]
        for cell, (text, confidence) in zip(cells, readings):
            x0, y0, x1, y1 = (value * scale for value in cell.box)
            text = " ".join(text.split())
            for token in re.finditer(r"\S+", text):
                start = x0 + (x1 - x0) * token.start() / len(text)
                stop = x0 + (x1 - x0) * token.end() / len(text)
                result.append(
                    {
                        "text": token[0],
                        "x0": start,
                        "x1": stop,
                        "top": y0,
                        "bottom": y1,
                        "page": page,
                        "doctop": doctop + y0,
                        "width": stop - start,
                        "height": y1 - y0,
                        "upright": True,
                        "direction": "ltr",
                        "confidence": confidence,
                    }
                )
        self.pages[page] = grid.metadata(scale)
        return result


def recognize_tesseract_cells(
    cells: list[Cell],
    *,
    language: str,
    timeout: int,
    alternate: bool = False,
    local: bool = False,
    digits: bool = False,
) -> list[tuple[str, float]]:
    """Una llamada por tipo de celda, con cada renglón en un espacio propio."""
    import pytesseract

    if local:
        readings = []
        config = (
            "--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789"
            if digits
            else "--oem 3 --psm 7"
        )
        for cell in cells:
            data = pytesseract.image_to_data(
                ImageOps.expand(cell.alternate if alternate else cell.image, border=18, fill=255),
                lang=language,
                config=config,
                output_type=pytesseract.Output.DICT,
                timeout=timeout,
            )
            words = [(t.strip(), float(c)) for t, c in zip(data["text"], data["conf"]) if t.strip()]
            separator = "" if digits else " "
            readings.append(
                (separator.join(t for t, _ in words), min((c for _, c in words), default=0))
            )
        return readings

    result = [("", 0.0) for _ in cells]
    for columns, whitelist in (
        ({0}, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        ({1}, ""),
        ({2, 3, 4}, "0123456789.,-"),
    ):
        indexes = [i for i, cell in enumerate(cells) if cell.column in columns]
        if not indexes:
            continue
        crops = [cells[i].alternate if alternate else cells[i].image for i in indexes]
        height = max(crop.height for crop in crops) + 24
        width = max(crop.width for crop in crops) + 32
        strip = Image.new("L", (width, height * len(indexes)), 255)
        for row, crop in enumerate(crops):
            strip.paste(crop, (16, row * height + (height - crop.height) // 2))
        config = "--oem 3 --psm 11" if alternate else "--oem 3 --psm 6"
        if whitelist and not alternate:
            config += f" -c tessedit_char_whitelist={whitelist}"
        data = pytesseract.image_to_data(
            strip,
            lang=language,
            config=config,
            output_type=pytesseract.Output.DICT,
            timeout=timeout,
        )
        tokens: list[list[tuple[int, str, float]]] = [[] for _ in indexes]
        for i, text in enumerate(data["text"]):
            if text.strip():
                center = data["top"][i] + data["height"][i] / 2
                row = min(int(center / height), len(indexes) - 1)
                tokens[row].append((data["left"][i], text.strip(), float(data["conf"][i])))
        for i, words in zip(indexes, tokens):
            if words:
                result[i] = (
                    " ".join(text for _, text, _ in sorted(words)),
                    min(score for _, _, score in words),
                )
    return result
