"""Replay opt-in de muestras autorizadas; no incluye documentos particulares."""

from __future__ import annotations

import copy
import json
import os
import re
from decimal import Decimal
from pathlib import Path

import pytest

from parsers.santander import parse_santander
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from validators.movimiento_validator import validar_movimientos

pytestmark = pytest.mark.integration


def test_local_santander_samples_reconcile_and_keep_reader_data():
    directory = os.environ.get("SANTANDER_SAMPLE_DIR")
    if not directory:
        pytest.skip("Configure SANTANDER_SAMPLE_DIR con PDFs y JSON autorizados.")
    root = Path(directory)
    files = sorted(root.glob("*__paddleocr_words.json"))
    assert files, "No hay JSON de words PaddleOCR en SANTANDER_SAMPLE_DIR."
    for path in files:
        words = json.loads(path.read_text(encoding="utf-8"))
        before = copy.deepcopy(words)
        native = parse_santander(DocumentData(spatial_words=words))
        stem = path.stem.removesuffix("__paddleocr_words")
        source = root / f"{stem}.pdf"
        if not source.exists():
            candidates = [p for p in root.glob("*.pdf") if re.sub(r"\(\d+\)$", "", p.stem) == stem]
            assert len(candidates) == 1, "El JSON requiere un único PDF de origen."
            source = candidates[0]
        canonical = ReaderManager.project_ocr_document(
            source, DocumentData(spatial_words=words), engine="paddleocr"
        )
        actual = parse_santander(canonical)
        assert native == actual
        assert words == before
        assert actual.movimientos
        assert all(m.fecha_operacion for m in actual.movimientos)
        validations = validar_movimientos(actual.movimientos, actual.resumen_financiero)
        assert len(validations) == 4
        assert all(v.correcto for v in validations)
        # Comprobar cada saldo impreso también detecta intercambios de columnas
        # que por casualidad se compensen en las sumas globales.
        previous = Decimal(str(actual.resumen_financiero.saldo_anterior))
        for movement in actual.movimientos:
            expected = previous + Decimal(str(movement.abono)) - Decimal(str(movement.cargo))
            balance = Decimal(str(movement.saldo_operacion))
            assert balance == expected
            previous = balance
