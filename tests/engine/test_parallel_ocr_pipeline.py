"""Contrato de eventos del modo OCR paralelo; no necesita modelos ni PDFs reales."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from engine import parallel_ocr_pipeline as parallel
from engine.pipeline import PreparedStatement


def test_ocr_workers_keep_indices_and_digital_path(monkeypatch):
    calls: list[tuple[str, object]] = []
    lock = threading.Lock()

    def prepare(pdf_path, file_name):
        method = "Digital" if file_name == "digital.pdf" else "OCR"
        return PreparedStatement(file_name, pdf_path, None, method)

    def process(prepared, ocr_primary_engine="tesseract", cancel_event=None,
                ocr_artifact_dir=None):
        with lock:
            calls.append((prepared.file_name, cancel_event))
        return f"resultado:{prepared.file_name}"

    def fake_pool(*, max_workers, mp_context, initializer, initargs):
        return ThreadPoolExecutor(
            max_workers=max_workers, initializer=initializer, initargs=initargs
        )

    monkeypatch.setattr(parallel, "_prepare_statement", prepare)
    monkeypatch.setattr(parallel, "_process_prepared_statement", process)
    monkeypatch.setattr(parallel, "ProcessPoolExecutor", fake_pool)

    names = ["ocr-a.pdf", "digital.pdf", "ocr-b.pdf"]
    events = list(parallel.process_bank_statements_parallel_incremental(
        names, names, ocr_workers=2, ocr_primary_engine="paddleocr"
    ))
    assert sorted((e.index, e.file_name) for e in events if e.kind == "started") == [
        (0, "ocr-a.pdf"), (1, "digital.pdf"), (2, "ocr-b.pdf")
    ]
    assert sorted((e.index, e.result) for e in events if e.kind == "completed") == [
        (0, "resultado:ocr-a.pdf"),
        (1, "resultado:digital.pdf"),
        (2, "resultado:ocr-b.pdf"),
    ]
    assert not any(e.kind == "error" for e in events)
    assert {name for name, event in calls if event is not None} == {
        "ocr-a.pdf", "ocr-b.pdf"
    }
    assert {name for name, event in calls if event is None} == {"digital.pdf"}


def test_pre_cancelled_batch_does_not_process_documents(monkeypatch):
    def fail_if_prepared(*args):
        raise AssertionError("No debería iniciarse clasificación")

    monkeypatch.setattr(parallel, "_prepare_statement", fail_if_prepared)
    cancel = threading.Event()
    cancel.set()
    events = list(parallel.process_bank_statements_parallel_incremental(
        ["a.pdf", "b.pdf"], cancel_event=cancel
    ))
    assert [(event.kind, event.index) for event in events] == [
        ("cancelled", 0), ("cancelled", 1)
    ]


def test_invalid_ocr_worker_count_is_rejected():
    with pytest.raises(ValueError, match="ocr_workers"):
        list(parallel.process_bank_statements_parallel_incremental(["a.pdf"], ocr_workers=5))
