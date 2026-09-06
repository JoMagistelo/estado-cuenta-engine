from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from readers.paddleocr_pdf_reader import PaddleOCRPDFReader


MODEL_NAMES = (
    PaddleOCRPDFReader.DEFAULT_DETECTION_MODEL_NAME,
    PaddleOCRPDFReader.DEFAULT_RECOGNITION_MODEL_NAME,
)
ALLOWED_SOURCES = ("huggingface", "aistudio", "bos", "modelscope")


def _default_destination() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "EstadoCuentaEngine" / "PaddleOCR"
    return Path.home() / ".local" / "share" / "EstadoCuentaEngine" / "PaddleOCR"


def _is_usable_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        return any(item.is_file() for item in path.rglob("*"))
    except OSError:
        return False


def _candidate_sources(model_name: str, local_source_root: Path | None) -> Iterable[Path]:
    if local_source_root is not None:
        yield local_source_root / model_name

    for candidate in PaddleOCRPDFReader._model_dir_candidates(model_name):
        yield candidate


def _find_existing_model(model_name: str, local_source_root: Path | None) -> Path | None:
    seen: set[str] = set()
    for candidate in _candidate_sources(model_name, local_source_root):
        key = str(candidate.expanduser()).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _is_usable_model_dir(candidate):
            return candidate.expanduser().resolve()
    return None


def _download_official_model(model_name: str, source: str) -> Path:
    previous_source = os.environ.get("PADDLE_PDX_MODEL_SOURCE")
    previous_disable = os.environ.get("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK")

    os.environ["PADDLE_PDX_MODEL_SOURCE"] = source
    os.environ.pop("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", None)

    try:
        try:
            from paddlex import create_model
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PaddleX/PaddleOCR no está instalado. Ejecuta primero: "
                'python -m pip install -e ".[desktop,paddleocr]"'
            ) from exc

        print(f"Preparando modelo oficial {model_name} desde {source}...")
        model = create_model(model_name=model_name)
        del model
    finally:
        if previous_source is None:
            os.environ.pop("PADDLE_PDX_MODEL_SOURCE", None)
        else:
            os.environ["PADDLE_PDX_MODEL_SOURCE"] = previous_source

        if previous_disable is None:
            os.environ.pop("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", None)
        else:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = previous_disable

    cache_dir = Path.home() / ".paddlex" / "official_models" / model_name
    if not _is_usable_model_dir(cache_dir):
        raise RuntimeError(
            f"PaddleX terminó sin dejar un modelo utilizable en {cache_dir}."
        )
    return cache_dir.resolve()


def _copy_model(source: Path, destination: Path, *, force: bool) -> None:
    if source.resolve() == destination.resolve():
        return

    if destination.exists() and force:
        shutil.rmtree(destination)

    if _is_usable_model_dir(destination) and not force:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _directory_digest(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0

    for item in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: str(p).lower()):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                total_bytes += len(chunk)
        file_count += 1

    return digest.hexdigest(), file_count, total_bytes


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _write_manifest(destination_root: Path, source_label: str) -> Path:
    models: dict[str, dict[str, object]] = {}
    for model_name in MODEL_NAMES:
        model_dir = destination_root / model_name
        sha256, files, size_bytes = _directory_digest(model_dir)
        models[model_name] = {
            "relative_path": model_name,
            "sha256_tree": sha256,
            "files": files,
            "size_bytes": size_bytes,
        }

    payload = {
        "schema_version": 1,
        "source": source_label,
        "network_downloads_during_statement_processing": False,
        "models": models,
        "runtime": {
            "paddlepaddle": _package_version("paddlepaddle"),
            "paddleocr": _package_version("paddleocr"),
            "paddlex": _package_version("paddlex"),
        },
    }

    manifest_path = destination_root / "paddleocr-models-manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _verify_reader_configuration(destination_root: Path, *, run_inference: bool) -> None:
    managed_vars = {
        "PADDLEOCR_TEXT_DETECTION_MODEL_DIR": None,
        "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR": None,
        "PADDLEOCR_MODEL_ROOT": str(destination_root),
        "PADDLEOCR_ENABLE_MKLDNN": "0",
        "PADDLEOCR_LANG": "es",
    }
    previous = {name: os.environ.get(name) for name in managed_vars}

    for name, value in managed_vars.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    PaddleOCRPDFReader._engine = None
    PaddleOCRPDFReader._engine_signature = None

    try:
        config = PaddleOCRPDFReader._load_config()
        if not run_inference:
            return

        engine = PaddleOCRPDFReader._get_engine(**config)

        from PIL import Image, ImageDraw

        image = Image.new("RGB", (720, 220), "white")
        draw = ImageDraw.Draw(image)
        draw.text((24, 80), "PRUEBA OCR 1234567890", fill="black")
        PaddleOCRPDFReader._read_page(
            engine=engine,
            image=image,
            logical_page=1,
            page_width=612.0,
            doctop_offset=0.0,
            text_det_limit_side_len=1200,
        )
    finally:
        PaddleOCRPDFReader._engine = None
        PaddleOCRPDFReader._engine_signature = None
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def prepare_models(
    *,
    destination_root: Path,
    local_source_root: Path | None,
    source: str,
    allow_downloads: bool,
    force: bool,
    run_inference: bool,
) -> Path:
    destination_root = destination_root.expanduser().resolve()
    local_source_root = (
        local_source_root.expanduser().resolve()
        if local_source_root is not None
        else None
    )

    destination_root.mkdir(parents=True, exist_ok=True)
    used_download = False

    for model_name in MODEL_NAMES:
        destination = destination_root / model_name
        if _is_usable_model_dir(destination) and not force:
            print(f"OK {model_name}: ya está instalado.")
            continue

        source_dir = _find_existing_model(model_name, local_source_root)
        if source_dir is None:
            if not allow_downloads:
                raise RuntimeError(
                    f"No se encontró {model_name} localmente y las descargas están deshabilitadas."
                )
            source_dir = _download_official_model(model_name, source)
            used_download = True

        _copy_model(source_dir, destination, force=force)
        if not _is_usable_model_dir(destination):
            raise RuntimeError(f"El modelo {model_name} quedó incompleto en {destination}.")
        print(f"OK {model_name}: instalado en {destination}")

    _verify_reader_configuration(destination_root, run_inference=run_inference)
    if run_inference:
        print("OK Inferencia PaddleOCR real: el engine local ejecutó predict().")
    else:
        print("OK Configuración PaddleOCR: el reader resolvió ambos modelos locales.")

    source_label = source if used_download else "local"
    manifest_path = _write_manifest(destination_root, source_label)
    print(f"Manifest: {manifest_path}")
    return destination_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara los dos modelos locales usados por Estado Cuenta Engine. "
            "La descarga, cuando se permite, ocurre sólo durante este bootstrap; "
            "el reader de estados de cuenta continúa sin descargar modelos en runtime."
        )
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=_default_destination(),
        help=(
            "Raíz donde se instalarán los modelos. Por defecto usa "
            "%LOCALAPPDATA%\\EstadoCuentaEngine\\PaddleOCR en Windows."
        ),
    )
    parser.add_argument(
        "--origen-local",
        type=Path,
        help="Raíz opcional que ya contiene las carpetas de ambos modelos.",
    )
    parser.add_argument(
        "--fuente",
        choices=ALLOWED_SOURCES,
        default="bos",
        help="Fuente oficial preferida por PaddleX cuando haga falta descargar.",
    )
    parser.add_argument(
        "--sin-descargas",
        action="store_true",
        help="Falla si los modelos no están ya disponibles localmente.",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reemplaza las carpetas de modelo existentes en el destino.",
    )
    parser.add_argument(
        "--probar-inferencia",
        action="store_true",
        help=(
            "Después de preparar los modelos, inicializa PaddleOCR y ejecuta una "
            "inferencia sintética sin datos bancarios."
        ),
    )
    args = parser.parse_args()

    try:
        destination = prepare_models(
            destination_root=args.destino,
            local_source_root=args.origen_local,
            source=args.fuente,
            allow_downloads=not args.sin_descargas,
            force=args.forzar,
            run_inference=args.probar_inferencia,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("PaddleOCR preparado correctamente.")
    print(f"PADDLEOCR_MODEL_ROOT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
