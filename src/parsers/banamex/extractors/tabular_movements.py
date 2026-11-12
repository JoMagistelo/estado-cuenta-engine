"""Detalle MiCuenta con fecha de inicio y saldo al final de cada bloque."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from cep.catalog import valid_clabe
from models.movimiento import Movimiento

from ..utils.words_grafico_filter import remove_after_banamex_movements
from .movimientos import (
    line_text,
    movement_from_fields,
    normalize_upper,
    word_center_x,
    word_center_y,
)


DATE = re.compile(
    r"^([\dOILSB]{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AG[O0]|SEP|[O0]CT|N[O0]V|D[I1L]C)\b"
)
AMOUNT = re.compile(r"^([($+\-]*)(\d{1,3}(?:[.,]\d{3})+|\d+)[.,](\d{2})([)\-]?)$")
TRACKING_LABEL = r"\b[IL|]?R\s*A[S5]\s*T\s*R\s*E\.?\s*[O0]\b"
TRACKING = re.compile(TRACKING_LABEL + r"\s*[:.]?\s*([^\n]+)", re.I)
ACCOUNT_LABEL = r"\bC[TI]A\s*\.?\s*(?:BENEFICIARIO|ORDENANTE)\b"
ACCOUNT_NUMBER = r"((?:\d[ ./:]*){8,20})(?![ ./:]*\d)"
ACCOUNT = re.compile(ACCOUNT_LABEL + r"\s*[:.]?\s*" + ACCOUNT_NUMBER, re.I)
AUTH = re.compile(r"\bAUT\s*[:.]?\s*(\d{4,12})\b", re.I)
BOX = re.compile(r"\bCAJA\s*[:.]?\s*(\d{2,6})\b", re.I)
HOUR = re.compile(r"\bHORA\s*[:.]?\s*([01]\d|2[0-3])\s*[:.° ]?\s*([0-5]\d)\b", re.I)
REFERENCE = re.compile(r"\b(?:VR)?REF\s*[:.,]?\s*(\d{6,20})\b", re.I)


def _date(text: str) -> str:
    text = normalize_upper(text).strip(" .|*_'’[(-")
    text = re.sub(r"^(\d)\s*[!|](?=\s*[A-Z]{3}\b)", r"\g<1>1", text)
    if match := DATE.match(text):
        day = int(match[1].translate(str.maketrans("OILSB", "01158")))
        if 1 <= day <= 31:
            month = match[2].replace("0", "O").replace("D1C", "DIC").replace("DLC", "DIC")
            return f"{day:02d} {month}"
    return ""


def _money(text: str) -> int | None:
    text = text.strip(" |!_;{}[]'’—Il").replace("−", "-")
    # El formato siempre imprime dos posiciones decimales. Los reconocedores
    # pueden perder un separador o devolverlo como espacio entre dos dígitos.
    text = re.sub(r"(?<=\d)\s+(?=\d{2}\s*$)", ".", text)
    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[+-]?\d{3,12}", text):
        return int(text)
    if match := AMOUNT.fullmatch(text):
        cents = int(re.sub(r"\D", "", match[2])) * 100 + int(match[3])
        return -cents if "-" in match[1] + match[4] or "(" in match[1] else cents
    if re.fullmatch(r"\d[\d.,]*[.,]\d{2}", text):
        return int(re.sub(r"\D", "", text))
    return None


@dataclass(frozen=True, slots=True)
class DetailRow:
    fecha: str
    concepto: str
    cargo: int | None
    abono: int | None
    saldo: int | None


def _rows(words: list[dict], grids: dict[int, dict]) -> Iterable[DetailRow]:
    pages: dict[int, list[dict]] = defaultdict(list)
    detail = [word for word in words if int(word.get("page") or 1) > 1]
    for word in remove_after_banamex_movements(detail):
        pages[int(word.get("page") or 1)].append(word)
    for page, items in sorted(pages.items()):
        grid = grids.get(page)
        if grid is None:
            continue
        first, pitch, bottom = (grid[key] for key in ("first_center", "pitch", "bottom"))
        rows: dict[int, list[list[dict]]] = defaultdict(lambda: [[], [], [], [], []])
        for word in items:
            y = word_center_y(word)
            index = round((y - first) / pitch)
            if index < 0 or y >= bottom:
                continue
            column = bisect_right(grid["dividers"], word_center_x(word))
            rows[index][column].append(word)
        for _, columns in sorted(rows.items()):
            fecha, concepto, cargo, abono, saldo = map(line_text, columns)
            if "SALDOANTERIOR" in re.sub(r"[^A-Z]", "", normalize_upper(concepto)):
                continue
            yield DetailRow(_date(fecha), concepto, _money(cargo), _money(abono), _money(saldo))


def _tracking(concept: str) -> str | None:
    # El número puede estar en el siguiente renglón o fragmentado por OCR.
    match = TRACKING.search(concept)
    if not match:
        return None
    text = re.sub(r"(?<=TEF)\s*\.?\s*B[5S]\d{2}\s*$", "", match[1].strip(), flags=re.I)
    text = text.strip(" |!;:.,_–—-")
    if re.fullmatch(r"[\d\s-]+", text):
        text = re.sub(r"[\s-]", "", text)
    key = re.sub(r"\s+", "", text).strip(".:")
    # La regla izquierda a veces se reconoce como I, l o 1. En estos dos
    # formatos el prefijo y el número de posiciones distinguen esa regla.
    if match := re.fullmatch(r"[IJL1]?(016\d{18}TEF)", key, re.I):
        return match[1].upper()
    if match := re.fullmatch(r"[IL]?(MBAN[0-9O]{20})", key, re.I):
        return match[1].upper().replace("O", "0")
    if re.fullmatch(r"[A-Z0-9-]{6,35}", key, re.I) and any(c.isdigit() for c in key):
        return key
    return None


def _last_nonzero(pattern: re.Pattern[str], text: str) -> str | None:
    return next((value for value in reversed(pattern.findall(text)) if int(value)), None)


@dataclass(slots=True)
class _Block:
    fecha: str = ""
    lines: list[str] = field(default_factory=list)
    cargo: int | None = None
    abono: int | None = None

    def build(self, saldo: int | None) -> Movimiento:
        concept = "\n".join(self.lines)
        result = movement_from_fields(
            self.fecha,
            concept,
            (self.cargo or 0) / 100,
            (self.abono or 0) / 100,
            (saldo or 0) / 100,
        )
        result.clave_rastreo = _tracking(concept)
        if reference := REFERENCE.search(concept):
            result.referencia = reference[1]
        account = ACCOUNT.search(concept)
        result.cuenta_beneficiario = re.sub(r"\D", "", account[1]) if account else None
        result.clabe_beneficiario = (
            result.cuenta_beneficiario if valid_clabe(result.cuenta_beneficiario) else None
        )
        result.autorizacion = _last_nonzero(AUTH, concept)
        result.caja = _last_nonzero(BOX, concept)
        times = HOUR.findall(concept)
        result.hora_operacion = ":".join(times[-1]) if times else None
        return result


def extract_tabular_movements(words: list[dict], grids: dict[int, dict]) -> list[Movimiento]:
    moves = []
    block = _Block()
    for row in _rows(words, grids):
        if row.fecha and block.lines:
            if block.fecha or block.cargo is not None or block.abono is not None:
                moves.append(block.build(None))
            block = _Block()
        if row.fecha:
            block.fecha = row.fecha
        if row.concepto:
            block.lines.append(row.concepto)
        if row.cargo is not None:
            block.cargo = row.cargo
        if row.abono is not None:
            block.abono = row.abono
        if row.saldo is not None:
            if block.fecha or block.cargo is not None or block.abono is not None:
                moves.append(block.build(row.saldo))
            block = _Block()
    if block.fecha or block.cargo is not None or block.abono is not None:
        moves.append(block.build(None))
    # Dos fechas impresas iguales acotan un renglón intermedio sin día
    # legible. En un cambio de día se conserva el campo pendiente.
    for previous, current, following in zip(moves, moves[1:], moves[2:]):
        if not current.fecha_operacion and previous.fecha_operacion == following.fecha_operacion:
            current.fecha_operacion = previous.fecha_operacion
    return moves
