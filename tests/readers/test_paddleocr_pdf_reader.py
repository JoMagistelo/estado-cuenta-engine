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

    config = PaddleOCRPDFReader._load_config()

    assert config["detection_model_dir"] == str(detection.resolve())
    assert config["recognition_model_dir"] == str(recognition.resolve())
    assert config["detection_model_name"] == "PP-OCRv5_mobile_det"
    assert config["recognition_model_name"] == "latin_PP-OCRv5_mobile_rec"
