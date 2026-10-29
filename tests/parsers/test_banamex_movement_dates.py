"""Fechas y etiquetas ficticias: el resumen no debe crear movimientos."""

from __future__ import annotations

import copy
import random
from dataclasses import asdict

import pytest

from parsers.banamex.extractors.movimientos import is_date_text
from validators.movimiento_validator import validar_movimientos

from test_banamex_cover_layout import cover_words, line, parse


@pytest.mark.parametrize(
    "text",
    [
        "Otros",
        "OTROS",
        "0 TROS",
        "Otros cargos",
        "00 ENE",
        "32 NOV",
        "00/ENE",
        "32-NOV",
        "00 ENERO 2030",
        "32/NOV/2030",
        "18 ABC",
        "18/ABC",
        "18-ABC",
        "18 ABC 2030",
        "18/ABC/2030",
    ],
)
def test_summary_labels_invalid_days_and_unknown_months_do_not_start_movements(text):
    assert not is_date_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "1 ENE",
        "31 DIC",
        "17/ENE",
        "17-ENE",
        "17 ENERO",
        "17 SEPTIEMBRE",
        "17 ENERO 2030",
        "17/ENE/2030",
        "O7NOV",
        "17ENE",
        "_17 NOV",
        "-27 NOV",
        "21 _NQV",
        "17 ENE*",
    ],
)
def test_existing_digital_and_ocr_date_formats_still_start_movements(text):
    assert is_date_text(text)


@pytest.mark.parametrize("scale,offset", [(1, 0), (1.2, 25), (0.85, 8)])
def test_cover_summary_does_not_add_a_phantom_credit_at_any_scale(scale, offset):
    words = cover_words()
    # La etiqueta cabe en la columna FECHA del fallback de portada. Su importe
    # cae en DEPÓSITOS, pero es contenido de resumen, no una operación.
    words += line("Otros cargos", 425) + line("345.67", 425, 440)
    for word in words:
        for key in ("x0", "x1", "top", "bottom"):
            word[key] = word[key] * scale + offset
    random.Random(29).shuffle(words)
    original = copy.deepcopy(words)

    state = parse(words)
    expected = parse(cover_words())
    assert [asdict(m) for m in state.movimientos] == [asdict(m) for m in expected.movimientos]
    assert all(v.correcto for v in validar_movimientos(state.movimientos, state.resumen_financiero))
    assert words == original

    # La corrección no fuerza palomitas cuando falta un abono real.
    state.movimientos.pop(0)
    checks = validar_movimientos(state.movimientos, state.resumen_financiero)
    assert not next(v for v in checks if v.nombre == "Total depósitos / abonos").correcto


def test_each_period_excludes_its_cover_summary_and_keeps_real_credits():
    first = cover_words() + line("Otros cargos", 425) + line("345.67", 425, 440)
    second = cover_words(
        opening=1675, deposit=300, charge=125, month="febrero", end="marzo", days=28
    )
    second += line("Otros cargos", 425) + line("456.78", 425, 440)
    second = [{**word, "page": word["page"] + 3} for word in second]

    state = parse(first + second)
    assert [m.abono for m in state.movimientos] == [700, 0, 300, 0]
    assert [len(part.movimientos) for part in state.resumen_financiero.periods] == [2, 2]
    assert all(v.correcto for v in validar_movimientos(state.movimientos, state.resumen_financiero))
