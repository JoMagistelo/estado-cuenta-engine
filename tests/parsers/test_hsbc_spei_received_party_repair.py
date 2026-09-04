from __future__ import annotations

from typing import Any

from parsers.hsbc.extractors.movimientos import SpeiRow
from parsers.hsbc.utils.spei_received_party_repair import (
    repair_received_spei_row_party,
)


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
        "bottom": top + 7.0,
        "page": 4,
    }


def _received_row(
    lines: list[list[dict[str, Any]]],
    participant: str,
    orderer: str,
) -> SpeiRow:
    return SpeiRow(
        tipo="recibidos",
        page=4,
        lines=lines,
        fecha="23/12/2024",
        hora="15:31:32",
        participante=participant,
        beneficiario=orderer,
        cuenta_beneficiaria="00012180015334958488",
        nombre_ordenante=orderer,
        cuenta_ordenante="00012180015334958488",
        concepto="PAGO",
        monto=1000.0,
        clave_rastreo="MBAN01002412230000000000",
        numero_referencia="00000000000001712240",
    )


def test_repairs_bbva_bancomer_fused_with_orderer_name() -> None:
    row = _received_row(
        lines=[
            [
                _word("BBVA", 129.8, 149.5, 626.9),
                _word("BANCOMEROGELIO", 152.6, 227.0, 626.9),
            ],
            [_word("VAZQUEZ", 192.2, 228.7, 635.0)],
            [_word("LOPEZ", 193.0, 217.4, 644.2)],
        ],
        participant="BBVA BANCOMEROGELIO",
        orderer="VAZQUEZ LOPEZ",
    )

    assert repair_received_spei_row_party(row) is True
    assert row.participante == "BBVA BANCOMER"
    assert row.nombre_ordenante == "ROGELIO VAZQUEZ LOPEZ"
    assert row.beneficiario == "ROGELIO VAZQUEZ LOPEZ"


def test_repairs_paged_er_without_touching_existing_surnames() -> None:
    row = _received_row(
        lines=[
            [_word("PAGEDERULISES", 128.0, 220.0, 400.0)],
            [_word("BAEZ", 192.0, 214.0, 408.0)],
            [_word("LOPEZ", 192.0, 216.0, 416.0)],
        ],
        participant="PAGEDERULISES",
        orderer="BAEZ LOPEZ",
    )

    assert repair_received_spei_row_party(row) is True
    assert row.participante == "PAGEDER"
    assert row.nombre_ordenante == "ULISES BAEZ LOPEZ"


def test_unknown_crossing_word_is_left_untouched() -> None:
    row = _received_row(
        lines=[
            [_word("INSTITUCIONNOMBRE", 140.0, 225.0, 400.0)],
            [_word("APELLIDO", 192.0, 225.0, 408.0)],
        ],
        participant="INSTITUCIONNOMBRE",
        orderer="APELLIDO",
    )

    assert repair_received_spei_row_party(row) is False
    assert row.participante == "INSTITUCIONNOMBRE"
    assert row.nombre_ordenante == "APELLIDO"
    assert row.beneficiario == "APELLIDO"
