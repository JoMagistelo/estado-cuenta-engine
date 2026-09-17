"""Regresiones para digital rápido, entrega en vivo y limpieza de ejecutores.

Se simulan motores pesados: no se necesitan PDFs privados ni modelos OCR en CI.
"""

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


def _prepare(path, file_name):
    method = "OCR" if file_name.startswith("scan") else "Digital"
    return PreparedStatement(file_name, path, None, method)


def test_digital_only_never_constructs_an_ocr_pool(monkeypatch):
    monkeypatch.setattr(parallel, "_prepare_statement", _prepare)
    monkeypatch.setattr(
        parallel,
        "_process_prepared_statement",
        lambda prepared, *args, **kwargs: prepared.file_name,
    )

    def forbidden_pool(**kwargs):
        raise AssertionError("Los PDF digitales no deben iniciar ProcessPoolExecutor")

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", forbidden_pool)
    events = list(parallel.process_bank_statements_parallel_incremental(
        ["digital-1.pdf", "digital-2.pdf"], ocr_workers=4
    ))
    assert [(event.file_name, event.result) for event in events if event.kind == "completed"] == [
        ("digital-1.pdf", "digital-1.pdf"),
        ("digital-2.pdf", "digital-2.pdf"),
    ] or sorted(
        (event.file_name, event.result) for event in events if event.kind == "completed"
    ) == [("digital-1.pdf", "digital-1.pdf"), ("digital-2.pdf", "digital-2.pdf")]


def test_digital_completed_before_earlier_ocr_and_pool_is_joined(monkeypatch):
    digital_done = threading.Event()
    digital_delivered = threading.Event()
    shutdown_calls = []
    monkeypatch.setattr(parallel, "_prepare_statement", _prepare)

    def process(prepared, *args, **kwargs):
        if prepared.processing_method == "OCR":
            assert digital_done.wait(timeout=8), "El documento digital quedó bloqueado por OCR"
            assert digital_delivered.wait(timeout=8), "El resultado digital no se publicó en vivo"
        else:
            digital_done.set()
        return prepared.file_name

    class TrackedPool(ThreadPoolExecutor):
        def shutdown(self, wait=True, *, cancel_futures=False):
            shutdown_calls.append(wait)
            return super().shutdown(wait=wait, cancel_futures=cancel_futures)

    def fake_ocr_pool(**kwargs):
        return TrackedPool(
            max_workers=kwargs["max_workers"],
            initializer=kwargs["initializer"],
            initargs=kwargs["initargs"],
        )

    monkeypatch.setattr(parallel, "_process_prepared_statement", process)
    monkeypatch.setattr(parallel, "ProcessPoolExecutor", fake_ocr_pool)
    events = []
    for event in parallel.process_bank_statements_parallel_incremental(
        ["scan-slow.pdf", "digital-fast.pdf"], ocr_workers=2
    ):
        events.append(event)
        if event.kind == "completed" and event.file_name == "digital-fast.pdf":
            digital_delivered.set()
    completed = [event.file_name for event in events if event.kind == "completed"]
    assert completed == ["digital-fast.pdf", "scan-slow.pdf"]
    assert shutdown_calls == [True]


def test_ocr_failure_does_not_hide_a_completed_digital(monkeypatch):
    monkeypatch.setattr(parallel, "_prepare_statement", _prepare)

    def process(prepared, *args, **kwargs):
        if prepared.processing_method == "OCR":
            raise RuntimeError("Synthetic OCR failure")
        return prepared.file_name

    monkeypatch.setattr(parallel, "_process_prepared_statement", process)
    monkeypatch.setattr(
        parallel,
        "ProcessPoolExecutor",
        lambda **kwargs: ThreadPoolExecutor(
            max_workers=kwargs["max_workers"],
            initializer=kwargs["initializer"],
            initargs=kwargs["initargs"],
        ),
    )
    events = list(parallel.process_bank_statements_parallel_incremental(
        ["scan-error.pdf", "digital-ok.pdf"], ocr_workers=2
    ))
    assert [(event.kind, event.file_name) for event in events if event.kind in {"completed", "error"}] in (
        [("completed", "digital-ok.pdf"), ("error", "scan-error.pdf")],
        [("error", "scan-error.pdf"), ("completed", "digital-ok.pdf")],
    )
