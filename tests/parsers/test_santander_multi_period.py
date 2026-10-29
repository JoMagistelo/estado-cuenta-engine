"""Periodos y tipografías PDF sobre los contratos Santander ficticios existentes."""

from __future__ import annotations

import copy
import pickle
from dataclasses import asdict

import pytest

from parsers.santander import parse_santander
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from validators.movimiento_validator import validar_movimientos
from test_santander_parser import statement_words


def second_period():
    replacements = {
        "16-DIC-2025": "16-ENE-2026",
        "15-ENE-2026": "15-FEB-2026",
        "17-DIC-2025": "17-ENE-2026",
        "18-DIC-2025": "18-ENE-2026",
        "04-ENE-2026": "04-FEB-2026",
        "100.00": "110.00",
        "150.00": "160.00",
        "125.00": "135.00",
        "110.00": "120.00",
    }
    result = copy.deepcopy(statement_words())
    for w in result:
        w["page"] += 4
        w["text"] = replacements.get(w["text"], w["text"])
    return result


def parse(words):
    return parse_santander(DocumentData(spatial_words=words))


def test_two_periods_consolidate_independent_printed_totals_and_keep_exportable_data():
    result = parse(statement_words() + second_period())
    assert len(result.movimientos) == 6
    assert result.datos_cuenta.periodo_inicio == "16/12/2025"
    assert result.datos_cuenta.periodo_fin == "15/02/2026"
    assert result.datos_cuenta.fecha_corte == "15/02/2026"
    summary = result.resumen_financiero
    assert (
        summary.saldo_anterior,
        summary.depositos_abonos,
        summary.retiros_cargos,
        summary.saldo_final,
    ) == (100, 100, 80, 120)
    assert summary.dias_periodo == 62
    assert len(summary.periods) == 2
    assert all(v.correcto for v in validar_movimientos(result.movimientos, summary))
    # El mismo objeto viaja entre procesos en el runtime paralelo y congelado.
    restored = pickle.loads(pickle.dumps(result))
    assert restored == result
    assert all(
        v.correcto for v in validar_movimientos(restored.movimientos, restored.resumen_financiero)
    )
    tables = estado_cuenta_to_tables(
        [
            ProcessingResult(
                file_name="prueba.pdf",
                bank_key="santander",
                estado_cuenta=result,
                raw_text="",
                normalized_text="",
            )
        ]
    )
    assert len(tables["Movimientos"]) == 6
    assert len(tables["Resumen Financiero"]) == 1
    assert tables["Datos de la Cuenta"][0]["Periodo de Fin"] == "15/02/2026"


def test_opposite_errors_cannot_cancel_between_periods():
    result = parse(statement_words() + second_period())
    result.movimientos[0].abono += 5
    result.movimientos[3].abono -= 5
    checks = validar_movimientos(result.movimientos, result.resumen_financiero)
    assert checks[0].correcto  # El consolidado por sí solo ocultaría el error.
    assert not all(v.correcto for v in checks)
    assert sum(not v.correcto for v in checks if "depósitos" in v.nombre) == 2


def test_overprinted_font_words_and_private_unicode_letters_keep_the_same_statement():
    words = statement_words()
    expected = asdict(parse(copy.deepcopy(words)))
    substitutions = {
        "Depositos": "Dep\ue0a4sitos",
        "Dias": "D\ue09eas",
        "interes": "inter\ue09as",
        "minimo": "m\ue09enimo",
    }
    for w in words:
        w["text"] = substitutions.get(w["text"], w["text"])
    words += [{**w, "top": w["top"] + 0.02, "bottom": w["bottom"] + 0.02} for w in words]
    original = copy.deepcopy(words)
    assert asdict(parse(words)) == expected
    assert words == original


def test_distinct_accounts_are_not_consolidated():
    second = second_period()
    for w in second:
        w["text"] = w["text"].replace("56-90000001-1", "56-90000002-2")
    with pytest.raises(ValueError, match="misma cuenta"):
        parse(statement_words() + second)


def test_repeated_period_is_reported_instead_of_getting_a_valid_consolidation():
    duplicate = [{**w, "page": w["page"] + 4} for w in statement_words()]
    result = parse(statement_words() + duplicate)
    assert len(result.movimientos) == 6
    checks = validar_movimientos(result.movimientos, result.resumen_financiero)
    assert not next(v for v in checks if "continuidad de fechas" in v.nombre).correcto


def test_incomplete_period_summary_is_not_replaced_by_its_movements():
    second = second_period()
    # La fila de abonos del resumen desaparece; el detalle sigue intacto.
    second = [w for w in second if not (w["page"] == 5 and w["top"] == 253 and w["x0"] >= 307)]
    result = parse(statement_words() + second)
    assert len(result.movimientos) == 6
    assert result.resumen_financiero.depositos_abonos is None
    checks = validar_movimientos(result.movimientos, result.resumen_financiero)
    assert any(not v.correcto and "resumen incompleto" in v.nombre for v in checks)
