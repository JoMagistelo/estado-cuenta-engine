"""Distribución OCR por documento, optativa y sin modificar lectores ni parsers.

El proceso principal conserva clasificación, PDFs digitales, eventos y cancelación.
Cada proceso hijo ejecuta exactamente _process_prepared_statement del pipeline.
"""

from __future__ import annotations

import multiprocessing
import os
from concurrent.futures import (
    CancelledError,
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    wait,
)
from typing import Any

from engine.ocr_fallback_policy import normalize_ocr_engine
from engine.pipeline import (
    PreparedStatement,
    ProcessingEvent,
    _cancel_requested,
    _get_file_name,
    _prepare_statement,
    _process_prepared_statement,
)

_worker_cancel_event: Any | None = None
MAX_OCR_WORKERS = 8
MAX_PADDLE_THREADS_PER_WORKER = 10
_THREAD_ENVIRONMENT_VARIABLES = (
    "PADDLEOCR_CPU_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def recommended_ocr_threads_per_worker(
    workers: int,
    *,
    logical_cpus: int | None = None,
) -> int:
    """Reparte la CPU entre motores Paddle sin multiplicar diez hilos por proceso.

    El override es exclusivo del modo paralelo; el lector y el modo estándar
    conservan intacta su configuración histórica.
    """
    if not 1 <= workers <= MAX_OCR_WORKERS:
        raise ValueError(f"workers debe estar entre 1 y {MAX_OCR_WORKERS}")

    configured = os.getenv("PADDLEOCR_PARALLEL_THREADS_PER_WORKER", "").strip()
    if configured:
        try:
            return max(1, min(int(configured), 32))
        except ValueError:
            pass

    cpu_budget = logical_cpus if logical_cpus is not None else (os.cpu_count() or 1)
    cpu_budget = max(1, int(cpu_budget))
    return max(1, min(MAX_PADDLE_THREADS_PER_WORKER, cpu_budget // workers))


def _initialize_ocr_worker(cancel_event: Any, threads_per_worker: int) -> None:
    """Configura cancelación y presupuesto CPU dentro de cada hijo ``spawn``."""
    global _worker_cancel_event
    _worker_cancel_event = cancel_event
    thread_count = str(threads_per_worker)
    for variable in _THREAD_ENVIRONMENT_VARIABLES:
        os.environ[variable] = thread_count


def _process_ocr_document(
    prepared: PreparedStatement,
    engine: str,
    artifact_dir: str | None,
):
    """Entrada pickleable: un PDF completo por proceso, sin otro motor OCR."""
    return _process_prepared_statement(
        prepared,
        ocr_primary_engine=engine,
        cancel_event=_worker_cancel_event,
        ocr_artifact_dir=artifact_dir,
    )


def process_bank_statements_parallel_incremental(
    pdf_paths: list[str],
    file_names: list[str] | None = None,
    classification_workers: int = 2,
    digital_workers: int = 4,
    ocr_workers: int = 2,
    ocr_threads_per_worker: int | None = None,
    ocr_primary_engine: str = "tesseract",
    cancel_event: Any | None = None,
    ocr_artifact_dir: str | None = None,
):
    """Emite los mismos ProcessingEvent; sólo OCR usa procesos independientes.

    No se omite ninguna página; cada hijo sigue OCR -> PDF incrustado verificado
    -> lector digital -> parser. Requiere arranque spawn/freeze_support en EXE.
    """
    total = len(pdf_paths)
    if not total:
        return
    if not 1 <= ocr_workers <= MAX_OCR_WORKERS:
        raise ValueError(f"ocr_workers debe estar entre 1 y {MAX_OCR_WORKERS}")
    if ocr_threads_per_worker is not None and not 1 <= ocr_threads_per_worker <= 32:
        raise ValueError("ocr_threads_per_worker debe estar entre 1 y 32")

    primary_engine = normalize_ocr_engine(ocr_primary_engine)
    classification_workers = max(1, min(classification_workers, total))
    digital_workers = max(1, min(digital_workers, total))
    requested_ocr_workers = min(ocr_workers, total)
    context = multiprocessing.get_context("spawn")
    shared_cancel = context.Event()
    classifiers = ThreadPoolExecutor(
        max_workers=classification_workers, thread_name_prefix="statement-classifier"
    )
    digital = ThreadPoolExecutor(
        max_workers=digital_workers, thread_name_prefix="statement-digital"
    )
    # No iniciar ni reservar motores OCR cuando el lote contiene sólo digitales.
    ocr: ProcessPoolExecutor | None = None

    future_map: dict[Any, tuple[str, int, str, PreparedStatement | None]] = {}
    pending_ocr: list[tuple[int, str, PreparedStatement]] = []
    remaining_classifications = 0
    cancelled_indices: set[int] = set()
    finished_indices: set[int] = set()
    stop_early = False
    try:
        for index, pdf_path in enumerate(pdf_paths):
            file_name = _get_file_name(pdf_path, file_names, index)
            if _cancel_requested(cancel_event):
                cancelled_indices.add(index)
                yield ProcessingEvent(
                    kind="cancelled", index=index, file_name=file_name, processing_method=None
                )
                continue
            future = classifiers.submit(_prepare_statement, pdf_path, file_name)
            future_map[future] = ("classification", index, file_name, None)
            remaining_classifications += 1

        while future_map:
            if _cancel_requested(cancel_event):
                stop_early = True
                shared_cancel.set()
                for future, (_, index, file_name, prepared) in list(future_map.items()):
                    future.cancel()
                    if index in finished_indices or index in cancelled_indices:
                        continue
                    cancelled_indices.add(index)
                    yield ProcessingEvent(
                        kind="cancelled",
                        index=index,
                        file_name=file_name,
                        processing_method=(
                            prepared.processing_method if prepared is not None else None
                        ),
                    )
                for index, file_name, prepared in pending_ocr:
                    if index in finished_indices or index in cancelled_indices:
                        continue
                    cancelled_indices.add(index)
                    yield ProcessingEvent(
                        kind="cancelled",
                        index=index,
                        file_name=file_name,
                        processing_method=prepared.processing_method,
                    )
                pending_ocr.clear()
                future_map.clear()
                break

            done, _ = wait(future_map.keys(), timeout=0.1, return_when=FIRST_COMPLETED)
            for future in done:
                data = future_map.pop(future, None)
                if data is None:
                    continue
                future_type, index, file_name, prepared = data
                if future.cancelled():
                    if future_type == "classification":
                        remaining_classifications -= 1
                    if index not in cancelled_indices:
                        cancelled_indices.add(index)
                        yield ProcessingEvent(
                            kind="cancelled",
                            index=index,
                            file_name=file_name,
                            processing_method=(
                                prepared.processing_method if prepared is not None else None
                            ),
                        )
                    continue

                if future_type == "classification":
                    remaining_classifications -= 1
                    try:
                        prepared = future.result()
                    except CancelledError:
                        if index not in cancelled_indices:
                            cancelled_indices.add(index)
                            yield ProcessingEvent(
                                kind="cancelled",
                                index=index,
                                file_name=file_name,
                                processing_method=None,
                            )
                        continue
                    except Exception as exc:
                        finished_indices.add(index)
                        yield ProcessingEvent(
                            kind="error",
                            index=index,
                            file_name=file_name,
                            processing_method=None,
                            error=exc,
                        )
                        continue

                    if _cancel_requested(cancel_event):
                        if index not in cancelled_indices:
                            cancelled_indices.add(index)
                            yield ProcessingEvent(
                                kind="cancelled",
                                index=index,
                                file_name=file_name,
                                processing_method=prepared.processing_method,
                            )
                        continue

                    yield ProcessingEvent(
                        kind="started",
                        index=index,
                        file_name=file_name,
                        processing_method=prepared.processing_method,
                    )
                    if prepared.processing_method == "OCR":
                        # Esperar sólo a que concluya la clasificación permite
                        # conocer cuántos OCR existen y repartir la CPU entre los
                        # procesos que realmente podrán trabajar simultáneamente.
                        pending_ocr.append((index, file_name, prepared))
                    else:
                        # Un digital nunca entra al pool OCR ni consume su modelo.
                        future = digital.submit(
                            _process_prepared_statement, prepared, primary_engine, cancel_event
                        )
                        future_map[future] = ("processing", index, file_name, prepared)
                    continue

                try:
                    result = future.result()
                except CancelledError:
                    if index not in cancelled_indices:
                        cancelled_indices.add(index)
                        yield ProcessingEvent(
                            kind="cancelled",
                            index=index,
                            file_name=file_name,
                            processing_method=(
                                prepared.processing_method if prepared is not None else None
                            ),
                        )
                    continue
                except Exception as exc:
                    finished_indices.add(index)
                    yield ProcessingEvent(
                        kind="error",
                        index=index,
                        file_name=file_name,
                        processing_method=(
                            prepared.processing_method if prepared is not None else None
                        ),
                        error=exc,
                    )
                    continue

                if _cancel_requested(cancel_event):
                    if index not in cancelled_indices:
                        cancelled_indices.add(index)
                        yield ProcessingEvent(
                            kind="cancelled",
                            index=index,
                            file_name=file_name,
                            processing_method=prepared.processing_method,
                        )
                    continue
                finished_indices.add(index)
                yield ProcessingEvent(
                    kind="completed",
                    index=index,
                    file_name=file_name,
                    processing_method=prepared.processing_method,
                    result=result,
                )

            if remaining_classifications == 0 and pending_ocr and ocr is None:
                effective_workers = min(requested_ocr_workers, len(pending_ocr))
                threads_per_worker = (
                    ocr_threads_per_worker
                    if ocr_threads_per_worker is not None
                    else recommended_ocr_threads_per_worker(effective_workers)
                )
                ocr = ProcessPoolExecutor(
                    max_workers=effective_workers,
                    mp_context=context,
                    initializer=_initialize_ocr_worker,
                    initargs=(shared_cancel, threads_per_worker),
                )
                for index, file_name, prepared in pending_ocr:
                    future = ocr.submit(
                        _process_ocr_document,
                        prepared,
                        primary_engine,
                        str(ocr_artifact_dir) if ocr_artifact_dir is not None else None,
                    )
                    future_map[future] = ("processing", index, file_name, prepared)
                pending_ocr.clear()
    finally:
        # No permitir que Flet limpie los PDFs temporales mientras los hijos OCR
        # siguen trabajando. Detener es cooperativo; el worker de UI espera en
        # segundo plano y Flet conserva la capacidad de actualizar la pantalla.
        if stop_early or _cancel_requested(cancel_event):
            shared_cancel.set()
        classifiers.shutdown(wait=True, cancel_futures=stop_early)
        digital.shutdown(wait=True, cancel_futures=stop_early)
        if ocr is not None:
            ocr.shutdown(wait=True, cancel_futures=stop_early)
