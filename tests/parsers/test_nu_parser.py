from __future__ import annotations

from typing import Any

from parsers.nu import parse_nu
from parsers.nu.extractors.movimientos import extract_movimientos_words
from parsers.nu_ocr import parse_nu_ocr
from readers.models.document_data import DocumentData


def _word(text: str, x0: float, top: float, page: int = 1) -> dict[str, Any]:
    width = max(8.0, len(text) * 4.5)
    return {
        "text": text,
        "x0": x0,
        "x1": x0 + width,
        "top": top,
        "bottom": top + 10.0,
        "doctop": (page - 1) * 850.0 + top,
        "page": page,
    }


def _line(text: str, top: float, page: int = 1, x0: float = 48.0) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    cursor = x0
    for token in text.split():
        word = _word(token, cursor, top, page)
        words.append(word)
        cursor = word["x1"] + 3.0
    return words


def _nu_words() -> list[dict[str, Any]]:
    rows = [
        ("Persona De Prueba", 45, 1),
        ("Cuenta Nu: 00012345678", 60, 1),
        ("RFC: PEPA900101ABC", 75, 1),
        ("CLABE: 638180000000000000", 90, 1),
        ("Periodo: del 01 al 30 sep 2025", 105, 1),
        ("Saldo inicial $100.00", 353, 1),
        ("Depósitos +$900.00", 381, 1),
        ("Gastos -$650.00", 409, 1),
        ("Comisiones cobradas por Nu $0.00", 437, 1),
        ("Saldo al generar este estado de cuenta $350.00", 465, 1),
        ("30 SEP 2025 Persona Beneficiaria Renta -$650.00", 150, 2),
        ("Transferencia SPEI, Hora: 13:09:O5, Enviado a BANCO PRUEBA. Al", 175, 2),
        ("cliente Persona Beneficiaria (Dato no verificado por esta", 195, 2),
        ("institución), por concepto Renta. A la cuenta", 215, 2),
        # El detalle continúa en la página siguiente antes del próximo movimiento.
        ("638180000000000001 clabe, Clave de rastreo NU38DEMO123,", 105, 3),
        ("Clave de referencia 300925", 125, 3),
        ("30 SEP 2025 Persona Origen Transferencia interbancaria +$900.00", 185, 3),
        ("Depósito SPEI, Hora: 12:00:01, Recibido de BANCO ORIGEN. Del", 210, 3),
        ("cliente Persona Origen (Dato no verificado por esta institución),", 230, 3),
        ("por concepto Transferencia interbancaria. De la cuenta", 250, 3),
        ("002180000000000001 clabe, Clave de rastreo 1234567890ABC,", 270, 3),
        ("Clave de referencia 300925", 290, 3),
        ("Con estos movimientos, tu saldo promedio del periodo fue de $200.00", 500, 3),
        ("Dinero generado antes de impuestos (Interés Bruto Anual de 0%) $0.00", 120, 4),
        ("Impuestos sobre el dinero generado (ISR de 0%) $0.00", 145, 4),
    ]
    result: list[dict[str, Any]] = []
    for text, top, page in rows:
        result.extend(_line(text, top, page))
    return result


def test_nu_parser_extracts_account_summary_movements_and_spei_metadata() -> None:
    words = _nu_words()
    state = parse_nu(DocumentData(spatial_words=words))

    assert state.datos_cuenta.producto_principal == "Cuenta Nu"
    assert state.datos_cuenta.periodo_inicio == "01/09/2025"
    assert state.datos_cuenta.periodo_fin == "30/09/2025"
    assert state.datos_cuenta.fecha_corte == "30/09/2025"
    assert state.datos_cuenta.numero_cuenta == "00012345678"
    assert state.datos_cuenta.numero_cliente is None
    assert state.datos_cuenta.clabe == "638180000000000000"
    assert state.datos_cuenta.nombre_cliente == "Persona De Prueba"
    assert state.datos_cuenta.rfc == "PEPA900101ABC"

    assert state.resumen_financiero.saldo_anterior == 100.0
    assert state.resumen_financiero.depositos_abonos == 900.0
    assert state.resumen_financiero.retiros_cargos == 650.0
    assert state.resumen_financiero.saldo_final == 350.0
    assert state.resumen_financiero.saldo_promedio == 200.0
    assert state.resumen_financiero.dias_periodo == 30
    assert state.resumen_financiero.manejo_cuenta == 0.0

    assert len(state.movimientos) == 2
    enviado, recibido = state.movimientos

    assert enviado.concepto == "Renta"
    assert enviado.concepto_original.startswith("Persona Beneficiaria Renta Transferencia SPEI")
    assert enviado.tipo_operacion == "TRANSFERENCIA SPEI ENVIADA"
    assert enviado.cargo == 650.0
    assert enviado.abono == 0.0
    assert enviado.beneficiario == "Persona Beneficiaria"
    assert enviado.cuenta_beneficiario == "638180000000000001"
    assert enviado.clabe_beneficiario == "638180000000000001"
    assert enviado.clave_rastreo == "NU38DEMO123"
    assert enviado.referencia == "300925"
    assert enviado.hora_operacion == "13:09:05"
    assert enviado.sucursal == "BANCO PRUEBA"

    assert recibido.tipo_operacion == "TRANSFERENCIA SPEI RECIBIDA"
    assert recibido.abono == 900.0
    assert recibido.beneficiario == "Persona Origen"
    assert recibido.cuenta_beneficiario == "002180000000000001"
    assert recibido.clabe_beneficiario == "002180000000000001"
    assert recibido.clave_rastreo == "1234567890ABC"
    assert recibido.referencia == "300925"
    assert recibido.hora_operacion == "12:00:01"
    assert recibido.sucursal == "BANCO ORIGEN"

    assert state.otros_productos.contrato == "N/A"
    assert state.otros_productos.producto == "N/A"
    assert state.otros_productos.total_comisiones == "N/A"


def test_nu_ocr_route_reuses_same_semantic_parser() -> None:
    document = DocumentData(spatial_words=_nu_words())
    assert parse_nu_ocr(document) == parse_nu(document)


def test_nu_movement_parser_keeps_cross_page_spei_detail() -> None:
    movimientos = extract_movimientos_words(_nu_words())
    assert movimientos[0].clabe_beneficiario == "638180000000000001"
    assert movimientos[0].clave_rastreo == "NU38DEMO123"
