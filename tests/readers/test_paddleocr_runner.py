from queue import Empty

import pytest

from readers import paddleocr_runner
from readers.models import DocumentData


class _FakeQueue:
    def __init__(self, payload=None, timeout=False):
        self.payload = payload
        self.timeout = timeout
        self.closed = False
        self.joined = False

    def get(self, timeout):
        if self.timeout:
            raise Empty
        return self.payload

    def close(self):
        self.closed = True

    def join_thread(self):
        self.joined = True


class _FakeProcess:
    def __init__(self):
        self.alive = False
        self.started = False
        self.terminated = False
        self.killed = False

    def start(self):
        self.started = True
        self.alive = True

    def join(self, timeout=None):
        if not self.terminated and not self.killed:
            self.alive = False

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False

    def kill(self):
        self.killed = True
        self.alive = False


class _FakeContext:
    def __init__(self, queue):
        self.queue = queue
        self.process = _FakeProcess()

    def Queue(self, maxsize=1):
        return self.queue

    def Process(self, **kwargs):
        return self.process


def test_timeout_is_bounded_and_configurable(monkeypatch):
    monkeypatch.delenv("PADDLEOCR_TIMEOUT_SECONDS", raising=False)
    assert paddleocr_runner.configured_timeout_seconds() == 120

    monkeypatch.setenv("PADDLEOCR_TIMEOUT_SECONDS", "45")
    assert paddleocr_runner.configured_timeout_seconds() == 45

    monkeypatch.setenv("PADDLEOCR_TIMEOUT_SECONDS", "1")
    assert paddleocr_runner.configured_timeout_seconds() == 15

    monkeypatch.setenv("PADDLEOCR_TIMEOUT_SECONDS", "5000")
    assert paddleocr_runner.configured_timeout_seconds() == 900

    monkeypatch.setenv("PADDLEOCR_TIMEOUT_SECONDS", "invalido")
    assert paddleocr_runner.configured_timeout_seconds() == 120


def test_isolated_reader_returns_document(monkeypatch):
    document = DocumentData(
        raw_text="PADDLE",
        metadata={"reader": "paddleocr"},
    )
    queue = _FakeQueue(payload=("ok", document, None))
    context = _FakeContext(queue)

    monkeypatch.setattr(
        paddleocr_runner.mp,
        "get_context",
        lambda method: context,
    )

    result = paddleocr_runner.read_paddle_ocr_isolated(
        "statement.pdf",
        timeout_seconds=30,
    )

    assert result is document
    assert context.process.started is True
    assert queue.closed is True
    assert queue.joined is True


def test_isolated_reader_terminates_process_on_timeout(monkeypatch):
    queue = _FakeQueue(timeout=True)
    context = _FakeContext(queue)

    monkeypatch.setattr(
        paddleocr_runner.mp,
        "get_context",
        lambda method: context,
    )

    with pytest.raises(paddleocr_runner.PaddleOCRTimeoutError):
        paddleocr_runner.read_paddle_ocr_isolated(
            "statement.pdf",
            timeout_seconds=15,
        )

    assert context.process.terminated is True
    assert context.process.is_alive() is False
    assert queue.closed is True


def test_isolated_reader_preserves_worker_error_type(monkeypatch):
    queue = _FakeQueue(payload=("error", None, "NotImplementedError"))
    context = _FakeContext(queue)

    monkeypatch.setattr(
        paddleocr_runner.mp,
        "get_context",
        lambda method: context,
    )

    with pytest.raises(paddleocr_runner.PaddleOCRWorkerError) as exc_info:
        paddleocr_runner.read_paddle_ocr_isolated(
            "statement.pdf",
            timeout_seconds=30,
        )

    assert exc_info.value.error_type == "NotImplementedError"
