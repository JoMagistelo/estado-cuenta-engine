from __future__ import annotations

import re

from models.movimiento import Movimiento

from ..layouts import Columns, detect_columns, is_section_end
from .common import ACCOUNT, DATE, Line, group_lines, money, normalized, parse_date


LABEL = re.compile(
    r"(?<![A-Z0-9])(?:ENVIADO\s+A|RECIBIDO\s+DE|(?:A|DE)\s+LA\s+CUENTA|"
    r"(?:AL|DEL)\s+CLIENTE|POR\s+ORDEN\s+DE|CTA\.?\s+ORDENANTE|"
    r"CLAVE\s+DE\s+RASTREO|RASTREO|REF(?:ERENCIA)?|CONCEPTO|"
    r"RFC|REC|CLABE|CUENTA|SUCURSAL|AUT(?:ORIZACION)?|CAJA|IVA|HORA)"
    r"\b\s*:?\s*",
)
RFC = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}")


def _fields(parts: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    active = None
    for index, text in enumerate(parts):
        upper = normalized(text)
        matches = list(LABEL.finditer(upper)) if index == 0 else []
        if index:
            match = LABEL.match(upper)
            if match:
                # Dentro de un mensaje libre sólo el RFC bancario en una línea
                # independiente cierra el memo; "REF:" escrito por la persona
                # permanece en concepto_original.
                valid_rfc = match[0].strip(" :") in {"RFC", "REC"} and RFC.fullmatch(
                    upper[match.end() :].strip()
                )
                if active != "CONCEPTO" or valid_rfc:
                    matches = [match]
            elif active in {"RFC", "IVA", "REF", "AUTORIZACION", "CAJA"}:
                matches = list(LABEL.finditer(upper))
        # Un concepto ya concatenado no permite distinguir el RFC bancario de
        # una etiqueta escrita dentro del mensaje. Conservar todo el memo.
        for i, match in enumerate(matches):
            if match[0].strip(" :") == "CONCEPTO":
                matches = matches[: i + 1]
                break
        if matches:
            if index and active and matches[0].start():
                fields[active] = (fields[active] + " " + text[: matches[0].start()]).strip()
            for i, match in enumerate(matches):
                key = re.sub(r"\s+", " ", match[0].strip(" :"))
                key = {"REC": "RFC", "REFERENCIA": "REF", "RASTREO": "CLAVE DE RASTREO"}.get(
                    key, key
                )
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                fields[key] = text[match.end() : end].strip()
                active = key
        elif active:
            fields[active] = (fields[active] + " " + text).strip()
    return fields


def enrich_movement_metadata_from_concepto(
    movement: Movimiento,
    parts: list[str] | None = None,
) -> Movimiento:
    """Extraer sólo datos impresos; el mensaje libre y el detalle son distintos."""
    fields = _fields(parts or [movement.concepto])

    def get(*keys: str) -> str | None:
        return next((fields[k] for k in keys if fields.get(k)), None)

    name = get("AL CLIENTE", "DEL CLIENTE", "POR ORDEN DE")
    if name:
        name = re.split(r"\(\s*1\s*\)|\bDATO\s+NO\s+VERIFICADO\b", name, flags=re.I)[0]
        movement.beneficiario = name.strip() or None
    else:
        # Transferencia rápida: el nombre puede ocupar varias líneas y termina
        # al llegar al RFC/IVA/REF, no al primer espacio.
        match = re.search(
            r"\bTRANSFERENCIA\s+(?:A|DE)\s+(.+?)(?=\s+(?:RFC|REC|IVA|REF|CAJA|CLAVE DE RASTREO)\b|$)",
            normalized(movement.concepto),
        )
        if match and re.search(
            r"\b(?:RAPIDA|TRANSE?F?|SANTANDER)\b", normalized(movement.concepto)
        ):
            movement.beneficiario = movement.concepto[match.start(1) : match.end(1)].strip()
        if movement.beneficiario is None:
            match = re.search(r"\bDEPOSITO DE\s+(.+?)(?=\s+\d|$)", normalized(movement.concepto))
            if match:
                movement.beneficiario = movement.concepto[match.start(1) : match.end(1)].strip()
    account = get("A LA CUENTA", "DE LA CUENTA", "CTA ORDENANTE", "CUENTA")
    if account and re.fullmatch(r"[\d -]{5,}", account):
        movement.cuenta_beneficiario = re.sub(r"\D", "", account)
        if len(movement.cuenta_beneficiario) == 18:
            movement.clabe_beneficiario = movement.cuenta_beneficiario
    clabe = get("CLABE")
    if clabe and re.fullmatch(r"[\d -]+", clabe):
        digits = re.sub(r"\D", "", clabe)
        if len(digits) == 18:
            movement.clabe_beneficiario = digits
            movement.cuenta_beneficiario = movement.cuenta_beneficiario or digits
    movement.sucursal = get("ENVIADO A", "RECIBIDO DE", "SUCURSAL")
    if not movement.sucursal and re.search(
        r"\bTRANSF\s+RAPIDA\s+SANTANDER\b", normalized(movement.concepto)
    ):
        movement.sucursal = "SANTANDER"
    movement.clave_rastreo = get("CLAVE DE RASTREO")
    movement.referencia = get("REF") or movement.referencia
    movement.autorizacion = get("AUTORIZACION", "AUT")
    movement.caja = get("CAJA")
    movement.concepto_original = get("CONCEPTO")
    rfc = get("RFC")
    if rfc and RFC.fullmatch(normalized(rfc)):
        movement.rfc = rfc
    if movement.rfc is None:
        # Compras: RFC del comercio dividido en dos palabras por el reader.
        match = re.search(r"\b([A-ZÑ&]{3,4})\s+(\d{6}[A-Z0-9]{3})\b", normalized(movement.concepto))
        if match:
            movement.rfc = match[1] + match[2]
    match = re.search(
        r"(?<![A-Z])HORA[\s_:]*([0-2O]\d:[0-5O]\d:[0-5O]\d)\b", normalized(movement.concepto)
    )
    if match:
        value = match[1].replace("O", "0")
        h, m, s = map(int, value.split(":"))
        if h < 24 and m < 60 and s < 60:
            movement.hora_operacion = value
    if movement.concepto_original is None:
        match = re.search(r"\bABONO TRANSFERENCIA ENLACE\s+(.+)$", normalized(movement.concepto))
        if match:
            movement.concepto_original = movement.concepto[match.start(1) : match.end(1)].strip()
    return movement


def extract_movimientos_lines(
    lines: list[Line],
    account: str | None = None,
) -> list[Movimiento]:
    movements: list[Movimiento] = []
    pending: Movimiento | None = None
    detail: list[str] = []
    columns: Columns | None = None
    current_page = None
    selected_account = True

    def flush() -> None:
        nonlocal pending, detail
        if pending is not None:
            pending.concepto = " ".join(detail).strip()
            movements.append(enrich_movement_metadata_from_concepto(pending, detail))
        pending, detail = None, []

    for line in lines:
        if line.page != current_page:
            current_page = line.page
            columns = None
        detected = detect_columns(line)
        if detected is not None:
            columns = detected if selected_account else None
            continue
        if columns is None:
            found_account = ACCOUNT.search(line.text)
            if found_account and account:
                selected_account = found_account[0] == account
            continue
        upper = normalized(line.text)
        if re.match(r"^(?:PAGINA|HOJA)\s+\d+\s+DE\b", upper):
            columns = None
            continue
        if is_section_end(line.text):
            flush()
            columns = None
            continue

        prefix = " ".join(
            str(w["text"]) for w in line.words if float(w["x0"]) < columns.concept_left
        )
        date_match = DATE.match(normalized(prefix))
        cells = {key: money(value) for key, value in columns.amount_cells(line).items()}
        # Sólo una fila con fecha o importe en depósito/retiro abre movimiento.
        # No inferir cargo/abono por el texto ni reconstruir cifras con el saldo.
        has_amount = any(cells.get(key) is not None for key in ("abono", "cargo"))
        if date_match or has_amount:
            flush()
            date_text = parse_date(date_match) if date_match else ""
            folio = prefix[date_match.end() :].strip() if date_match else prefix.strip()
            if folio and not re.fullmatch(r"\d+", folio):
                folio = None
            detail = [columns.concept(line)]
            cargo, abono = cells.get("cargo") or 0.0, cells.get("abono") or 0.0
            pending = Movimiento(
                fecha_operacion=date_text or "",
                fecha_liquidacion=None,
                concepto="",
                tipo_operacion="CARGO"
                if cargo and not abono
                else "ABONO"
                if abono and not cargo
                else "No identificado",
                cargo=cargo,
                abono=abono,
                referencia=folio,
                saldo_operacion=cells.get("saldo") or 0.0,
            )
        elif pending is not None:
            continuation = columns.concept(line)
            if continuation:
                detail.append(continuation)
    flush()
    return movements


def extract_movimientos_words(words: list[dict]) -> list[Movimiento]:
    return extract_movimientos_lines(group_lines(words))
