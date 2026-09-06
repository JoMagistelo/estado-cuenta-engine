import os
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

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
    monkeypatch.delenv("PADDLEOCR_ENABLE_MKLDNN", raising=False)
    monkeypatch.delenv("PADDLEOCR_CPU_THREADS", raising=False)

    config = PaddleOCRPDFReader._load_config()

    assert config["language"] == "es"
    assert config["detection_model_dir"] == str(detection.resolve())
    assert config["recognition_model_dir"] == str(recognition.resolve())
    assert config["detection_model_name"] == "PP-OCRv5_mobile_det"
    assert config["recognition_model_name"] == "latin_PP-OCRv5_mobile_rec"
    assert config["enable_mkldnn"] is False
    assert config["cpu_threads"] == 10


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


def test_cpu_engine_disables_mkldnn_by_default(monkeypatch):
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
            enable_mkldnn=False,
            cpu_threads=10,
        )

        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "0"
        assert captured_kwargs["enable_mkldnn"] is False
        assert captured_kwargs["cpu_threads"] == 10
        assert captured_kwargs["device"] == "cpu"
        assert "lang" not in captured_kwargs
        assert "ocr_version" not in captured_kwargs
    finally:
        PaddleOCRPDFReader._engine = None
        PaddleOCRPDFReader._engine_signature = None


def test_cpu_engine_can_enable_mkldnn_explicitly(monkeypatch):
    captured_kwargs = {}

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCR=FakePaddleOCR),
    )

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
            enable_mkldnn=True,
            cpu_threads=4,
        )

        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "1"
        assert captured_kwargs["enable_mkldnn"] is True
        assert captured_kwargs["cpu_threads"] == 4
    finally:
        PaddleOCRPDFReader._engine = None
        PaddleOCRPDFReader._engine_signature = None


def test_cpu_threads_are_bounded_and_configurable(monkeypatch):
    monkeypatch.delenv("PADDLEOCR_CPU_THREADS", raising=False)
    assert PaddleOCRPDFReader._configured_cpu_threads() == 10

    monkeypatch.setenv("PADDLEOCR_CPU_THREADS", "6")
    assert PaddleOCRPDFReader._configured_cpu_threads() == 6

    monkeypatch.setenv("PADDLEOCR_CPU_THREADS", "0")
    assert PaddleOCRPDFReader._configured_cpu_threads() == 1

    monkeypatch.setenv("PADDLEOCR_CPU_THREADS", "99")
    assert PaddleOCRPDFReader._configured_cpu_threads() == 32


def test_detection_side_limit_is_bounded_and_configurable(monkeypatch):
    monkeypatch.delenv("PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN", raising=False)
    assert PaddleOCRPDFReader._configured_detection_side_len() == 1600

    monkeypatch.setenv("PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN", "1200")
    assert PaddleOCRPDFReader._configured_detection_side_len() == 1200

    monkeypatch.setenv("PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN", "500")
    assert PaddleOCRPDFReader._configured_detection_side_len() == 960

    monkeypatch.setenv("PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN", "5000")
    assert PaddleOCRPDFReader._configured_detection_side_len() == 2400

    monkeypatch.setenv("PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN", "invalido")
    assert PaddleOCRPDFReader._configured_detection_side_len() == 1600


def test_read_page_limits_detector_by_max_side(monkeypatch):
    captured_kwargs = {}
    fake_array = SimpleNamespace(shape=(200, 100, 3))
    monkeypatch.setitem(
        sys.modules,
        "numpy",
        SimpleNamespace(asarray=lambda image: fake_array),
    )

    class FakeEngine:
        def predict(self, image, **kwargs):
            assert image.shape == (200, 100, 3)
            captured_kwargs.update(kwargs)
            return []

    words, page_text = PaddleOCRPDFReader._read_page(
        engine=FakeEngine(),
        image=Image.new("RGB", (100, 200)),
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
        text_det_limit_side_len=1200,
    )

    assert words == []
    assert page_text == ""
    assert captured_kwargs == {
        "text_det_limit_side_len": 1200,
        "text_det_limit_type": "max",
    }
