from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_release_is_versioned_as_3_0():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    flet_source = (ROOT / "app" / "main_flet.py").read_text(encoding="utf-8")
    spec = (ROOT / "EstadoCuentaEngine.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows_release.ps1").read_text(
        encoding="utf-8"
    )

    assert 'version = "3.0"' in pyproject
    assert "APP_VERSION = '3.0'" in flet_source
    assert "APP_VERSION = (3, 0, 0, 0)" in spec
    assert '[string]$Version = "3.0"' in build_script
