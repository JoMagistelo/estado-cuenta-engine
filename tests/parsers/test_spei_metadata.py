"""Synthetic structures only. No customer statements or identifiers."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from engine import statement_processor
from models.movimiento import Movimiento
from readers.models import DocumentData
from utils.spei_metadata import enrich_missing_spei_fields, extract_spei_metadata
from parsers.bbva.extractors.movimientos import extract_clave_rastreo_from_concepto


def synthetic_clabe(prefix="072"):
    base = prefix + "180" + "12345678901"
    total = sum(int(c) * (3, 7, 1)[i % 3] % 10 for i, c in enumerate(base))
    return base + str((10 - total % 10) % 10)


@pytest.mark.parametrize("label", ["CLAVE DE RASTREO", "CLAVE RASTREO", "CVE RAST", "CVE. RASTREO",
                                    "RASTREO", "CLV RASTREO", "CLAVE DE RASTREO SPEI"])
@pytest.mark.parametrize("separator", [": ", " = ", "\n"])
def test_labelled_tracking_all_banks_and_ocr_line_breaks(label, separator):
    found = extract_spei_metadata("santander", f"SPEI ENVIADO {label}{separator}SYNTHETIC2026001 REF: 0000007")
    assert found.tracking == "SYNTHETIC2026001"
    assert found.reference == "0000007"


@pytest.mark.parametrize("key", ["MBAN20260103000000000001", "BNET20260103000000000001",
                                 "07200P20260103000000000001", "12345678901234567A", "SYNTHETIC8"])
@pytest.mark.parametrize("sent", [True, False])
def test_bbva_positional_key_requires_spei_block_and_checked_account(key, sent):
    heading = "SPEI ENVIADO BANORTE" if sent else "SPEI RECIBIDOBANORTE"
    text = f"{heading}\n0000123MENSAJE SINTETICO\n00{synthetic_clabe()}\n{key}\nPERSONA SINTETICA"
    found = extract_spei_metadata("bbva", text)
    assert found.tracking == key
    assert found.clabe == synthetic_clabe()
    assert found.reference == "0000123"
    assert found.bank == "40072"
    assert found.direction == ("ENVIADO" if sent else "RECIBIDO")
    assert extract_clave_rastreo_from_concepto(text) == key
    assert not extract_spei_metadata("banamex", text).tracking
    assert extract_spei_metadata("bbva", text.replace("SPEI", "TRASPASO")).tracking == ""
    assert extract_spei_metadata("bbva", text.replace(synthetic_clabe(), "7" * 18)).tracking == ""


def test_bbva_already_flattened_export_and_banorte_prefix():
    text = f"SPEI ENVIADO BANORTE 0000123MENSAJE 00{synthetic_clabe()} MBAN20260103000000000001 PERSONA SINTETICA"
    assert extract_spei_metadata("bbva", text).tracking == "MBAN20260103000000000001"
    assert extract_spei_metadata("banorte", "SYNTHETIC001 SPEI RECIBIDO, REF 0007").tracking == "SYNTHETIC001"


@pytest.mark.parametrize("text", [
    "PAGO TARJETA REF: 1234567 CUENTA: 1234567890123456",
    "PAGO CUENTA DE TERCERO\nBNET 1234567890 MENSAJE",
    "SPEI ENVIADO CLAVE DE RASTREO: NO DISPONIBLE",
    "SPEI ENVIADO RASTREO: CLABE BENEFICIARIO: 123456789012345678",
    "SPEI ENVIADO RASTREO: " + "A1" * 21,
])
def test_account_reference_and_placeholders_do_not_become_tracking(text):
    assert not extract_spei_metadata("bbva", text).tracking


def test_conflicting_evidence_never_overwrites_confirmed_metadata_or_money():
    m = Movimiento("03 ENE", None, "CVE RAST: SYNTHETIC001", "CARGO", 50.25, 0,
                   clave_rastreo="CONFIRMED001", referencia="0007", clabe_beneficiario=synthetic_clabe())
    before = asdict(m)
    enrich_missing_spei_fields([m], "bbva")
    assert asdict(m) == before
    found = extract_spei_metadata("nu", "RASTREO: SYNTHETIC001 RASTREO: SYNTHETIC002")
    assert not found.tracking and found.notes


def test_sender_memo_cannot_supply_bank_tracking_or_accounts():
    memo = "RASTREO: MEMOSYNTHETIC001 REF: 9876543"
    found = extract_spei_metadata("santander", "SPEI ENVIADO CONCEPTO: " + memo, memo)
    assert not found.tracking and not found.reference
    text = f"SPEI ENVIADO BANORTE\n0000007{memo}\n00{synthetic_clabe()}\nMBAN20260103000000000001\nPERSONA SINTETICA"
    found = extract_spei_metadata("BBVA", text, memo)
    assert found.tracking == "MBAN20260103000000000001"
    assert found.reference == "0000007"
    assert extract_spei_metadata("BANORTE", "SYNTHETIC001 SPEI RECIBIDO").tracking == "SYNTHETIC001"


@pytest.mark.parametrize("bank", list(statement_processor.PARSER_REGISTRY))
@pytest.mark.parametrize("ocr", [False, True])
def test_shared_recovery_runs_on_every_registered_digital_and_ocr_route(monkeypatch, bank, ocr):
    m = Movimiento("03 ENE", None, "SPEI ENVIADO CVE RAST: SYNTHETIC001", "CARGO", 10.25, 0)
    state = SimpleNamespace(movimientos=[m])
    parser = lambda document: state
    monkeypatch.setitem(statement_processor.PARSER_REGISTRY, bank, parser)
    monkeypatch.setattr(statement_processor, "_resolve_ocr_parser", lambda key: parser)
    doc = DocumentData(raw_text="SYNTHETIC", metadata={"ocr": ocr})
    result, _ = statement_processor._process_once(doc, bank)
    assert len(result.movimientos) == 1 and result.movimientos[0] is m
    assert m.clave_rastreo == "SYNTHETIC001"
    assert (m.fecha_operacion, m.cargo, m.abono, m.concepto) == ("03 ENE", 10.25, 0, "SPEI ENVIADO CVE RAST: SYNTHETIC001")
