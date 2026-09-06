import threading
from types import SimpleNamespace
from engine import pipeline, statement_processor
from models.ocr_review import OCRCandidate, OCRReview
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from validators.resultado_validacion import ResultadoValidacion

def _validation(name: str, correcto: bool) -> ResultadoValidacion:
    return ResultadoValidacion(nombre=name, esperado=1.0, obtenido=1.0 if correcto else 2.0, diferencia=0.0 if correcto else 1.0, correcto=correcto, mensaje='test')

def _failed_primary_validations():
    return [_validation('Total depósitos / abonos', False), _validation('Total retiros / cargos', True)]

def _ok_primary_validations():
    return [_validation('Total depósitos / abonos', True), _validation('Total retiros / cargos', True)]

def test_stop_request_skips_secondary_ocr_after_primary_failure(monkeypatch):
    primary_estado = SimpleNamespace(movimientos=[SimpleNamespace(tipo_operacion='TRANSFERENCIA')], resumen_financiero=object())
    primary_document = DocumentData(raw_text='HSBC', normalized_text='', spatial_words=[], metadata={'ocr': True, 'reader': 'tesseract', 'source_path': 'statement.pdf', 'start_page': 0})
    monkeypatch.setattr(statement_processor, '_process_once', lambda document, bank_key: (primary_estado, document))
    monkeypatch.setattr(statement_processor, '_validation_results', lambda estado: _failed_primary_validations())

    def _must_not_run(*args, **kwargs):
        raise AssertionError('El OCR secundario no debe arrancar después de solicitar Stop.')
    monkeypatch.setattr(statement_processor.ReaderManager, 'read_paddle_ocr', _must_not_run)
    stop_event = threading.Event()
    stop_event.set()
    estado, document, review = statement_processor.process_single_statement_with_ocr_review(primary_document, 'hsbc', cancel_event=stop_event)
    assert estado is primary_estado
    assert document is primary_document
    assert review is None
    assert document.metadata['ocr_fallback_attempted'] is False
    assert document.metadata['ocr_fallback_skipped_cancelled'] is True

def test_cancelled_batch_does_not_schedule_any_file(monkeypatch):
    calls = []

    def _must_not_prepare(*args, **kwargs):
        calls.append(args)
        raise AssertionError('No debe clasificarse un archivo con Stop ya solicitado.')
    monkeypatch.setattr(pipeline, '_prepare_statement', _must_not_prepare)
    stop_event = threading.Event()
    stop_event.set()
    events = list(pipeline.process_bank_statements_incremental(['a.pdf', 'b.pdf'], ['a.pdf', 'b.pdf'], cancel_event=stop_event))
    assert calls == []
    assert [event.kind for event in events] == ['cancelled', 'cancelled']
    assert [event.file_name for event in events] == ['a.pdf', 'b.pdf']

def test_all_parsers_leave_tipo_operacion_as_no_identificado(monkeypatch):
    movimiento = SimpleNamespace(tipo_operacion='TRANSFERENCIA')
    estado = SimpleNamespace(movimientos=[movimiento], resumen_financiero=None)
    document = DocumentData(raw_text='BANCO', normalized_text='', spatial_words=[], metadata={})
    monkeypatch.setitem(statement_processor.PARSER_REGISTRY, 'fake_bank', lambda doc: estado)
    parsed, _ = statement_processor._process_once(document, 'fake_bank')
    assert parsed.movimientos[0].tipo_operacion == 'No identificado'

def test_manual_ocr_selection_changes_result_kept_for_export():
    tesseract_estado = SimpleNamespace(movimientos=[SimpleNamespace(tipo_operacion='No identificado')], resumen_financiero=object())
    paddle_estado = SimpleNamespace(movimientos=[SimpleNamespace(tipo_operacion='No identificado'), SimpleNamespace(tipo_operacion='No identificado')], resumen_financiero=object())
    tesseract_document = DocumentData(raw_text='TESSERACT', normalized_text='TESSERACT', spatial_words=[], metadata={'ocr': True, 'reader': 'tesseract'})
    paddle_document = DocumentData(raw_text='PADDLE', normalized_text='PADDLE', spatial_words=[], metadata={'ocr': True, 'reader': 'paddleocr'})
    review = OCRReview(candidates={'tesseract': OCRCandidate(engine='tesseract', estado_cuenta=tesseract_estado, document=tesseract_document, validaciones=_failed_primary_validations()), 'paddleocr': OCRCandidate(engine='paddleocr', estado_cuenta=paddle_estado, document=paddle_document, validaciones=_ok_primary_validations())}, recommended_engine='paddleocr', selected_engine='paddleocr')
    result = ProcessingResult(file_name='statement.pdf', bank_key='hsbc', estado_cuenta=paddle_estado, raw_text=paddle_document.raw_text, normalized_text=paddle_document.normalized_text, validaciones=_ok_primary_validations(), processing_method='OCR', ocr_review=review, ocr_engine='paddleocr', ocr_primary_engine='tesseract', ocr_secondary_engine='paddleocr', fallback_attempted=True, fallback_used=True)
    result.select_ocr_engine('tesseract')
    assert result.estado_cuenta is tesseract_estado
    assert result.raw_text == 'TESSERACT'
    assert result.ocr_engine == 'tesseract'
    assert result.fallback_used is False
    result.select_ocr_engine('paddleocr')
    assert result.estado_cuenta is paddle_estado
    assert result.raw_text == 'PADDLE'
    assert result.ocr_engine == 'paddleocr'
    assert result.fallback_used is True
