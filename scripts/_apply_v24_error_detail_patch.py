from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


reader = Path("src/readers/paddleocr_pdf_reader.py")
text = reader.read_text(encoding="utf-8")
text = replace_once(
    text,
    """            except Exception as exc:\n                raise PaddleOCRConfigurationError(\n                    \"No se pudo inicializar PaddleOCR con los modelos locales \"\n                    \"configurados.\"\n                ) from exc\n""",
    """            except Exception as exc:\n                detail = str(exc).strip()\n                if detail:\n                    detail = f\"{type(exc).__name__}: {detail[:300]}\"\n                else:\n                    detail = type(exc).__name__\n                raise PaddleOCRConfigurationError(\n                    \"No se pudo inicializar PaddleOCR con los modelos locales \"\n                    f\"configurados. Causa: {detail}.\"\n                ) from exc\n""",
    "preserve Paddle constructor error",
)
reader.write_text(text, encoding="utf-8")


tests = Path("tests/readers/test_paddleocr_pdf_reader.py")
text = tests.read_text(encoding="utf-8")
marker = """def test_cpu_engine_can_enable_mkldnn_explicitly(monkeypatch):\n"""
new_test = """def test_engine_configuration_error_preserves_underlying_reason(monkeypatch):\n    class FakePaddleOCR:\n        def __init__(self, **kwargs):\n            raise ValueError(\"modelo local incompatible\")\n\n    monkeypatch.setitem(\n        sys.modules,\n        \"paddleocr\",\n        SimpleNamespace(PaddleOCR=FakePaddleOCR),\n    )\n\n    PaddleOCRPDFReader._engine = None\n    PaddleOCRPDFReader._engine_signature = None\n\n    try:\n        with pytest.raises(\n            PaddleOCRConfigurationError,\n            match=\"ValueError: modelo local incompatible\",\n        ):\n            PaddleOCRPDFReader._get_engine(\n                language=\"es\",\n                device=\"cpu\",\n                detection_model_name=\"PP-OCRv5_mobile_det\",\n                recognition_model_name=\"latin_PP-OCRv5_mobile_rec\",\n                detection_model_dir=\"C:/modelos/det\",\n                recognition_model_dir=\"C:/modelos/rec\",\n                enable_mkldnn=False,\n                cpu_threads=10,\n            )\n    finally:\n        PaddleOCRPDFReader._engine = None\n        PaddleOCRPDFReader._engine_signature = None\n\n\n"""
text = replace_once(text, marker, new_test + marker, "Paddle constructor error regression")
tests.write_text(text, encoding="utf-8")


docs = Path("docs/14_paddleocr_fallback.md")
text = docs.read_text(encoding="utf-8")
text = replace_once(
    text,
    '$env:PADDLEOCR_ENABLE_MKLDNN = "1"',
    '$env:PADDLEOCR_ENABLE_MKLDNN = "0"',
    "stable MKLDNN example",
)
docs.write_text(text, encoding="utf-8")
