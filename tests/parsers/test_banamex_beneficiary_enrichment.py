from __future__ import annotations

import pytest

from models.movimiento import Movimiento
from parsers.banamex.beneficiary_enrichment import (
    enrich_banamex_beneficiaries,
    extract_ordering_party,
)


@pytest.mark.parametrize(
    ("concept", "expected"),
    [
        (
            "PAGO RECIBIDO DE BBVA MEXICO\n"
            "POR ORDEN DE JOSE DANIEL AVILA\n"
            "CERRILLO REF.0912250 pago\n"
            "RASTREO\n"
            "MBAN01002512240071789237\n"
            "CAJA 0078 AUT 01147005\n"
            "HORA 16:35 SUC 0859",
            "JOSE DANIEL AVILA CERRILLO",
        ),
        (
            "PAGO RECIBIDO DE NU MEXICO POR\n"
            "ORDEN DE JOSE DANIEL AVILA\n"
            "CERRILLO CTA.ORDENANTE\n"
            "638180000102963942 REF.0030126\n"
            "SUC 0\n"
            "CAJA O AUT O HORA 0: 0\n"
            "Transferencia RASTREO:\n"
            "NU39B60TBMLA883BC7E7MAL74VQL\n"
            "CAJA 0078 AUT 00684319\n"
            "HORA 14:53 SUC 0859",
            "JOSE DANIEL AVILA CERRILLO",
        ),
    ],
)
def test_extract_ordering_party_from_received_payment_variants(
    concept: str,
    expected: str,
) -> None:
    assert extract_ordering_party(concept) == expected


def test_enrichment_only_fills_empty_beneficiary() -> None:
    movement = Movimiento(
        fecha_operacion="24 DIC",
        fecha_liquidacion=None,
        concepto="PAGO RECIBIDO DE BBVA MEXICO POR ORDEN DE JOSE DANIEL AVILA CERRILLO REF.0912250",
        tipo_operacion="ABONO",
        cargo=0.0,
        abono=100.0,
        beneficiario=None,
        concepto_original=None,
    )

    enrich_banamex_beneficiaries([movement])

    assert movement.beneficiario == "JOSE DANIEL AVILA CERRILLO"


def test_enrichment_preserves_existing_beneficiary() -> None:
    movement = Movimiento(
        fecha_operacion="24 DIC",
        fecha_liquidacion=None,
        concepto="PAGO RECIBIDO POR ORDEN DE PERSONA DISTINTA REF.1",
        tipo_operacion="ABONO",
        cargo=0.0,
        abono=100.0,
        beneficiario="BENEFICIARIO YA EXTRAIDO",
        concepto_original=None,
    )

    enrich_banamex_beneficiaries([movement])

    assert movement.beneficiario == "BENEFICIARIO YA EXTRAIDO"


def test_unrelated_concept_is_not_modified() -> None:
    assert extract_ordering_party("PAGO DE SERVICIO REF.12345") is None
