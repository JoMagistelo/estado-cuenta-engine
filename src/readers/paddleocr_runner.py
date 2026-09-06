from __future__ import annotations

import multiprocessing as mp
import os
from queue import Empty
from typing import Any

from readers.models import DocumentData


class PaddleOCRTimeoutError(TimeoutError):
    """PaddleOCR excedió el tiempo máximo permitido para el fallback."""


class PaddleOCRWorkerError(RuntimeError):
    """Error reportado por el proceso aislado de PaddleOCR."""

    def __init__(self, error_type: str):
        self.error_type = error_type or "PaddleOCRWorkerError"
        super().__init__(self.error_type)


# El OCR Paddle completo puede tardar más de dos minutos en CPU sobre estados
# de cuenta multipágina. Cinco minutos mantiene protección contra bloqueos
# indefinidos sin convertir ejecuciones válidas de UAT en falsos timeouts.
DEFAULT_TIMEOUT_SECONDS = 300
MIN_TIMEOUT_SECONDS = 15
MAX_TIMEOUT_SECONDS = 900


def configured_timeout_seconds() -> int:
    configured = os.getenv("PADDLEOCR_TIMEOUT_SECONDS", "").strip()
    if not configured:
        return DEFAULT_TIMEOUT_SECONDS

    try:
        seconds = int(configured)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS

    return max(MIN_TIMEOUT_SECONDS, min(seconds, MAX_TIMEOUT_SECONDS))


def _worker_read(
    file_path: str,
    start_page: int,
    result_queue: Any,
) -> None:
    """Lee con PaddleOCR dentro de un proceso desechable.

    No se transmite contenido bancario por logs. El ``DocumentData`` viaja por
    IPC únicamente al proceso padre local de la aplicación.
    """
    try:
        from readers.paddleocr_pdf_reader import PaddleOCRPDFReader

        document = PaddleOCRPDFReader.read(
            file_path,
            start_page=start_page,
        )
        result_queue.put(("ok", document, None))
    except BaseException as exc:  # pragma: no cover - ejecuta en proceso hijo
        result_queue.put(("error", None, type(exc).__name__))


def _stop_process(process: Any) -> None:
    if not process.is_alive():
        return

    process.terminate()
    process.join(timeout=3)

    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=3)


def _raise_worker_error(error_type: str | None) -> None:
    normalized = str(error_type or "PaddleOCRWorkerError")
    error_class = type(
        normalized,
        (PaddleOCRWorkerError,),
        {},
    )
    raise error_class(normalized)


def read_paddle_ocr_isolated(
    file_path: str,
    start_page: int = 0,
    timeout_seconds: int | None = None,
) -> DocumentData:
    """Ejecuta PaddleOCR fuera del proceso principal y limita su duración.

    El fallback no puede bloquear indefinidamente Flet, Streamlit ni el CLI.
    Si PaddleOCR no termina dentro del límite, el proceso se elimina y el flujo
    superior conserva el candidato Tesseract.
    """
    timeout = timeout_seconds or configured_timeout_seconds()
    timeout = max(MIN_TIMEOUT_SECONDS, min(int(timeout), MAX_TIMEOUT_SECONDS))

    context = mp.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_worker_read,
        args=(str(file_path), int(start_page), result_queue),
        name="estado-cuenta-paddleocr",
        daemon=True,
    )
    process.start()

    try:
        try:
            status, document, error_type = result_queue.get(timeout=timeout)
        except Empty as exc:
            _stop_process(process)
            raise PaddleOCRTimeoutError(
                f"PaddleOCR excedió el límite técnico de {timeout} segundos."
            ) from exc

        process.join(timeout=3)
        if process.is_alive():
            _stop_process(process)

        if status != "ok" or document is None:
            _raise_worker_error(error_type)

        return document
    finally:
        if process.is_alive():
            _stop_process(process)
        result_queue.close()
        result_queue.join_thread()
