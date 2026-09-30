from __future__ import annotations

import re

from models.datos_cuenta import DatosCuenta

from .common import Line, group_lines, long_dates, normalized


def extract_datos_cuenta_lines(lines: list[Line]) -> DatosCuenta:
    # El bloque del titular termina antes del resumen; nunca leer el RFC emisor
    # del CFDI ni cuentas de contraparte como identidad del estado.
    header = []
    for line in lines:
        if line.page != 1 or "RESUMEN MENSUAL" in normalized(line.text):
            break
        header.append(line)
    text = "\n".join(line.text for line in header)
    upper = normalized(text)

    def capture(pattern: str) -> str | None:
        match = re.search(pattern, upper)
        return match[1].strip() if match else None

    clabe = capture(r"CUENTA\s+CLABE:\s*((?:\d[ -]*){18})(?!\d)")

    period = next((long_dates(l.text) for l in header if "PERIODO:" in normalized(l.text)), [])
    cut = next((long_dates(l.text) for l in header if "FECHA DE CORTE:" in normalized(l.text)), [])
    name = None
    for line in header:
        value = normalized(line.text)
        if "NO. CLIENTE" in value or "RFC:" in value:
            break
        if "BANCO" not in value and ":" not in value and re.search(r"[A-Z]", value):
            name = line.text.strip()

    return DatosCuenta(
        producto_principal=capture(r"TIPO DE CUENTA:\s*([^\n]+?)(?=\s+DOMICILIO:|\n|$)"),
        periodo_inicio=period[0].strftime("%d/%m/%Y") if len(period) == 2 else None,
        periodo_fin=period[1].strftime("%d/%m/%Y") if len(period) == 2 else None,
        fecha_corte=cut[0].strftime("%d/%m/%Y") if cut else None,
        numero_cuenta=capture(r"NO\.?\s*CUENTA:\s*(\d+)"),
        numero_cliente=capture(r"NO\.?\s*CLIENTE:\s*(\d+)"),
        clabe=re.sub(r"\D", "", clabe) if clabe else None,
        nombre_cliente=name,
        rfc=capture(r"\bRFC:\s*([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b"),
    )


def extract_datos_cuenta_words(words: list[dict]) -> DatosCuenta:
    return extract_datos_cuenta_lines(group_lines(words))
