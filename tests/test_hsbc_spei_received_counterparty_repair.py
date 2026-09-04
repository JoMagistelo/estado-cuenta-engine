from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from parsers.hsbc.utils.spei_received_counterparty_repair import (
    repair_received_spei_counterparty,
)


PARTICIPANT_BOX = (120.0, 188.0, 0.0, 900.0)
COUNTERPARTY_BOX = (188.0, 246.0, 0.0, 900.0)


@dataclass
class _Row:
    tipo: str
    lines: list[list[dict[str, Any]]]
    participante: Optional[str] = None
    nombre_ordenante: Optional[str] = None
    beneficiario: Optional[str] = None


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 6.0,
        "page": 4,
    }


def test_received_shared_boundary_r_stays_with_orderer() -> None:
    # Caso sintético equivalente al OCR que colapsa las dos R del borde:
    # BBVA BANCOMER + REMITENTE -> BBVA BANCOMEREMITENTE.
    row = _Row(
        tipo="recibidos",
        lines=[
            [
                _word("BBVA", 128.88, 148.80, 568.56),
                _word("BANCOMEREMITENTE", 152.64, 233.64, 567.60),
            ],
            [_word("PRUEBA", 191.28, 222.00, 576.72)],
        ],
        participante="BBVA",
        nombre_ordenante="BANCOMEREMITENTE PRUEBA",
        beneficiario="BANCOMEREMITENTE PRUEBA",
    )

    changed = repair_received_spei_counterparty(
        row,
        PARTICIPANT_BOX,
        COUNTERPARTY_BOX,
    )

    assert changed is True
    assert row.participante == "BBVA BANCOMER"
    assert row.nombre_ordenante == "REMITENTE PRUEBA"
    assert row.beneficiario == "REMITENTE PRUEBA"


def test_received_already_separated_row_is_untouched() -> None:
    row = _Row(
        tipo="recibidos",
        lines=[
            [
                _word("BBVA", 128.0, 148.0, 500.0),
                _word("BANCOMER", 150.0, 184.0, 500.0),
                _word("ORDENANTE", 193.0, 232.0, 500.0),
            ]
        ],
        participante="BBVA BANCOMER",
        nombre_ordenante="ORDENANTE",
        beneficiario="ORDENANTE",
    )

    changed = repair_received_spei_counterparty(
        row,
        PARTICIPANT_BOX,
        COUNTERPARTY_BOX,
    )

    assert changed is False
    assert row.participante == "BBVA BANCOMER"
    assert row.nombre_ordenante == "ORDENANTE"
    assert row.beneficiario == "ORDENANTE"


def test_sent_spei_is_never_modified() -> None:
    row = _Row(
        tipo="enviados",
        lines=[
            [
                _word("BBVA", 128.88, 148.80, 568.56),
                _word("BANCOMEREMITENTE", 152.64, 233.64, 567.60),
            ]
        ],
        participante="ORIGINAL",
        beneficiario="ORIGINAL",
    )

    changed = repair_received_spei_counterparty(
        row,
        PARTICIPANT_BOX,
        COUNTERPARTY_BOX,
    )

    assert changed is False
    assert row.participante == "ORIGINAL"
    assert row.beneficiario == "ORIGINAL"
