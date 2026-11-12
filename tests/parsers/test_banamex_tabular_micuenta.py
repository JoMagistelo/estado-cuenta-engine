from copy import deepcopy

from engine.statement_processor import _process_once
from parsers.banamex.beneficiary_enrichment import enrich_banamex_beneficiaries
from parsers.banamex.extractors.movimientos import movement_from_fields
from parsers.banamex.extractors.tabular_cover import TabularCover
from parsers.banamex.extractors.tabular_movements import _tracking
from readers.models import DocumentData
from validators.movimiento_validator import validar_movimientos


def _text(words, page, y, x, text):
    for token in text.split():
        width = len(token) * 4
        words.append(
            {
                "page": page,
                "x0": x,
                "x1": x + width,
                "top": y - 4,
                "bottom": y + 4,
                "doctop": (page - 1) * 790 + y - 4,
                "text": token,
            }
        )
        x += width + 3


def _statement():
    words = []
    for y, x, text in (
        (20, 210, "ESTADO DE CUENTA AL 19 DE DICIEMBRE DE 2025"),
        (32, 205, "CLIENTE: 00000120"),
        (44, 205, "Registro Federal de Contribuyentes AAXX010101001"),
        (142, 70, "ANA PRUEBA FICTICIA"),
        (154, 70, "20 CALLE DE PRUEBA 10"),
        (382, 25, "PRODUCTO/SERVICIO CONTRATO SALDO ANTERIOR SALDO AL 19/DIC/2025"),
        (394, 25, "MiCuenta 00001234567 $105.50 $775.00"),
        (406, 25, "CLABE Interbancaria 002000000000000008"),
        (447, 25, "RESUMEN DEL 22/NO0V/2025 AL 21/DIC/2025"),
        (459, 25, "CONTRATO 00001234567"),
        (471, 25, "Saldo Anterior $105.50"),
        (483, 25, "(+) 1 Depósitos $700.00"),
        (495, 25, "(-) 1 Retiros $30.50"),
        (507, 25, "SALDO AL 19 DE DICIEMBRE DE 2025 $775.00"),
        (530, 25, "Saldo Promedio $454.80"),
        (542, 25, "Días Transcurridos 30"),
        (648, 25, "RESUMEN POR MEDIOS DE ACCESO RETIROS DEPOSITOS"),
        (660, 25, "RETIROS $999.00"),
    ):
        _text(words, 1, y, x, text)
    for page, y, x, text in (
        (2, 108, 60, "SALDO ANTERIOR"),
        (2, 108, 410, "105.50"),
        (2, 120, 14, "25 NOV"),
        (2, 120, 60, "DEPOSITO EN VENTANILLA"),
        (2, 132, 324, "700.00"),
        (2, 144, 60, "DEP EN EFECTIVO"),
        (3, 108, 60, "CAJA 0068 AUT 00000870"),
        (3, 108, 410, "805.50"),
        (3, 120, 14, "25 NOV"),
        (3, 120, 60, "PAGO INTERBANCARIO A STP AL BENEF. ANA PRUEBA"),
        (3, 132, 60, "(DATO NO VERIFICADO) CIA. BENEFICIARIO"),
        (3, 144, 60, "002000000000:000008 CLAVE"),
        (3, 156, 60, "RASTREO 085900000010000009"),
        (3, 168, 60, "REF. 0000225 Transferencia"),
        (3, 180, 60, "CAJA 0071 AUT 00000001 HORA 16:04 SUC 0870"),
        (3, 180, 270, "3050"),
        (3, 180, 410, "775.00"),
    ):
        _text(words, page, y, x, text)
    grid = {"first_center": 108, "pitch": 12, "bottom": 186, "dividers": [55, 250, 320, 395]}
    return words, {2: grid, 3: grid}


def test_micuenta_tabular_reads_cover_and_cross_page_detail():
    words, grids = _statement()
    original = deepcopy(words)
    doc = DocumentData(spatial_words=words, metadata={"ocr": True, "banamex_tabular_pages": grids})
    statement, _ = _process_once(doc, "banamex")
    assert words == original
    account = statement.datos_cuenta
    assert account.periodo_inicio == "22/11/2025"
    assert account.periodo_fin == "21/12/2025"
    assert account.fecha_corte == "19/12/2025"
    assert account.numero_cliente == "00000120"
    assert account.numero_cuenta == "00001234567"
    assert account.clabe == "002000000000000008"
    assert account.nombre_cliente == "ANA PRUEBA FICTICIA"
    assert [
        (m.fecha_operacion, m.cargo, m.abono, m.saldo_operacion) for m in statement.movimientos
    ] == [("25 NOV", 0, 700, 805.50), ("25 NOV", 30.50, 0, 775)]
    assert statement.movimientos[-1].clave_rastreo == "085900000010000009"
    assert statement.movimientos[-1].clabe_beneficiario == "002000000000000008"
    assert statement.movimientos[-1].hora_operacion == "16:04"
    assert all(
        c.correcto for c in validar_movimientos(statement.movimientos, statement.resumen_financiero)
    )


def test_same_cover_without_paper_grid_keeps_legacy_path():
    words, _ = _statement()
    cover = TabularCover.detect([w for w in words if w["page"] == 1])
    assert cover is not None
    statement, _ = _process_once(
        DocumentData(spatial_words=words, metadata={"ocr": True}), "banamex"
    )
    assert not hasattr(statement.resumen_financiero, "deposit_count")


def test_tabular_balance_continuity_detects_same_total_error():
    words, grids = _statement()
    statement, _ = _process_once(
        DocumentData(spatial_words=words, metadata={"ocr": True, "banamex_tabular_pages": grids}),
        "banamex",
    )
    statement.movimientos[0].saldo_operacion = 800.50
    checks = {
        c.nombre: c.correcto
        for c in validar_movimientos(statement.movimientos, statement.resumen_financiero)
    }
    assert checks["Total depósitos / abonos"]
    assert checks["Total retiros / cargos"]
    assert not checks["Continuidad de saldos MiCuenta"]


def test_tracking_uses_printed_format_to_remove_ruling_artifacts():
    assert _tracking("RASTREO\nJ016000000000000000000TEF. B536") == "016000000000000000000TEF"
    assert _tracking("RASTREO IMBANO0123400000000000001") == "MBAN00123400000000000001"
    assert _tracking("RASTREO 1001234567") == "1001234567"


def test_tabular_enrichment_keeps_unverified_digits_out_of_clabe_field():
    movement = movement_from_fields(
        "25 NOV",
        "PAGO RECIBIDO DE BANCO PRUEBA POR ORDEN DE ANA PRUEBA\nCTA ORDENANTE\n002000000000000000",
        0,
        150,
        150,
    )
    movement.cuenta_beneficiario = None
    movement.clabe_beneficiario = None
    enrich_banamex_beneficiaries([movement], require_valid_clabe=True)
    assert movement.cuenta_beneficiario == "002000000000000000"
    assert movement.clabe_beneficiario is None
