from __future__ import annotations

import pytest

from parsers.bbva.extractors.datos import extract_datos_cuenta_words
from parsers.bbva.extractors.movimientos import (
    extract_movimientos_words,
    normalize_bbva_date,
)
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


@pytest.mark.parametrize(
    ("raw_date", "expected"),
    [
        ("03/AGO", "03/AGO"),
        ("O3/AGO", "03/AGO"),
        ("O06/OCT", "06/OCT"),
        ("27INOV", "27/NOV"),
        ("11/0CT", "11/OCT"),
        ("13IOCT", "13/OCT"),
        ("14JJUL", "14/JUL"),
        ("44/0CT", None),
    ],
)
def test_ocr_date_variants_are_normalized_conservatively(
    raw_date: str,
    expected: str | None,
) -> None:
    assert normalize_bbva_date(raw_date) == expected


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


def test_ocr_perforated_operation_dates_keep_their_movements() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        # Movimiento normal previo: conserva exactamente la ruta histórica.
        word("14/JUN", 20.0, 54.0, 100.0),
        word("15/JUN", 65.0, 99.0, 100.0),
        word("PAGO", 110.0, 140.0, 100.0),
        word("CUENTA", 145.0, 185.0, 100.0),
        word("DE", 190.0, 205.0, 100.0),
        word("TERCERO", 210.0, 260.0, 100.0),
        word("1,450.00", 388.0, 421.0, 100.0),
        word("72,962.11", 486.0, 528.0, 100.0),
        word("67,994.36", 548.0, 590.0, 100.0),
        # El oyuelo elimina día y diagonal; sólo queda el mes.
        word("JUN", 25.0, 50.0, 122.0),
        word("12/JUN", 65.0, 99.0, 122.0),
        word("SUPERCENTER", 110.0, 180.0, 122.0),
        word("RIO", 185.0, 205.0, 122.0),
        word("DE", 210.0, 225.0, 122.0),
        word("LOS", 230.0, 250.0, 122.0),
        word("869.00", 390.0, 421.0, 122.0),
        word("RFC:", 110.0, 135.0, 134.0),
        word("NWM9709244W4", 140.0, 215.0, 134.0),
        word("14:43", 220.0, 250.0, 134.0),
        word("AUT:", 255.0, 278.0, 134.0),
        word("598229", 282.0, 312.0, 134.0),
        word("Referencia", 321.0, 364.0, 134.0),
        word("******6302", 368.0, 420.0, 134.0),
        # El aro puede ser reconocido como una O delante del mes.
        word("OJUN", 20.0, 50.0, 156.0),
        word("29/JUN", 65.0, 99.0, 156.0),
        word("SITH2000013602961", 110.0, 205.0, 156.0),
        word("2,785.50", 388.0, 421.0, 156.0),
        word("31,520.36", 486.0, 528.0, 156.0),
        word("31,520.36", 548.0, 590.0, 156.0),
        word("Referencia", 321.0, 364.0, 168.0),
        word("424502705632070", 368.0, 445.0, 168.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 3

    normal, perforated, perforated_with_ring_noise = movements
    assert normal.fecha_operacion == "14/JUN"
    assert normal.fecha_liquidacion == "15/JUN"
    assert normal.cargo == pytest.approx(1450.00)

    # El día no se inventa: se conserva el mes recuperable y se extrae el resto.
    assert perforated.fecha_operacion == "JUN"
    assert perforated.fecha_liquidacion == "12/JUN"
    assert perforated.concepto == (
        "SUPERCENTER RIO DE LOS\n"
        "RFC: NWM9709244W4 14:43 AUT: 598229"
    )
    assert perforated.cargo == pytest.approx(869.00)
    assert perforated.referencia == "******6302"
    assert perforated.rfc == "NWM9709244W4"
    assert perforated.autorizacion == "598229"
    assert perforated.hora_operacion == "14:43"

    assert perforated_with_ring_noise.fecha_operacion == "JUN"
    assert perforated_with_ring_noise.fecha_liquidacion == "29/JUN"
    assert perforated_with_ring_noise.concepto == "SITH2000013602961"
    assert perforated_with_ring_noise.cargo == pytest.approx(2785.50)
    assert perforated_with_ring_noise.saldo_operacion == pytest.approx(31520.36)
    assert perforated_with_ring_noise.saldo_liquidacion == pytest.approx(31520.36)
    assert perforated_with_ring_noise.referencia == "424502705632070"


def test_ocr_perforation_repairs_shifted_and_split_date_geometry() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("14/JUN", 20.0, 54.0, 96.0),
        word("15/JUN", 65.0, 99.0, 96.0),
        word("PAGO", 110.0, 140.0, 96.0),
        word("100.00", 390.0, 421.0, 96.0),
        # La marca circular desplaza JUN a la banda de liquidación y deja cada
        # parte de la misma fila visual en una línea OCR diferente.
        word("JUN", 54.0, 72.0, 119.5),
        word("12/JUN", 73.0, 107.0, 124.0),
        word("SUPERCENTER", 110.0, 180.0, 129.0),
        word("RIO", 185.0, 205.0, 129.0),
        word("DE", 210.0, 225.0, 129.0),
        word("LOS", 230.0, 250.0, 129.0),
        word("869.00", 390.0, 421.0, 128.5),
        word("Referencia", 321.0, 364.0, 140.0),
        word("******6302", 368.0, 420.0, 140.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 2
    repaired = movements[1]
    assert repaired.fecha_operacion == "JUN"
    assert repaired.fecha_liquidacion == "12/JUN"
    assert repaired.concepto == "SUPERCENTER RIO DE LOS"
    assert repaired.cargo == pytest.approx(869.00)
    assert repaired.referencia == "******6302"


def test_month_fragment_alone_does_not_split_a_normal_movement() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("14/JUN", 20.0, 54.0, 100.0),
        word("15/JUN", 65.0, 99.0, 100.0),
        word("PAGO", 110.0, 140.0, 100.0),
        # Sin fecha completa de liquidación no se activa el fallback.
        word("JUN", 20.0, 50.0, 112.0),
        word("CONTINUACION", 110.0, 180.0, 112.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 1
    assert movements[0].fecha_operacion == "14/JUN"
    assert movements[0].concepto == "PAGO\nCONTINUACION"


def test_ocr_missing_operation_date_uses_liquidation_and_amount_as_start() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("03/AGO", 20.0, 54.0, 100.0),
        word("03/AGO", 65.0, 99.0, 100.0),
        word("PAGO", 110.0, 140.0, 100.0),
        word("TARJETA", 145.0, 195.0, 100.0),
        word("4,000.00", 390.0, 421.0, 100.0),
        # Caso real del oyuelo: la operación es ilegible, pero sobreviven
        # liquidación, concepto, cargo y referencia.
        word("viAGO", 20.0, 54.0, 130.0),
        word("O3/AGO", 65.0, 99.0, 130.0),
        word("PAGO", 110.0, 140.0, 130.0),
        word("CUENTA", 145.0, 190.0, 130.0),
        word("DE", 195.0, 210.0, 130.0),
        word("TERCERO", 215.0, 270.0, 130.0),
        word("10,000.00", 388.0, 421.0, 130.0),
        word("BNET", 110.0, 140.0, 142.0),
        word("2856337333", 145.0, 210.0, 142.0),
        word("pension", 215.0, 260.0, 142.0),
        word("Hannia", 265.0, 305.0, 142.0),
        word("Referencia", 321.0, 364.0, 142.0),
        word("0002838638", 368.0, 420.0, 142.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 2
    damaged = movements[1]
    assert damaged.fecha_operacion == "viAGO"
    assert damaged.fecha_liquidacion == "03/AGO"
    assert damaged.concepto == (
        "PAGO CUENTA DE TERCERO\n"
        "BNET 2856337333 pension Hannia"
    )
    assert damaged.cargo == pytest.approx(10000.00)
    assert damaged.referencia == "0002838638"


def test_ocr_abono_without_balances_is_not_omitted() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("O6/OCT", 20.0, 54.0, 100.0),
        word("O06/OCT", 65.0, 99.0, 100.0),
        word("SPEI", 110.0, 135.0, 100.0),
        word("RECIBIDO", 140.0, 190.0, 100.0),
        word("NAFIN", 195.0, 230.0, 100.0),
        word("8,500.00", 430.0, 461.0, 100.0),
        word("18408682700", 110.0, 180.0, 112.0),
        word("EGRESOS", 185.0, 235.0, 112.0),
        word("SPEI", 240.0, 265.0, 112.0),
        word("SVD", 270.0, 295.0, 112.0),
        word("Referencia", 321.0, 364.0, 112.0),
        word("0109272533", 368.0, 420.0, 112.0),
        word("135", 425.0, 445.0, 112.0),
        word("06/OCT", 20.0, 54.0, 160.0),
        word("06/OCT", 65.0, 99.0, 160.0),
        word("SPEI", 110.0, 135.0, 160.0),
        word("ENVIADO", 140.0, 190.0, 160.0),
        word("BANCOPPEL", 195.0, 260.0, 160.0),
        word("3,750.00", 390.0, 421.0, 160.0),
        word("4,990.45", 490.0, 525.0, 160.0),
        word("4,990.45", 550.0, 590.0, 160.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 2
    received, sent = movements
    assert received.fecha_operacion == "06/OCT"
    assert received.fecha_liquidacion == "06/OCT"
    assert received.concepto.startswith("SPEI RECIBIDO NAFIN")
    assert received.cargo == 0.0
    assert received.abono == pytest.approx(8500.00)
    assert received.saldo_operacion == 0.0
    assert received.saldo_liquidacion == 0.0
    assert sent.cargo == pytest.approx(3750.00)


def test_ocr_consecutive_spei_with_corrupted_dates_are_not_merged() -> None:
    words = [
        word("REFERENCIA", 321.0, 379.0, 70.0),
        word("11/0CT", 20.0, 54.0, 100.0),
        word("13IOCT", 65.0, 99.0, 100.0),
        word("SPEI", 110.0, 135.0, 100.0),
        word("ENVIADO", 140.0, 190.0, 100.0),
        word("AZTECA", 195.0, 240.0, 100.0),
        word("8,000.00", 390.0, 421.0, 100.0),
        word("0109250octubre", 110.0, 200.0, 112.0),
        word("maria", 205.0, 235.0, 112.0),
        word("00004027666120969315", 110.0, 240.0, 124.0),
        word("MBAN01002510130080186046", 110.0, 285.0, 136.0),
        word("magdalena", 110.0, 175.0, 148.0),
        word("alvarez", 180.0, 225.0, 148.0),
        # Día imposible y mes con cero: operación irrecuperable. La liquidación
        # válida y el cargo deben abrir un movimiento nuevo.
        word("44/0CT", 20.0, 54.0, 170.0),
        word("13/OCT", 65.0, 99.0, 170.0),
        word("SPEI", 110.0, 135.0, 170.0),
        word("ENVIADO", 140.0, 190.0, 170.0),
        word("AZTECA", 195.0, 240.0, 170.0),
        word("8,000.00", 390.0, 421.0, 170.0),
        word("0109250noviembre", 110.0, 215.0, 182.0),
        word("Maria", 220.0, 250.0, 182.0),
        word("00004027666120969315", 110.0, 240.0, 194.0),
        word("MBAN01002510130080251923", 110.0, 285.0, 206.0),
        word("magdalena", 110.0, 175.0, 218.0),
        word("alvarez", 180.0, 225.0, 218.0),
        word("11/0CT", 20.0, 54.0, 240.0),
        word("13/OCT", 65.0, 99.0, 240.0),
        word("SPEI", 110.0, 135.0, 240.0),
        word("ENVIADO", 140.0, 190.0, 240.0),
        word("BANAMEX", 195.0, 250.0, 240.0),
        word("6,900.00", 390.0, 421.0, 240.0),
        word("0109250renta", 110.0, 190.0, 252.0),
        word("octubre", 195.0, 235.0, 252.0),
        word("00002180037179005364", 110.0, 240.0, 264.0),
        word("MBAN01002510130080557245", 110.0, 285.0, 276.0),
        word("Jessica", 110.0, 150.0, 288.0),
        word("Pacheco", 155.0, 205.0, 288.0),
        word("Hernandez", 210.0, 275.0, 288.0),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 3
    assert [
        movement.concepto.splitlines()[0]
        for movement in movements
    ] == [
        "SPEI ENVIADO AZTECA",
        "SPEI ENVIADO AZTECA",
        "SPEI ENVIADO BANAMEX",
    ]
    assert [movement.cargo for movement in movements] == pytest.approx(
        [8000.00, 8000.00, 6900.00]
    )
    assert all(
        movement.concepto.count("SPEI ENVIADO") == 1
        for movement in movements
    )


def test_ocr_footer_cut_uses_the_top_of_the_whole_visual_line() -> None:
    words = [
        word("inflación", 280.0, 320.0, 765.6),
        word("rendimiento", 95.0, 150.0, 767.2),
        word("GAT", 34.0, 51.0, 768.0),
        word("La", 23.0, 32.0, 768.0),
    ]

    assert remove_bbva_footer(words) == []
