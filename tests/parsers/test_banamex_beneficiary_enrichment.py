from __future__ import annotations

import pytest

from models.movimiento import Movimiento
from parsers.banamex.beneficiary_enrichment import (
    enrich_banamex_beneficiaries,
    extract_ordering_party,
)


BBVA_PAYMENT = (
    "PAGO RECIBIDO DE BBVA MEXICO\n"
    "POR ORDEN DE JOSE DANIEL AVILA\n"
    "CERRILLO REF.0912250 pago\n"
    "RASTREO\n"
    "MBAN01002512240071789237\n"
    "CAJA 0078 AUT 01147005\n"
    "HORA 16:35 SUC 0859"
)
NU_PAYMENT = (
    "PAGO RECIBIDO DE NU MEXICO POR\n"
    "ORDEN DE JOSE DANIEL AVILA\n"
    "CERRILLO CTA.ORDENANTE\n"
    "638180000102963942 REF.0030126\n"
    "SUC 0\n"
    "CAJA O AUT O HORA 0: 0\n"
    "Transferencia RASTREO:\n"
    "NU39B60TBMLA883BC7E7MAL74VQL\n"
    "CAJA 0078 AUT 00684319\n"
    "HORA 14:53 SUC 0859"
)


def _movement(concept: str, **fields: str | None) -> Movimiento:
    return Movimiento(
        fecha_operacion="24 DIC",
        fecha_liquidacion=None,
        concepto=concept,
        tipo_operacion="ABONO",
        cargo=0.0,
        abono=100.0,
        **fields,
    )


@pytest.mark.parametrize(
    ("concept", "expected_name", "expected_bank"),
    [
        (BBVA_PAYMENT, "JOSE DANIEL AVILA CERRILLO", "BBVA MEXICO"),
        (NU_PAYMENT, "JOSE DANIEL AVILA CERRILLO", "NU MEXICO"),
        (
            "PAGO RECIBIDO DE BANCO EJEMPLO 123 POR ORDEN DE ANA MARIA PEREZ "
            "DE LA CRUZ REF.777 CAJA 0021",
            "ANA MARIA PEREZ DE LA CRUZ",
            "BANCO EJEMPLO 123",
        ),
        (
            "Pago recibido de Institución Financiera del Norte\n"
            "por\norden de María López Sánchez CTA.ORDENANTE 123456789012345678 "
            "REF.abc999 RASTREO XYZ123456",
            "María López Sánchez",
            "Institución Financiera del Norte",
        ),
    ],
)
def test_received_payment_uses_variable_bank_and_full_ordering_party(
    concept: str, expected_name: str, expected_bank: str
) -> None:
    assert extract_ordering_party(concept) == expected_name
    movement = _movement(concept, sucursal="0859")
    enrich_banamex_beneficiaries([movement])
    assert movement.beneficiario == expected_name
    assert movement.sucursal == expected_bank
    assert movement.concepto == concept
    assert movement.abono == 100.0
    assert movement.cargo == 0.0


def test_received_payment_completes_reference_rastreo_and_authorization() -> None:
    movement = _movement(BBVA_PAYMENT, sucursal="0859")
    enrich_banamex_beneficiaries([movement])
    assert movement.beneficiario == "JOSE DANIEL AVILA CERRILLO"
    assert movement.sucursal == "BBVA MEXICO"
    assert movement.referencia == "0912250"
    assert movement.clave_rastreo == "MBAN01002512240071789237"
    assert movement.caja == "0078"
    assert movement.autorizacion == "01147005"


def test_received_payment_uses_ordering_account_and_skips_ocr_zero_placeholders() -> None:
    movement = _movement(NU_PAYMENT, sucursal="0", caja="O", autorizacion="O")
    enrich_banamex_beneficiaries([movement])
    assert movement.beneficiario == "JOSE DANIEL AVILA CERRILLO"
    assert movement.sucursal == "NU MEXICO"
    assert movement.cuenta_beneficiario == "638180000102963942"
    assert movement.clabe_beneficiario == "638180000102963942"
    assert movement.referencia == "0030126"
    assert movement.clave_rastreo == "NU39B60TBMLA883BC7E7MAL74VQL"
    assert movement.caja == "0078"
    assert movement.autorizacion == "00684319"


def test_existing_confirmed_fields_are_kept_other_than_numeric_suc_code() -> None:
    movement = _movement(
        NU_PAYMENT,
        beneficiario="PERSONA CONFIRMADA",
        sucursal="0859",
        referencia="REFERENCIA CONFIRMADA",
        clave_rastreo="RASTREO CONFIRMADO",
        cuenta_beneficiario="CUENTA CONFIRMADA",
        clabe_beneficiario="CLABE CONFIRMADA",
        caja="1234",
        autorizacion="9999",
    )
    enrich_banamex_beneficiaries([movement])
    assert movement.beneficiario == "PERSONA CONFIRMADA"
    assert movement.sucursal == "NU MEXICO"
    assert movement.referencia == "REFERENCIA CONFIRMADA"
    assert movement.clave_rastreo == "RASTREO CONFIRMADO"
    assert movement.cuenta_beneficiario == "CUENTA CONFIRMADA"
    assert movement.clabe_beneficiario == "CLABE CONFIRMADA"
    assert movement.caja == "1234"
    assert movement.autorizacion == "9999"


@pytest.mark.parametrize(
    "concept",
    [
        "PAGO DE SERVICIO POR ORDEN DE ANA PEREZ REF.12345",
        "TRANSFERENCIA ENVIADA A BANCO EJEMPLO POR ORDEN DE ANA PEREZ",
        "PAGO RECIBIDO DE BANCO EJEMPLO REF.12345",
        "PAGO RECIBIDO DE BANCO EJEMPLO POR ORDEN DE REF.12345",
    ],
)
def test_unrelated_or_incomplete_movement_is_not_enriched(concept: str) -> None:
    movement = _movement(concept, sucursal="SUC ORIGINAL")
    enrich_banamex_beneficiaries([movement])
    assert extract_ordering_party(concept) is None
    assert movement.beneficiario is None
    assert movement.sucursal == "SUC ORIGINAL"
