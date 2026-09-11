from __future__ import annotations

import pytest

from parsers.bbva.extractors.datos import extract_datos_cuenta_words
from parsers.bbva.extractors.movimientos import extract_movimientos_words
from parsers.bbva.utils.words_footer_filter import remove_bbva_footer


def word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    *,
    page: int = 1,
    bottom: float | None = None,
) -> dict[str, object]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": bottom if bottom is not None else top + 8.0,
        "page": page,
    }


def test_ocr_account_header_uses_line_order_and_repeated_values() -> None:
    words = [
        # El orden por ``top`` puro sería Digital/Cuenta/Básico/Libretón.
        word("Digital", 566.0, 599.0, 16.5, bottom=30.0),
        word("Cuenta", 533.0, 562.0, 17.0, bottom=30.0),
        word("Básico", 500.0, 529.0, 17.5, bottom=30.0),
        word("Libretón", 459.0, 496.0, 18.0, bottom=30.0),
        word("05/12/2023", 498.0, 539.0, 49.0, bottom=58.0),
        word("04/01/2024", 554.0, 596.0, 49.4, bottom=58.4),
        word("04/01/2024", 554.0, 596.0, 65.0, bottom=73.0),
        word("1234567890", 550.0, 596.0, 80.0, bottom=89.0),
        # El titular está desplazado debajo de la caja digital histórica.
        word("ANA", 40.0, 61.0, 114.0, bottom=123.0),
        word("PEREZ", 67.0, 103.0, 113.5, bottom=123.0),
        word("LOPEZ", 109.0, 145.0, 113.0, bottom=123.0),
        word("PELA900101ABC", 530.0, 596.0, 111.0, bottom=122.0),
        # Fragmentos con variación vertical y último dígito fuera de x=596.
        word("9", 594.0, 600.0, 127.0, bottom=139.0),
        word("00012345678", 540.0, 590.0, 128.0, bottom=139.0),
        word("180", 523.0, 537.0, 128.5, bottom=139.0),
        word("012", 506.0, 520.0, 129.0, bottom=139.0),
        # Tesseract puede omitir el cliente en página 1; BBVA lo repite.
        word("A1234567", 556.0, 598.0, 121.0, page=3, bottom=130.0),
    ]

    result = extract_datos_cuenta_words(words)

    assert result.producto_principal == "Libretón Básico Cuenta Digital"
    assert result.periodo_inicio == "05/12/2023"
    assert result.periodo_fin == "04/01/2024"
    assert result.fecha_corte == "04/01/2024"
    assert result.numero_cuenta == "1234567890"
    assert result.numero_cliente == "A1234567"
    assert result.rfc == "PELA900101ABC"
    assert result.clabe == "012180000123456789"
    assert result.nombre_cliente == "ANA PEREZ LOPEZ"


def test_ocr_split_rows_restore_amounts_and_skip_inserted_page() -> None:
    words = [
        word("REFERENCIA", 328.0, 380.0, 70.0),
        # Movimiento 1: concepto e importes aparecen arriba de las fechas.
        word("SPEI", 110.0, 135.0, 100.0),
        word("ENVIADO", 140.0, 182.0, 100.0),
        word("BANCO", 187.0, 220.0, 100.0),
        word("1,250.50", 390.0, 421.0, 100.0),
        word("750.25", 490.0, 520.0, 100.0),
        word("05/DIC", 20.0, 54.0, 106.0),
        word("O5/DIC", 65.0, 99.0, 106.0),
        word("PRUEBA", 110.0, 150.0, 118.0),
        # Hoja publicitaria intercalada: no debe entrar al concepto.
        word("PUBLICIDAD", 110.0, 180.0, 100.0, page=2),
        word("SIN", 185.0, 205.0, 100.0, page=2),
        word("MOVIMIENTOS", 210.0, 290.0, 100.0, page=2),
        # Movimiento 2: el importe aparece debajo de fecha/concepto y trae
        # sustituciones y basura típicas de Tesseract.
        word("06/DIC", 20.0, 54.0, 100.0, page=3),
        word(". 06/DIC", 58.0, 99.0, 100.0, page=3),
        word("SPEI", 110.0, 135.0, 100.0, page=3),
        word("RECIBIDO", 140.0, 190.0, 100.0, page=3),
        word("5oo.oo<ruido>", 430.0, 460.0, 106.0, page=3),
        word("1,250.25", 490.0, 525.0, 106.0, page=3),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 2

    first, second = movements
    assert first.fecha_operacion == "05/DIC"
    assert first.fecha_liquidacion == "05/DIC"
    assert first.concepto == "SPEI ENVIADO BANCO\nPRUEBA"
    assert first.cargo == pytest.approx(1250.50)
    assert first.abono == 0.0
    assert first.saldo_operacion == pytest.approx(750.25)
    assert first.tipo_operacion == "CARGO"

    assert second.fecha_operacion == "06/DIC"
    assert second.fecha_liquidacion == "06/DIC"
    assert second.concepto == "SPEI RECIBIDO"
    assert second.cargo == 0.0
    assert second.abono == pytest.approx(500.0)
    assert second.saldo_operacion == pytest.approx(1250.25)
    assert second.tipo_operacion == "ABONO"
    assert all("PUBLICIDAD" not in movement.concepto for movement in movements)


def test_digital_movement_row_keeps_historical_extraction() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("07/DIC", 20.0, 54.0, 100.0),
        word("08/DIC", 65.0, 99.0, 100.0),
        word("PAGO", 110.0, 140.0, 100.0),
        word("SERVICIO", 145.0, 200.0, 100.0),
        word("75.90", 390.0, 420.0, 100.0),
        word("924.10", 490.0, 520.0, 100.0),
        word("924.10", 550.0, 590.0, 100.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 1
    assert movements[0].fecha_operacion == "07/DIC"
    assert movements[0].fecha_liquidacion == "08/DIC"
    assert movements[0].concepto == "PAGO SERVICIO"
    assert movements[0].cargo == pytest.approx(75.90)
    assert movements[0].saldo_operacion == pytest.approx(924.10)
    assert movements[0].saldo_liquidacion == pytest.approx(924.10)


def test_ocr_footer_cut_uses_the_top_of_the_whole_visual_line() -> None:
    words = [
        word("inflación", 280.0, 320.0, 765.6),
        word("rendimiento", 95.0, 150.0, 767.2),
        word("GAT", 34.0, 51.0, 768.0),
        word("La", 23.0, 32.0, 768.0),
    ]

    assert remove_bbva_footer(words) == []
