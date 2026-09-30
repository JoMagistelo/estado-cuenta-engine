from __future__ import annotations

import re
from datetime import datetime

from models.movimiento import Movimiento

from .common import Line, group_lines, normalized

DATE = re.compile(r"^(\d{2}/\d{2}/\d{4})(?!\d)[_\s]*")
SIGNED_MONEY = re.compile(r"(?:\(\s*([+\-−])\s*\)|([+\-−]))?\s*\$\s*([\d,]+\.\d{2})(?!\d)")
LABEL = re.compile(
    r"\b(EMISOR|RECEPTOR|NOM\s+ORIG[I1]|NOM\s+BENEF|BENEFICIARIO|"
    r"CUENTA(?:\s+BENEFICIARI[AO])?|CTA|CLABE(?:\s+BENEFICIARI[AO])?|"
    r"RASTREO|REF|CONCEPTO|RFC|SUCURSAL|AUT(?:ORIZACION)?|CAJA|HORA)\s*:",
    re.IGNORECASE,
)


def enrich_movement_metadata_from_concepto(movement: Movimiento) -> Movimiento:
    """Concepto conserva el detalle completo; Original sólo el texto etiquetado."""
    text = movement.concepto
    # La normalización mantiene la longitud para conservar el texto y mayúsculas
    # originales al delimitar los valores (incluido el mensaje del ordenante).
    matches = list(LABEL.finditer(normalized(text)))
    # El memo puede contener palabras como "REF:" o "RFC:" escritas por la
    # persona que transfiere. Después de CONCEPTO: todo pertenece a ese memo.
    for index, match in enumerate(matches):
        if match[1] == "CONCEPTO":
            matches = matches[: index + 1]
            break
    fields = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fields[" ".join(match[1].split())] = text[match.end() : end].strip()

    def get(*keys: str) -> str | None:
        return next((fields[k] for k in keys if fields.get(k)), None)

    name = get("NOM BENEF", "BENEFICIARIO", "NOM ORIGI", "NOM ORIG1")
    if name:
        name = re.split(r"\bDATO\s+NO\s+VERIFICADO\b", name, flags=re.IGNORECASE)[0]
        movement.beneficiario = name.strip(" .(),") or None
    account = get("CUENTA BENEFICIARIO", "CUENTA BENEFICIARIA", "CUENTA", "CTA")
    clabe = get("CLABE BENEFICIARIO", "CLABE BENEFICIARIA", "CLABE")
    if account and re.fullmatch(r"[\d -]{5,}", account):
        movement.cuenta_beneficiario = re.sub(r"\D", "", account)
        if len(movement.cuenta_beneficiario) == 18:
            movement.clabe_beneficiario = movement.cuenta_beneficiario
    if clabe and re.fullmatch(r"[\d -]+", clabe):
        digits = re.sub(r"\D", "", clabe)
        if len(digits) == 18:
            movement.clabe_beneficiario = digits
            if movement.cuenta_beneficiario is None:
                movement.cuenta_beneficiario = digits
    movement.sucursal = get("EMISOR", "RECEPTOR", "SUCURSAL") or movement.sucursal
    movement.clave_rastreo = get("RASTREO")
    movement.referencia = get("REF")
    movement.concepto_original = get("CONCEPTO")
    movement.rfc = get("RFC")
    movement.autorizacion = get("AUTORIZACION", "AUT")
    movement.caja = get("CAJA")
    movement.hora_operacion = get("HORA")
    return movement


def extract_movimientos_lines(lines: list[Line]) -> list[Movimiento]:
    movements: list[Movimiento] = []
    pending: Movimiento | None = None
    detail: list[str] = []
    direction: str | None = None
    # Anclas actualizadas con cada encabezado/fecha, en las coordenadas del OCR.
    concept_left = 0.0
    money_left = float("inf")
    suspended = False
    current_page = None

    def flush() -> None:
        nonlocal pending, detail
        if pending is not None:
            pending.concepto = " ".join(detail).strip()
            movements.append(enrich_movement_metadata_from_concepto(pending))
        pending, detail = None, []

    for line in lines:
        if line.page != current_page:
            current_page = line.page
            suspended = False
        text, upper = line.text, normalized(line.text)
        if re.match(r"^TOTAL (?:DE )?DEPOSITOS DEL MES", upper):
            flush()
            direction, suspended = "ABONO", False
            continue
        if re.match(r"^TOTAL (?:DE )?RETIROS DEL MES", upper):
            flush()
            direction, suspended = "CARGO", False
            continue
        if "FECHA" in upper and "CONCEPTO" in upper and "MONTO" in upper:
            for word in line.words:
                if normalized(str(word["text"])) == "MONTO":
                    height = float(word.get("bottom", word["top"])) - float(word["top"])
                    money_left = float(word["x0"]) - height
            suspended = False
            continue
        if re.match(r"^CONTINUA EN LA SIGUIENTE HOJA", upper):
            suspended = True
            continue
        if re.match(
            r"^(?:HOJA \d+ DE|BANCO\W+(?:\w\W+)?AZTECA$|ESTE DOCUMENTO ES|LUGAR O CANAL|OPERACION$)",
            upper,
        ) or upper.startswith("* EN CASO DE NO CONTAR CON RFC"):
            if "EN CASO DE NO CONTAR" in upper:
                suspended = True
            continue
        if re.match(
            r"^(?:TOTAL\s*\$|CUANTO RECIBI|COMISIONES QUE|PARA FINES|"
            r"IMPUESTOS RETENIDOS|CARGOS OBJETADOS|TUS MOVIMIENTOS|GLOSARIO)",
            upper,
        ):
            flush()
            direction = None
            continue
        if direction is None or suspended:
            continue

        date_match = DATE.match(text)
        amount_match = SIGNED_MONEY.search(text)
        # Una fila parcial con importe se conserva sólo en la columna monetaria.
        partial_amount = (
            not date_match
            and amount_match
            and any(float(w["x0"]) >= money_left and "$" in str(w["text"]) for w in line.words)
        )
        if date_match or partial_amount:
            flush()
            date_text = date_match[1] if date_match else ""
            if date_text:
                try:
                    datetime.strptime(date_text, "%d/%m/%Y")
                except ValueError:
                    continue
                date_words = [w for w in line.words if DATE.match(str(w["text"]))]
                if date_words:
                    concept_left = float(date_words[0]["x1"])
            amount = float(amount_match[3].replace(",", "")) if amount_match else 0.0
            sign = (amount_match[1] or amount_match[2]) if amount_match else None
            row_direction = ("ABONO" if sign == "+" else "CARGO") if sign else direction
            start = date_match.end() if date_match else 0
            end = amount_match.start() if amount_match else len(text)
            if amount_match:
                detail = [text[start:end].strip()]
            else:
                detail = [
                    " ".join(
                        str(w["text"])
                        for w in line.words
                        if concept_left <= float(w["x0"]) < money_left
                    ).strip()
                ]
            channel = text[amount_match.end() :].strip() if amount_match else ""
            pending = Movimiento(
                fecha_operacion=date_text,
                fecha_liquidacion=None,
                concepto="",
                tipo_operacion=row_direction,
                cargo=amount if row_direction == "CARGO" else 0.0,
                abono=amount if row_direction == "ABONO" else 0.0,
                sucursal="BANCO AZTECA" if "BANCO AZTECA" in normalized(channel) else None,
            )
        elif pending is not None:
            continuation = " ".join(
                str(w["text"]) for w in line.words if concept_left <= float(w["x0"]) < money_left
            ).strip()
            if continuation:
                detail.append(continuation)
    flush()
    return movements


def extract_movimientos_words(words: list[dict]) -> list[Movimiento]:
    return extract_movimientos_lines(group_lines(words))
