from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from engine import pipeline
from readers.models import DocumentData


def _prepared(file_name: str) -> pipeline.PreparedStatement:
    return pipeline.PreparedStatement(
        file_name=file_name,
        pdf_path=file_name,
        document=DocumentData(
            raw_text='BANCO',
            normalized_text='',
            spatial_words=[],
            metadata={},
        ),
        processing_method='Digital',
    )


def test_stop_returns_control_without_waiting_for_running_job(monkeypatch):
    cancel_event = threading.Event()
    processing_started = threading.Event()
    events = []

    monkeypatch.setattr(
        pipeline,
        '_prepare_statement',
        lambda pdf_path, file_name: _prepared(file_name),
    )

    def slow_process(prepared, primary_engine, cancel_event):
        processing_started.set()
        cancel_event.wait(timeout=5)
        time.sleep(0.35)
        return SimpleNamespace(file_name=prepared.file_name)

    monkeypatch.setattr(pipeline, '_process_prepared_statement', slow_process)

    def consume():
        events.extend(
            pipeline.process_bank_statements_incremental(
                ['slow.pdf'],
                ['slow.pdf'],
                classification_workers=1,
                digital_workers=1,
                cancel_event=cancel_event,
            )
        )

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert processing_started.wait(timeout=1.5)

    started = time.perf_counter()
    cancel_event.set()
    worker.join(timeout=0.8)
    elapsed = time.perf_counter() - started

    assert not worker.is_alive()
    assert elapsed < 0.5
    assert any(event.kind == 'cancelled' for event in events)
    assert not any(event.kind == 'completed' for event in events)


def test_stop_keeps_results_completed_before_request(monkeypatch):
    cancel_event = threading.Event()
    first_completed = threading.Event()
    slow_started = threading.Event()
    events = []

    monkeypatch.setattr(
        pipeline,
        '_prepare_statement',
        lambda pdf_path, file_name: _prepared(file_name),
    )

    def process(prepared, primary_engine, cancel_event):
        if prepared.file_name == 'done.pdf':
            return SimpleNamespace(file_name=prepared.file_name)
        slow_started.set()
        cancel_event.wait(timeout=5)
        time.sleep(0.35)
        return SimpleNamespace(file_name=prepared.file_name)

    monkeypatch.setattr(pipeline, '_process_prepared_statement', process)

    def consume():
        for event in pipeline.process_bank_statements_incremental(
            ['done.pdf', 'slow.pdf'],
            ['done.pdf', 'slow.pdf'],
            classification_workers=1,
            digital_workers=1,
            cancel_event=cancel_event,
        ):
            events.append(event)
            if event.kind == 'completed' and event.file_name == 'done.pdf':
                first_completed.set()

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert first_completed.wait(timeout=1.5)
    assert slow_started.wait(timeout=1.5)

    cancel_event.set()
    worker.join(timeout=0.8)

    assert not worker.is_alive()
    assert any(
        event.kind == 'completed' and event.file_name == 'done.pdf'
        for event in events
    )
    assert any(
        event.kind == 'cancelled' and event.file_name == 'slow.pdf'
        for event in events
    )
