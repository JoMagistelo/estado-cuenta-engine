"""Conciliación Nu con estados y movimientos íntegramente ficticios."""

from __future__ import annotations

import copy
from dataclasses import asdict

import pytest

from engine.ocr_reprocessing import _validations
from engine.pipeline import _result_validations
from engine.statement_processor import _validation_results
from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero
from parsers.nu import parse_nu
from parsers.nu.validacion import flow_kind
from readers.models import DocumentData
from validators.movimiento_validator import validar_movimientos


def word(text: str, y: float, page: int = 1) -> dict:
    return {"text": text, "x0": 48, "x1": 540, "top": y, "bottom": y + 10, "page": page}


def statement(
    *,
    start="1,000.00",
    deposits="120.00",
    expenses="200.00",
    fees="3.00",
    gross="5.00",
    tax="0.80",
    net="4.20",
    final="921.20",
):
    rows = [
        word("PERSONA PRUEBA", 40),
        word("Cuenta Nu: 00000000001", 55),
        word("RFC: DEMO010101AA1", 70),
        word("CLABE: 638180000000000001", 85),
        word("Periodo: del 01 al 31 ene 2030", 100),
    ]
    for index, (label, value) in enumerate(
        [
            ("Saldo inicial", start),
            ("Depósitos", deposits),
            ("Gastos", expenses),
            ("Comisiones cobradas por Nu", fees),
            ("Dinero generado este mes", net),
            ("Saldo al generar este estado de cuenta", final),
        ]
    ):
        if value is not None:
            rows.append(word(f"{label} ${value}", 300 + index * 20))
    for index, (label, value) in enumerate(
        [
            ("Dinero generado antes de impuestos (Interés Bruto Anual de 1%)", gross),
            ("Impuestos sobre el dinero generado (ISR de 1%)", tax),
        ]
    ):
        if value is not None:
            rows.append(word(f"{label} ${value}", 120 + index * 20, 2))
    return parse_nu(DocumentData(spatial_words=rows))


def movement(concept: str, *, cargo=0.0, abono=0.0, original=None):
    return Movimiento(
        "10/01/2030",
        None,
        concept,
        "CARGO" if cargo else "ABONO",
        cargo,
        abono,
        concepto_original=original,
    )


def detail():
    return [
        movement("Ingreso prueba", abono=120),
        movement("Pago prueba", cargo=200),
        movement("Depósito en Cajita: Fondo ejemplo", cargo=120),
        movement("Depósito en Cajita: Fondo ejemplo", abono=120),
        movement("Retiro de Cajita: Fondo ejemplo", cargo=175),
        movement("Retiro de Cajita: Fondo ejemplo", abono=175),
        movement("Congelaste saldo hasta el 18 ENE 2030 en tu Cajita: Fondo ejemplo", cargo=220),
        movement("Descongelamos saldo de tu Cajita: Fondo ejemplo", abono=233),
    ]


def checks(state):
    return {v.nombre: v for v in validar_movimientos(state.movimientos, state.resumen_financiero)}


def test_nu_keeps_gross_sums_and_printed_totals_while_validating_external_flows():
    state = statement()
    state.movimientos = detail()
    before = copy.deepcopy(state)
    assert sum(m.abono for m in state.movimientos) == 648
    assert sum(m.cargo for m in state.movimientos) == 715
    results = checks(state)
    assert all(v.correcto for v in results.values())
    assert results["Total depósitos / abonos"].esperado == 120
    assert results["Total depósitos / abonos"].obtenido == 120
    assert results["Total retiros / cargos"].esperado == 200
    assert results["Total retiros / cargos"].obtenido == 200
    assert "648.00" in results["Total depósitos / abonos"].mensaje
    assert "715.00" in results["Total retiros / cargos"].mensaje
    assert "Cajitas" in results["Total depósitos / abonos"].mensaje
    assert state == before


@pytest.mark.parametrize(
    "title",
    [
        "Retiro de Cajita: Fondo A",
        "Depósito en Cajita: Fondo B",
        "Congelaste saldo hasta el 18 ENE 2030 en tu Cajita: Fondo C",
        "Descongelamos saldo de tu Cajita: Fondo D",
    ],
)
def test_internal_flow_rules_use_operation_labels_and_not_the_name_of_the_cajita(title):
    assert flow_kind(movement(title, cargo=20)) == "interno"


@pytest.mark.parametrize(
    "title",
    [
        "Operación desconocida Cajita A",
        "Pago comercio Cajita Feliz",
        "Transferencia por concepto Retiro de Cajita",
    ],
)
def test_unknown_or_free_text_operations_are_not_silently_excluded(title):
    assert flow_kind(movement(title, cargo=20)) == "externo"


def test_spei_memo_that_mentions_cajitas_remains_external():
    m = movement(
        "Retiro de Cajita: Fondo A",
        cargo=20,
        original="Persona prueba Transferencia SPEI. Por concepto Retiro de Cajita: Fondo A",
    )
    assert flow_kind(m) == "externo"


@pytest.mark.parametrize(
    "removed,failed_check", [(0, "Total depósitos / abonos"), (1, "Total retiros / cargos")]
)
def test_missing_external_movement_is_still_a_validation_failure(removed, failed_check):
    state = statement()
    state.movimientos = detail()
    state.movimientos.pop(removed)
    assert checks(state)[failed_check].correcto is False


def test_bad_external_amount_is_not_reconciled_using_the_balance():
    state = statement()
    state.movimientos = detail()
    state.movimientos[0].abono += 2
    assert checks(state)["Total depósitos / abonos"].diferencia == 2
    assert checks(state)["Total depósitos / abonos"].correcto is False


def test_equation_explicitly_accounts_for_net_earnings_tax_and_fees():
    state = statement()
    result = checks(state)["Ecuación financiera"]
    assert result.correcto
    assert result.obtenido == 921.2
    assert state.resumen_financiero.intereses_a_favor == 5
    assert state.resumen_financiero.isr_retenido == 0.8
    assert state.resumen_financiero.manejo_cuenta == 3
    assert state.resumen_financiero.rendimiento_neto == 4.2


def test_mismatching_net_and_gross_less_tax_is_not_accepted():
    state = statement(net="3.00", final="920.00")
    result = checks(state)["Rendimiento neto Nu"]
    assert result.correcto is False
    assert result.obtenido == 4.2


@pytest.mark.parametrize("kind,field", [("Comisión Nu", "cargo"), ("Rendimiento", "abono")])
def test_explicit_fee_or_yield_movements_are_compared_to_their_own_summary(kind, field):
    state = statement()
    state.movimientos = detail() + [movement(kind, **{field: 9})]
    results = checks(state)
    assert not results["Comisiones Nu" if field == "cargo" else "Rendimientos Nu"].correcto


@pytest.mark.parametrize(
    "validator", [_validation_results, _validations, lambda s: _result_validations(s, None)]
)
def test_empty_month_with_printed_yield_is_validated_without_inventing_movements(validator):
    state = statement(deposits="0.00", expenses="0.00", fees="0.00", final="1,004.20")
    assert state.movimientos == []
    results = validator(state)
    assert len(results) == 4
    assert all(v.correcto for v in results)
    assert state.movimientos == []


def test_no_movements_with_nonzero_printed_flows_is_a_real_failure():
    state = statement()
    results = checks(state)
    assert not results["Total depósitos / abonos"].correcto
    assert not results["Total retiros / cargos"].correcto


def test_missing_summary_values_remain_missing_instead_of_using_transaction_sums():
    state = statement(start=None, deposits=None, expenses=None, final=None)
    state.movimientos = detail()
    summary = state.resumen_financiero
    assert summary.saldo_anterior is None
    assert summary.saldo_final is None
    assert summary.depositos_abonos is None
    assert summary.retiros_cargos is None
    assert all(
        v.nombre
        not in {"Total depósitos / abonos", "Total retiros / cargos", "Ecuación financiera"}
        for v in checks(state).values()
    )


def test_unknown_yield_does_not_default_to_zero_for_the_equation():
    state = statement(net=None, gross=None, tax=None)
    result = checks(state)["Ecuación financiera"]
    assert result.correcto is False
    assert result.obtenido is None


def test_other_banks_keep_the_original_validation_equation_and_empty_handling():
    state = statement()
    data = asdict(state.resumen_financiero)
    data.pop("rendimiento_neto")
    state.resumen_financiero = ResumenFinanciero(**data)
    assert _validation_results(state) == []
    results = checks(state)
    assert results["Ecuación financiera"].obtenido == 920
    assert results["Ecuación financiera"].correcto is False
    assert "Rendimiento neto Nu" not in results


def test_invalid_external_amount_is_reported_as_a_failure_not_an_exception():
    state = statement()
    state.movimientos = [movement("Pago prueba", cargo=float("nan"))]
    assert checks(state)["Total retiros / cargos"].correcto is False
