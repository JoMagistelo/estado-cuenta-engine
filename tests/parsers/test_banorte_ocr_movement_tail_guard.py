from __future__ import annotations

from typing import Any

import pytest

from parsers.banorte_ocr.extractors.movimientos import extract_movimientos_words
from parsers.banorte_ocr.movement_tail_guard import (
    trim_after_last_confirmed_movement,
)


def _word(
    text: str,
    *,
    x0: float,
    x1: float,
    top: float,
    height: float = 6.5,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + height,
        "doctop": top,
        "width": x1 - x0,
        "height": height,
        "page": page,
        "confidence": 95.0,
    }


def _movement_line(
    date: str,
    concept: str,
    amount: str,
    balance: str,
    *,
    top: float,
) -> list[dict[str, Any]]:
    return [
        _word(date, x0=57.0, x1=84.5, top=top),
        _word(concept, x0=87.0, x1=245.0, top=top),
        _word(amount, x0=394.0, x1=418.0, top=top),
        _word(balance, x0=532.0, x1=560.0, top=top),
    ]


def _fixture_with_promotional_tail() -> list[dict[str, Any]]:
    lines = [
        _movement_line(
            "18-DIC-23",
            "WAL MART",
            "100.00",
            "49,000.00",
            top=100.0,
        ),
        _movement_line(
            "19-DIC-23",
            "DEPOSITO NOMINA",
            "1,000.00",
            "50,000.00",
            top=111.0,
        ),
        # La última operación puede ser cualquier día del mes. No se usa 30/31
        # como criterio de paro.
        _movement_line(
            "20-DIC-23",
            "SPEI RECIBIDO",
            "2,200.00",
            "53,382.88",
            top=150.0,
        ),
        [
            _word(
                "MARTINEZ MIRIAM SUSANA DE LA CLABE 127180013821254090",
                x0=87.0,
                x1=334.0,
                top=161.0,
            )
        ],
        [
            _word(
                "CONCEPTO: xxx REFERENCIA: 0924066 CVE RAST: 2401020718783675361",
                x0=87.0,
                x1=283.0,
                top=172.0,
            )
        ],
        # Geometría equivalente al hallazgo real: después del concepto del
        # último movimiento comienza una imagen promocional con texto más grande
        # y una separación vertical aproximadamente doble a la cadencia de tabla.
        [
            _word(
                "¡PREPARA TUS REGALOS CON TIEMPO",
                x0=93.0,
                x1=303.0,
                top=195.0,
                height=9.4,
            )
        ],
        [
            _word(
                "PARA LA MEJOR TEMPORADA DEL AÑO!",
                x0=87.0,
                x1=310.0,
                top=208.0,
                height=9.0,
            )
        ],
        [
            _word(
                "Activa Banorte Móvil y comienza a ahorrar",
                x0=127.0,
                x1=271.0,
                top=225.0,
                height=5.5,
            )
        ],
    ]

    return [word for line in lines for word in line]


def test_promotional_ocr_tail_is_not_concatenated_to_last_movement() -> None:
    words = _fixture_with_promotional_tail()

    trimmed = trim_after_last_confirmed_movement(words)
    trimmed_text = " ".join(str(word["text"]) for word in trimmed)

    assert "MARTINEZ MIRIAM" in trimmed_text
    assert "CONCEPTO: xxx" in trimmed_text
    assert "PREPARA TUS REGALOS" not in trimmed_text
    assert "TEMPORADA DEL AÑO" not in trimmed_text

    movements = extract_movimientos_words(trimmed)

    assert len(movements) == 3
    last = movements[-1]
    assert last.fecha_operacion == "20-DIC-23"
    assert last.abono == pytest.approx(2200.0)
    assert last.saldo_operacion == pytest.approx(53382.88)
    assert "MARTINEZ MIRIAM" in last.concepto
    assert "CONCEPTO: xxx" in last.concepto
    assert "PREPARA TUS REGALOS" not in last.concepto


def test_normal_continuation_is_preserved_without_visual_break() -> None:
    words = _fixture_with_promotional_tail()

    # Quitamos la promoción y añadimos una continuación legítima algo separada,
    # pero con la misma tipografía/geometría de los conceptos de movimientos.
    words = [
        word
        for word in words
        if "PREPARA" not in str(word["text"])
        and "TEMPORADA" not in str(word["text"])
        and "Activa Banorte" not in str(word["text"])
    ]
    continuation = _word(
        "RFC: TIMM780511DS0",
        x0=87.0,
        x1=190.0,
        top=190.0,
        height=6.5,
    )
    words.append(continuation)

    trimmed = trim_after_last_confirmed_movement(words)

    assert trimmed is words
    assert continuation in trimmed


def test_guard_is_conservative_when_last_row_lacks_complete_money_evidence() -> None:
    words = _fixture_with_promotional_tail()

    # Simula un movimiento final parcialmente dañado por OCR: conserva fecha y
    # depósito, pero pierde el saldo. El guard no debe adivinar ni recortar.
    words = [
        word
        for word in words
        if not (
            str(word["text"]) == "53,382.88"
            and float(word["top"]) == 150.0
        )
    ]

    trimmed = trim_after_last_confirmed_movement(words)
    text = " ".join(str(word["text"]) for word in trimmed)

    assert trimmed is words
    assert "PREPARA TUS REGALOS" in text


def test_cutoff_does_not_depend_on_day_30_or_31() -> None:
    words = _fixture_with_promotional_tail()

    trimmed = trim_after_last_confirmed_movement(words)
    text = " ".join(str(word["text"]) for word in trimmed)

    assert "20-DIC-23" in text
    assert "PREPARA TUS REGALOS" not in text
