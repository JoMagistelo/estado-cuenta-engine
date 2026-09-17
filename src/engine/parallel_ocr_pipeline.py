"""Distribución OCR por documento, optativa y sin modificar lectores ni parsers.

El proceso principal conserva clasificación, PDFs digitales, eventos y cancelación.
Cada proceso hijo ejecuta exactamente _process_prepared_statement del pipeline.
"""

from __future__ import annotations

import multiprocessing
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


def _initialize_ocr_worker(cancel_event: Any) -> None:
    """Compartir la señal de cancelación usando el contexto spawn de Windows."""
    global _worker_cancel_event
    _worker_cancel_event = cancel_event


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
    if not 1 <= ocr_workers <= 4:
        raise ValueError("ocr_workers debe estar entre 1 y 4")

    primary_engine = normalize_ocr_engine(ocr_primary_engine)
    classification_workers = max(1, min(classification_workers, total))
    digital_workers = max(1, min(digital_workers, total))
    ocr_workers = min(ocr_workers, total)
    context = multiprocessing.get_context("spawn")
    shared_cancel = context.Event()
    classifiers = ThreadPoolExecutor(
        max_workers=classification_workers, thread_name_prefix="statement-classifier"
    )
    digital = ThreadPoolExecutor(
        max_workers=digital_workers, thread_name_prefix="statement-digital"
    )
    ocr = ProcessPoolExecutor(
        max_workers=ocr_workers,
        mp_context=context,
        initializer=_initialize_ocr_worker,
        initargs=(shared_cancel,),
    )

    future_map: dict[Any, tuple[str, int, str, PreparedStatement | None]] = {}
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
                future_map.clear()
                break

            done, _ = wait(future_map.keys(), timeout=0.1, return_when=FIRST_COMPLETED)
            for future in done:
                data = future_map.pop(future, None)
                if data is None:
                    continue
                future_type, index, file_name, prepared = data
                if future.cancelled():
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
                        future = ocr.submit(
                            _process_ocr_document,
                            prepared,
                            primary_engine,
                            str(ocr_artifact_dir) if ocr_artifact_dir is not None else None,
                        )
                    else:
                        if ocr_artifact_dir is None:
                            future = digital.submit(
                                _process_prepared_statement, prepared, primary_engine, cancel_event
                            )
                        else:
                            # La ruta digital no consume el directorio OCR.
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
    finally:
        if stop_early or _cancel_requested(cancel_event):
            shared_cancel.set()
        classifiers.shutdown(wait=not stop_early, cancel_futures=stop_early)
        digital.shutdown(wait=not stop_early, cancel_futures=stop_early)
        ocr.shutdown(wait=not stop_early, cancel_futures=stop_early)
