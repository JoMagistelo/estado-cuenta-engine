"""Portada y detalle de CTA Mujer Banorte con dos productos en portada."""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import asdict
from datetime import date

from cep.catalog import valid_clabe
from models.datos_cuenta import DatosCuenta
from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from validators.resultado_validacion import ResultadoValidacion

from .datos import (
    _compact,
    _extract_dates,
    _find_customer_number,
    _find_rfc,
    _group_lines,
    _line_text,
    _norm,
    _x0,
)
from .movimientos import _cy, _semantic_text, movement_from_fields
from .resumen import extract_resumen_financiero_words


PRODUCT = "CTA MUJER BANORTE SALDO PROM"
PRODUCT_KEY = _compact(PRODUCT)
MONTHS = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")
DATE = re.compile(
    r"^\s*[|!'\"(-]*\s*([0-9OILSG]{1,2})[ .:/-]*"
    r"(ENE|FEB|MAR|ABR|MAY|JUN|JUL|A[GC][O0]|SEP|[O0]C[T1I]|CT|N[O0]V|D[I1L]C|DK)"
    r"[ .:/-]*([0-9OIL]{2})",
    re.I,
)
AMOUNT_COLUMNS = ((0.576, 0.705), (0.708, 0.824), (0.832, 0.929))
DATE_LEFT = 0.080
DESCRIPTION_LEFT = 0.140
DESCRIPTION_RIGHT = 0.575
MONEY = re.compile(r"^\d[\d.,]*[.,]\d{2}$")
TRACE = re.compile(r"3843([2C(])[P0OFR]([0-9OIL]{20})(?!\d)")
TRACE_LABEL = re.compile(r"\b(?:CVE[.\s]*)?RAST(?:REO|R)?\s*[:;.=]?\s*")
ACCOUNT = re.compile(r"\b(?:CTA\s*[/|]?\s*)?CLAB[E3]\s*[:;.=]?\s*((?:\d[ .-]*){16,20})(?![ .-]*\d)")
SPEI_REFERENCE = re.compile(r"\bORDEN\s+DE\s+PAGO\s+SPEI\s+(\d{7})(?!\d)")
AUTHORIZATION = re.compile(r"\bAUTORIZA\s*[:;.]?\s*(\d{6})(?!\d)")


def scan_cents(text: str, *, separator_required: bool = False) -> int | None:
    token = text.strip(" |:_![]{}'’").replace("$", "").replace("−", "-")
    token = re.sub(r"(?<=\d)\s+(?=\d{2}\s*$)", ".", token)
    token = re.sub(r"\s+", "", token)
    negative = token.startswith(("-", "(")) or token.endswith("-")
    token = token.strip("+()-")
    if MONEY.fullmatch(token) or (not separator_required and re.fullmatch(r"\d{3,12}", token)):
        amount = int(re.sub(r"\D", "", token))
        return -amount if negative else amount
    return None


def scan_date(text: str) -> tuple[str, date, int] | None:
    match = DATE.match(text)
    if not match:
        return None
    day, month, year = match.groups()
    digits = str.maketrans("OILSG", "01156")
    month = month.upper().replace("0", "O").replace("1", "I")
    month = {"ACO": "AGO", "OCI": "OCT", "CT": "OCT", "DLC": "DIC", "DK": "DIC"}.get(month, month)
    try:
        parsed = date(
            2000 + int(year.upper().translate(digits)),
            MONTHS.index(month) + 1,
            int(day.upper().translate(digits)),
        )
    except ValueError:
        return None
    return f"{parsed.day:02d}-{month}-{parsed.year % 100:02d}", parsed, match.end()


def outgoing_trace(text: str) -> str | None:
    # En la clave emitida por Banorte, el prefijo y la fecha identifican las
    # posiciones reservadas a letras aun cuando el OCR confunde P con un cero.
    compact = re.sub(r"[\s._|'’]", "", _norm(text))
    if match := TRACE.search(compact):
        suffix = match[2].translate(str.maketrans("OIL", "011"))
        if not re.fullmatch(r"0[1-9]20\d{16}", suffix):
            return None
        try:
            date(int(suffix[2:6]), int(suffix[6:8]), int(suffix[8:10]))
        except ValueError:
            return None
        return "3843" + match[1].replace("(", "C") + "P" + suffix
    return None


def _enrich_movement(move: Movimiento) -> None:
    search = _semantic_text(move.concepto)
    if reference := SPEI_REFERENCE.search(search):
        move.referencia = reference[1]
    if authorization := AUTHORIZATION.search(search):
        move.autorizacion = authorization[1]
    if account := ACCOUNT.search(search):
        digits = re.sub(r"\D", "", account[1])
        if valid_clabe(digits):
            move.clabe_beneficiario = digits
        elif len(digits) == 16:
            move.cuenta_beneficiario = digits
    if move.clabe_beneficiario and not valid_clabe(move.clabe_beneficiario):
        move.clabe_beneficiario = None
    if trace := outgoing_trace(search):
        move.clave_rastreo = trace
    elif move.clave_rastreo:
        move.clave_rastreo = move.clave_rastreo.strip(" _")


def is_mujer_cover(words: list[dict]) -> bool:
    text = _compact(" ".join(str(w.get("text", "")) for w in words))
    return all(
        label in text
        for label in (
            PRODUCT_KEY,
            "ESTADODECUENTA",
            "INVERSIONMUJERBANORTE",
            "SALDOINICIALDELPERIODO",
            "TOTALDEDEPOSITOS",
            "TOTALDERETIROS",
        )
    )


def is_mujer_detail(words: list[dict], width: float) -> bool:
    header = _compact(
        " ".join(str(w.get("text", "")) for w in words if 0.053 * width < _cy(w) < 0.177 * width)
    )
    return all(label in header for label in ("FECHA", "DESCRIPCION", "DEPOSITO", "RETIRO"))


def _columns(line: list[dict], width: float, left: float, right: float) -> list[dict]:
    return [w for w in line if left * width <= _x0(w) < right * width]


def _summary_amount(lines: list[list[dict]], width: float, label: str) -> float | None:
    for line in lines:
        if _compact(_line_text(_columns(line, width, 0, 0.34))).startswith(label):
            cell = _columns(line, width, 0.34, 0.448)
            recognized = [
                value
                for w in cell
                if (value := scan_cents(w["text"], separator_required=True)) is not None
            ]
            if len(recognized) > 1:
                continue
            amount = (
                recognized[0]
                if recognized
                else scan_cents(
                    _line_text(cell),
                    separator_required=True,
                )
            )
            if amount is not None:
                return amount / 100
    return None


class MujerSummary(ResumenFinanciero):
    validar_sin_movimientos = True

    def validar_componentes(self, movimientos: list[Movimiento]) -> list[ResultadoValidacion]:
        missing = sum(
            value is None
            for value in (
                self.saldo_anterior,
                self.saldo_final,
                self.depositos_abonos,
                self.retiros_cargos,
            )
        )
        results = []
        if missing:
            results.append(
                ResultadoValidacion(
                    "Resumen impreso Banorte",
                    0,
                    missing,
                    missing,
                    False,
                    "Importes impresos pendientes",
                )
            )
        if movimientos and self.saldo_anterior is not None:
            previous = round(self.saldo_anterior * 100)
            differences = 0
            for move in movimientos:
                printed = round(move.saldo_operacion * 100)
                differences += (
                    previous + round(move.abono * 100) - round(move.cargo * 100) != printed
                )
                previous = printed
            results.append(
                ResultadoValidacion(
                    "Continuidad de saldos Banorte",
                    0,
                    differences,
                    differences,
                    not differences,
                    "Saldo e importe de cada operación",
                )
            )
        return results


def extract_cover(words: list[dict], width: float) -> tuple[DatosCuenta, MujerSummary]:
    lines = _group_lines(words)
    start = finish = cutoff = None
    name = None
    previous: list[dict] = []
    left_lines = []
    account = clabe = None
    for line in lines:
        left = _columns(line, width, 0.065, 0.46)
        left_lines.append(left)
        text = _norm(_line_text(left))
        if not name and re.match(r"^(CALLE|AVENIDA|AV\.|ANDADOR|PRIVADA)\b", text):
            candidate = _line_text(previous).strip()
            if re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ .'-]+", candidate.upper()):
                name = candidate.upper()
        if left:
            previous = left
        right = _norm(_line_text(_columns(line, width, 0.58, 0.94)))
        dates = _extract_dates(right)
        if "PERIODO" in _compact(right) and len(dates) == 2:
            start, finish = dates
        if "CORTE" in _compact(right) and dates:
            cutoff = dates[-1]
        if _compact(text).startswith(PRODUCT_KEY):
            digits = re.sub(r"\D", "", _line_text(_columns(line, width, 0.335, 0.455)))
            possible_clabe = re.sub(r"\D", "", _line_text(_columns(line, width, 0.455, 0.63)))
            if len(digits) == 10:
                account = digits
                if valid_clabe(possible_clabe):
                    clabe = possible_clabe

    left_lines = [line for line in left_lines if line]
    customer = _find_customer_number(left_lines)
    data = DatosCuenta(
        producto_principal=PRODUCT,
        periodo_inicio=start,
        periodo_fin=finish,
        fecha_corte=cutoff,
        numero_cuenta=account,
        numero_cliente=customer,
        clabe=clabe,
        nombre_cliente=name,
        rfc=_find_rfc(left_lines, customer),
    )
    # El extractor común calcula comisiones e intereses sobre la columna
    # de la cuenta seleccionada. La inversión ocupa otra columna en esta portada.
    values = asdict(extract_resumen_financiero_words([w for w in words if _x0(w) < width * 0.448]))
    for field, label in (
        ("saldo_anterior", "SALDOINICIALDELPERIODO"),
        ("depositos_abonos", "TOTALDEDEPOSITOS"),
        ("retiros_cargos", "TOTALDERETIROS"),
        ("saldo_final", "SALDOACTUAL"),
        ("saldo_promedio", "ENELPERIODO"),
    ):
        if (amount := _summary_amount(lines, width, label)) is not None:
            values[field] = amount
    return data, MujerSummary(**values)


def _group_by_anchor(words: list[dict], anchors: list[float], tolerance: float):
    groups = [[] for _ in anchors]
    for word in words:
        i = bisect_left(anchors, _cy(word))
        possible = range(max(0, i - 1), min(len(anchors), i + 1))
        index = min(possible, key=lambda j: abs(_cy(word) - anchors[j]), default=None)
        if index is not None and abs(_cy(word) - anchors[index]) <= tolerance:
            groups[index].append(word)
    return groups


def extract_movements(words: list[dict], tables: dict[int, dict]) -> list[Movimiento]:
    by_page = {}
    for word in words:
        by_page.setdefault(int(word.get("page") or 1), []).append(word)
    result = []
    for page, table in sorted(tables.items()):
        width, anchors = table["width"], table["rows"]
        top, bottom = table["top"], table["bottom"]
        body = [w for w in by_page.get(page, []) if top <= _cy(w) < bottom]
        numeric = _group_by_anchor(body, anchors, width * 0.009)
        description = _columns(body, width, DATE_LEFT, DESCRIPTION_RIGHT)
        starts = [anchor - width * 0.009 for anchor in anchors]
        for i, row in enumerate(numeric):
            end = starts[i + 1] if i + 1 < len(starts) else bottom
            lines = _group_lines([w for w in description if starts[i] <= _cy(w) < end])
            parts = [_line_text(line) for line in lines]
            date_words = sorted(
                _columns(row, width, DATE_LEFT, DESCRIPTION_LEFT),
                key=lambda w: abs(_cy(w) - anchors[i]),
            )
            operation_date = next(
                (parsed for w in date_words if (parsed := scan_date(str(w["text"])))),
                None,
            )
            if parts and (printed := scan_date(parts[0])):
                parts[0] = parts[0][printed[2] :].strip()
                operation_date = operation_date or printed
            concept = "\n".join(part for part in parts if part)
            if "SALDOANTERIOR" in _compact(concept):
                continue
            abono, cargo, saldo = [
                scan_cents(_line_text(_columns(row, width, left, right))) or 0
                for left, right in AMOUNT_COLUMNS
            ]
            if not (abono or cargo or operation_date):
                continue
            move = movement_from_fields(
                operation_date[0] if operation_date else "",
                concept,
                abono / 100,
                cargo / 100,
                saldo / 100,
            )
            _enrich_movement(move)
            result.append(move)
    return result
