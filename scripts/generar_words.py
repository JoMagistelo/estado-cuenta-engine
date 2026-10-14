"""Exporta las words nativas de los readers, sin procesamiento bancario."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from readers.paddleocr_pdf_reader import PaddleOCRPDFReader
from readers.pdf_word_reader import PDFWordReader


def _write_words(path: Path, words: list[dict]) -> None:
    """Serializar la lista intacta y reemplazar el JSON sólo si terminó bien."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix="words_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(words, handle, ensure_ascii=False, indent=2)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Genera JSON con las words originales de PDFWordReader y PaddleOCRPDFReader. "
            "Procesa todos los PDFs de la carpeta y sus subcarpetas."
        )
    )
    parser.add_argument("carpeta", type=Path, help="Carpeta que contiene los PDFs.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=PROJECT_ROOT / "output",
        help="Carpeta de salida; por defecto output en la raíz del proyecto.",
    )
    parser.add_argument(
        "--modo",
        choices=("ambos", "digital", "paddleocr"),
        default="ambos",
        help="Readers que se ejecutarán; por defecto ambos.",
    )
    args = parser.parse_args(argv)
    source = args.carpeta.expanduser().resolve()
    output = args.salida.expanduser().resolve()
    if not source.is_dir():
        print(f"ERROR: no existe la carpeta de PDFs: {source}", file=sys.stderr)
        return 2
    pdfs = sorted(
        (p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda p: p.relative_to(source).as_posix().casefold(),
    )
    if not pdfs:
        print(f"ERROR: la carpeta no contiene PDFs: {source}", file=sys.stderr)
        return 2

    exported = errors = skipped = 0
    for index, pdf in enumerate(pdfs, start=1):
        relative = pdf.relative_to(source)
        destination = output / relative.parent
        print(f"[{index}/{len(pdfs)}] {relative}", flush=True)
        for mode in ("digital", "paddleocr"):
            if args.modo not in ("ambos", mode):
                continue
            try:
                if mode == "digital":
                    words = PDFWordReader.read(pdf, start_page=0)
                    if not words:
                        skipped += 1
                        print("  digital: sin words extraíbles; se omite el JSON.", flush=True)
                        continue
                    suffix = "__readwords.json"
                else:
                    document = PaddleOCRPDFReader.read(pdf, start_page=0)
                    words = document.spatial_words
                    suffix = "__paddleocr_words.json"
                path = destination / f"{pdf.stem}{suffix}"
                _write_words(path, words)
                exported += 1
                print(f"  {mode}: {len(words)} words -> {path}", flush=True)
            except Exception as exc:
                errors += 1
                print(f"  ERROR {mode}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    print(f"Terminó: {exported} JSON, {skipped} lecturas digitales sin words, {errors} errores.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
