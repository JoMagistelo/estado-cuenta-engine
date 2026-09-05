import os
import sys
from types import SimpleNamespace

import pytest

from readers.paddleocr_pdf_reader import (
    PaddleOCRConfigurationError,
    PaddleOCRPDFReader,
)


def test_split_recognition_preserves_spatial_contract():
    words = PaddleOCRPDFReader._split_recognition_into_words(
        text="SALDO FINAL 1,234.56",
        pdf_box=(100.0, 200.0, 300.0, 220.0),
        logical_page=2,
        doctop_offset=800.0,
        confidence=98.5,
    )

    assert [word["text"] for word in words] == [
        "SALDO",
        "FINAL",
        "1,234.56",
    ]
    assert all(word["page"] == 2 for word in words)
    assert all(word["top"] == 200.0 for word in words)
    assert all(word["bottom"] == 220.0 for word in words)
    assert all(word["doctop"] == 1000.0 for word in words)
    assert words[0]["x0"] >= 100.0
    assert words[-1]["x1"] <= 300.0
    assert words[0]["x0"] < words[1]["x0"] < words[2]["x0"]


def test_result_field_reads_official_json_shape():
    result = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["HSBC", "SALDO"],
                "rec_scores": [0.99, 0.95],
            }
        }
    )

    assert PaddleOCRPDFReader._result_field(
        result,
        "rec_texts",
        default=[],
    ) == ["HSBC", "SALDO"]


def test_model_directories_are_required(monkeypatch):
    monkeypatch.delenv(
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
        raising=False,
    )
    monkeypatch.delenv(
        "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR",
        raising=False,
    )

    with pytest.raises(PaddleOCRConfigurationError):
        PaddleOCRPDFReader._load_config()


def test_local_model_configuration_uses_approved_paths(tmp_path, monkeypatch):
    detection = tmp_path / "det"
    recognition = tmp_path / "rec"
    detection.mkdir()
    recognition.mkdir()

    monkeypatch.setenv(
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
        str(detection),
    )
    monkeypatch.setenv(
        "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR",
        str(recognition),
    )
    monkeypatch.setenv("PADDLEOCR_LANG", "es")

    config = PaddleOCRPDFReader._load_config()

    assert config["language"] == "es"
    assert config["detection_model_dir"] == str(detection.resolve())
    assert config["recognition_model_dir"] == str(recognition.resolve())
    assert config["detection_model_name"] == "PP-OCRv5_mobile_det"
    assert config["recognition_model_name"] == "latin_PP-OCRv5_mobile_rec"


def test_paddleocr_rejects_non_spanish_language(tmp_path, monkeypatch):
    detection = tmp_path / "det"
    recognition = tmp_path / "rec"
    detection.mkdir()
    recognition.mkdir()

    monkeypatch.setenv(
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
        str(detection),
    )
    monkeypatch.setenv(
        "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR",
        str(recognition),
    )
    monkeypatch.setenv("PADDLEOCR_LANG", "en")

    with pytest.raises(PaddleOCRConfigurationError, match="únicamente en español"):
        PaddleOCRPDFReader._load_config()


def test_cpu_engine_disables_mkldnn_for_stable_paddle_inference(monkeypatch):
    captured_kwargs = {}

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCR=FakePaddleOCR),
    )
    monkeypatch.delenv("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", raising=False)

    PaddleOCRPDFReader._engine = None
    PaddleOCRPDFReader._engine_signature = None

    try:
        PaddleOCRPDFReader._get_engine(
            language="es",
            device="cpu",
            detection_model_name="PP-OCRv5_mobile_det",
            recognition_model_name="latin_PP-OCRv5_mobile_rec",
            detection_model_dir="C:/modelos/det",
            recognition_model_dir="C:/modelos/rec",
        )

        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "0"
        assert captured_kwargs["enable_mkldnn"] is False
        assert captured_kwargs["device"] == "cpu"
        assert "lang" not in captured_kwargs
        assert "ocr_version" not in captured_kwargs
    finally:
        PaddleOCRPDFReader._engine = None
        PaddleOCRPDFReader._engine_signature = None