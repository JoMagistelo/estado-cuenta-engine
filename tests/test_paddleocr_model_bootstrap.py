from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preparar_modelos_paddleocr.py"
SPEC = importlib.util.spec_from_file_location("preparar_modelos_paddleocr", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def _create_model_tree(root: Path, model_name: str, marker: bytes) -> Path:
    model_dir = root / model_name
    model_dir.mkdir(parents=True)
    (model_dir / "inference.pdiparams").write_bytes(marker)
    (model_dir / "inference.json").write_text("{}", encoding="utf-8")
    return model_dir


def test_prepare_models_copies_existing_local_models_without_network(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    for index, model_name in enumerate(bootstrap.MODEL_NAMES, start=1):
        _create_model_tree(source_root, model_name, f"model-{index}".encode())

    def unexpected_download(*args, **kwargs):
        raise AssertionError("No debía intentar una descarga")

    monkeypatch.setattr(bootstrap, "_download_official_model", unexpected_download)

    result = bootstrap.prepare_models(
        destination_root=destination_root,
        local_source_root=source_root,
        source="bos",
        allow_downloads=False,
        force=False,
        run_inference=False,
    )

    assert result == destination_root.resolve()
    for model_name in bootstrap.MODEL_NAMES:
        assert (destination_root / model_name / "inference.pdiparams").is_file()

    manifest = json.loads(
        (destination_root / "paddleocr-models-manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["models"]) == set(bootstrap.MODEL_NAMES)
    assert manifest["network_downloads_during_statement_processing"] is False
    assert all(manifest["models"][name]["files"] >= 2 for name in bootstrap.MODEL_NAMES)


def test_prepare_models_downloads_only_missing_model(tmp_path, monkeypatch):
    destination_root = tmp_path / "destination"
    cached_root = tmp_path / "cache"
    first, second = bootstrap.MODEL_NAMES
    _create_model_tree(destination_root, first, b"already-installed")
    downloaded = _create_model_tree(cached_root, second, b"downloaded")
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        bootstrap,
        "_find_existing_model",
        lambda model_name, local_source_root: None,
    )

    def fake_download(model_name: str, source: str):
        calls.append((model_name, source))
        assert model_name == second
        return downloaded

    monkeypatch.setattr(bootstrap, "_download_official_model", fake_download)

    bootstrap.prepare_models(
        destination_root=destination_root,
        local_source_root=None,
        source="bos",
        allow_downloads=True,
        force=False,
        run_inference=False,
    )

    assert calls == [(second, "bos")]
    assert (destination_root / second / "inference.pdiparams").read_bytes() == b"downloaded"
