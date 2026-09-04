from models.movimiento import Movimiento
from models.resumen_financiero import ResumenFinanciero

from parsers.hsbc.utils.robust_recovery import (
    normalize_hsbc_ocr_words,
    repair_resumen_financiero,
    repair_movimientos,
)
from parsers.hsbc.utils.words_footer_filter import (
    filter_hsbc_footer_words,
)


def word(text, x0, x1, top, page=1, confidence=95.0):
    return {
        "text": text,
        "x0": float(x0),
        "x1": float(x1),
        "top": float(top),
        "bottom": float(top + 6.0),
        "page": page,
        "confidence": confidence,
    }


def financial_summary():
    return ResumenFinanciero(
        saldo_promedio=None,
        dias_periodo=None,
        tasa_bruta_anual=None,
        saldo_promedio_gravable=None,
        intereses_a_favor=None,
        isr_retenido=None,
        cheques_pagados=None,
        manejo_cuenta=None,
        cargos_objetados=None,
        abonos_objetados=None,
        saldo_anterior=None,
        depositos_abonos=None,
        retiros_cargos=None,
        saldo_final=None,
        saldo_promedio_minimo_mensual=None,
        saldo_global=None,
    )


def movement(concepto, cargo, abono, saldo):
    return Movimiento(
        fecha_operacion="02/12/2024",
        fecha_liquidacion=None,
        concepto=concepto,
        tipo_operacion=None,
        cargo=cargo,
        abono=abono,
        referencia="13611089\n3793",
        saldo_operacion=saldo,
        saldo_liquidacion=0.0,
    )


def test_normalizes_only_real_etalle_movimientos_header():
    words = [
        word("ETALLE", 50, 80, 470),
        word("MOVIMIENTOS", 85, 140, 470),
        word("ETALLE", 50, 80, 300),
    ]

    normalized = normalize_hsbc_ocr_words(words)

    assert normalized[0]["text"] == "DETALLE"
    assert normalized[2]["text"] == "ETALLE"
    assert words[0]["text"] == "ETALLE"


def test_summary_recovery_uses_semantic_rows_not_fixed_y():
    words = [
        word("RESUMEN", 405, 445, 113, page=2),
        word("DE", 448, 458, 113, page=2),
        word("CUENTAS", 461, 500, 113, page=2),
        word("Depósitos/", 367, 405, 133, page=2),
        word("$", 506, 510, 133, page=2),
        word("69,937.00", 512, 547, 133, page=2),
        word("Retiros/Cargos", 367, 418, 158, page=2),
        word("$", 506, 510, 158, page=2),
        word("74,755.01", 512, 547, 158, page=2),
        word("Saldo", 74, 93, 255, page=4),
        word("Final", 96, 111, 255, page=4),
        word("$13,478.19", 113, 151, 255, page=4),
        word("Saldo", 398, 418, 263, page=4),
        word("Inicial", 421, 442, 263, page=4),
        word("$", 445, 448, 263, page=4),
        word("18,296.20", 473, 506, 263, page=4),
    ]

    resumen = financial_summary()
    repair_resumen_financiero(words, resumen)

    assert resumen.saldo_anterior == 18296.20
    assert resumen.depositos_abonos == 69937.00
    assert resumen.retiros_cargos == 74755.01
    assert resumen.saldo_final == 13478.19
    assert resumen.intereses_a_favor == 0.0
    assert resumen.isr_retenido == 0.0


def test_first_partial_movement_is_repaired_only_if_totals_prove_it():
    resumen = financial_summary()
    resumen.saldo_anterior = 18296.20
    resumen.depositos_abonos = 0.0
    resumen.retiros_cargos = 3090.0

    first = movement(
        "RETIRO CAJERO",
        None,
        None,
        None,
    )
    second = movement(
        "DESPENSA",
        2000.0,
        0.0,
        15206.20,
    )

    movimientos = [first, second]
    repair_movimientos(movimientos, resumen)

    assert first.cargo == 1090.0
    assert first.abono == 0.0
    assert first.saldo_operacion == 17206.20


def test_first_partial_movement_is_not_invented_when_total_disagrees():
    resumen = financial_summary()
    resumen.saldo_anterior = 18296.20
    resumen.depositos_abonos = 0.0
    resumen.retiros_cargos = 9999.0

    first = movement(
        "RETIRO CAJERO",
        None,
        None,
        None,
    )
    second = movement(
        "DESPENSA",
        2000.0,
        0.0,
        15206.20,
    )

    repair_movimientos([first, second], resumen)

    assert first.cargo is None
    assert first.abono is None
    assert first.saldo_operacion is None


def test_footer_filter_removes_footer_and_graphic_noise_not_reference():
    graphic_noise = word(
        "—“L—];;———————e€ci—;j——TTLT;—;—————;—;]",
        113,
        288,
        689,
        page=3,
        confidence=0.0,
    )
    reference = word(
        "49671",
        305,
        331,
        694,
        page=3,
        confidence=96.0,
    )
    movement_word = word(
        "RETIRO",
        63,
        92,
        680,
        page=3,
    )
    footer = [
        word("Emitido", 40, 70, 730, page=3),
        word("por:", 72, 84, 730, page=3),
        word("HSBC", 86, 105, 730, page=3),
        word("Paseo", 40, 65, 740, page=3),
        word("de", 67, 75, 740, page=3),
        word("la", 77, 84, 740, page=3),
        word("Reforma", 86, 120, 740, page=3),
    ]

    filtered = filter_hsbc_footer_words(
        [
            movement_word,
            graphic_noise,
            reference,
            *footer,
        ]
    )
    texts = [item["text"] for item in filtered]

    assert "RETIRO" in texts
    assert "49671" in texts
    assert graphic_noise["text"] not in texts
    assert "Emitido" not in texts
    assert "Paseo" not in texts
