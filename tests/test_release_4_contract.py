from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_4_2_0_across_app_package_and_windows_build():
    main_desktop = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")
    main_flet = (ROOT / "app" / "main_flet.py").read_text(encoding="utf-8")
    main_streamlit = (ROOT / "app" / "main_streamlit.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    spec = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows_release.ps1").read_text(
        encoding="utf-8"
    )

    assert 'RELEASE_VERSION = "4.2.0"' in main_desktop
    assert "ui.APP_VERSION = RELEASE_VERSION" in main_desktop
    assert "APP_VERSION = '4.2.0'" in main_flet
    assert "APP_VERSION = '4.2.0'" in main_streamlit
    assert 'version = "4.2.0"' in pyproject
    assert "APP_VERSION = (4, 2, 0, 0)" in spec
    assert '[string]$Version = "4.2.0"' in build_script
    assert '"--self-test-parallel-runtime"' in build_script


def test_parallel_settings_use_plain_language_and_recommended_defaults():
    source = (ROOT / "app" / "main_flet_parallel.py").read_text(encoding="utf-8")
    settings_block = source.split("def show_combined_settings", 1)[1].split(
        "config_button.on_click", 1
    )[0]

    assert 'performance = {"enabled": True, "workers": MAX_OCR_WORKERS}' in source
    assert "PaddleOCR · recomendado por mayor precisión" in settings_block
    assert "Tesseract · alternativa si PaddleOCR falla" in settings_block
    assert "Velocidad {value}/8" in settings_block
    assert "Mantén 8/8 para obtener el mejor rendimiento" in settings_block
    assert "hilos de CPU" not in settings_block
    assert "procesamiento OCR paralelo (experimental)" not in settings_block


def test_information_modal_explains_scanned_pdfs_without_ocr_jargon():
    source = (ROOT / "app" / "main_flet.py").read_text(encoding="utf-8")
    help_block = source.split("def show_help(e=None):", 1)[1].split(
        "def clear_loading_dialog_refs()", 1
    )[0]

    assert "Lectura de PDFs escaneados" in help_block
    assert "PDF escaneado con texto seleccionable" in help_block
    assert "capa de texto añadida" in help_block
    assert "seleccionar, copiar y buscar texto" in help_block
    assert "Bancos y tipos de estado de cuenta habilitados" in help_block
    assert "Tipos admitidos" in help_block
    assert "Motor OCR activo" not in help_block
    assert "PDF OCR y reprocesado" not in help_block
    assert "Escaneado (OCR)" not in help_block
