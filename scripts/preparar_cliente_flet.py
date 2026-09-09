from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path


EXPECTED_WINDOWS_ARTIFACT = "flet-windows.zip"
EXPECTED_WINDOWS_EXECUTABLE = "flet/flet.exe"


def _validate_client_root(client_root: Path) -> Path:
    """Valida la estructura que Flet Desktop espera dentro de su caché."""
    client_root = client_root.expanduser().resolve()
    executable = client_root / "flet" / "flet.exe"
    if not executable.is_file():
        raise RuntimeError(
            "El cliente Flet Desktop no contiene flet/flet.exe: "
            f"{client_root}"
        )
    return client_root


def build_windows_client_archive(
    client_root: str | Path,
    archive_path: str | Path,
) -> Path:
    """Empaqueta una caché Flet ya verificada con la estructura oficial."""
    source_root = _validate_client_root(Path(client_root))
    destination = Path(archive_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for item in sorted(source_root.rglob("*")):
                if not item.is_file():
                    continue
                archive.write(item, item.relative_to(source_root).as_posix())

        with zipfile.ZipFile(temporary, mode="r") as archive:
            normalized_names = {name.replace("\\", "/") for name in archive.namelist()}
            if EXPECTED_WINDOWS_EXECUTABLE not in normalized_names:
                raise RuntimeError(
                    "El archivo Flet preparado no contiene "
                    f"{EXPECTED_WINDOWS_EXECUTABLE}."
                )
            bad_member = archive.testzip()
            if bad_member is not None:
                raise RuntimeError(
                    f"El archivo Flet preparado está corrupto en: {bad_member}"
                )

        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return destination


def prepare_windows_client(destination_dir: str | Path) -> Path:
    """
    Prepara el cliente Flet exacto de la versión instalada para PyInstaller.

    ``flet_desktop.ensure_client_cached()`` usa primero la caché local. Sólo si
    esa caché no existe, Flet obtiene su cliente oficial desde GitHub Releases.
    La descarga, cuando hace falta, ocurre en la computadora de build; el EXE
    resultante recibirá este archivo y no necesitará Internet al arrancar.
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "El cliente portable Flet para Windows debe prepararse en Windows."
        )

    try:
        import flet_desktop
    except ImportError as exc:
        raise RuntimeError(
            "No está instalado flet-desktop. Instala primero el extra .[desktop]."
        ) from exc

    artifact_name = flet_desktop.get_artifact_filename()
    if artifact_name != EXPECTED_WINDOWS_ARTIFACT:
        raise RuntimeError(
            "Se esperaba el artefacto Flet para Windows "
            f"{EXPECTED_WINDOWS_ARTIFACT!r}, pero Flet resolvió {artifact_name!r}."
        )

    cache_root = _validate_client_root(
        Path(flet_desktop.ensure_client_cached())
    )

    destination_root = Path(destination_dir).expanduser().resolve()
    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    return build_windows_client_archive(
        cache_root,
        destination_root / artifact_name,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara el cliente Flet Desktop de Windows para incluirlo dentro "
            "del EXE portable PyInstaller."
        )
    )
    parser.add_argument(
        "--destino",
        required=True,
        help="Directorio de staging donde se escribirá flet-windows.zip.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    archive = prepare_windows_client(args.destino)
    print(f"Cliente Flet portable preparado: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
