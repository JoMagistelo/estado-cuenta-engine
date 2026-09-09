from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spec_can_embed_paddle_models_inside_one_file():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "PADDLEOCR_BUNDLE_ROOT" in source
    assert '"models/paddleocr"' in source
    assert "_bundled_paddle_model_datas()" in source


def test_spec_can_embed_flet_desktop_client_inside_one_file():
    source = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")

    assert "FLET_DESKTOP_BUNDLE_ARCHIVE" in source
    assert '"flet_desktop/app"' in source
    assert '"flet-windows.zip"' in source
    assert "_bundled_flet_client_datas()" in source


def test_release_script_has_strict_portable_offline_profile():
    source = (ROOT / "scripts" / "build_windows_release.ps1").read_text(encoding="utf-8")

    assert "[switch]$PortableOffline" in source
    assert "PADDLEOCR_BUNDLE_ROOT" in source
    assert "--self-test-portable-paddleocr-runtime" in source
    assert "--sin-descargas" in source
    assert "-PortableOffline" in source


def test_release_script_embeds_and_verifies_flet_client():
    source = (ROOT / "scripts" / "build_windows_release.ps1").read_text(encoding="utf-8")

    assert "preparar_cliente_flet.py" in source
    assert "FLET_DESKTOP_BUNDLE_ARCHIVE" in source
    assert "flet_desktop/app/flet-windows.zip" in source
    assert "CArchiveReader" in source


def test_desktop_launcher_forces_embedded_models_and_offline_runtime():
    source = (ROOT / "app" / "main_desktop.py").read_text(encoding="utf-8")

    assert '"models" / "paddleocr"' in source
    assert 'os.environ["PADDLEOCR_MODEL_ROOT"]' in source
    assert 'os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"' in source
    assert 'os.environ["HF_HUB_OFFLINE"] = "1"' in source
    assert 'os.environ["TRANSFORMERS_OFFLINE"] = "1"' in source
    assert "--self-test-portable-paddleocr-runtime" in source


def test_streamlit_disables_usage_telemetry():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    assert "[browser]" in config
    assert "gatherUsageStats = false" in config
