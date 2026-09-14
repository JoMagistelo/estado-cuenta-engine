from __future__ import annotations

from typing import Any

from parsers.scotiabank.extractors.datos import extract_datos_cuenta_words


def _word(text: str, x0: float, top: float, *, width: float = 28.0) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x0 + width,
        "top": top,
        "bottom": top + 6.0,
        "doctop": top,
        "width": width,
        "height": 6.0,
        "upright": True,
        "direction": "ltr",
        "page": 1,
        "confidence": 90.0,
    }


def test_scotiabank_ocr_account_data_survives_split_labels_and_values() -> None:
    words = [
        _word("Periodo", 420.0, 108.0, width=30.0),
        _word("13-NOV-24", 462.0, 108.5, width=48.0),
        _word("al", 514.0, 108.0, width=8.0),
        _word("13-DIC-24", 526.0, 108.5, width=48.0),
        _word("ORTEGA", 68.0, 142.0, width=36.0),
        _word("LEDESMA", 108.0, 142.4, width=44.0),
        _word("MARIA", 156.0, 142.0, width=30.0),
        _word("MAGDALENA", 190.0, 142.3, width=54.0),
        _word("Cuenta", 360.0, 164.0, width=30.0),
        _word("CLABE", 360.0, 181.0, width=28.0),
        _word("044180001004397526", 401.0, 183.0, width=92.0),
        _word("Resumen", 118.0, 266.0, width=32.0),
        _word("de", 153.0, 266.0, width=8.0),
        _word("Saldos", 164.0, 266.0, width=24.0),
    ]

    result = extract_datos_cuenta_words(words)

    assert result.periodo_inicio == "13-NOV-24"
    assert result.periodo_fin == "13-DIC-24"
    assert result.fecha_corte == "13-DIC-24"
    assert result.nombre_cliente == "ORTEGA LEDESMA MARIA MAGDALENA"
    assert result.clabe == "044180001004397526"
    assert result.numero_cuenta == "00100439752"


def test_scotiabank_ocr_prefers_explicit_account_number_when_available() -> None:
    words = [
        _word("Cuenta", 360.0, 164.0, width=30.0),
        _word("00100439752", 404.0, 169.5, width=58.0),
        _word("CLABE", 360.0, 181.0, width=28.0),
        _word("044180001004397526", 401.0, 181.5, width=92.0),
    ]

    result = extract_datos_cuenta_words(words)

    assert result.numero_cuenta == "00100439752"
    assert result.clabe == "044180001004397526"
