"""Relectura de las celdas impresas del detalle CTA Mujer Banorte."""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import product
import re

from PIL import Image, ImageFilter, ImageOps

from readers.banamex_tabular_ocr import Cell, _runs
from parsers.banorte_ocr.extractors.datos import _group_lines, _line_text, _norm
from parsers.banorte_ocr.extractors.mujer import (
    AMOUNT_COLUMNS,
    DATE_LEFT,
    DESCRIPTION_LEFT,
    DESCRIPTION_RIGHT,
    TRACE_LABEL,
    extract_cover,
    is_mujer_cover,
    is_mujer_detail,
    outgoing_trace,
    scan_cents,
    scan_date,
)


@dataclass(frozen=True, slots=True)
class MujerTable:
    top: int
    bottom: int
    rows: tuple[tuple[int, int], ...]

    @classmethod
    def detect(cls, image: Image.Image) -> MujerTable | None:
        width, height = image.size
        ink = image.filter(ImageFilter.MedianFilter(3)).point(
            [255 if value < 155 else 0 for value in range(256)]
        )

        def projection(left: float, right: float) -> bytes:
            box = (round(width * left), 0, round(width * right), height)
            return ink.crop(box).resize((1, height), Image.Resampling.BOX).tobytes()

        scale = height / 3168
        full = projection(0.085, 0.912)
        balance = projection(*AMOUNT_COLUMNS[-1])
        rule = [y for y in range(round(0.106 * height), round(0.139 * height)) if full[y] > 128]
        if not rule:
            return None
        top = rule[-1] + round(3 * scale)
        # La banda de la siguiente tabla termina el detalle de la cuenta.
        terminal = next(
            (
                a
                for a, b in _runs([v > 115 for v in full], max(1, round(2 * scale)))
                if a > top + 20 * scale and b - a >= 9 * scale
            ),
            round(0.933 * height),
        )
        bottom = min(terminal, round(0.938 * height))
        spans = _runs(
            [7 <= v <= 235 and full[y] < 130 and top < y < bottom for y, v in enumerate(balance)],
            max(1, round(3 * scale)),
        )
        rows = tuple((a, b) for a, b in spans if 8 * scale <= b - a <= 38 * scale)
        return cls(top, bottom, rows) if rows else None


def _cells(gray: Image.Image, table: MujerTable) -> dict[tuple[int, int], Cell]:
    width, height = gray.size
    pad = max(2, round(height * 0.0022))
    smooth = gray.filter(ImageFilter.MedianFilter(3))
    lut = [max(0, min(255, (value - 88) * 5)) for value in range(256)]
    columns = ((DATE_LEFT, DESCRIPTION_LEFT + 0.013), *AMOUNT_COLUMNS)
    cells = {}
    for row, (a, b) in enumerate(table.rows):
        for col, (left, right) in zip((0, 2, 3, 4), columns):
            x0, x1 = round(width * left), round(width * right)
            box = (x0, max(table.top, a - pad), x1, min(table.bottom, b + pad))
            crop = smooth.crop(box).point(lut)
            ink = crop.point([255 if value < 170 else 0 for value in range(256)])
            bounds = ink.getbbox()
            if not bounds or bounds[3] - bounds[1] < height * 0.0027:
                continue
            if ink.histogram()[255] < (height / 3168) ** 2 * 45:
                continue
            cells[row, col] = Cell(
                row,
                col,
                box,
                crop,
                ImageOps.autocontrast(gray.crop(box)),
            )
    return cells


def _native_readings(words, table: MujerTable, scale: float, width: float):
    centers = [(a + b) / 2 for a, b in table.rows]
    groups = defaultdict(list)
    for word in words:
        y = (word["top"] + word["bottom"]) / (2 * scale)
        if not table.top <= y < table.bottom:
            continue
        x = word["x0"] / width
        if DATE_LEFT <= x < DESCRIPTION_LEFT + 0.005:
            col = 0
        else:
            col = next((i for i, (a, b) in enumerate(AMOUNT_COLUMNS, 2) if a <= x < b), None)
        if col is None:
            continue
        i = bisect_left(centers, y)
        row = min(range(max(0, i - 1), min(len(centers), i + 1)), key=lambda j: abs(centers[j] - y))
        if abs(y - centers[row]) * scale < width * 0.008:
            groups[row, col].append(word)
    return {
        k: (
            " ".join(w["text"] for w in sorted(v, key=lambda w: w["x0"])),
            min(float(w.get("confidence", 0)) for w in v),
        )
        for k, v in groups.items()
    }


def _money_path(readings, size: int, opening: int | None):
    """Usa la continuidad para elegir entre importes reconocidos en el papel."""
    states = {opening: ((0, 0.0), [])}
    for row in range(size):
        next_states = {}
        choices = []
        for col in (2, 3, 4):
            values = {}
            for text, score in readings.get((row, col), ()):
                value = scan_cents(text)
                if value is not None and (value not in values or values[value][1] < score):
                    values[value] = (text, score)
            choices.append(list(values.items()) or [(None if col == 4 else 0, ("", 0.0))])
        for abono, cargo, saldo in product(*choices):
            for previous, (rank, path) in states.items():
                agrees = (
                    saldo[0] is not None
                    and previous is not None
                    and previous + abono[0] - cargo[0] == saldo[0]
                )
                rating = (rank[0] + agrees, rank[1] + abono[1][1] + cargo[1][1] + saldo[1][1])
                incumbent = next_states.get(saldo[0])
                if incumbent is None or rating > incumbent[0]:
                    next_states[saldo[0]] = rating, [*path, (abono, cargo, saldo)]
        states = next_states
    _, path = max(states.values(), key=lambda value: value[0])
    unresolved = set()
    previous = opening
    for row, (abono, cargo, saldo) in enumerate(path):
        if saldo[0] is None or (
            previous is not None and previous + abono[0] - cargo[0] != saldo[0]
        ):
            unresolved.update((row, max(0, row - 1)))
        previous = saldo[0]
    return path, unresolved


def _date_path(readings, size, previous):
    states = {previous: ((0, 0.0), [])}
    for row in range(size):
        next_states = {}
        options = defaultdict(list)
        for text, score in readings.get((row, 0), ()):
            if parsed := scan_date(text):
                options[parsed[1]].append((parsed[0], score))
        for last, (rating, path) in states.items():
            ordered = [(last, "", 0.0)]
            for day, candidates in options.items():
                if last is None or day >= last:
                    text, confidence = max(candidates, key=lambda pair: pair[1])
                    ordered.append((day, text, confidence + 25 * (len(candidates) - 1)))
            for day, text, score in ordered:
                rank = (rating[0] + bool(text), rating[1] + score)
                if day not in next_states or rank > next_states[day][0]:
                    next_states[day] = rank, [*path, (text, score)]
        states = next_states
    latest, (_, path) = max(states.items(), key=lambda item: item[1][0])
    return latest, path


def _tesseract_region(gray, box, *, page, scale, doctop, language, timeout):
    import pytesseract

    left, top, _, _ = box
    strip = gray.crop(box).filter(ImageFilter.MedianFilter(3))
    border = 10
    data = pytesseract.image_to_data(
        ImageOps.expand(strip, border=border, fill=255),
        lang=language,
        config="--oem 3 --psm 6",
        output_type=pytesseract.Output.DICT,
        timeout=timeout,
    )
    words = []
    for i, value in enumerate(data["text"]):
        if text := value.strip():
            x = (left + data["left"][i] - border) * scale
            y = (top + data["top"][i] - border) * scale
            w, h = data["width"][i] * scale, data["height"][i] * scale
            words.append(
                {
                    "text": text,
                    "x0": x,
                    "x1": x + w,
                    "top": y,
                    "bottom": y + h,
                    "page": page,
                    "doctop": doctop + y,
                    "width": w,
                    "height": h,
                    "upright": True,
                    "direction": "ltr",
                    "confidence": float(data["conf"][i]),
                }
            )
    return words


_AFTER_TRACE = re.compile(r"\s+(?:RFC|REC|RC|AFC|IVA|H[O0]RA|HORALI)\b", re.I)


def _x_at(line: list[dict], offset: int) -> float:
    for word in line:
        size = len(word["text"])
        if offset <= size:
            return word["x0"] + offset / max(1, size) * (word["x1"] - word["x0"])
        offset -= size + 1
    return line[-1]["x1"]


def _trace_lines(words, table, scale, cargo_rows):
    anchors = [(a + b) / 2 * scale for a, b in table.rows]
    awaiting = None
    for line in _group_lines(words):
        y = sum((w["top"] + w["bottom"]) / 2 for w in line) / len(line)
        row = bisect_left(anchors, y + 3.5) - 1
        if row not in cargo_rows:
            awaiting = None
            continue
        text = _line_text(line)
        label = TRACE_LABEL.search(_norm(text))
        if label is None and awaiting != row:
            continue
        start = label.end() if label else 0
        if not text[start:].strip():
            awaiting = row
            continue
        awaiting = None
        end = _AFTER_TRACE.search(text, start)
        yield line, text, start, end.start() if end else len(text), y


def _key_crop(gray, line, left, right, scale):
    x0 = max(0, round(left / scale) - 7)
    x1 = min(gray.width, round(right / scale))
    top = max(0, round(min(w["top"] for w in line) / scale) - 4)
    bottom = min(gray.height, round(max(w["bottom"] for w in line) / scale) + 4)
    return gray.crop((x0, top, x1, bottom))


def _read_trace_crop(crop, blur, mode, language, timeout, *, focused=False):
    import pytesseract

    if blur is None:
        clean = crop.filter(ImageFilter.MedianFilter(3))
        enlarged = clean.resize((clean.width * 2, clean.height * 2), Image.Resampling.BICUBIC)
    else:
        clean = crop.filter(ImageFilter.GaussianBlur(blur)).point(
            [max(0, min(255, (value - 72) * 5)) for value in range(256)]
        )
        enlarged = clean.resize((clean.width * 2, clean.height * 2), Image.Resampling.LANCZOS)
    config = f"--oem 3 --psm {mode}"
    if focused:
        config += " -c tessedit_char_whitelist=0123456789CPORIL"
    text = pytesseract.image_to_string(
        ImageOps.expand(enlarged, border=18, fill=255),
        lang=language,
        config=config,
        timeout=timeout,
    )
    return outgoing_trace(text)


def _rewrite_line(line, text):
    left, right = line[0]["x0"], max(w["x1"] for w in line)
    base = line[0]
    updated = []
    for word in re.finditer(r"\S+", text):
        x0 = left + (right - left) * word.start() / len(text)
        x1 = left + (right - left) * word.end() / len(text)
        updated.append({**base, "text": word[0], "x0": x0, "x1": x1, "width": x1 - x0})
    return updated


def _recover_tesseract_traces(gray, words, native, table, scale, width, money, language, timeout):
    cargo_rows = {i for i, (_, cargo, _) in enumerate(money) if cargo[0]}
    body = [w for w in words if table.top * scale <= w["top"] < table.bottom * scale]
    replacements = []
    removed = set()
    for line, text, start, end, y in _trace_lines(body, table, scale, cargo_rows):
        current = outgoing_trace(text[start:end])
        previous = outgoing_trace(
            _line_text(
                [
                    w
                    for w in native
                    if w["x0"] < DESCRIPTION_RIGHT * width
                    and abs((w["top"] + w["bottom"]) / 2 - y) < 3.2
                ]
            )
        )
        if current and current == previous:
            continue
        begin = _x_at(line, start)
        focused = _key_crop(gray, line, begin, begin + 0.24 * width, scale)
        focused_readings = [
            _read_trace_crop(focused, blur, 13, language, timeout, focused=True)
            for blur in (0, 0.45)
        ]
        if focused_readings[0] and focused_readings[0] == focused_readings[1]:
            selected = focused_readings[0]
        else:
            full = _key_crop(gray, line, line[0]["x0"], max(w["x1"] for w in line), scale)
            alternatives = [
                _read_trace_crop(full, blur, 7, language, timeout) for blur in (0.45, 0.8)
            ]
            votes = Counter(
                value for value in (current, previous, *focused_readings, *alternatives) if value
            )
            selected = votes.most_common(1)[0][0] if votes and max(votes.values()) >= 2 else current
        if not selected:
            center = round(y / scale)
            pad = round(gray.height * 0.0066)
            row_strip = gray.crop(
                (
                    round(gray.width * 0.128),
                    max(0, center - pad),
                    round(gray.width * DESCRIPTION_RIGHT),
                    min(gray.height, center + pad),
                )
            )
            # La mediana conserva los trazos en la franja cuando el recorte
            # derivado de las cajas OCR pierde el primer dígito.
            first = _read_trace_crop(row_strip, None, 7, language, timeout)
            second = _read_trace_crop(row_strip, None, 11, language, timeout)
            if first and first == second:
                selected = first
        if selected and selected != current:
            replacements.extend(_rewrite_line(line, f"{text[:start]} {selected} {text[end:]}"))
            removed.update(id(w) for w in line)
    return [w for w in words if id(w) not in removed] + replacements if removed else words


class MujerOCR:
    def __init__(self, *, tesseract: bool = False):
        self.tesseract = tesseract
        self.cover_width: float | None = None
        self.pages: dict[int, dict] = {}
        self.corrected: dict[int, list[dict]] = {}
        self.failed = False
        self.previous_balance = None
        self.previous_date = None

    def finish(self, words: list[dict]) -> tuple[list[dict], dict]:
        if self.failed or not self.pages:
            return words, {}
        result = []
        replaced = set()
        for word in words:
            page = int(word.get("page") or 1)
            if page not in self.corrected:
                result.append(word)
            elif page not in replaced:
                result.extend(self.corrected[page])
                replaced.add(page)
        return result, {
            "banorte_mujer_tables": self.pages,
            "banorte_mujer_cover_width": self.cover_width,
        }

    def read_page(self, image, words, *, page, width, doctop, recognize, language="", timeout=30):
        if self.failed:
            return
        if page == 1:
            cover = self.read_cover(
                image, words, width=width, doctop=doctop, language=language, timeout=timeout
            )
            if self.cover_width is not None:
                self.corrected[page] = cover
            return
        if self.cover_width is None or not is_mujer_detail(words, width):
            return
        table = MujerTable.detect(image.convert("L"))
        if table is None or recognize is None:
            self.failed = True
            return
        self.corrected[page] = self.read_table(
            image,
            table,
            words,
            page=page,
            width=width,
            doctop=doctop,
            recognize=recognize,
            tess_language=language,
            tess_timeout=timeout,
        )

    def read_cover(self, image, words, *, width, doctop, language="", timeout=30):
        if not is_mujer_cover(words):
            return words
        if self.tesseract:
            gray = image.convert("L")
            box = (
                round(gray.width * 0.583),
                round(gray.height * 0.120),
                round(gray.width * 0.925),
                round(gray.height * 0.167),
            )
            scale = width / gray.width
            reread = _tesseract_region(
                gray, box, page=1, scale=scale, doctop=doctop, language=language, timeout=timeout
            )
            if reread:
                candidate = [
                    w
                    for w in words
                    if not (
                        box[0] * scale <= w["x0"] < box[2] * scale
                        and box[1] * scale <= (w["top"] + w["bottom"]) / 2 < box[3] * scale
                    )
                ] + reread
                data, _ = extract_cover(candidate, width)
                if data.periodo_inicio and data.periodo_fin and data.fecha_corte:
                    words = candidate
        self.cover_width = width
        _, summary = extract_cover(words, width)
        if summary.saldo_anterior is not None:
            self.previous_balance = round(summary.saldo_anterior * 100)
        return words

    def read_table(
        self,
        image,
        table,
        words,
        *,
        page,
        width,
        doctop,
        recognize: Callable[..., list[tuple[str, float]]],
        tess_language: str = "",
        tess_timeout: int = 30,
    ):
        gray = image.convert("L")
        scale = width / image.width
        cells = _cells(gray, table)
        left = words
        if self.tesseract:
            box = (
                round(gray.width * DATE_LEFT),
                table.top,
                round(gray.width * DESCRIPTION_RIGHT),
                table.bottom,
            )
            left = (
                _tesseract_region(
                    gray,
                    box,
                    page=page,
                    scale=scale,
                    doctop=doctop,
                    language=tess_language,
                    timeout=tess_timeout,
                )
                or words
            )
        native = _native_readings(words, table, scale, width)
        readings = defaultdict(list)
        for index, reading in native.items():
            if index in cells or index[1] == 0:
                readings[index].append(reading)
        if left is not words:
            for index, reading in _native_readings(left, table, scale, width).items():
                if index[1] == 0:
                    readings[index].append(reading)

        size = len(table.rows)
        _, weak = _money_path(readings, size, self.previous_balance)
        targets = [
            k
            for k in cells
            if (k[1] > 0 and k[0] in weak)
            or (k[1] == 0 and (self.tesseract or not any(scan_date(t) for t, _ in readings[k])))
        ]
        for alternate in (False, True):
            for k, reading in zip(
                targets, recognize([cells[k] for k in targets], alternate=alternate)
            ):
                readings[k].append(reading)
        money, weak = _money_path(readings, size, self.previous_balance)
        latest, dates = _date_path(readings, size, self.previous_date)
        retry = [
            k for k in cells if (k[1] > 0 and k[0] in weak) or (k[1] == 0 and not dates[k[0]][0])
        ]
        if retry:
            crops = [
                replace(
                    cells[k],
                    image=ImageOps.autocontrast(gray.crop(cells[k].box)).resize(
                        (cells[k].image.width * 2, cells[k].image.height * 2),
                        Image.Resampling.LANCZOS,
                    ),
                )
                for k in retry
            ]
            for k, reading in zip(retry, recognize(crops, local=True)):
                readings[k].append(reading)
            money, _ = _money_path(readings, size, self.previous_balance)
            latest, dates = _date_path(readings, size, self.previous_date)
        self.previous_date = latest
        self.previous_balance = money[-1][2][0]
        if self.tesseract:
            left = _recover_tesseract_traces(
                gray,
                left,
                words,
                table,
                scale,
                width,
                money,
                tess_language,
                tess_timeout,
            )
        top, bottom = table.top * scale, table.bottom * scale

        def body(word):
            return top <= (word["top"] + word["bottom"]) / 2 < bottom

        result = [w for w in words if not body(w)]
        for word in left:
            if body(word) and word["x0"] < DESCRIPTION_RIGHT * width:
                # Conserva el texto pegado a la fecha sin duplicar su lectura.
                text = word["text"]
                if word["x0"] < DESCRIPTION_LEFT * width and (printed := scan_date(text)):
                    text = text[printed[2] :].strip()
                    if not text:
                        continue
                    word = {**word, "text": text, "x0": max(word["x0"], DESCRIPTION_LEFT * width)}
                elif word["x0"] < 0.112 * width and word["x1"] < DESCRIPTION_LEFT * width:
                    continue
                result.append(word)
        centers = [(a + b) / 2 * scale for a, b in table.rows]
        column_x = (DATE_LEFT + 0.008, *(a + 0.007 for a, _ in AMOUNT_COLUMNS))
        for row, center in enumerate(centers):
            selected = [dates[row], *(part[1] for part in money[row])]
            for x, (text, confidence) in zip(column_x, selected):
                if not text:
                    continue
                x0 = x * width
                # Los candidatos monetarios ya se validaron con sus dos decimales.
                # La capa de texto recibe un token por celda.
                if x != column_x[0]:
                    value = scan_cents(text)
                    text = f"{value / 100:.2f}"
                x1 = x0 + min(width * 0.077, len(text) * 3.8)
                top_y, bottom_y = center - 2.6, center + 2.6
                result.append(
                    {
                        "text": text,
                        "x0": x0,
                        "x1": x1,
                        "top": top_y,
                        "bottom": bottom_y,
                        "page": page,
                        "doctop": doctop + top_y,
                        "width": x1 - x0,
                        "height": bottom_y - top_y,
                        "upright": True,
                        "direction": "ltr",
                        "confidence": min(100, confidence),
                    }
                )
        self.pages[page] = {"width": width, "top": top, "bottom": bottom, "rows": centers}
        return result
