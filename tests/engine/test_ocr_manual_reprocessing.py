from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine import ocr_reprocessing
from exporters.excel import batch_exporter
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from validators.resultado_validacion import ResultadoValidacion


def _validation(ok: bool) -> ResultadoValidacion:
    return ResultadoValidacion(
        nombre="Total depósitos / abonos",
        esperado=1.0,
        obtenido=1.0 if ok else 2.0,
        diferencia=0.0 if ok else 1.0,
        correcto=ok,
        mensaje="test",
    )


def _estado(name: str):
    return SimpleNamespace(
        name=name,
        movimientos=[SimpleNamespace()],
        resumen_financiero=SimpleNamespace(),
    )


def test_manual_reprocess_uses_only_secondary_and_activates_it(monkeypatch, tmp_path: Path):
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF")
    primary_artifact = tmp_path / "primary.pdf"
    primary_artifact.write_bytes(b"primary")
    secondary_artifact = tmp_path / "secondary.pdf"
    secondary_artifact.write_bytes(b"secondary")

    primary_estado = _estado("primary")
    secondary_estado = _estado("secondary")
    result = ProcessingResult(
        file_name="statement.pdf",
        bank_key="hsbc",
        estado_cuenta=primary_estado,
        raw_text="PRIMARY",
        normalized_text="PRIMARY",
        validaciones=[_validation(False)],
        processing_method="OCR",
        ocr_engine="tesseract",
        ocr_primary_engine="tesseract",
        source_pdf_path=str(source),
        ocr_artifacts={"tesseract": str(primary_artifact)},
    )

    calls: list[str] = []
    secondary_document = DocumentData(
        raw_text="SECONDARY",
        normalized_text="SECONDARY",
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": "paddleocr",
            "ocr_artifact_path": str(secondary_artifact),
        },
    )

    def _read(file_path, engine, start_page=0, cancel_event=None, *, artifact_dir=None):
        calls.append(engine)
        assert Path(file_path) == source
        assert Path(artifact_dir) == tmp_path
        return secondary_document

    monkeypatch.setattr(ocr_reprocessing.ReaderManager, "read_ocr_for_parser", _read)
    monkeypatch.setattr(
        ocr_reprocessing,
        "process_single_statement_with_ocr_review",
        lambda **kwargs: (secondary_estado, kwargs["document"], None),
    )
    monkeypatch.setattr(ocr_reprocessing, "_validations", lambda estado: [_validation(True)])

    updated = ocr_reprocessing.reprocess_with_secondary_ocr(
        result,
        artifact_dir=tmp_path,
    )

    assert updated is result
    assert calls == ["paddleocr"]
    assert result.ocr_engine == "paddleocr"
    assert result.ocr_secondary_engine == "paddleocr"
    assert result.estado_cuenta is secondary_estado
    assert result.raw_text == "SECONDARY"
    assert result.ocr_reprocessed is True
    assert result.fallback_attempted is False
    assert result.fallback_used is False
    assert result.ocr_artifacts == {
        "tesseract": str(primary_artifact),
        "paddleocr": str(secondary_artifact.resolve()),
    }
    assert result.ocr_review is not None
    assert result.ocr_review.selected_engine == "paddleocr"
    assert result.ocr_review.confirmed_engine == "paddleocr"
    assert result.ocr_review.trigger_reasons == ("reproceso_manual",)

    # La vista puede volver temporalmente al primario, pero Excel siempre debe
    # restaurar el secundario que el reprocesado dejó confirmado.
    result.preview_ocr_engine("tesseract")

    def _tables(export_results):
        assert export_results[0] is result
        assert result.estado_cuenta is secondary_estado
        assert result.ocr_engine == "paddleocr"
        assert result.raw_text == "SECONDARY"
        assert result.fallback_used is False
        return {"Prueba": [{"Motor OCR": result.ocr_engine}]}

    monkeypatch.setattr(batch_exporter, "estado_cuenta_to_tables", _tables)
    output = batch_exporter.export_batch_excel([result], tmp_path / "secondary.xlsx")
    assert output.is_file()


def test_manual_reprocess_failure_keeps_primary_result(monkeypatch, tmp_path: Path):
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF")
    primary_estado = _estado("primary")
    result = ProcessingResult(
        file_name="statement.pdf",
        bank_key="hsbc",
        estado_cuenta=primary_estado,
        raw_text="PRIMARY",
        normalized_text="PRIMARY",
        validaciones=[_validation(False)],
        processing_method="OCR",
        ocr_engine="tesseract",
        ocr_primary_engine="tesseract",
        source_pdf_path=str(source),
    )

    monkeypatch.setattr(
        ocr_reprocessing.ReaderManager,
        "read_ocr_for_parser",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secondary failed")),
    )

    with pytest.raises(RuntimeError, match="secondary failed"):
        ocr_reprocessing.reprocess_with_secondary_ocr(
            result,
            artifact_dir=tmp_path,
        )

    assert result.estado_cuenta is primary_estado
    assert result.ocr_engine == "tesseract"
    assert result.ocr_secondary_engine is None
    assert result.ocr_reprocessed is False
    assert result.ocr_review is None


def test_manual_reprocess_without_verified_artifact_keeps_primary_result(
    monkeypatch,
    tmp_path: Path,
):
    source = tmp_path / "statement.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF")
    primary_artifact = tmp_path / "primary.pdf"
    primary_artifact.write_bytes(b"primary")
    primary_estado = _estado("primary")
    secondary_estado = _estado("secondary")
    primary_validations = [_validation(False)]
    result = ProcessingResult(
        file_name="statement.pdf",
        bank_key="hsbc",
        estado_cuenta=primary_estado,
        raw_text="PRIMARY",
        normalized_text="PRIMARY",
        validaciones=primary_validations,
        processing_method="OCR",
        ocr_engine="tesseract",
        ocr_primary_engine="tesseract",
        source_pdf_path=str(source),
        ocr_artifacts={"tesseract": str(primary_artifact)},
    )
    secondary_document = DocumentData(
        raw_text="SECONDARY",
        normalized_text="SECONDARY",
        spatial_words=[],
        metadata={"ocr": True, "reader": "paddleocr"},
    )

    monkeypatch.setattr(
        ocr_reprocessing.ReaderManager,
        "read_ocr_for_parser",
        lambda *args, **kwargs: secondary_document,
    )
    monkeypatch.setattr(
        ocr_reprocessing,
        "process_single_statement_with_ocr_review",
        lambda **kwargs: (secondary_estado, kwargs["document"], None),
    )
    monkeypatch.setattr(ocr_reprocessing, "_validations", lambda estado: [_validation(True)])

    with pytest.raises(RuntimeError, match="sin producir un PDF OCR secundario"):
        ocr_reprocessing.reprocess_with_secondary_ocr(
            result,
            artifact_dir=tmp_path,
        )

    assert result.estado_cuenta is primary_estado
    assert result.raw_text == "PRIMARY"
    assert result.normalized_text == "PRIMARY"
    assert result.validaciones is primary_validations
    assert result.ocr_engine == "tesseract"
    assert result.ocr_secondary_engine is None
    assert result.ocr_reprocessed is False
    assert result.ocr_review is None
    assert result.ocr_artifacts == {"tesseract": str(primary_artifact)}
