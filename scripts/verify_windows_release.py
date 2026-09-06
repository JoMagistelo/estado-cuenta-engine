"""Verifica el ejecutable Windows antes de entregarlo a TIC.

La validación comprueba formato PE, calcula SHA-256 y rechaza identificadores
específicos del repositorio de desarrollo que no deben aparecer en el artefacto
distribuible. No elimina ni bloquea atribuciones legítimas de terceros.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FORBIDDEN_MARKERS = (
    "github.com/JoMagistelo",
    "githubusercontent.com/JoMagistelo",
    "JoMagistelo",
    "estado-cuenta-engine",
)


def _contains_marker(payload: bytes, marker: str) -> bool:
    variants = (marker, marker.lower(), marker.upper())
    encodings = tuple(
        encoded
        for variant in variants
        for encoded in (
            variant.encode("utf-8"),
            variant.encode("utf-16-le"),
        )
    )
    return any(encoded in payload for encoded in encodings)


def verify_executable(exe_path: Path) -> dict[str, object]:
    payload = exe_path.read_bytes()
    if not payload.startswith(b"MZ"):
        raise ValueError(f"{exe_path} no parece un ejecutable PE de Windows.")

    found = [marker for marker in FORBIDDEN_MARKERS if _contains_marker(payload, marker)]
    if found:
        joined = ", ".join(found)
        raise ValueError(
            "El ejecutable contiene identificadores propios del repositorio de desarrollo: "
            f"{joined}"
        )

    return {
        "file": exe_path.name,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "project_repository_markers": "none_detected",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--version", default="2.3.0")
    args = parser.parse_args()

    exe_path = args.exe.resolve()
    if not exe_path.is_file():
        raise FileNotFoundError(exe_path)

    output_dir = (args.output_dir or exe_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = verify_executable(exe_path)
    manifest["product"] = "Extractor de Movimientos Financieros"
    manifest["version"] = args.version

    sha_path = output_dir / "Extractor_de_Movimientos_Financieros.sha256.txt"
    sha_path.write_text(
        f"{manifest['sha256']}  {exe_path.name}\n",
        encoding="ascii",
    )

    manifest_path = output_dir / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
