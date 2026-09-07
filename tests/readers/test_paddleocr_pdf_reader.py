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


def test_model_directories_raise_when_no_local_model_is_resolvable(monkeypatch):
    monkeypatch.delenv(
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
        raising=False,
    )
    monkeypatch.delenv(
        "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR",
        raising=False,
    )
    monkeypatch.delenv("PADDLEOCR_MODEL_ROOT", raising=False)
    monkeypatch.setattr(
        PaddleOCRPDFReader,
        "_model_dir_candidates",
        classmethod(lambda cls, model_name: []),
    )

    with pytest.raises(PaddleOCRConfigurationError, match="No se encontró el modelo local"):
        PaddleOCRPDFReader._load_config()


def test_cached_paddlex_models_are_resolved_without_session_env(tmp_path, monkeypatch):
    detection = tmp_path / "PP-OCRv5_mobile_det"
    recognition = tmp_path / "latin_PP-OCRv5_mobile_rec"
    detection.mkdir()
    recognition.mkdir()

    monkeypatch.delenv("PADDLEOCR_TEXT_DETECTION_MODEL_DIR", raising=False)
    monkeypatch.delenv("PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR", raising=False)
    monkeypatch.delenv("PADDLEOCR_MODEL_ROOT", raising=False)
    monkeypatch.setattr(
        PaddleOCRPDFReader,
        "_model_dir_candidates",
        classmethod(lambda cls, model_name: [tmp_path / model_name]),
    )

    config = PaddleOCRPDFReader._load_config()

    assert config["detection_model_dir"] == str(detection.resolve())
    assert config["recognition_model_dir"] == str(recognition.resolve())


def test_explicit_invalid_model_path_does_not_silently_fallback(tmp_path, monkeypatch):
    cached = tmp_path / "PP-OCRv5_mobile_det"
    cached.mkdir()
    monkeypatch.setenv(
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
        str(tmp_path / "missing"),
    )
    monkeypatch.setattr(
        PaddleOCRPDFReader,
        "_model_dir_candidates",
        classmethod(lambda cls, model_name: [cached]),
    )

    with pytest.raises(PaddleOCRConfigurationError, match="ruta configurada"):
        PaddleOCRPDFReader._resolve_model_dir(
            "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
            "PP-OCRv5_mobile_det",
        )


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
    assert config["enable_mkldnn"] is True
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


def test_cpu_engine_uses_mkldnn_by_default(monkeypatch):
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
            enable_mkldnn=True,
            cpu_threads=10,
        )

        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "1"
        assert captured_kwargs["enable_mkldnn"] is True
        assert captured_kwargs["cpu_threads"] == 10
        assert captured_kwargs["device"] == "cpu"
        assert "lang" not in captured_kwargs
        assert "ocr_version" not in captured_kwargs
    finally:
        PaddleOCRPDFReader._engine = None
        PaddleOCRPDFReader._engine_signature = None


def test_engine_configuration_error_preserves_underlying_reason(monkeypatch):
    class FakePaddleOCR:
        def __init__(self, **kwargs):
            raise ValueError("modelo local incompatible")

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCR=FakePaddleOCR),
    )

    PaddleOCRPDFReader._engine = None
    PaddleOCRPDFReader._engine_signature = None

    try:
        with pytest.raises(
            PaddleOCRConfigurationError,
            match="ValueError: modelo local incompatible",
        ):
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


def _install_fake_numpy(monkeypatch):
    fake_array = SimpleNamespace(shape=(200, 100, 3))
    monkeypatch.setitem(
        sys.modules,
        "numpy",
        SimpleNamespace(asarray=lambda image: fake_array),
    )
    return fake_array


def test_backend_recovery_retries_notimplemented_without_mkldnn(monkeypatch):
    _install_fake_numpy(monkeypatch)

    class FastEngine:
        def predict(self, image, **kwargs):
            raise NotImplementedError("oneDNN kernel unavailable")

    class SafeEngine:
        def predict(self, image, **kwargs):
            return []

    safe_engine = SafeEngine()
    requested_configs = []

    def fake_get_engine(**config):
        requested_configs.append(config)
        assert config["enable_mkldnn"] is False
        return safe_engine

    monkeypatch.setattr(PaddleOCRPDFReader, "_get_engine", fake_get_engine)

    config = {
        "language": "es",
        "device": "cpu",
        "detection_model_name": "PP-OCRv5_mobile_det",
        "recognition_model_name": "latin_PP-OCRv5_mobile_rec",
        "detection_model_dir": "C:/modelos/det",
        "recognition_model_dir": "C:/modelos/rec",
        "enable_mkldnn": True,
        "cpu_threads": 10,
    }

    engine, words, page_text, recovered = PaddleOCRPDFReader._read_page_with_backend_recovery(
        engine=FastEngine(),
        config=config,
        image=Image.new("RGB", (100, 200)),
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
        text_det_limit_side_len=1200,
    )

    assert engine is safe_engine
    assert words == []
    assert page_text == ""
    assert recovered is True
    assert len(requested_configs) == 1


def test_backend_recovery_does_not_hide_unrelated_errors(monkeypatch):
    _install_fake_numpy(monkeypatch)

    class BrokenEngine:
        def predict(self, image, **kwargs):
            raise ValueError("bad input")

    config = {
        "enable_mkldnn": True,
    }

    with pytest.raises(ValueError, match="bad input"):
        PaddleOCRPDFReader._read_page_with_backend_recovery(
            engine=BrokenEngine(),
            config=config,
            image=Image.new("RGB", (100, 200)),
            logical_page=1,
            page_width=612.0,
            doctop_offset=0.0,
            text_det_limit_side_len=1200,
        )


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
    fake_array = _install_fake_numpy(monkeypatch)

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
    assert fake_array.shape == (200, 100, 3)
    assert captured_kwargs == {
        "text_det_limit_side_len": 1200,
        "text_det_limit_type": "max",
    }
