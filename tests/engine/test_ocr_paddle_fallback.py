from __future__ import annotations

from types import SimpleNamespace

from engine.statement_processor import (
    _ocr_quality_score,
    _result_needs_paddle_fallback,
)
from validators.resultado_validacion import ResultadoValidacion


def _estado(
    movimientos: int,
    validaciones_correctas: int,
    validaciones_incorrectas: int,
    missing_core: int = 0,
):
    core = [
        100.0,
        200.0,
        50.0,
        250.0,
    ]

    for index in range(min(missing_core, 4)):
        core[index] = None

    estado = SimpleNamespace(
        movimientos=[
            SimpleNamespace(
                cargo=0.0,
                abono=1.0,
                saldo_operacion=1.0,
            )
            for _ in range(movimientos)
        ],
        resumen_financiero=SimpleNamespace(
            saldo_anterior=core[0],
            depositos_abonos=core[1],
            retiros_cargos=core[2],
            saldo_final=core[3],
        ),
        datos_cuenta=SimpleNamespace(
            numero_cuenta="1234567890",
            numero_cliente="12345678",
            nombre_cliente="CLIENTE PRUEBA",
            rfc="AAAA000000AAA",
        ),
    )

    validations = []

    for _ in range(validaciones_correctas):
        validations.append(
            ResultadoValidacion(
                nombre="ok",
                esperado=1.0,
                obtenido=1.0,
                diferencia=0.0,
                correcto=True,
                mensaje="ok",
            )
        )

    for _ in range(validaciones_incorrectas):
        validations.append(
            ResultadoValidacion(
                nombre="fail",
                esperado=1.0,
                obtenido=2.0,
                diferencia=1.0,
                correcto=False,
                mensaje="fail",
            )
        )

    return estado, validations


def test_quality_score_rewards_financially_valid_candidate(monkeypatch):
    weak, weak_validations = _estado(
        movimientos=20,
        validaciones_correctas=2,
        validaciones_incorrectas=2,
    )
    strong, strong_validations = _estado(
        movimientos=20,
        validaciones_correctas=4,
        validaciones_incorrectas=0,
    )

    from engine import statement_processor

    def fake_validations(estado):
        if estado is weak:
            return weak_validations
        return strong_validations

    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        fake_validations,
    )

    assert _ocr_quality_score(strong) > _ocr_quality_score(weak)


def test_result_needs_fallback_when_any_validation_fails(monkeypatch):
    estado, validations = _estado(
        movimientos=10,
        validaciones_correctas=3,
        validaciones_incorrectas=1,
    )

    from engine import statement_processor

    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda _: validations,
    )

    assert _result_needs_paddle_fallback(estado) is True


def test_result_does_not_need_fallback_when_all_validations_pass(monkeypatch):
    estado, validations = _estado(
        movimientos=10,
        validaciones_correctas=4,
        validaciones_incorrectas=0,
    )

    from engine import statement_processor

    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda _: validations,
    )

    assert _result_needs_paddle_fallback(estado) is False


def test_missing_core_summary_can_trigger_fallback_without_validations(monkeypatch):
    estado, _ = _estado(
        movimientos=10,
        validaciones_correctas=0,
        validaciones_incorrectas=0,
        missing_core=2,
    )

    from engine import statement_processor

    monkeypatch.setattr(
        statement_processor,
        "_validation_results",
        lambda _: [],
    )

    assert _result_needs_paddle_fallback(estado) is True
