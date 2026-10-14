"""Contrato Santander: datos ficticios, geometría variable y readers reales."""

from __future__ import annotations

import copy
from dataclasses import asdict

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from detectors.bank_detector import identify_bank_key
from engine.statement_processor import process_single_statement
from mappers.estado_cuenta_tables import estado_cuenta_to_tables
from models.processing_result import ProcessingResult
from parsers.santander import parse_santander
from parsers.santander import layouts
from parsers.santander.extractors.movimientos import enrich_movement_metadata_from_concepto
from models.movimiento import Movimiento
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from validators.movimiento_validator import validar_movimientos


def line(text: str, y: float, page: int = 1, x: float = 110) -> list[dict]:
    words = []
    for token in text.split():
        width = len(token) * 3.2
        words.append(
            {"text": token, "x0": x, "x1": x + width, "top": y, "bottom": y + 8, "page": page}
        )
        x += width + 2
    return words


def header(y: float = 165, page: int = 2, *, aliases: bool = False) -> list[dict]:
    labels = (
        ("Fecha", "Referencia", "Concepto", "Abonos", "Cargos", "Saldo")
        if aliases
        else ("FECHA", "FOLIO", "DESCRIPCION", "DEPOSITO", "RETIRO", "SALDO")
    )
    return sum(
        (line(label, y, page, x) for label, x in zip(labels, (38, 81, 115, 374, 446, 523))), []
    )


def row(
    day: str,
    text: str,
    y: float,
    *,
    page: int = 2,
    folio: str = "0000001",
    cargo: str | None = None,
    abono: str | None = None,
    saldo: str | None = None,
    fused: bool = False,
) -> list[dict]:
    words = (
        line(day + folio, y, page, 28)
        if fused
        else line(day, y, page, 28) + line(folio, y, page, 78)
    )
    words += line(text, y, page, 110)
    for value, x in ((cargo, 468), (abono, 395), (saldo, 545)):
        if value is not None:
            words += line(value, y, page, x)
    return words


def statement_words() -> list[dict]:
    words = (
        line("Banco Santander Mexico", 20, x=30)
        + line("PERSONA PRUEBA", 60, x=40)
        + line("CODIGO DE CLIENTE NO.90000001", 60, x=356)
        + line("R.F.C. XAXX010101000", 76, x=356)
        + line("PERIODO 16-DIC-2025 AL 15-ENE-2026", 100, x=356)
        + line("CORTE AL 15-ENE-2026", 112, x=356)
        + line("Resumen informativo.", 140, x=50)
        + line("PRODUCTO", 160, x=70)
        + line("NO. DE CUENTA", 160, x=172)
        + line("INTERESES BRUTOS", 160, x=244)
        + line("ISR RETENIDO (0.90%)", 160, x=322)
        + line("INTERESES NETOS", 160, x=422)
        + line("COMISIONES COBRADAS", 160, x=495)
        + line("SUPER NOMINA", 174, x=70)
        + line("56-90000001-1", 174, x=172)
        + line("1.00", 174, x=268)
        + line("0.10", 174, x=353)
        + line("0.90", 174, x=447)
        + line("2.00", 174, x=528)
        + line("Cuenta de cheques.", 205, x=30)
        + line("SUPER NOMINA", 220, x=55)
        + line("56-90000001-1", 220, x=229)
        + line("CUENTA CLABE: 014180000000000001", 220, x=328)
    )
    for y, left_label, left_value, right_label, right_value in (
        (240, "Saldo promedio", "110.50", "Saldo inicial", "100.00"),
        (253, "Tasa bruta de interes anual", "0.1250%", "+ Depositos", "50.00"),
        (266, "Dias del periodo", "31", "- Retiros", "40.00"),
        (279, "Saldo promedio minimo", "3,000.00", "= Saldo final", "110.00"),
    ):
        words += line(left_label, y, x=55) + line(left_value, y, x=258)
        words += line(right_label, y, x=307) + line(right_value, y, x=480)
    words += (
        line("Grafico cuenta de cheques.", 310, x=392)
        + line("Saldo inicial $999,999.00", 324, x=392)
        + line("Pagina 1 de 2.", 768, x=38)
        + line("Banco Santander Mexico", 20, 2, 30)
        + header()
        + row(
            "20-DIC-2025",
            "ABONO TRANSFERENCIA SPEI HORA 09:10:11",
            185,
            abono="50.00",
            saldo="150.00",
        )
        + line("RECIBIDO DE BANCO PRUEBA", 197, 2)
        + line("DE LA CUENTA 012180000000000001", 209, 2)
        + line("DEL CLIENTE PERSONA EJEMPLO", 221, 2)
        + line("CLAVE DE RASTREO TEST-IN-001", 233, 2)
        + line("REF 0001234", 245, 2)
        + line("CONCEPTO pago de comida", 257, 2)
        + line("RFC XEXX010101000", 269, 2)
        + row(
            "03-ENE-2026",
            "PAGO TRANSFERENCIA SPEI_HORA 10:20:30",
            300,
            cargo="25.00",
            saldo="125.00",
            fused=True,
            folio="0000002",
        )
        + line("ENVIADO A BANCO DESTINO", 312, 2)
        + line("A LA CUENTA 1234567890", 324, 2)
        + line("AL CLIENTE PERSONA DESTINO ( 1 )", 336, 2)
        + line("( 1 ) DATO NO VERIFICADO POR ESTA INSTITUCION", 348, 2)
        + line("CLAVE DE RASTREO TEST-OUT-002", 360, 2)
        + line("REF 0005678", 372, 2)
        + line("CONCEPTO compra", 384, 2)
        + row(
            "15-ENE-2026",
            "RETIRO EFEC SIN TARJETA EN ATM",
            410,
            cargo="15.00",
            saldo="110.00",
            folio="0000000",
        )
        + line("TOTAL", 435, 2)
        + line("50.00", 435, 2, 395)
        + line("40.00", 435, 2, 468)
        + line("SALDO FINAL 110.00", 450, 2)
        + row("15-ENE-2026", "PUBLICIDAD", 470, cargo="999.00", saldo="0.00")
    )
    return words


def test_account_summary_movements_metadata_and_export_contract():
    words = statement_words()
    before = copy.deepcopy(words)
    state = parse_santander(DocumentData(spatial_words=words))
    assert asdict(state.datos_cuenta) == {
        "producto_principal": "SUPER NOMINA",
        "periodo_inicio": "16/12/2025",
        "periodo_fin": "15/01/2026",
        "fecha_corte": "15/01/2026",
        "numero_cuenta": "56-90000001-1",
        "numero_cliente": "90000001",
        "clabe": "014180000000000001",
        "nombre_cliente": "PERSONA PRUEBA",
        "rfc": "XAXX010101000",
    }
    summary = state.resumen_financiero
    assert (
        summary.saldo_anterior,
        summary.depositos_abonos,
        summary.retiros_cargos,
        summary.saldo_final,
    ) == (100, 50, 40, 110)
    assert summary.saldo_promedio == 110.50
    assert summary.saldo_promedio_minimo_mensual == 3000
    assert summary.tasa_bruta_anual == 0.125
    assert summary.dias_periodo == 31
    assert (summary.intereses_a_favor, summary.isr_retenido, summary.manejo_cuenta) == (1, 0.1, 2)
    assert len(state.movimientos) == 3
    incoming, outgoing, atm = state.movimientos
    assert incoming.fecha_operacion == "20/12/2025"
    assert incoming.beneficiario == "PERSONA EJEMPLO"
    assert incoming.cuenta_beneficiario == incoming.clabe_beneficiario == "012180000000000001"
    assert incoming.sucursal == "BANCO PRUEBA"
    assert incoming.rfc == "XEXX010101000"
    assert incoming.referencia == "0001234"
    assert incoming.clave_rastreo == "TEST-IN-001"
    assert incoming.hora_operacion == "09:10:11"
    assert incoming.concepto_original == "pago de comida"
    assert "RFC XEXX010101000" in incoming.concepto
    assert outgoing.fecha_operacion == "03/01/2026"
    assert outgoing.beneficiario == "PERSONA DESTINO"
    assert outgoing.cuenta_beneficiario == "1234567890"
    assert outgoing.clabe_beneficiario is None
    assert outgoing.hora_operacion == "10:20:30"
    assert outgoing.referencia == "0005678"
    assert outgoing.concepto_original == "compra"
    assert "DATO NO VERIFICADO" in outgoing.concepto
    assert atm.saldo_operacion == 110
    assert atm.beneficiario is None
    assert all(v.correcto for v in validar_movimientos(state.movimientos, summary))
    assert state.otros_productos.producto == "N/A"
    assert words == before
    tables = estado_cuenta_to_tables(
        [
            ProcessingResult(
                file_name="prueba.pdf",
                bank_key="santander",
                estado_cuenta=state,
                processing_method="Digital",
                raw_text="",
                normalized_text="",
            )
        ]
    )
    assert len(tables["Movimientos"]) == 3


@pytest.mark.parametrize("scale,offset", [(0.5, 0), (1, 25), (2, 10)])
def test_scaled_shifted_unordered_words_do_not_change_output(scale, offset):
    words = statement_words()
    expected = parse_santander(DocumentData(spatial_words=words))
    for word in words:
        for key in ("x0", "x1", "top", "bottom"):
            word[key] = word[key] * scale + offset
    assert parse_santander(DocumentData(spatial_words=words[::-1])) == expected


def test_column_aliases_and_swapped_deposit_withdrawal_are_geometric():
    words = header(165, 1, aliases=True)
    words += row(
        "01/08/2026", "ABONO en columna cargo", 185, page=1, cargo="100.00", saldo="100.00"
    )
    words += row("02/08/2026", "PAGO en columna abono", 200, page=1, abono="20.00", saldo="120.00")
    state = parse_santander(DocumentData(spatial_words=words))
    assert state.movimientos[0].cargo == 100
    assert state.movimientos[1].abono == 20
    for w in words:
        if 370 <= w["x0"] < 440:
            w["x0"] += 72
            w["x1"] += 72
        elif 440 <= w["x0"] < 510:
            w["x0"] -= 72
            w["x1"] -= 72
    assert parse_santander(DocumentData(spatial_words=words)) == state


def test_spei_continues_after_page_header_and_multiline_memo_keeps_user_labels():
    words = (
        header(165, 1)
        + row("01-AGO-2026", "PAGO TRANSFERENCIA SPEI", 185, page=1, cargo="20.00", saldo="80.00")
        + line("ENVIADO A BANCO PRUEBA", 197)
        + line("A LA CUENTA 012180000000000001", 209)
        + line("AL CLIENTE PERSONA", 221)
        + line("APELLIDO (1)", 233)
        + line("CLAVE DE RASTREO", 245)
        + line("Pagina 1 de 2.", 768, x=38)
        + line("Banco Santander Mexico", 20, 2, 30)
        + line("PERSONA PRUEBA CODIGO DE CLIENTE NO.90000001", 130, 2, 30)
        + header()
        + line("TEST-CROSS-003", 185, 2)
        + line("REF 0012345", 197, 2)
        + line("CONCEPTO comida", 209, 2)
        + line("REF: mensaje escrito por usuario", 221, 2)
        + line("para manana", 233, 2)
        + line("RFC XAXX010101000", 245, 2)
        + row("02-AG0-2026", "ABONO", 270, abono="5.00", saldo="85.00")
    )
    movements = parse_santander(DocumentData(spatial_words=words)).movimientos
    assert len(movements) == 2
    assert movements[0].beneficiario == "PERSONA APELLIDO"
    assert movements[0].clave_rastreo == "TEST-CROSS-003"
    assert movements[0].referencia == "0012345"
    assert movements[0].concepto_original == "comida REF: mensaje escrito por usuario para manana"
    assert "CODIGO" not in movements[0].concepto
    assert "Pagina" not in movements[0].concepto
    assert movements[1].fecha_operacion == "02/08/2026"


def test_quick_transfer_full_name_and_inline_ref_rfc():
    words = (
        header(165, 1)
        + row(
            "01-AGO-2026",
            "PAGO TRANSF RAPIDA SPEI TRANSFERENCIA A PERSONA RFC",
            185,
            page=1,
            cargo="20.00",
            saldo="80.00",
        )
        + line("XAXX010101000 IVA 0.0 REF 0000456", 197)
        + row(
            "02-AGO-2026",
            "CARGO TRANSF RAPIDA SANTANDER Transferencia a Persona",
            220,
            page=1,
            cargo="10.00",
            saldo="70.00",
        )
        + line("Segundo Apellido", 232)
    )
    a, b = parse_santander(DocumentData(spatial_words=words)).movimientos
    assert (a.beneficiario, a.rfc, a.referencia) == ("PERSONA", "XAXX010101000", "0000456")
    assert a.concepto_original is None
    assert b.beneficiario == "Persona Segundo Apellido"
    assert b.sucursal == "SANTANDER"
    assert b.concepto_original is None


def test_partial_rows_invalid_dates_and_missing_totals_are_not_invented():
    words = (
        header(165, 1)
        + row("01-AGO-2026", "FECHA SIN IMPORTE", 185, page=1, saldo="100.00")
        + row("31-FEB-2026", "FECHA INVALIDA", 200, page=1, cargo="20.00", saldo="80.00")
        + line("CONCEPTO memo sin fecha", 220)
        + line("10.00", 220, x=395)
        + line("90.00", 220, x=545)
    )
    state = parse_santander(DocumentData(spatial_words=words))
    assert len(state.movimientos) == 3
    assert (state.movimientos[0].cargo, state.movimientos[0].abono) == (0, 0)
    assert state.movimientos[0].tipo_operacion == "No identificado"
    assert state.movimientos[1].fecha_operacion == ""
    assert state.movimientos[2].fecha_operacion == ""
    assert state.movimientos[2].abono == 10
    assert state.resumen_financiero.depositos_abonos is None
    assert state.resumen_financiero.retiros_cargos is None
    assert state.resumen_financiero.saldo_final is None


def test_split_currency_signed_amounts_and_zero_balance():
    words = header(165, 1) + row(
        "01-AGO-2026", "DEVOLUCION", 185, page=1, cargo="$ -20.00", saldo="0.00"
    )
    movement = parse_santander(DocumentData(spatial_words=words)).movimientos[0]
    assert movement.cargo == -20
    assert movement.abono == 0
    assert movement.saldo_operacion == 0


@pytest.mark.parametrize("reader", ["pdfplumber", "paddleocr", "tesseract"])
def test_engine_registry_and_direction_for_all_reader_paths(reader):
    document = DocumentData(
        raw_text="Santander Cuenta CLABE: 014180000000000001",
        spatial_words=statement_words(),
        metadata={"reader": reader, "ocr": reader != "pdfplumber"},
    )
    assert identify_bank_key(document.raw_text, "prueba.pdf") == "santander"
    state, canonical = process_single_statement(document, "santander")
    assert canonical is document
    assert [m.tipo_operacion for m in state.movimientos] == ["ABONO", "CARGO", "CARGO"]


def _write_digital_pdf(path, words):
    """PDF digital sintético: objetos PDF reales, sin depender de reportlab."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    for number in sorted({w["page"] for w in words}):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        commands = []
        for word in words:
            if word["page"] != number:
                continue
            escaped = word["text"].replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(
                f"BT /F1 4 Tf 1 0 0 1 {word['x0']} {792 - word['top'] - 8} Tm ({escaped} ) Tj ET"
            )
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)


def test_real_digital_readers_and_ocr_pdf_roundtrip(tmp_path):
    words = statement_words()
    digital_pdf = tmp_path / "santander_digital_sintetico.pdf"
    _write_digital_pdf(digital_pdf, words)
    digital = ReaderManager.read(digital_pdf)
    digital_state = parse_santander(digital)
    expected = parse_santander(DocumentData(spatial_words=words))
    assert digital_state == expected
    scan_pdf = tmp_path / "santander_scan_sintetico.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with scan_pdf.open("wb") as handle:
        writer.write(handle)
    canonical = ReaderManager.project_ocr_document(
        scan_pdf, DocumentData(spatial_words=words), engine="paddleocr"
    )
    assert canonical.metadata["ocr_text_layer_verified"] is True
    assert parse_santander(canonical) == expected


def test_concatenated_metadata_keeps_memo_labels_and_por_orden_de_name():
    movement = Movimiento(
        "01/08/2026",
        None,
        "PAGO RECIBIDO DE BANCO PRUEBA POR ORDEN DE PERSONA SEGUNDO APELLIDO "
        "REF 0000123 CTA ORDENANTE 1234567890 RASTREO TEST-LEGACY CAJA 4 "
        "CONCEPTO compra REF: cena RFC: pendiente",
        "ABONO",
        0,
        10,
    )
    result = enrich_movement_metadata_from_concepto(movement)
    assert result.beneficiario == "PERSONA SEGUNDO APELLIDO"
    assert result.cuenta_beneficiario == "1234567890"
    assert result.referencia == "0000123"
    assert result.clave_rastreo == "TEST-LEGACY"
    assert result.caja == "4"
    assert result.concepto_original == "compra REF: cena RFC: pendiente"
    assert result.rfc is None


def test_other_account_table_does_not_mix_movements_or_summary():
    words = statement_words()
    words += (
        line("Cuenta de cheques.", 500, 2, 30)
        + line("OTRO PRODUCTO 56-90000002-2", 515, 2, 30)
        + header(530, 2)
        + row("15-ENE-2026", "NO PERTENECE A CUENTA PRINCIPAL", 550, cargo="999.00", saldo="999.00")
        + line("TOTAL", 570, 2)
    )
    assert parse_santander(DocumentData(spatial_words=words)) == parse_santander(
        DocumentData(spatial_words=statement_words())
    )


def test_new_layout_profile_can_be_registered_without_changing_extractors(monkeypatch):
    profile = layouts.SantanderLayout(
        "variante_sintetica",
        date_labels=("OPERACION",),
        description_labels=("DETALLE",),
        deposit_labels=("ENTRADAS",),
        withdrawal_labels=("SALIDAS",),
    )
    monkeypatch.setattr(layouts, "LAYOUTS", (*layouts.LAYOUTS, profile))
    words = (
        line("OPERACION", 165, x=38)
        + line("FOLIO", 165, x=81)
        + line("DETALLE", 165, x=115)
        + line("ENTRADAS", 165, x=374)
        + line("SALIDAS", 165, x=446)
        + line("SALDO", 165, x=523)
        + row("01-AGO-2026", "DEPOSITO", 185, page=1, abono="10.00", saldo="110.00")
    )
    state = parse_santander(DocumentData(spatial_words=words))
    assert len(state.movimientos) == 1
    assert state.movimientos[0].abono == 10


def test_repeated_zero_folio_atm_rows_are_all_kept():
    words = header(165, 1)
    for y, balance in ((185, "90.00"), (200, "80.00")):
        words += row(
            "01-AGO-2026", "RETIRO ATM", y, page=1, cargo="10.00", saldo=balance, folio="0000000"
        )
    movements = parse_santander(DocumentData(spatial_words=words)).movimientos
    assert len(movements) == 2
    assert sum(m.cargo for m in movements) == 20
