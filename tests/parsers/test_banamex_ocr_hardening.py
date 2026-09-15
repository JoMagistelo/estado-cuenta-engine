from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from engine import statement_processor
from parsers.banamex.extractors.movimientos import extract_movimientos_words
from parsers.normalizadores.banamex import normalize_banamex_words
from readers.models import DocumentData


SpatialWord = dict[str, Any]


def _line(
    page: int,
    center_y: float,
    entries: list[tuple[str, float, float]],
    *,
    skew: float = -0.004,
    height: float = 10.0,
) -> list[SpatialWord]:
    words: list[SpatialWord] = []
    for text, x0, x1 in entries:
        center_x = (x0 + x1) / 2.0
        word_center_y = center_y + skew * (center_x - 250.0)
        top = word_center_y - height / 2.0
        bottom = word_center_y + height / 2.0
        words.append(
            {
                "text": text,
                "x0": x0,
                "x1": x1,
                "top": top,
                "bottom": bottom,
                "doctop": top + (page - 1) * 792.0,
                "width": x1 - x0,
                "height": height,
                "page": page,
            }
        )
    return words


def _micuenta_ocr_words() -> list[SpatialWord]:
    words: list[SpatialWord] = []

    words += _line(
        1,
        46.0,
        [
            ("ESTADO", 232.0, 268.0),
            ("DE", 273.0, 286.0),
            ("CUENTA", 291.0, 329.0),
            ("AL", 334.0, 345.0),
            ("05", 350.0, 362.0),
            ("DE", 367.0, 379.0),
            ("AGOSTO", 384.0, 422.0),
            ("DE", 427.0, 439.0),
            ("2026", 444.0, 470.0),
        ],
    )
    words += _line(
        1,
        56.0,
        [("Banamex", 60.0, 102.0), ("CLIENTE:", 370.0, 420.0), ("123456789", 425.0, 475.0)],
    )
    words += _line(
        1,
        68.0,
        [
            ("Registro", 210.0, 250.0),
            ("Federal", 255.0, 290.0),
            ("de", 295.0, 305.0),
            ("Contribuyentes", 310.0, 385.0),
            ("TEST900101ABC", 410.0, 478.0),
        ],
    )
    words += _line(
        1,
        380.0,
        [
            ("PRODUCTO/SERVICIO", 53.0, 145.0),
            ("CONTRATO", 204.0, 252.0),
            ("SALDO", 269.0, 296.0),
            ("ANTERIOR", 301.0, 350.0),
            ("SALDO", 367.0, 391.0),
            ("AL", 396.0, 408.0),
            ("05/AGO/2026", 413.0, 470.0),
        ],
    )
    words += _line(
        1,
        391.0,
        [
            ("MiCuenta", 54.0, 92.0),
            ("987654321", 209.0, 252.0),
            ("$0.91", 330.0, 354.0),
            ("$13.50", 441.0, 470.0),
        ],
    )
    words += _line(
        1,
        402.0,
        [
            ("CLABE", 54.0, 75.0),
            ("Interbancaria", 79.0, 134.0),
            ("002180000000000001", 164.0, 248.0),
        ],
    )
    words += _line(
        1,
        440.0,
        [
            ("RESUMEN", 55.0, 95.0),
            ("DEL", 101.0, 118.0),
            ("06/JUL/2026", 123.0, 186.0),
            ("AL", 192.0, 203.0),
            ("05/AGO/2026", 209.0, 272.0),
        ],
    )
    words += _line(1, 450.0, [("CONTRATO", 55.0, 104.0), ("987654321", 110.0, 166.0)])
    words += _line(
        1,
        461.0,
        [("Saldo", 54.0, 75.0), ("Anterior", 79.0, 110.0), ("$0.91", 306.0, 330.0)],
    )
    words += _line(
        1,
        472.0,
        [
            ("(+)", 54.0, 67.0),
            ("2", 95.0, 100.0),
            ("Depósitos", 104.0, 145.0),
            ("$4,534.00", 284.0, 328.0),
        ],
    )
    words += _line(
        1,
        482.0,
        [
            ("(-)", 54.0, 67.0),
            ("1", 95.0, 100.0),
            ("Retiros", 104.0, 136.0),
            ("$4,521.41", 284.0, 328.0),
        ],
    )
    words += _line(
        1,
        493.0,
        [
            ("SALDO", 54.0, 84.0),
            ("AL", 89.0, 101.0),
            ("05", 107.0, 119.0),
            ("DE", 124.0, 136.0),
            ("AGOSTO", 142.0, 177.0),
            ("DE", 183.0, 195.0),
            ("2026", 201.0, 224.0),
            ("$13.50", 300.0, 336.0),
        ],
    )
    words += _line(
        1,
        515.0,
        [("Saldo", 54.0, 76.0), ("Promedio", 80.0, 115.0), ("$30.77", 224.0, 253.0)],
    )
    words += _line(
        1,
        525.0,
        [("Dias", 54.0, 70.0), ("Transcurridos", 74.0, 126.0), ("31", 242.0, 256.0)],
    )

    words += _line(
        2,
        48.0,
        [
            ("ESTADO", 230.0, 266.0),
            ("DE", 271.0, 284.0),
            ("CUENTA", 289.0, 327.0),
            ("AL", 332.0, 343.0),
            ("05", 348.0, 360.0),
            ("DE", 365.0, 377.0),
            ("AGOSTO", 382.0, 420.0),
            ("DE", 425.0, 437.0),
            ("2026", 442.0, 468.0),
        ],
    )
    words += _line(
        2,
        59.0,
        [("Banamex", 60.0, 102.0), ("CLIENTE:", 370.0, 420.0), ("123456789", 425.0, 475.0)],
    )
    words += _line(
        2,
        70.0,
        [("Página:", 210.0, 250.0), ("2", 455.0, 461.0), ("de", 465.0, 475.0), ("2", 480.0, 486.0)],
    )
    words += _line(
        2,
        80.0,
        [("ANA", 60.0, 80.0), ("PEREZ", 85.0, 120.0), ("LOPEZ", 125.0, 160.0)],
    )
    words += _line(
        2, 101.0, [("DETALLE", 190.0, 230.0), ("DE", 235.0, 248.0), ("OPERACIONES", 253.0, 320.0)]
    )
    words += _line(
        2,
        123.0,
        [
            ("FECHA", 53.0, 84.0),
            ("CONCEPTO", 155.0, 203.0),
            ("RETIROS", 283.0, 320.0),
            ("DEPOSITOS", 342.0, 391.0),
            ("SALDO", 421.0, 451.0),
        ],
    )
    words += _line(
        2,
        135.0,
        [
            ("06", 49.0, 59.0),
            ("JUL", 64.0, 78.0),
            ("SALDO", 90.0, 116.0),
            ("ANTERIOR", 122.0, 163.0),
            ("0.91", 452.0, 472.0),
        ],
    )
    words += _line(
        2,
        147.0,
        [
            ("06", 49.0, 59.0),
            ("JUL", 64.0, 78.0),
            ("PAGO", 90.0, 110.0),
            ("RECIBIDO", 115.0, 155.0),
            ("34.00", 379.0, 403.0),
            ("34.91", 447.0, 472.0),
        ],
    )
    words += _line(
        2,
        171.0,
        [
            ("07", 49.0, 59.0),
            ("JUL", 64.0, 78.0),
            ("COMISION", 90.0, 130.0),
            ("0.78", 315.0, 335.0),
            ("34.13", 447.0, 472.0),
        ],
    )
    words += _line(
        2,
        195.0,
        [
            ("05", 49.0, 59.0),
            ("AGO", 64.0, 82.0),
            ("DISPOSICIONES", 90.0, 154.0),
            ("EN", 159.0, 169.0),
            ("CAJERO", 174.0, 204.0),
            ("EXENTAS", 209.0, 245.0),
            ("5", 250.0, 255.0),
            ("34.13", 447.0, 472.0),
        ],
    )
    return words


def test_statement_processor_registers_micuenta_ocr_before_parsing() -> None:
    words = _micuenta_ocr_words()
    original = deepcopy(words)
    document = DocumentData(
        spatial_words=words,
        metadata={"ocr": True, "reader": "paddleocr"},
    )

    result, normalized_document = statement_processor._process_once(document, "banamex")

    assert words == original
    assert normalized_document.spatial_words is not words
    assert result.datos_cuenta.producto_principal == "MiCuenta"
    assert result.datos_cuenta.numero_cuenta == "987654321"
    assert result.datos_cuenta.numero_cliente == "123456789"
    assert result.datos_cuenta.rfc == "TEST900101ABC"
    assert result.datos_cuenta.clabe == "002180000000000001"
    assert result.datos_cuenta.nombre_cliente == "ANA PEREZ LOPEZ"

    summary = result.resumen_financiero
    assert summary.saldo_anterior == pytest.approx(0.91)
    assert summary.depositos_abonos == pytest.approx(4534.0)
    assert summary.retiros_cargos == pytest.approx(4521.41)
    assert summary.saldo_final == pytest.approx(13.50)
    assert summary.saldo_promedio == pytest.approx(30.77)
    assert summary.dias_periodo == 31


def test_ocr_columns_keep_retiros_depositos_and_skip_informational_row() -> None:
    normalized = normalize_banamex_words(_micuenta_ocr_words())

    movements = extract_movimientos_words(normalized)

    assert len(movements) == 2
    deposit, withdrawal = movements
    assert deposit.fecha_operacion == "06 JUL"
    assert deposit.cargo == 0.0
    assert deposit.abono == pytest.approx(34.0)
    assert deposit.saldo_operacion == pytest.approx(34.91)
    assert withdrawal.fecha_operacion == "07 JUL"
    assert withdrawal.cargo == pytest.approx(0.78)
    assert withdrawal.abono == 0.0
    assert withdrawal.saldo_operacion == pytest.approx(34.13)
    assert all("DISPOSICIONES EN CAJERO EXENTAS" not in item.concepto for item in movements)


def test_normalizer_leaves_other_banamex_layouts_untouched() -> None:
    words = _line(
        1,
        15.0,
        [
            ("ESTADO", 219.0, 261.0),
            ("DE", 264.0, 278.0),
            ("CUENTA", 281.0, 326.0),
            ("BASE", 330.0, 360.0),
            ("BANAMEX", 364.0, 420.0),
        ],
        skew=0.0,
    )

    normalized = normalize_banamex_words(words)

    assert normalized is words
    assert all(
        normalized_word is original_word
        for normalized_word, original_word in zip(normalized, words)
    )


def test_digital_movement_column_contract_is_preserved() -> None:
    words = _line(
        1,
        96.2,
        [
            ("FECHA", 18.6, 52.5),
            ("CONCEPTO", 129.5, 186.2),
            ("RETIROS", 271.0, 315.5),
            ("DEPOSITOS", 336.6, 394.9),
            ("SALDO", 424.6, 458.5),
        ],
        skew=0.0,
    )
    words += _line(
        1,
        108.5,
        [
            ("08", 14.2, 25.0),
            ("JUL", 30.0, 48.0),
            ("PAGO", 57.6, 84.0),
            ("SERVICIO", 89.0, 135.0),
            ("75.90", 297.0, 327.6),
            ("924.10", 448.5, 479.1),
        ],
        skew=0.0,
    )

    movements = extract_movimientos_words(words)

    assert len(movements) == 1
    assert movements[0].cargo == pytest.approx(75.90)
    assert movements[0].abono == 0.0
    assert movements[0].saldo_operacion == pytest.approx(924.10)
