from copy import deepcopy

from parsers.banorte_ocr.extractors.mujer import MujerSummary, _summary_amount, outgoing_trace
from parsers.banorte_ocr.parser import parse_banorte_ocr
from readers.models import DocumentData
from validators.movimiento_validator import validar_movimientos


def _word(words, page, x, y, text):
    words.append(
        {
            "text": text,
            "page": page,
            "x0": x,
            "x1": x + min(150, len(text) * 4),
            "top": y - 3,
            "bottom": y + 3,
            "doctop": (page - 1) * 792 + y - 3,
        }
    )


def _clabe():
    stem = "07218000000123456"
    total = sum(int(digit) * (3, 7, 1)[i % 3] % 10 for i, digit in enumerate(stem))
    return stem + str((-total) % 10)


def _statement():
    words = []
    for x, y, text in (
        (345, 18, "ESTADO DE CUENTA / CTA MUJER BANORTE SALDO PROM"),
        (50, 64, "ANA CUENTA PRUEBA"),
        (50, 74, "CALLE FICTICIA 10"),
        (364, 109, "Periodo Del 01/Marzo/2025 al 31/Marzo/2025"),
        (364, 121, "Fecha de corte 31/Marzo/2025"),
        (50, 140, "NO. DE CLIENTE"),
        (102, 140, "00123456"),
        (50, 149, "RFC"),
        (68, 149, "XAXX010101000"),
        (50, 205, "RESUMEN INTEGRAL"),
        (50, 225, "CTA MUJER BANORTE SALDO PROM"),
        (217, 225, "0000123456"),
        (284, 225, _clabe()),
        (50, 235, "INVERSION MUJER BANORTE"),
        (217, 235, "0000123457"),
        (50, 285, "Saldo inicial del periodo"),
        (50, 295, "+ Total de depósitos"),
        (50, 305, "- Total de retiros"),
        (50, 356, "Saldo actual"),
        (50, 410, "En el Periodo 01 Mar al 31 Mar"),
        (50, 420, "Días que comprende el periodo"),
        (246, 420, "31"),
    ):
        _word(words, 1, x, y, text)
    for y, value in (
        (285, "$100.00"),
        (295, "$5.00"),
        (305, "$40.00"),
        (356, "$65.00"),
        (410, "$90.30"),
    ):
        _word(words, 1, 235, y, value)
        _word(words, 1, 340, y, "$0.00")
    for x, y, text in (
        (54, 87, "FECHA"),
        (86, 87, "DESCRIPCION / ESTABLECIMIENTO"),
        (351, 87, "MONTO DEL DEPOSITO"),
        (441, 87, "MONTO DEL RETIRO"),
        (531, 87, "SALDO"),
        (54, 103, "28-FEB-25"),
        (88, 103, "SALDO ANTERIOR"),
        (515, 103, "100.00"),
        (54, 120, "01-MAR-25"),
        (88, 120, "COMPRA ORDEN DE PAGO SPEI 0001234 =REFERENCIA CTA/CLABE: " + _clabe()),
        (439, 120, "40.00"),
        (515, 120, "60.00"),
        (88, 128, "CVE.RASTR: 38432001202503010000000001 RFC: ND"),
        (54, 140, "01-MAR-25"),
        (88, 140, "DEPOSITO EN EFECTIVO"),
        (360, 140, "5.00"),
        (515, 140, "65.00"),
        (354, 191, "800"),
    ):
        _word(words, 2, x, y, text)
    table = {"width": 612, "top": 98, "bottom": 164, "rows": [103, 120, 140]}
    return words, {
        "ocr": True,
        "banorte_mujer_cover_width": 612,
        "banorte_mujer_tables": {2: table},
    }


def test_mujer_scan_reads_main_account_and_validates_each_balance():
    words, metadata = _statement()
    original = deepcopy(words)
    state = parse_banorte_ocr(DocumentData(spatial_words=words, metadata=metadata))
    assert words == original
    assert state.datos_cuenta.numero_cuenta == "0000123456"
    assert state.datos_cuenta.clabe == _clabe()
    assert state.datos_cuenta.nombre_cliente == "ANA CUENTA PRUEBA"
    assert state.datos_cuenta.fecha_corte == "31/Marzo/2025"
    assert state.resumen_financiero.depositos_abonos == 5
    assert state.resumen_financiero.retiros_cargos == 40
    assert [
        (m.fecha_operacion, m.cargo, m.abono, m.saldo_operacion) for m in state.movimientos
    ] == [
        ("01-MAR-25", 40, 0, 60),
        ("01-MAR-25", 0, 5, 65),
    ]
    assert state.movimientos[0].clave_rastreo == "38432P01202503010000000001"
    assert state.movimientos[0].clabe_beneficiario == _clabe()
    assert all(
        check.correcto for check in validar_movimientos(state.movimientos, state.resumen_financiero)
    )


def test_cover_alone_keeps_legacy_ocr_and_unrelated_layout_ignores_mujer_metadata():
    words, metadata = _statement()
    state = parse_banorte_ocr(DocumentData(spatial_words=words, metadata={"ocr": True}))
    assert not isinstance(state.resumen_financiero, MujerSummary)
    legacy = [
        {**w, "text": w["text"].replace("CTA MUJER BANORTE SALDO PROM", "SUMANOMINA")}
        for w in words
    ]
    without = parse_banorte_ocr(DocumentData(spatial_words=legacy, metadata={"ocr": True}))
    with_metadata = parse_banorte_ocr(DocumentData(spatial_words=legacy, metadata=metadata))
    assert with_metadata == without


def test_trace_repair_requires_banorte_format_and_a_printed_date():
    assert outgoing_trace("RASTREO 38432001202503010000000001") == "38432P01202503010000000001"
    assert outgoing_trace("RASTREO 38432001202513010000000001") is None


def test_cover_does_not_merge_two_complete_amounts():
    words = []
    _word(words, 1, 50, 305, "TOTAL DE RETIROS")
    _word(words, 1, 220, 305, "5.00")
    _word(words, 1, 252, 305, "40.00")
    assert _summary_amount([words], 612, "TOTALDERETIROS") is None
