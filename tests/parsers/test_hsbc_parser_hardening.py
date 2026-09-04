from __future__ import annotations

from typing import Any

from models.movimiento import Movimiento
from parsers.hsbc.extractors.datos import extract_datos_cuenta_words
from parsers.hsbc.extractors.movimientos import (
    SpeiRow,
    enrich_movements_from_spei,
    extract_day_from_line,
    extract_movimientos_words,
    normalize_spei_date_token,
)
from parsers.hsbc.extractors.resumen import (
    extract_resumen_financiero_words,
)
from parsers.hsbc.utils.words_footer_filter import filter_page_footer


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 8.0,
        "page": page,
    }


def _movement(
    *,
    reference: str,
    concept: str,
    cargo: float = 0.0,
    abono: float = 0.0,
) -> Movimiento:
    return Movimiento(
        fecha_operacion="19/08/2025",
        fecha_liquidacion=None,
        concepto=concept,
        tipo_operacion=None,
        cargo=cargo,
        abono=abono,
        referencia=reference,
        clave_rastreo=None,
        autorizacion=None,
        beneficiario=None,
        cuenta_beneficiario=None,
        clabe_beneficiario=None,
        rfc=None,
        sucursal=None,
        caja=None,
        hora_operacion=None,
        saldo_operacion=0.0,
        saldo_liquidacion=0.0,
        concepto_original=concept,
    )


def _sent_spei(
    key: str,
    amount: float,
    beneficiary: str,
) -> SpeiRow:
    return SpeiRow(
        tipo="enviados",
        page=4,
        lines=[],
        fecha="19/08/2025",
        hora="12:34:56",
        participante="BBVA MEXICO",
        beneficiario=beneficiary,
        cuenta_beneficiaria="000000000000000000",
        concepto="PAGO",
        monto=amount,
        clave_rastreo=key,
        numero_referencia="00000000000000000000",
    )


def test_movement_table_starts_after_cover_noise_and_repairs_first_row() -> None:
    words = [
        _word(
            "Periodo del 01/01/2025 al 31/01/2025",
            350,
            555,
            250,
        ),
        _word("Saldo Inicial del", 370, 450, 280),
        _word("$", 505, 510, 280),
        _word("1,000.00", 515, 558, 280),
        # El 5 de una dirección no debe activar la tabla.
        _word("AV", 35, 43, 130, 2),
        _word("5", 45, 50, 130, 2),
        _word("NORTE", 65, 95, 130, 2),
        _word("RFC:", 40, 65, 260, 2),
        # Tesseract perdió la D inicial de DETALLE.
        _word("ETALLE DE MOVIMIENTOS", 40, 235, 500, 2),
        _word("NOMINA FLEXIBLE HSBC", 240, 370, 500, 2),
        _word("Día", 40, 55, 512, 2),
        _word("Descripción", 65, 130, 512, 2),
        _word("Referencia/Serial", 280, 345, 512, 2),
        _word("Retiro/Cargo", 350, 410, 512, 2),
        _word("Depósito/Abono", 425, 500, 512, 2),
        _word("Saldo", 520, 558, 512, 2),
        # Primer movimiento: OCR omitió importe y saldo.
        _word("01", 45, 53, 525, 2),
        _word("CGO", 68, 87, 525, 2),
        _word("Pago", 90, 115, 525, 2),
        _word("08040002", 285, 330, 525, 2),
        _word("004201", 295, 330, 534, 2),
        # El segundo movimiento y el saldo inicial cierran la ecuación.
        _word("02", 45, 53, 545, 2),
        _word("ABONO NOMINA", 68, 145, 545, 2),
        _word("08040003", 285, 330, 545, 2),
        _word("100", 445, 468, 545, 2),
        _word("950.00", 525, 560, 545, 2),
        _word("123456", 295, 330, 554, 2),
        _word(
            "Emitido por: HSBC México S.A. Grupo Financiero HSBC",
            35,
            430,
            730,
            2,
        ),
    ]

    movements = extract_movimientos_words(words)

    assert len(movements) == 2
    assert movements[0].fecha_operacion == "01/01/2025"
    assert movements[0].referencia == "08040002\n004201"
    assert movements[0].cargo == 150.0
    assert movements[0].abono == 0.0
    assert movements[0].saldo_operacion == 850.0
    assert movements[1].saldo_operacion == 950.0


def test_spei_matching_preserves_references_and_supports_hsb_hsbc() -> None:
    movements = [
        _movement(reference="08040001\n7654321", concept="CGO PAGO", cargo=10),
        _movement(reference="08040002\n004201", concept="CGO PAGO", cargo=20),
        _movement(reference="08040003\n54321", concept="CGO PAGO", cargo=30),
        _movement(reference="08040004\n654321", concept="CGO PAGO", cargo=40),
        _movement(reference="08040005\n111", concept="PAGO 1234500", abono=220),
    ]
    spei_rows = [
        _sent_spei("HSB7654321", 10, "UNO"),
        _sent_spei("HSB00C4201", 20, "DOS"),
        _sent_spei("HSBC054321", 30, "TRES"),
        _sent_spei("HSBC654321", 40, "CUATRO"),
        SpeiRow(
            tipo="recibidos",
            page=4,
            lines=[],
            fecha="19/08/2025",
            hora="13:00:00",
            participante="BANORTE",
            beneficiario="ORDENANTE",
            cuenta_beneficiaria="000000000000000000",
            nombre_ordenante="ORDENANTE",
            cuenta_ordenante="000000000000000000",
            concepto="PAGO",
            monto=220.0,
            clave_rastreo="MBAN01002508190000000000",
            numero_referencia="00000000000001234500",
        ),
    ]
    original_references = [movement.referencia for movement in movements]

    enrich_movements_from_spei(movements, spei_rows)

    assert [movement.referencia for movement in movements] == original_references
    assert [movement.clave_rastreo for movement in movements] == [
        "HSB7654321",
        "HSB00C4201",
        "HSBC054321",
        "HSBC654321",
        "MBAN01002508190000000000",
    ]
    assert all(
        movement.fecha_liquidacion == "19/08/2025"
        for movement in movements
    )
    assert movements[-1].beneficiario == "ORDENANTE"
    assert movements[-1].cuenta_beneficiario == "000000000000000000"
    assert movements[-1].clabe_beneficiario == "000000000000000000"
    assert movements[-1].sucursal == "BANORTE"
    assert movements[0].clabe_beneficiario == "000000000000000000"
    assert movements[0].sucursal == "BBVA MEXICO"


def test_ocr_days_and_dates_are_reconstructed_conservatively() -> None:
    line = [
        _word("12", 47.0, 62.6, 190),
        _word("1", 54.0, 56.2, 190),
        _word("3", 57.8, 61.7, 190),
        _word("CGO", 70, 90, 190),
        _word("08040002", 285, 330, 190),
        _word("100.00", 365, 400, 190),
        _word("900.00", 525, 560, 190),
    ]

    assert extract_day_from_line(line) == 13
    assert normalize_spei_date_token("B0/07/2025") == "30/07/2025"
    assert normalize_spei_date_token("81/07/2026") == "31/07/2026"
    assert normalize_spei_date_token("D9/12/2024") == "09/12/2024"
    assert normalize_spei_date_token("&'z/12/2024") is None


def test_shifted_summary_uses_anchor_rows_instead_of_fixed_heights() -> None:
    words = [
        _word("RESUMEN DE CUENTAS", 405, 500, 225),
        _word("Saldo Inicial del", 370, 450, 250),
        _word("$", 505, 510, 250),
        _word("1,000.00", 515, 558, 250),
        _word("Depósitos/Abonos", 370, 460, 275),
        _word("$", 505, 510, 275),
        _word("500.00", 520, 558, 275),
        _word("Retiros/Cargos", 370, 455, 300),
        _word("$", 505, 510, 300),
        _word("200.00", 520, 558, 300),
        _word("Saldo Final", 370, 435, 325),
        _word("$", 505, 510, 325),
        _word("1,300.00", 515, 558, 325),
        _word("Periodo del 01/01/2025 al 31/01/2025", 350, 558, 345),
        _word("Comisiones Cobradas en el Mes", 350, 495, 365),
        _word("$", 505, 510, 365),
        _word("147.00", 520, 558, 365),
        _word("Saldo Promedio Mínimo Requerido", 350, 495, 385),
        _word("$", 505, 510, 385),
        _word("0.00", 530, 558, 385),
        _word("Saldo Promedio en el Mes", 350, 475, 405),
        _word("$", 505, 510, 405),
        _word("1,125.50", 515, 558, 405),
        _word("Tasa Promedio Nominal", 350, 470, 425),
        _word("0.0000%", 515, 558, 425),
        _word("Pago Interés Nominal en el Mes", 350, 490, 445),
        _word("$", 505, 510, 445),
        _word("0.00", 530, 558, 445),
        _word("ISR Retenido en el Mes", 350, 470, 465),
        _word("$", 505, 510, 465),
        _word("0.00", 530, 558, 465),
    ]

    summary = extract_resumen_financiero_words(words)

    assert summary.saldo_anterior == 1000.0
    assert summary.depositos_abonos == 500.0
    assert summary.retiros_cargos == 200.0
    assert summary.saldo_final == 1300.0
    assert summary.saldo_promedio == 1125.5
    assert summary.saldo_promedio_minimo_mensual == 0.0
    assert summary.tasa_bruta_anual == 0.0
    assert summary.manejo_cuenta == 147.0


def test_average_fallback_does_not_shift_into_minimum_balance() -> None:
    words = [
        _word("RESUMEN DE TU NOMINA FLEXIBLE HSBC", 350, 550, 350),
        _word("Saldo Promedio Mínimo Requerido", 350, 495, 374),
        _word("Saldo P| d 1M del rIO", 350, 485, 384),
        _word("$", 505, 510, 384),
        _word("22,113.10", 515, 560, 384),
        _word("Pago de Interés Nominal en el Año", 350, 495, 412),
        _word("$0.00", 520, 558, 412),
    ]

    summary = extract_resumen_financiero_words(words)

    assert summary.saldo_promedio == 22113.1
    assert summary.saldo_promedio_minimo_mensual is None


def test_identity_block_and_footer_survive_ocr_layout_drift() -> None:
    words = [
        _word("NOMINA FLEXIBLE HSBC", 245, 370, 20),
        _word("ANA", 46, 78, 99),
        _word("PRUEBA", 82, 112, 99),
        _word("DEMO", 116, 142, 99),
        _word("COL", 46, 62, 128),
        _word("NOPALUCAN", 65, 112, 128),
        _word("DE", 115, 125, 128),
        _word("LA", 128, 137, 128),
        _word("GRANJA", 140, 171, 128),
        _word("NÚMERO DE CUENTA", 40, 130, 206),
        _word("1234567890", 45, 100, 217),
        _word("CLABE INTERBANCARIA", 170, 280, 206),
        _word("000000000000000000", 175, 280, 217),
        _word("NÚMERO DE CLIENTE", 40, 135, 226),
        _word("12345678", 45, 90, 250),
        _word("REC", 45, 65, 245),
        _word("XAXX010101000", 45, 120, 255),
        _word("Período del 01/12/2024 al 31/12/2024", 350, 560, 265),
    ]

    data = extract_datos_cuenta_words(words)

    assert data.producto_principal == "Nomina Flexible HSBC"
    assert data.nombre_cliente == "ANA PRUEBA DEMO"
    assert data.numero_cliente == "12345678"
    assert data.rfc == "XAXX010101000"

    page_words = [
        _word("31", 45, 55, 710),
        _word("CGO", 70, 90, 710),
        _word("1,000.00", 365, 405, 710),
        _word("Emitido por:", 35, 100, 730),
        _word("HSBC México", 105, 175, 730),
        _word("S.A.", 180, 205, 730),
        _word("Paseo de la Reforma", 35, 150, 741),
        _word("PAG. 3/8", 520, 565, 741),
    ]

    filtered = filter_page_footer(page_words)

    assert [word["text"] for word in filtered] == [
        "31",
        "CGO",
        "1,000.00",
    ]
