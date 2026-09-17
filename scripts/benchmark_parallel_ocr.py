"""Benchmark aislado: mismo pipeline bancario, varios procesos independientes.

No modifica el engine, los readers, los parsers, la interfaz ni el portable.
Ejecutar desde un entorno Python con los mismos modelos locales del build.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def collect_pdf_paths(inputs: list[str]) -> list[str]:
    """Expande directorios, ordena los PDF y evita procesar duplicados."""
    found: list[Path] = []
    seen: set[str] = set()
    for item in inputs:
        path = Path(item).expanduser().resolve()
        if path.is_file() and path.suffix.casefold() == ".pdf":
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(
                (p for p in path.iterdir() if p.is_file() and p.suffix.casefold() == ".pdf"),
                key=lambda p: p.name.casefold(),
            )
        else:
            raise ValueError("Cada entrada debe ser un PDF o un directorio existente.")
        for candidate in candidates:
            key = os.path.normcase(str(candidate))
            if key not in seen:
                seen.add(key)
                found.append(candidate)
    if not found:
        raise ValueError("No se encontraron archivos PDF para la prueba.")
    return [str(path) for path in found]


def _process_all(paths: list[str], engine: str, artifact_dir: str) -> list[Any]:
    """Ejecuta el pipeline original dentro de un proceso sin cambiarlo."""
    from engine.pipeline import process_bank_statements

    return process_bank_statements(
        paths,
        ocr_primary_engine=engine,
        ocr_artifact_dir=artifact_dir,
    )


def _process_one(path: str, engine: str, artifact_dir: str) -> Any:
    """Trabajo ejecutado en un proceso hijo: reutiliza su motor entre tareas."""
    return _process_all([path], engine, artifact_dir)[0]


def run_serial(paths: list[str], engine: str, artifact_dir: str) -> tuple[list[Any], float]:
    """Referencia en proceso exclusivo: libera sus modelos antes de probar paralelo."""
    start = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=multiprocessing.get_context("spawn"),
    ) as pool:
        results = pool.submit(_process_all, paths, engine, artifact_dir).result()
    return results, time.perf_counter() - start


def run_parallel(
    paths: list[str], engine: str, artifact_dir: str, workers: int
) -> tuple[list[Any], float]:
    """Un PDF por tarea; cada hijo reutiliza su propio PaddleOCR entre tareas."""
    ordered: list[Any] = [None] * len(paths)
    start = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=min(workers, len(paths)),
        mp_context=multiprocessing.get_context("spawn"),
    ) as pool:
        futures = {
            pool.submit(_process_one, path, engine, artifact_dir): index
            for index, path in enumerate(paths)
        }
        for future in as_completed(futures):
            ordered[futures[future]] = future.result()
    return ordered, time.perf_counter() - start


def compare_results(serial: list[Any], parallel: list[Any]) -> list[int]:
    """Compara salida funcional y palabras del PDF OCR verificado, sin exponer datos."""
    from readers.ocr_searchable_pdf import OCR_LAYER_TAG
    from readers.pdf_word_reader import PDFWordReader

    if len(serial) != len(parallel):
        return list(range(1, max(len(serial), len(parallel)) + 1))

    fields = (
        "file_name", "bank_key", "estado_cuenta", "raw_text", "normalized_text",
        "validaciones", "processing_method", "debug", "ocr_review", "ocr_engine",
        "ocr_requested_primary_engine", "ocr_primary_engine", "ocr_secondary_engine",
        "fallback_attempted", "fallback_used", "source_pdf_path", "ocr_reprocessed",
    )
    different: list[int] = []
    for index, (first, second) in enumerate(zip(serial, parallel), start=1):
        if any(getattr(first, field, None) != getattr(second, field, None) for field in fields):
            different.append(index)
            continue
        left = getattr(first, "ocr_artifacts", {}) or {}
        right = getattr(second, "ocr_artifacts", {}) or {}
        if set(left) != set(right):
            different.append(index)
            continue
        # Las rutas y los bytes del contenedor PDF pueden variar por nombres
        # temporales; se compara la capa OCR canónica que realmente lee el parser.
        for engine in left:
            left_words = PDFWordReader.read(left[engine], layer_tag=OCR_LAYER_TAG)
            right_words = PDFWordReader.read(right[engine], layer_tag=OCR_LAYER_TAG)
            if left_words != right_words:
                different.append(index)
                break
    return different


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prueba CPU multiproceso con el mismo pipeline OCR, sin cambiar el EXE."
    )
    parser.add_argument("pdfs", nargs="+", help="PDF individuales o carpeta con PDF.")
    parser.add_argument("--workers", type=int, default=2, help="Procesos OCR (predeterminado: 2).")
    parser.add_argument("--engine", choices=("paddleocr", "tesseract"), default="paddleocr")
    parser.add_argument("--model-root", type=Path, help="Carpeta LOCAL con los modelos PaddleOCR.")
    parser.add_argument("--cpu-threads", type=int, help="Hilos por motor, igual en ambas pruebas.")
    parser.add_argument(
        "--parallel-only", action="store_true",
        help="Mide sólo el paralelo; no comprueba equivalencia con la referencia.",
    )
    parser.add_argument("--report", type=Path, help="Guarda métricas agregadas en JSON, sin datos bancarios.")
    args = parser.parse_args(argv)

    try:
        paths = collect_pdf_paths(args.pdfs)
        if args.workers < 1 or args.workers > 16:
            raise ValueError("--workers debe estar entre 1 y 16.")
        if args.cpu_threads is not None and not 1 <= args.cpu_threads <= 32:
            raise ValueError("--cpu-threads debe estar entre 1 y 32.")
        if args.model_root is not None:
            root = args.model_root.expanduser().resolve()
            if not root.is_dir():
                raise ValueError("--model-root debe apuntar a una carpeta existente.")
            os.environ["PADDLEOCR_MODEL_ROOT"] = str(root)
        if args.cpu_threads is not None:
            os.environ["PADDLEOCR_CPU_THREADS"] = str(args.cpu_threads)
    except ValueError as exc:
        parser.error(str(exc))

    # Ningún proceso debe consultar servicios de modelos externos.
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    workers = min(args.workers, len(paths))
    print(f"Documentos: {len(paths)} | motor: {args.engine} | procesos: {workers}")
    print("El informe no imprime nombres, texto OCR, cuentas ni importes.")

    try:
        with tempfile.TemporaryDirectory(prefix="ece_ocr_benchmark_") as tmp:
            base = Path(tmp)
            serial_results: list[Any] | None = None
            serial_seconds: float | None = None
            if not args.parallel_only:
                serial_dir = base / "serial"
                serial_dir.mkdir()
                serial_results, serial_seconds = run_serial(paths, args.engine, str(serial_dir))
                print(f"Secuencial: {serial_seconds:.1f} s")

            parallel_dir = base / "parallel"
            parallel_dir.mkdir()
            parallel_results, parallel_seconds = run_parallel(
                paths, args.engine, str(parallel_dir), workers
            )
            print(f"Paralelo: {parallel_seconds:.1f} s")

            different: list[int] | None = None
            if serial_results is not None:
                different = compare_results(serial_results, parallel_results)
                print(
                    "Equivalencia funcional y espacial: "
                    + ("OK" if not different else f"NO ({len(different)} documentos diferentes)")
                )

            reduction = (
                100.0 * (1.0 - parallel_seconds / serial_seconds)
                if serial_seconds and serial_seconds > 0 else None
            )
            if reduction is not None:
                print(f"Reducción del tiempo: {reduction:.1f}% | objetivo >= 50%: "
                      f"{'SÍ' if reduction >= 50 else 'NO'}")
            report = {
                "document_count": len(paths),
                "ocr_engine": args.engine,
                "workers": workers,
                "threads_per_worker": os.getenv("PADDLEOCR_CPU_THREADS", "10 (predeterminado)"),
                "sequential_seconds": serial_seconds,
                "parallel_seconds": parallel_seconds,
                "reduction_percent": reduction,
                "target_50_percent_met": reduction >= 50 if reduction is not None else None,
                "equivalent": not different if different is not None else None,
                "different_document_indices": different,
            }
            if args.report:
                output = args.report.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            return 2 if different else 0
    except Exception as exc:
        # No mostrar str(exc): algunos errores internos pueden incluir texto o rutas bancarias.
        print(f"La prueba no terminó: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
