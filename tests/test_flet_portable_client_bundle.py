from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from preparar_cliente_flet import build_windows_client_archive


def test_build_windows_client_archive_preserves_expected_flet_layout(tmp_path: Path):
    client_root = tmp_path / "cache"
    flet_dir = client_root / "flet"
    flet_dir.mkdir(parents=True)
    (flet_dir / "flet.exe").write_bytes(b"fake-flet-exe")
    (flet_dir / "flutter_windows.dll").write_bytes(b"fake-runtime")

    archive_path = tmp_path / "staging" / "flet-windows.zip"
    result = build_windows_client_archive(client_root, archive_path)

    assert result == archive_path.resolve()
    assert result.is_file()

    with zipfile.ZipFile(result, mode="r") as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert "flet/flet.exe" in names
        assert "flet/flutter_windows.dll" in names
        assert archive.testzip() is None


def test_build_windows_client_archive_rejects_incomplete_cache(tmp_path: Path):
    incomplete_root = tmp_path / "cache"
    incomplete_root.mkdir()

    with pytest.raises(RuntimeError, match="flet/flet.exe"):
        build_windows_client_archive(
            incomplete_root,
            tmp_path / "flet-windows.zip",
        )
