from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_does_not_create_tcl_tk_splash():
    spec = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "Splash(" not in spec
    assert "pyinstaller_splash_runtime" not in spec
    assert "runtime_hooks=[]" in spec


def test_pyinstaller_spec_includes_dynamically_loaded_main_flet():
    spec = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    # main_desktop usa importlib.import_module("main_flet"). PyInstaller no
    # descubre ese import dinámico durante Analysis, así que debe declararse.
    assert 'extra_hiddenimports = ["main_flet"]' in spec
    assert "hiddenimports=extra_hiddenimports" in spec


def test_desktop_extra_installs_flet_desktop_client():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    # El portable no debe intentar instalar flet-desktop al primer arranque.
    assert '"flet[desktop]>=0.86.5,<0.87"' in pyproject


def test_desktop_entrypoint_renders_professional_startup_before_heavy_ui_import():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert "async def _desktop_main" in source
    assert "STARTUP_WIDTH = 680" in source
    assert "STARTUP_HEIGHT = 420" in source
    assert "page.window.resizable = False" in source
    assert "page.window.maximizable = False" in source
    assert "page.window.always_on_top = True" in source
    assert "page.window.progress_bar = 0.08" in source
    assert "await page.window.center()" in source
    assert "page.window.visible = True" in source
    assert "ft.ProgressBar" in source
    assert "ft.ProgressRing(" in source
    assert 'await asyncio.to_thread(importlib.import_module, "main_flet")' in source
    assert "page.controls.clear()" in source
    assert "_prepare_main_window(page)" in source
    assert "await _show_startup_error(page, ex)" in source
    assert "ft.AppView.FLET_APP_HIDDEN" in source
    assert "ft.AlertDialog" not in source
