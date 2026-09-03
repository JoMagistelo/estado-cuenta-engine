from __future__ import annotations

from typing import Any

from detectors.clabe_detector import detect_by_clabe
from detectors.filename_bank_detector import detect_by_filename
from extractors.clabe_extractor import extract_clabes
from parsers.mercado_pago.extractors.datos import extract_datos_cuenta_words
from parsers.mercado_pago.extractors.movimientos import extract_movimientos_words
from parsers.mercado_pago.extractors.resumen import extract_resumen_financiero_words
from validators.movimiento_validator import validar_movimientos


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


def _mercado_pago_words() -> list[dict[str, Any]]:
    words = [
        _word("ESTADO DE SALDOS Y MOVIMIENTOS", 230, 415, 30),
        _word("Persona De Prueba", 290, 415, 45),
        _word("RFC/CURP: TEST900101HDFABC01", 280, 415, 56),
        _word("Cust id: 1234567890", 335, 415, 67),
        _word("Periodo: Del 1 al 31 de agosto de 2025", 270, 415, 85),
        _word("Entradas: $ 500.00", 195, 270, 124),
        _word("Saldo inicial: $ 1,000.00", 42, 180, 132),
        _word("Saldo final: $ 1,300.00", 250, 405, 132),
        _word("Salidas: $ -200.00", 195, 270, 140),
        _word("Fecha", 42, 63, 205),
        _word("Descripción", 93, 134, 205),
        _word("ID", 213, 221, 205),
        _word("Valor", 318, 336, 205),
        _word("Saldo", 382, 402, 205),
        # Transferencia recibida.
        _word("Transferencia interbancaria recibida", 94, 202, 235),
        _word("Ordenante: ANA PEREZ LOPEZ", 94, 202, 247),
        _word("Banco origen: BBVA MEXICO", 94, 202, 259),
        _word("Cuenta ordenante: 012345678901234567", 94, 202, 271),
        _word("Clave de rastreo: ABC123XYZ", 94, 202, 283),
        _word("01-08-2025", 42, 82, 283),
        _word("MP0001", 214, 265, 283),
        _word("$", 300, 305, 283),
        _word("500.00", 307, 338, 283),
        _word("$", 363, 368, 283),
        _word("1,500.00", 370, 404, 283),
        # Transferencia enviada.
        _word("Transferencia SPEI enviada", 94, 202, 345),
        _word("Beneficiario: LUIS LOPEZ", 94, 202, 357),
        _word("Institución destino: HSBC MEXICO", 94, 202, 369),
        _word("CLABE beneficiaria: 021345678901234567", 94, 202, 381),
        _word("CVE rastreo: SPEI-2025-ABC", 94, 202, 393),
        _word("02-08-2025", 42, 82, 393),
        _word("MP0002", 214, 265, 393),
        _word("$", 298, 303, 393),
        _word("-200.00", 305, 338, 393),
        _word("$", 363, 368, 393),
        _word("1,300.00", 370, 404, 393),
        _word("MP Agregador, S. de R.L. de C.V. (Mercado Pago)", 31, 404, 586),
    ]
    return words


def test_clabe_and_filename_detection_support_new_parsers() -> None:
    cases = (
        ("Contrato Cuenta CLABE 111 123 45678901234 5", "cetes"),
        ("Número de cuenta CLABE: 042123456789012345", "mifel"),
        ("Mercado Pago CLABE interbancaria: 722123456789012345", "mercado_pago"),
    )

    for text, expected_bank in cases:
        assert len(extract_clabes(text)) == 1
        assert detect_by_clabe(text) == expected_bank

    assert (
        extract_clabes(
            "Transferencia SPEI CTA/CLABE: 012123456789012345 "
            "BENEFICIARIO: ANA"
        )
        == []
    )
    assert (
        detect_by_filename("12.2_Débito_Mercado Pago_dic_24.pdf")
        == "mercado_pago"
    )


def test_mercado_pago_parser_reconciles_and_enriches_transfers() -> None:
    words = _mercado_pago_words()
    datos = extract_datos_cuenta_words(words)
    resumen = extract_resumen_financiero_words(words)
    movimientos = extract_movimientos_words(words)

    assert datos.producto_principal == "MERCADO PAGO"
    assert datos.periodo_inicio == "01/08/2025"
    assert datos.periodo_fin == "31/08/2025"
    assert datos.numero_cliente == "1234567890"
    assert datos.nombre_cliente == "Persona De Prueba"

    assert len(movimientos) == 2
    recibido, enviado = movimientos

    assert recibido.abono == 500.0
    assert recibido.referencia == "MP0001"
    assert recibido.beneficiario == "ANA PEREZ LOPEZ"
    assert recibido.cuenta_beneficiario == "012345678901234567"
    assert recibido.clabe_beneficiario == "012345678901234567"
    assert recibido.clave_rastreo == "ABC123XYZ"
    assert recibido.sucursal == "BBVA MEXICO"

    assert enviado.cargo == 200.0
    assert enviado.referencia == "MP0002"
    assert enviado.beneficiario == "LUIS LOPEZ"
    assert enviado.clabe_beneficiario == "021345678901234567"
    assert enviado.clave_rastreo == "SPEI-2025-ABC"
    assert enviado.sucursal == "HSBC MEXICO"

    assert resumen.saldo_anterior == 1000.0
    assert resumen.depositos_abonos == 500.0
    assert resumen.retiros_cargos == 200.0
    assert resumen.saldo_final == 1300.0
    assert all(result.correcto for result in validar_movimientos(movimientos, resumen))
