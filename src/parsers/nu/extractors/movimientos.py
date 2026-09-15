from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from models.movimiento import Movimiento

from .common import SpatialLine, group_words_into_lines, normalize_text, normalize_upper, parse_money

SpatialWord = Dict[str, Any]

MONTH_NUMBERS = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}

ANCHOR_RE = re.compile(
    r"^\s*(?P<day>\d{1,2})\s+"
    r"(?P<month>ENE(?:RO)?|FEB(?:RERO)?|MAR(?:ZO)?|ABR(?:IL)?|MAY(?:O)?|"
    r"JUN(?:IO)?|JUL(?:IO)?|AGO(?:STO)?|SEP(?:T(?:IEMBRE)?)?|SET(?:IEMBRE)?|"
    r"OCT(?:UBRE)?|NOV(?:IEMBRE)?|DIC(?:IEMBRE)?)\s+"
    r"(?P<year>\d{4})\s+(?P<concept>.+?)\s+"
    r"(?P<amount>[+-]\s*\$?\s*[\d,]+(?:\.\d{1,2})?)\s*$",
    re.IGNORECASE,
)
TIME_TOKEN_RE = re.compile(r"\bHORA\s*:\s*([0-9OoIl:]{4,10})", re.IGNORECASE)
TRACK_RE = re.compile(
    r"\bCLAVE\s+DE\s+RASTREO\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{3,80})",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"\bCLAVE\s+DE\s+REFERENCIA\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{1,49})",
    re.IGNORECASE,
)
BANK_RE = re.compile(
    r"\b(?:ENVIADO\s+A|RECIBIDO\s+DE)\s+(.+?)\.\s+(?:AL|DEL)\s+CLIENTE\b",
    re.IGNORECASE,
)
COUNTERPARTY_RE = re.compile(
    r"\b(?:AL|DEL)\s+CLIENTE\s+(.+?)\s*\(DATO\s+NO\s+VERIFICADO",
    re.IGNORECASE,
)
ACCOUNT_RE = re.compile(
    r"\b(?:A|DE)\s+LA\s+CUENTA\s+([0-9][0-9\s-]{7,30})\s+CLABE\b",
    re.IGNORECASE,
)
MEMO_RE = re.compile(
    r"\bPOR\s+CONCEPTO\s+(.+?)\.\s+(?:A|DE)\s+LA\s+CUENTA\b",
    re.IGNORECASE,
)

MOVEMENT_END_MARKERS = (
    "CON ESTOS MOVIMIENTOS",
    "DINERO GENERADO EN TU CUENTA NU",
    "CONTACTO",
    "COMPROBANTE FISCAL DIGITAL",
)


@dataclass(slots=True)
class MovementAnchor:
    line_index: int
    fecha: str
    concepto: str
    amount: float


def _month_number(value: str) -> Optional[int]:
    normalized = normalize_upper(value)
    return MONTH_NUMBERS.get(normalized[:3])


def _parse_anchor(line: SpatialLine, line_index: int) -> Optional[MovementAnchor]:
    match = ANCHOR_RE.match(normalize_text(line.text))
    if not match:
        return None
    month = _month_number(match.group("month"))
    amount = parse_money(match.group("amount"))
    if month is None or amount is None:
        return None
    try:
        parsed = date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None
    return MovementAnchor(
        line_index=line_index,
        fecha=parsed.strftime("%d/%m/%Y"),
        concepto=normalize_text(match.group("concept")),
        amount=amount,
    )


def _is_noise_line(line: SpatialLine) -> bool:
    normalized = normalize_upper(line.text)
    if not normalized:
        return True
    if line.center_y < 82.0:
        return True
    if line.center_y > 770.0:
        return True
    return any(
        marker in normalized
        for marker in (
            "DETALLE DE MOVIMIENTOS EN TU CUENTA",
            "FECHA DEL ",
            "MONTO EN PESOS MEXICANOS",
            "NU MEXICO FINANCIERA",
            "MANUEL AVILA CAMACHO",
            "TELEFONO: 800 099 1133",
        )
    )


def _movement_section_end(lines: Sequence[SpatialLine], start: int) -> int:
    for index in range(start, len(lines)):
        normalized = normalize_upper(lines[index].text)
        if any(marker in normalized for marker in MOVEMENT_END_MARKERS):
            return index
    return len(lines)


def _detail_text(lines: Sequence[SpatialLine]) -> str:
    return normalize_text(" ".join(line.text for line in lines if not _is_noise_line(line)))


def _extract_counterparty(text: str) -> Optional[str]:
    match = COUNTERPARTY_RE.search(text)
    if not match:
        return None
    return normalize_text(match.group(1)).strip(" ,.-") or None


def _extract_account(text: str) -> Optional[str]:
    match = ACCOUNT_RE.search(text)
    if not match:
        return None
    value = re.sub(r"\D", "", match.group(1))
    return value or None


def _extract_memo(text: str) -> Optional[str]:
    match = MEMO_RE.search(text)
    if not match:
        return None
    return normalize_text(match.group(1)).strip(" ,.-") or None


def _extract_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    return normalize_text(match.group(1)) if match else None


def _extract_time(text: str) -> Optional[str]:
    match = TIME_TOKEN_RE.search(text)
    if not match:
        return None
    candidate = match.group(1).translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"}))
    if not re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", candidate):
        return None
    return candidate


def _extract_tracking(text: str) -> Optional[str]:
    value = _extract_match(TRACK_RE, text)
    if not value:
        return None
    value = value.upper()
    if re.fullmatch(r"\d{18}L", value):
        value = value[:-1] + "I"
    return value


def _extract_tipo_operacion(anchor: MovementAnchor, text: str) -> str:
    normalized = normalize_upper(text)
    if "DEPOSITO SPEI" in normalized:
        return "TRANSFERENCIA SPEI RECIBIDA"
    if "TRANSFERENCIA SPEI" in normalized:
        return "TRANSFERENCIA SPEI ENVIADA"
    if "PAGO A TU TARJETA DE CREDITO NU" in normalized:
        return "PAGO TARJETA DE CREDITO"
    if "COMPRA" in normalize_upper(anchor.concepto):
        return "COMPRA"
    return "CARGO" if anchor.amount < 0 else "ABONO"


def _movement_from_block(
    anchor: MovementAnchor,
    detail_lines: Sequence[SpatialLine],
) -> Movimiento:
    detail = _detail_text(detail_lines)
    raw_concept = normalize_text(" ".join(part for part in (anchor.concepto, detail) if part))
    memo = _extract_memo(raw_concept)
    account = _extract_account(raw_concept)
    cargo = abs(anchor.amount) if anchor.amount < 0 else 0.0
    abono = anchor.amount if anchor.amount > 0 else 0.0

    return Movimiento(
        fecha_operacion=anchor.fecha,
        fecha_liquidacion=None,
        concepto=memo or anchor.concepto,
        tipo_operacion=_extract_tipo_operacion(anchor, raw_concept),
        cargo=round(cargo, 2),
        abono=round(abono, 2),
        referencia=_extract_match(REFERENCE_RE, raw_concept),
        autorizacion=None,
        beneficiario=_extract_counterparty(raw_concept),
        cuenta_beneficiario=account,
        clabe_beneficiario=account if account and len(account) == 18 else None,
        clave_rastreo=_extract_tracking(raw_concept),
        rfc=None,
        sucursal=_extract_match(BANK_RE, raw_concept),
        caja=None,
        hora_operacion=_extract_time(raw_concept),
        saldo_operacion=0.0,
        saldo_liquidacion=0.0,
        concepto_original=raw_concept,
    )


def extract_movimientos_words(words: List[SpatialWord]) -> List[Movimiento]:
    lines = group_words_into_lines(words)
    anchors = [
        anchor
        for index, line in enumerate(lines)
        if (anchor := _parse_anchor(line, index)) is not None
    ]
    if not anchors:
        return []

    section_end = _movement_section_end(lines, anchors[-1].line_index + 1)
    result: List[Movimiento] = []
    for index, anchor in enumerate(anchors):
        end = anchors[index + 1].line_index if index + 1 < len(anchors) else section_end
        detail_lines = lines[anchor.line_index + 1 : end]
        result.append(_movement_from_block(anchor, detail_lines))
    return result


__all__ = ["extract_movimientos_words"]
