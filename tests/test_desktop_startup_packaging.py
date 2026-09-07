from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_does_not_create_tcl_tk_splash():
    spec = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "Splash(" not in spec
    assert "pyinstaller_splash_runtime" not in spec
    assert "runtime_hooks=[]" in spec


def test_desktop_entrypoint_renders_native_progress_before_heavy_ui_import():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert "async def _desktop_main" in source
    assert 'ft.Text("Cargando aplicación"' in source
    assert "ft.ProgressBar" in source
    assert 'await asyncio.to_thread(importlib.import_module, "main_flet")' in source
    assert "await asyncio.sleep(0.08)" in source
