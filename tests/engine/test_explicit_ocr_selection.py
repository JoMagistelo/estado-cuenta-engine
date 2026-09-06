from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from exporters.excel import batch_exporter
from exporters.excel.writer import write_table_sheet
from models.ocr_review import OCRCandidate, OCRReview
from models.processing_result import ProcessingResult
from readers.models import DocumentData


def _candidate(engine: str, text: str, movement_count: int) -> OCRCandidate:
    estado = SimpleNamespace(
        movimientos=[SimpleNamespace() for _ in range(movement_count)],
        resumen_financiero=SimpleNamespace(),
    )
    document = DocumentData(
        raw_text=text,
        normalized_text=text,
        spatial_words=[],
        metadata={'ocr': True, 'reader': engine},
    )
    return OCRCandidate(
        engine=engine,
        estado_cuenta=estado,
        document=document,
        validaciones=[],
    )


def _dual_result() -> ProcessingResult:
    tesseract = _candidate('tesseract', 'TESSERACT', 1)
    paddle = _candidate('paddleocr', 'PADDLE', 2)
    review = OCRReview(
        candidates={'tesseract': tesseract, 'paddleocr': paddle},
        recommended_engine='paddleocr',
        selected_engine='paddleocr',
    )
    return ProcessingResult(
        file_name='dual.pdf',
        bank_key='hsbc',
        estado_cuenta=paddle.estado_cuenta,
        raw_text=paddle.document.raw_text,
        normalized_text=paddle.document.normalized_text,
        processing_method='OCR',
        ocr_review=review,
        ocr_engine='paddleocr',
        ocr_primary_engine='tesseract',
        ocr_secondary_engine='paddleocr',
        fallback_attempted=True,
        fallback_used=True,
    )


def test_dual_ocr_recommendation_is_not_export_confirmation() -> None:
    result = _dual_result()

    assert result.selected_ocr_engine == 'paddleocr'
    assert result.recommended_ocr_engine == 'paddleocr'
    assert result.confirmed_ocr_engine is None
    assert result.ocr_selection_confirmed is False

    result.preview_ocr_engine('tesseract')
    assert result.selected_ocr_engine == 'tesseract'
    assert result.confirmed_ocr_engine is None

    result.select_ocr_engine('paddleocr')
    assert result.confirmed_ocr_engine == 'paddleocr'
    assert result.ocr_selection_confirmed is True


def test_export_rejects_unconfirmed_dual_ocr(tmp_path) -> None:
    result = _dual_result()

    with pytest.raises(ValueError, match='elige explícitamente'):
        batch_exporter.export_batch_excel([result], tmp_path / 'pending.xlsx')


def test_export_restores_confirmed_engine_after_preview(monkeypatch, tmp_path) -> None:
    result = _dual_result()
    result.select_ocr_engine('tesseract')
    result.preview_ocr_engine('paddleocr')
    assert result.selected_ocr_engine == 'paddleocr'
    assert result.confirmed_ocr_engine == 'tesseract'

    def _tables(results):
        assert results[0].selected_ocr_engine == 'tesseract'
        assert results[0].raw_text == 'TESSERACT'
        return {'Prueba': [{'Cargo': 123.45, 'Abono': 5.0}]}

    monkeypatch.setattr(batch_exporter, 'estado_cuenta_to_tables', _tables)
    output = batch_exporter.export_batch_excel([result], tmp_path / 'confirmed.xlsx')
    assert output.is_file()


def test_excel_writer_uses_institutional_montserrat_style() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    write_table_sheet(
        worksheet,
        [
            {'Nombre del Archivo': 'uno.pdf', 'Cargo': 1234.5, 'Abono': 50.25},
            {'Nombre del Archivo': 'dos.pdf', 'Cargo': 0.0, 'Abono': 75.0},
        ],
    )

    assert worksheet['A1'].font.name == 'Montserrat'
    assert worksheet['A1'].font.sz == 11
    assert worksheet['A1'].font.bold is True
    assert worksheet['A1'].fill.fgColor.rgb.endswith('FFFFFF')
    assert worksheet['A2'].font.name == 'Montserrat'
    assert worksheet['A2'].font.sz == 11
    assert worksheet.freeze_panes == 'A2'
    assert worksheet.auto_filter.ref == worksheet.dimensions
    assert worksheet['B2'].number_format.startswith('$#,##0.00')
