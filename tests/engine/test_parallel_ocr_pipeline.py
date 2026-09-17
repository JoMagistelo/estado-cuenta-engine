"""Contrato de eventos del modo OCR paralelo; no necesita modelos ni PDFs reales."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from engine import parallel_ocr_pipeline as parallel
from engine.pipeline import PreparedStatement


@pytest.fixture(autouse=True)
def _restore_parallel_worker_environment(monkeypatch):
    for variable in parallel._THREAD_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


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
        list(parallel.process_bank_statements_parallel_incremental(["a.pdf"], ocr_workers=9))
    with pytest.raises(ValueError, match="ocr_threads_per_worker"):
        list(parallel.process_bank_statements_parallel_incremental(
            ["a.pdf"], ocr_threads_per_worker=33
        ))


def test_parallel_thread_budget_uses_active_workers_and_allows_override(monkeypatch):
    assert parallel.recommended_ocr_threads_per_worker(1, logical_cpus=16) == 10
    assert parallel.recommended_ocr_threads_per_worker(4, logical_cpus=16) == 4
    assert parallel.recommended_ocr_threads_per_worker(6, logical_cpus=16) == 2
    assert parallel.recommended_ocr_threads_per_worker(8, logical_cpus=16) == 2

    monkeypatch.setenv("PADDLEOCR_PARALLEL_THREADS_PER_WORKER", "3")
    assert parallel.recommended_ocr_threads_per_worker(8, logical_cpus=16) == 3


def test_worker_initializer_applies_cpu_budget_without_changing_reader_defaults(monkeypatch):
    cancel = threading.Event()
    parallel._initialize_ocr_worker(cancel, 3)
    assert parallel._worker_cancel_event is cancel
    assert {
        variable: parallel.os.environ[variable]
        for variable in parallel._THREAD_ENVIRONMENT_VARIABLES
    } == {variable: "3" for variable in parallel._THREAD_ENVIRONMENT_VARIABLES}


def test_eight_ocr_documents_overlap_and_receive_balanced_threads(monkeypatch):
    barrier = threading.Barrier(8)
    worker_threads: set[int] = set()
    lock = threading.Lock()
    pool_configuration = {}

    def prepare(path, file_name):
        return PreparedStatement(file_name, path, None, "OCR")

    def process(prepared, *args, **kwargs):
        with lock:
            worker_threads.add(threading.get_ident())
        barrier.wait(timeout=5)
        return prepared.file_name

    def fake_pool(*, max_workers, mp_context, initializer, initargs):
        pool_configuration.update(max_workers=max_workers, initargs=initargs)
        parallel._worker_cancel_event = initargs[0]
        return ThreadPoolExecutor(max_workers=max_workers)

    monkeypatch.setattr(parallel, "_prepare_statement", prepare)
    monkeypatch.setattr(parallel, "_process_prepared_statement", process)
    monkeypatch.setattr(parallel, "ProcessPoolExecutor", fake_pool)
    monkeypatch.setattr(parallel.os, "cpu_count", lambda: 16)

    names = [f"scan-{index}.pdf" for index in range(8)]
    events = list(parallel.process_bank_statements_parallel_incremental(
        names, names, ocr_workers=8, ocr_primary_engine="paddleocr"
    ))

    assert len([event for event in events if event.kind == "completed"]) == 8
    assert len(worker_threads) == 8
    assert pool_configuration["max_workers"] == 8
    assert pool_configuration["initargs"][1] == 2
