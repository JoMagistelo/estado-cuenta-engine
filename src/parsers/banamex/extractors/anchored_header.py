"""Portadas MiCuenta con identificación y resumen etiquetados.

Las etiquetas delimitan los campos y las columnas; no se reutilizan las cajas
del formato histórico ni se reconstruyen cifras a partir de los movimientos.
"""

from __future__ import annotations

import re
from datetime import date

from models.datos_cuenta import DatosCuenta
from models.resumen_financiero import ResumenFinanciero

from .movimientos import group_words_into_lines, line_text, normalize_upper


MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "ENERO",
            "FEBRERO",
            "MARZO",
            "ABRIL",
            "MAYO",
            "JUNIO",
            "JULIO",
            "AGOSTO",
            "SEPTIEMBRE",
            "OCTUBRE",
            "NOVIEMBRE",
            "DICIEMBRE",
        ),
        1,
    )
}
MONTH = "(?:" + "|".join(MONTHS) + ")"
PERIOD = re.compile(
    rf"\b(\d{{1,2}})\s+DE\s+({MONTH})\s+"
    rf"(?:(?:DE|DEL)\s+(\d{{4}})\s+)?AL\s+"
    rf"(\d{{1,2}})\s+DE\s+({MONTH})\s+(?:DE|DEL)\s+(\d{{4}})\b"
)
NATURAL_DATE = re.compile(rf"\b(\d{{1,2}})\s+DE\s+({MONTH})\s+(?:DE|DEL)\s+(\d{{4}})\b")
AMOUNT = re.compile(r"(?<![\d.])[-−]?\s*\$?\s*\d[\d,]*\.\d{2}(?!\d)")


def _text(line: list[dict]) -> str:
    text = normalize_upper(line_text(line))
    # Confusiones de letras en etiquetas OCR. Los identificadores y los
    # importes se capturan después y conservan exactamente sus caracteres.
    for pattern, replacement in (
        (r"\b[NM][UV][MN]ERO\b", "NUMERO"),
        (r"\bGALDO\b", "SALDO"),
        (r"\bPRONEDIO\b", "PROMEDIO"),
        (r"\bOROS CARGOS\b", "OTROS CARGOS"),
    ):
        text = re.sub(pattern, replacement, text)
    return text


def is_cover_page(words: list[dict]) -> bool:
    lines = group_words_into_lines(words)
    text = " ".join(_text(line) for line in lines)
    if not all(
        re.search(pattern, text)
        for pattern in (
            r"NUMERO\s+DE\s+CUENTA\s+DE\s+CHEQUES",
            r"NUMERO\s+DE\s+CONTRATO",
            r"SALDO\s+AL\s+CORTE",
        )
    ):
        return False
    return True


def _cover(words: list[dict]) -> list[list[dict]] | None:
    first = [word for word in words if int(word.get("page", 1)) == 1]
    return group_words_into_lines(first) if first and is_cover_page(first) else None


def _left_limit(lines: list[list[dict]]) -> float:
    title = next((line for line in lines if re.match(r"^ESTADO DE CUENTA\b", _text(line))), None)
    if title:
        return min(float(w["x0"]) for w in title)
    # La portada tiene dos columnas. El extremo impreso proporciona la escala
    # cuando el OCR pierde el título del recuadro derecho.
    return (
        min(float(w["x0"]) for l in lines for w in l)
        + max(float(w["x1"]) for l in lines for w in l)
    ) / 2


def _capture(lines: list[list[dict]], pattern: str, value: str) -> str | None:
    for line in lines:
        match = re.search(pattern + r"\s*:?\s*(" + value + ")", _text(line))
        if match:
            return match[1].strip()
    return None


def _dates(lines: list[list[dict]]) -> tuple[str | None, str | None]:
    for index, line in enumerate(lines):
        candidate = " ".join(_text(l) for l in lines[index : index + 2])
        match = PERIOD.search(candidate)
        if match:
            d1, m1, y1, d2, m2, y2 = match.groups()
            start_year = int(y1) if y1 else int(y2) - (MONTHS[m1] > MONTHS[m2])
            try:
                return (
                    date(start_year, MONTHS[m1], int(d1)).strftime("%d/%m/%Y"),
                    date(int(y2), MONTHS[m2], int(d2)).strftime("%d/%m/%Y"),
                )
            except ValueError:
                pass
    return None, None


def extract_cover_account(words: list[dict]) -> DatosCuenta | None:
    lines = _cover(words)
    if lines is None:
        return None
    limit = _left_limit(lines)
    title = next((l for l in lines if "ESTADO DE CUENTA" in _text(l)), None)
    top = (
        min(float(w["top"]) for w in title)
        if title
        else min(float(w["top"]) for l in lines for w in l)
    )
    name = None
    for line in lines:
        if min(float(w["top"]) for w in line) < top:
            continue
        tokens = [
            str(w["text"])
            for w in line
            if float(w["x0"]) < limit
            and not re.fullmatch(r"\d+", str(w["text"]).strip())
            and normalize_upper(w["text"]) not in ("MICUENTA", "MI", "CUENTA")
        ]
        candidate = " ".join(tokens).strip()
        if (
            len(candidate.split()) >= 2
            and re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ .'-]+", candidate.upper())
            and not re.search(
                r"BANAMEX|BANCO|PAGINA|FECHA|CUENTA|RESUMEN", normalize_upper(candidate)
            )
        ):
            name = candidate
            break
    left = [[w for w in line if float(w["x0"]) < limit] for line in lines]
    left = [line for line in left if line]
    cut = None
    for i, line in enumerate(left):
        if "FECHA DE CORTE" in _text(line):
            match = NATURAL_DATE.search(" ".join(_text(l) for l in left[max(0, i - 1) : i + 2]))
            if match:
                try:
                    cut = date(int(match[3]), MONTHS[match[2]], int(match[1])).strftime("%d/%m/%Y")
                except ValueError:
                    pass
            break
    headers = [l for l in group_words_into_lines(words) if int(l[0].get("page", 1)) == 2]
    for i, line in enumerate(headers):
        if "DETALLE DE OPERACIONES" in _text(line):
            headers = headers[:i]
            break
    start, end = _dates(lines + headers)
    return DatosCuenta(
        producto_principal="MiCuenta",
        periodo_inicio=start,
        periodo_fin=end,
        fecha_corte=cut,
        numero_cuenta=_capture(left, r"NUMERO DE CUENTA DE CHEQUES", r"\d{7,18}"),
        numero_cliente=_capture(left, r"NUMERO DE CLIENTE", r"\d{5,18}"),
        clabe=_capture(left, r"CLABE(?: INTERBANCARIA)?", r"\d{18}(?!\d)"),
        nombre_cliente=name,
        rfc=_capture(left, r"\bR\.?[FE]\.?C\.?", r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b"),
    )


def extract_cover_summary(words: list[dict]) -> ResumenFinanciero | None:
    cover = _cover(words)
    if cover is None:
        return None
    limit = _left_limit(cover)
    left = [[w for w in line if float(w["x0"]) < limit] for line in cover]
    left = [line for line in left if line]
    detail = []
    for line in group_words_into_lines(words):
        if int(line[0].get("page", 1)) != 2:
            continue
        if "DETALLE DE OPERACIONES" in _text(line):
            break
        detail.append(line)

    def value(pattern: str, rows: list[list[dict]]) -> float | None:
        for line in rows:
            label = re.search(pattern, _text(line))
            if label:
                match = AMOUNT.search(_text(line), label.end())
                if match:
                    return float(
                        match[0]
                        .replace("$", "")
                        .replace(",", "")
                        .replace(" ", "")
                        .replace("−", "-")
                    )
        return None

    def preferred(pattern: str) -> float | None:
        found = value(pattern, detail)
        return found if found is not None else value(pattern, left)

    cargos = value(r"\bRETIROS\s*/\s*OTROS CARGOS\b", detail)
    if cargos is None:
        cash = value(r"\bRETIROS EN EFECTIVO\b", left)
        other = value(r"\bOTROS CARGOS\b", left)
        cargos = round(cash + other, 2) if cash is not None and other is not None else None
    days = _capture(detail, r"DIAS DEL PERIODO", r"\d{1,3}\b")
    rate = _capture(detail, r"TASA DE INTERES BRUTA\*?", r"\d+(?:\.\d+)?(?=\s*%)")
    final = preferred(r"\bSALDO AL CORTE\b")
    return ResumenFinanciero(
        saldo_promedio=preferred(r"\bSALDO PROMEDIO MENSUAL\b"),
        dias_periodo=int(days) if days else None,
        tasa_bruta_anual=float(rate) if rate else None,
        saldo_promedio_gravable=None,
        intereses_a_favor=value(r"^INTERESES\b(?! MENOS)", detail),
        isr_retenido=value(r"^IMPUESTO SOBRE LA RENTA RETENIDO\b", detail),
        cheques_pagados=None,
        manejo_cuenta=value(r"COMISIONES EFECTIVAMENTE COBRADAS", cover),
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=preferred(r"\bSALDO ANTERIOR\b"),
        depositos_abonos=preferred(r"\bDEPOSITOS\b"),
        retiros_cargos=cargos,
        saldo_final=final,
        saldo_promedio_minimo_mensual=None,
        saldo_global=final,
    )
