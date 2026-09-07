from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spec_collects_paddlex_dynamic_resources():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert 'for package in ("paddle", "paddleocr", "paddlex"):' in source
    assert "collect_all(package_name)" in source


def test_spec_uses_full_tk_for_institutional_splash():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "full_tk=True" in source
    assert "minify_script=False" in source
    assert "pyinstaller_splash_runtime.py" in source


def test_desktop_entrypoint_exposes_frozen_paddlex_self_test():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert "--self-test-paddlex-pipeline" in source
    assert 'load_pipeline_config("OCR")' in source
