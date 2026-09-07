from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spec_collects_paddlex_dynamic_resources_and_metadata():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert 'for package in ("paddle", "paddleocr", "paddlex"):' in source
    assert "collect_all(package_name)" in source
    assert "copy_metadata" in source
    assert 'EXTRAS.get("ocr-core"' in source
    assert "_paddlex_ocr_metadata()" in source


def test_spec_uses_native_flet_startup_without_tcl_tk_splash():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "Splash(" not in source
    assert "full_tk=True" not in source
    assert "pyinstaller_splash_runtime.py" not in source
    assert "runtime_hooks=[]" in source


def test_desktop_entrypoint_validates_frozen_paddlex_dependencies_and_runtime():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert "--self-test-paddlex-pipeline" in source
    assert 'require_extra("ocr", obj_name="OCR", alt="ocr-core")' in source
    assert 'load_pipeline_config("OCR")' in source
    assert "--self-test-paddleocr-runtime" in source
    assert "PaddleOCRPDFReader._get_engine(**config)" in source
    assert "PaddleOCRPDFReader._read_page(" in source


def test_desktop_entrypoint_keeps_native_loading_feedback_and_window_icon():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert 'title=ft.Text("Cargando aplicación"' in source
    assert "ft.ProgressRing(width=28, height=28)" in source
    assert "ft.ProgressBar" in source
    assert "page.window.icon = str(icon_path)" in source
    assert "async def _desktop_main" in source
    assert 'await asyncio.to_thread(importlib.import_module, "main_flet")' in source
    assert "ft.run(_desktop_main)" in source
