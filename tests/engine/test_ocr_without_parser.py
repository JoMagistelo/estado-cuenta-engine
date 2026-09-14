import pytest

from engine import pipeline
from readers.models import DocumentData


def _ocr_document(tmp_path, engine: str = "tesseract"):
    artifact = tmp_path / f"ocr_{engine}.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% searchable OCR test artifact\n")
    document = DocumentData(
        raw_text="ESTADO DE CUENTA OCR SIN PARSER",
        normalized_text="",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": engine,
            "ocr_artifact_path": str(artifact),
        },
    )
    return document, artifact


def _ocr_prepared(tmp_path) -> pipeline.PreparedStatement:
    return pipeline.PreparedStatement(
        file_name="estado_escaneado.pdf",
        pdf_path=str(tmp_path / "estado_escaneado.pdf"),
        document=None,
        processing_method="OCR",
    )


def test_scanned_pdf_without_identified_bank_keeps_searchable_pdf(monkeypatch, tmp_path):
    document, artifact = _ocr_document(tmp_path)
    monkeypatch.setattr(
        pipeline.ReaderManager,
        "read_ocr_for_parser",
        lambda *args, **kwargs: document,
    )
    monkeypatch.setattr(pipeline, "identify_bank_key", lambda **kwargs: None)

    def _must_not_parse(*args, **kwargs):
        raise AssertionError("No debe intentarse un parser sin banco identificado")

    monkeypatch.setattr(
        pipeline,
        "process_single_statement_with_ocr_review",
        _must_not_parse,
    )

    result = pipeline._process_prepared_statement(
        _ocr_prepared(tmp_path),
        ocr_primary_engine="tesseract",
        ocr_artifact_dir=tmp_path,
    )

    assert result.processing_method == "OCR"
    assert result.bank_key == "no_identificado"
    assert result.estado_cuenta is None
    assert result.ocr_engine == "tesseract"
    assert result.ocr_primary_engine == "tesseract"
    assert result.ocr_artifact_path("tesseract") == str(artifact)
    assert result.debug == {"ocr_only": True, "reason": "bank_not_identified"}


def test_scanned_pdf_without_parser_keeps_searchable_pdf(monkeypatch, tmp_path):
    document, artifact = _ocr_document(tmp_path)
    monkeypatch.setattr(
        pipeline.ReaderManager,
        "read_ocr_for_parser",
        lambda *args, **kwargs: document,
    )
    monkeypatch.setattr(pipeline, "identify_bank_key", lambda **kwargs: "banco_nuevo")

    def _missing_parser(*args, **kwargs):
        raise NotImplementedError("No existe parser para 'banco_nuevo'.")

    monkeypatch.setattr(
        pipeline,
        "process_single_statement_with_ocr_review",
        _missing_parser,
    )

    result = pipeline._process_prepared_statement(
        _ocr_prepared(tmp_path),
        ocr_primary_engine="tesseract",
        ocr_artifact_dir=tmp_path,
    )

    assert result.processing_method == "OCR"
    assert result.bank_key == "banco_nuevo"
    assert result.estado_cuenta is None
    assert result.ocr_artifact_path("tesseract") == str(artifact)
    assert result.debug == {"ocr_only": True, "reason": "parser_not_available"}


def test_scanned_pdf_still_surfaces_real_parser_errors(monkeypatch, tmp_path):
    document, _artifact = _ocr_document(tmp_path)
    monkeypatch.setattr(
        pipeline.ReaderManager,
        "read_ocr_for_parser",
        lambda *args, **kwargs: document,
    )
    monkeypatch.setattr(pipeline, "identify_bank_key", lambda **kwargs: "hsbc")

    def _broken_parser(*args, **kwargs):
        raise RuntimeError("fallo real del parser")

    monkeypatch.setattr(
        pipeline,
        "process_single_statement_with_ocr_review",
        _broken_parser,
    )

    with pytest.raises(RuntimeError, match="fallo real del parser"):
        pipeline._process_prepared_statement(
            _ocr_prepared(tmp_path),
            ocr_primary_engine="tesseract",
            ocr_artifact_dir=tmp_path,
        )


def test_digital_pdf_without_identified_bank_keeps_existing_error(monkeypatch, tmp_path):
    document = DocumentData(
        raw_text="PDF DIGITAL DESCONOCIDO",
        normalized_text="",
        spatial_words=[],
        metadata={},
    )
    prepared = pipeline.PreparedStatement(
        file_name="digital.pdf",
        pdf_path=str(tmp_path / "digital.pdf"),
        document=document,
        processing_method="Digital",
    )
    monkeypatch.setattr(pipeline, "identify_bank_key", lambda **kwargs: None)

    with pytest.raises(ValueError, match="No se pudo identificar la institución financiera"):
        pipeline._process_prepared_statement(prepared)
