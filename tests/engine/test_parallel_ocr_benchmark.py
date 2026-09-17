"""Pruebas rápidas del experimento; no cargan modelos ni datos bancarios."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

# El benchmark es un script autónomo y no forma parte del paquete instalable.
# pytest en GitHub Actions no incluye necesariamente la raíz del repo en sys.path.
_benchmark_path = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_parallel_ocr.py"
_spec = importlib.util.spec_from_file_location("benchmark_parallel_ocr", _benchmark_path)
assert _spec is not None and _spec.loader is not None
_benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_benchmark)
collect_pdf_paths = _benchmark.collect_pdf_paths
compare_results = _benchmark.compare_results


def _result(**changes):
    data = {
        "file_name": "documento.pdf",
        "bank_key": "banco",
        "estado_cuenta": None,
        "raw_text": "texto de prueba",
        "normalized_text": "TEXTO DE PRUEBA",
        "validaciones": [],
        "processing_method": "OCR",
        "debug": None,
        "ocr_review": None,
        "ocr_engine": "paddleocr",
        "ocr_requested_primary_engine": "paddleocr",
        "ocr_primary_engine": "paddleocr",
        "ocr_secondary_engine": None,
        "fallback_attempted": False,
        "fallback_used": False,
        "source_pdf_path": "documento.pdf",
        "ocr_reprocessed": False,
        "ocr_artifacts": {},
    }
    data.update(changes)
    return SimpleNamespace(**data)


def test_collect_pdf_paths_preserves_order_and_deduplicates(tmp_path):
    folder = tmp_path / "entrada"
    folder.mkdir()
    first = folder / "01.pdf"
    second = folder / "02.PDF"
    ignored = folder / "nota.txt"
    for path in (first, second, ignored):
        path.write_bytes(b"test")

    assert collect_pdf_paths([str(folder), str(first)]) == [str(first), str(second)]


def test_collect_pdf_paths_rejects_missing_input(tmp_path):
    with pytest.raises(ValueError, match="PDF"):
        collect_pdf_paths([str(tmp_path / "inexistente")])


def test_identical_results_pass_equivalence():
    assert compare_results([_result()], [_result()]) == []


def test_changed_movements_or_ocr_text_are_detected():
    assert compare_results([_result(estado_cuenta={"movimientos": [1]})],
                           [_result(estado_cuenta={"movimientos": [2]})]) == [1]
    assert compare_results([_result()], [_result(raw_text="texto diferente")]) == [1]


def test_missing_or_different_ocr_artifacts_are_detected():
    assert compare_results([_result()], [_result(ocr_artifacts={"paddleocr": "x.pdf"})]) == [1]
    assert compare_results([_result(), _result()], [_result()]) == [1, 2]
