from __future__ import annotations

import re

from models.datos_cuenta import DatosCuenta

from .common import ACCOUNT, Line, dates, group_lines, normalized


def account_heading(lines: list[Line]) -> Line | None:
    return next(
        (
            line
            for line in lines
            if line.page == 1 and "CLABE" in normalized(line.text) and ACCOUNT.search(line.text)
        ),
        None,
    )


def extract_datos_cuenta_lines(lines: list[Line]) -> DatosCuenta:
    header = [line for line in lines if line.page == 1]
    heading = account_heading(header)
    text = "\n".join(line.text for line in header)
    upper = normalized(text)

    def capture(pattern: str) -> str | None:
        match = re.search(pattern, upper)
        return match[1].strip() if match else None

    period = next(
        (
            dates(l.text)
            for l in header
            if "PERIODO" in normalized(l.text) and len(dates(l.text)) == 2
        ),
        [],
    )
    cut = next((dates(l.text) for l in header if "CORTE" in normalized(l.text)), [])
    name = next(
        (
            line.text[: match.start()].strip()
            for line in header
            if (match := re.search(r"CODIGO\s+DE\s+CLIENTE", normalized(line.text)))
        ),
        None,
    )
    account = ACCOUNT.search(heading.text if heading else text)
    product = heading.text[: account.start()].strip() if heading and account else None
    clabe = capture(r"CLABE\s*:?\s*((?:\d[ -]*){18})(?!\d)")
    return DatosCuenta(
        producto_principal=product,
        periodo_inicio=period[0] if period else None,
        periodo_fin=period[1] if period else None,
        fecha_corte=cut[0] if cut else None,
        numero_cuenta=account[0] if account else None,
        numero_cliente=capture(r"CODIGO\s+DE\s+CLIENTE\s*(?:NO\.?\s*)?:?\s*(\d+)"),
        clabe=re.sub(r"\D", "", clabe) if clabe else None,
        nombre_cliente=name or None,
        rfc=capture(r"\bR\.?\s*F\.?\s*C\.?\s*:?\s*([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b"),
    )


def extract_datos_cuenta_words(words: list[dict]) -> DatosCuenta:
    return extract_datos_cuenta_lines(group_lines(words))
