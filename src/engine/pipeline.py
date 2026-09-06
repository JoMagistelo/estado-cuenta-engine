from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from detectors.bank_detector import identify_bank_key
from detectors.document_type_detector import DocumentType, detect_document_type
from engine.ocr_fallback_policy import normalize_ocr_engine
from engine.statement_processor import process_single_statement_with_ocr_review
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from validators.movimiento_validator import validar_movimientos

@dataclass(slots=True)
class PreparedStatement:
    file_name: str
    pdf_path: str
    document: DocumentData | None
    processing_method: str

@dataclass(slots=True)
class ProcessingEvent:
    kind: str
    index: int
    file_name: str
    processing_method: str | None = None
    result: ProcessingResult | None = None
    error: Exception | None = None

def _cancel_requested(cancel_event: Any | None) -> bool:
    """Comprueba cancelación cooperativa sin acoplar el engine a threading."""
    if cancel_event is None:
        return False
    is_set = getattr(cancel_event, 'is_set', None)
    return bool(callable(is_set) and is_set())

def _rebase_spatial_words(spatial_words: list[dict], start_page: int) -> list[dict]:
    if start_page <= 0:
        return spatial_words
    rebased_words: list[dict] = []
    for word in spatial_words:
        try:
            page = int(word.get('page', 1) or 1)
        except (TypeError, ValueError):
            continue
        if page <= start_page:
            continue
        rebased_word = dict(word)
        rebased_word['page'] = page - start_page
        rebased_words.append(rebased_word)
    return rebased_words

def _get_file_name(pdf_path: str, file_names: list[str] | None, index: int) -> str:
    return file_names[index] if file_names is not None else Path(pdf_path).name

def _prepare_statement(pdf_path: str, file_name: str) -> PreparedStatement:
    """Clasifica Digital/OCR sin ejecutar ningún motor OCR."""
    text_stage = ReaderManager.read_text_stage(pdf_path, start_page=0)
    document = text_stage.document
    if not text_stage.has_extractable_text:
        return PreparedStatement(file_name=file_name, pdf_path=pdf_path, document=None, processing_method='OCR')
    document_type = detect_document_type(document)
    if document_type == DocumentType.PDF_DIGITAL:
        spatial_words = ReaderManager.read_spatial_words(pdf_path, start_page=0)
        initial_empty_pages = text_stage.initial_empty_pages
        if initial_empty_pages != 0:
            logical_text_stage = ReaderManager.read_text_stage(pdf_path, start_page=initial_empty_pages)
            document = logical_text_stage.document
            spatial_words = _rebase_spatial_words(spatial_words, initial_empty_pages)
        document.spatial_words = spatial_words
        return PreparedStatement(file_name=file_name, pdf_path=pdf_path, document=document, processing_method='Digital')
    spatial_words = ReaderManager.read_spatial_words(pdf_path, start_page=0)
    document.spatial_words = spatial_words
    document_type = detect_document_type(document)
    if document_type == DocumentType.PDF_DIGITAL:
        initial_empty_pages = text_stage.initial_empty_pages
        if initial_empty_pages != 0:
            logical_text_stage = ReaderManager.read_text_stage(pdf_path, start_page=initial_empty_pages)
            document = logical_text_stage.document
            document.spatial_words = _rebase_spatial_words(spatial_words, initial_empty_pages)
        return PreparedStatement(file_name=file_name, pdf_path=pdf_path, document=document, processing_method='Digital')
    return PreparedStatement(file_name=file_name, pdf_path=pdf_path, document=None, processing_method='OCR')

def _result_validations(estado_cuenta, ocr_review) -> list:
    if ocr_review is not None:
        return list(ocr_review.get_candidate(ocr_review.selected_engine).validaciones)
    if getattr(estado_cuenta, 'movimientos', None) and getattr(estado_cuenta, 'resumen_financiero', None):
        return validar_movimientos(movimientos=estado_cuenta.movimientos, resumen=estado_cuenta.resumen_financiero)
    return []

def _process_prepared_statement(prepared: PreparedStatement, ocr_primary_engine: str='tesseract', cancel_event: Any | None=None) -> ProcessingResult:
    """Procesa un documento respetando el motor OCR principal elegido.

    Digital nunca entra a OCR. En OCR se ejecuta primero un único motor. El
    processor sólo invoca el secundario cuando las validaciones principales de
    abonos/cargos lo requieren y no se solicitó detener el lote.
    """
    document = prepared.document
    primary_engine = normalize_ocr_engine(ocr_primary_engine)
    if prepared.processing_method == 'OCR':
        document = ReaderManager.read_ocr_engine(prepared.pdf_path, engine=primary_engine, start_page=0)
    if document is None:
        raise RuntimeError(f"El documento no contiene un DocumentData válido para el método '{prepared.processing_method}'.")
    bank_key = identify_bank_key(raw_text=document.raw_text, file_name=prepared.file_name)
    if not bank_key:
        raise ValueError(f"No se pudo identificar la institución financiera para el archivo '{prepared.file_name}'. No se encontró una CLABE bancaria válida ni una firma bancaria reconocible en el nombre del archivo.")
    if cancel_event is None:
        estado_cuenta, document, ocr_review = process_single_statement_with_ocr_review(document=document, bank_key=bank_key)
    else:
        estado_cuenta, document, ocr_review = process_single_statement_with_ocr_review(document=document, bank_key=bank_key, cancel_event=cancel_event)
    validaciones = _result_validations(estado_cuenta, ocr_review)
    metadata = dict(document.metadata or {})
    selected_engine = None
    primary_used = None
    secondary_engine = None
    fallback_attempted = False
    fallback_used = False
    if prepared.processing_method == 'OCR':
        primary_used = str(metadata.get('ocr_primary_engine') or primary_engine)
        secondary_engine = metadata.get('ocr_secondary_engine')
        fallback_attempted = bool(metadata.get('ocr_fallback_attempted', False))
        fallback_used = bool(metadata.get('ocr_fallback_selected', False))
        selected_engine = str(metadata.get('reader') or primary_engine).lower()
        if ocr_review is not None:
            selected_engine = ocr_review.selected_engine
            fallback_attempted = True
            fallback_used = selected_engine != primary_used
            if secondary_engine is None:
                secondary_candidates = [engine for engine in ocr_review.available_engines() if engine != primary_used]
                secondary_engine = secondary_candidates[0] if secondary_candidates else None
    return ProcessingResult(file_name=prepared.file_name, bank_key=bank_key, estado_cuenta=estado_cuenta, raw_text=document.raw_text, normalized_text=document.normalized_text, validaciones=validaciones, processing_method=prepared.processing_method, ocr_review=ocr_review, ocr_engine=selected_engine, ocr_primary_engine=primary_used, ocr_secondary_engine=secondary_engine, fallback_attempted=fallback_attempted, fallback_used=fallback_used)

def process_bank_statements(pdf_paths: list[str], file_names: list[str] | None=None, ocr_primary_engine: str='tesseract') -> list[ProcessingResult]:
    results: list[ProcessingResult] = []
    primary_engine = normalize_ocr_engine(ocr_primary_engine)
    for index, pdf_path in enumerate(pdf_paths):
        file_name = _get_file_name(pdf_path, file_names, index)
        prepared = _prepare_statement(pdf_path=pdf_path, file_name=file_name)
        result = _process_prepared_statement(prepared, ocr_primary_engine=primary_engine)
        results.append(result)
    return results

def process_bank_statements_incremental(pdf_paths: list[str], file_names: list[str] | None=None, classification_workers: int=2, digital_workers: int=4, ocr_workers: int=1, ocr_primary_engine: str='tesseract', cancel_event: Any | None=None):
    """Procesa lotes concurrentes y emite resultados conforme terminan.

    La cancelación es cooperativa:
    - deja de programar archivos nuevos;
    - cancela futures que todavía no comenzaron;
    - permite terminar únicamente los trabajos que ya estaban ejecutándose;
    - evita iniciar un OCR secundario después de pulsar Stop.

    De esta forma los resultados ya completados se conservan y quedan
    disponibles para auditoría/exportación.
    """
    total = len(pdf_paths)
    if total == 0:
        return
    primary_engine = normalize_ocr_engine(ocr_primary_engine)
    classification_workers = max(1, min(classification_workers, total))
    digital_workers = max(1, min(digital_workers, total))
    ocr_workers = max(1, min(ocr_workers, total))
    with ThreadPoolExecutor(max_workers=classification_workers, thread_name_prefix='statement-classifier') as classification_executor, ThreadPoolExecutor(max_workers=digital_workers, thread_name_prefix='statement-digital') as digital_executor, ThreadPoolExecutor(max_workers=ocr_workers, thread_name_prefix='statement-ocr') as ocr_executor:
        future_map = {}
        cancelled_indices: set[int] = set()
        for index, pdf_path in enumerate(pdf_paths):
            file_name = _get_file_name(pdf_path, file_names, index)
            if _cancel_requested(cancel_event):
                cancelled_indices.add(index)
                yield ProcessingEvent(kind='cancelled', index=index, file_name=file_name, processing_method=None)
                continue
            future = classification_executor.submit(_prepare_statement, pdf_path, file_name)
            future_map[future] = ('classification', index, file_name, None)
        while future_map:
            if _cancel_requested(cancel_event):
                for future, data in list(future_map.items()):
                    future_type, index, file_name, prepared = data
                    if future.cancel():
                        future_map.pop(future, None)
                        if index not in cancelled_indices:
                            cancelled_indices.add(index)
                            method = prepared.processing_method if prepared is not None else None
                            yield ProcessingEvent(kind='cancelled', index=index, file_name=file_name, processing_method=method)
            if not future_map:
                break
            done, _ = wait(future_map.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                data = future_map.pop(future, None)
                if data is None:
                    continue
                future_type, index, file_name, prepared = data
                if future.cancelled():
                    if index not in cancelled_indices:
                        cancelled_indices.add(index)
                        yield ProcessingEvent(kind='cancelled', index=index, file_name=file_name, processing_method=prepared.processing_method if prepared is not None else None)
                    continue
                if future_type == 'classification':
                    try:
                        prepared = future.result()
                    except Exception as ex:
                        yield ProcessingEvent(kind='error', index=index, file_name=file_name, processing_method=None, error=ex)
                        continue
                    if _cancel_requested(cancel_event):
                        if index not in cancelled_indices:
                            cancelled_indices.add(index)
                            yield ProcessingEvent(kind='cancelled', index=index, file_name=file_name, processing_method=prepared.processing_method)
                        continue
                    yield ProcessingEvent(kind='started', index=index, file_name=file_name, processing_method=prepared.processing_method)
                    executor = ocr_executor if prepared.processing_method == 'OCR' else digital_executor
                    processing_future = executor.submit(_process_prepared_statement, prepared, primary_engine, cancel_event)
                    future_map[processing_future] = ('processing', index, file_name, prepared)
                    continue
                try:
                    result = future.result()
                except Exception as ex:
                    method = prepared.processing_method if prepared is not None else None
                    yield ProcessingEvent(kind='error', index=index, file_name=file_name, processing_method=method, error=ex)
                    continue
                yield ProcessingEvent(kind='completed', index=index, file_name=file_name, processing_method=prepared.processing_method, result=result)
