"""Diagnóstico local opt-in: compara el pipeline Flet estándar con el paralelo.

No imprime datos bancarios ni sube archivos. Para aislar memoria, el estándar
corre primero en un hijo que termina antes de levantar los motores paralelos.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmark_parallel_ocr import collect_pdf_paths, compare_results  # noqa: E402


def _run_standard(paths: list[str], engine: str, artifact_dir: str):
    """Mismo generador incremental que usa el botón Procesar estándar."""
    from engine.pipeline import process_bank_statements_incremental

    results = [None] * len(paths)
    failed: list[int] = []
    for event in process_bank_statements_incremental(
        paths,
        ocr_primary_engine=engine,
        ocr_artifact_dir=artifact_dir,
    ):
        if event.kind == "completed":
            results[event.index] = event.result
        elif event.kind in {"error", "cancelled"}:
            failed.append(event.index + 1)
    return results, sorted(set(failed))


def _run_parallel(paths: list[str], engine: str, artifact_dir: str, workers: int):
    """Mismo generador que emplea la entrada Flet experimental."""
    from engine.parallel_ocr_pipeline import process_bank_statements_parallel_incremental

    results = [None] * len(paths)
    failed: list[int] = []
    for event in process_bank_statements_parallel_incremental(
        paths,
        ocr_primary_engine=engine,
        ocr_artifact_dir=artifact_dir,
        ocr_workers=workers,
    ):
        if event.kind == "completed":
            results[event.index] = event.result
        elif event.kind in {"error", "cancelled"}:
            failed.append(event.index + 1)
    return results, sorted(set(failed))


def _difference_categories(first, second) -> list[str]:
    """Categorías de discrepancia, nunca valores de cuentas ni OCR."""
    from readers.ocr_searchable_pdf import OCR_LAYER_TAG
    from readers.pdf_word_reader import PDFWordReader

    if first is None or second is None:
        return ["documento_sin_resultado"]
    categories: list[str] = []
    if (first.raw_text, first.normalized_text) != (second.raw_text, second.normalized_text):
        categories.append("texto_ocr")
    if first.bank_key != second.bank_key:
        categories.append("banco")
    if first.estado_cuenta != second.estado_cuenta:
        categories.append("datos_o_movimientos")
    if first.validaciones != second.validaciones:
        categories.append("validaciones")
    left = first.ocr_artifacts or {}
    right = second.ocr_artifacts or {}
    if set(left) != set(right):
        categories.append("artefactos_ocr")
    for engine in set(left) & set(right):
        if PDFWordReader.read(left[engine], layer_tag=OCR_LAYER_TAG) != PDFWordReader.read(
            right[engine], layer_tag=OCR_LAYER_TAG
        ):
            categories.append("palabras_y_coordenadas_pdf")
            break
    if compare_results([first], [second]) and not categories:
        categories.append("otros_metadatos")
    return categories


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba datos y coordenadas Flet estándar/paralelo en el mismo PDF."
    )
    parser.add_argument("pdfs", nargs="+", help="PDF problemático o carpeta de PDF.")
    parser.add_argument("--engine", choices=("paddleocr", "tesseract"), default="paddleocr")
    parser.add_argument("--workers", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument("--report", type=Path, help="JSON local sin datos financieros.")
    args = parser.parse_args(argv)
    try:
        paths = collect_pdf_paths(args.pdfs)
    except ValueError as exc:
        parser.error(str(exc))

    # Heredadas por ambos modos sin fuentes de modelos externas.
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    print(f"Comparación local de {len(paths)} PDF | motor idéntico: {args.engine}")
    try:
        with tempfile.TemporaryDirectory(prefix="ece_compare_flet_") as temp:
            serial_dir = Path(temp) / "standard"
            parallel_dir = Path(temp) / "parallel"
            serial_dir.mkdir()
            parallel_dir.mkdir()
            started = time.perf_counter()
            # No mantener un tercer motor PaddleOCR cargado al iniciar paralelo.
            with ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn")
            ) as pool:
                baseline, baseline_failed = pool.submit(
                    _run_standard, paths, args.engine, str(serial_dir)
                ).result()
            standard_seconds = time.perf_counter() - started
            print(f"Estándar: {standard_seconds:.1f} s")
            started = time.perf_counter()
            parallel, parallel_failed = _run_parallel(
                paths, args.engine, str(parallel_dir), args.workers
            )
            parallel_seconds = time.perf_counter() - started
            print(f"Paralelo: {parallel_seconds:.1f} s")

            differences: list[dict] = []
            for index, (left, right) in enumerate(zip(baseline, parallel), start=1):
                categories = _difference_categories(left, right)
                if categories:
                    differences.append({"index": index, "categories": categories})
            if baseline_failed or parallel_failed:
                print("Hay archivos con errores; revisar índices en el JSON.")
            print(
                "Equivalencia funcional y espacial: "
                + ("OK" if not differences and not baseline_failed and not parallel_failed
                   else "NO; conservar modo estándar")
            )
            report = {
                "document_count": len(paths),
                "ocr_engine_both_modes": args.engine,
                "parallel_workers": args.workers,
                "standard_seconds": standard_seconds,
                "parallel_seconds": parallel_seconds,
                "standard_error_indices": baseline_failed,
                "parallel_error_indices": parallel_failed,
                "standard_ocr_without_bank_data_indices": [
                    index for index, result in enumerate(baseline, 1)
                    if result is not None and result.estado_cuenta is None
                ],
                "parallel_ocr_without_bank_data_indices": [
                    index for index, result in enumerate(parallel, 1)
                    if result is not None and result.estado_cuenta is None
                ],
                "differences": differences,
                "equivalent": not differences and not baseline_failed and not parallel_failed,
            }
            if args.report:
                output = args.report.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print("Informe JSON local guardado.")
            return 0 if report["equivalent"] else 2
    except Exception as exc:
        # El detalle técnico de excepciones puede contener rutas privadas;
        # no se copia al informe ni se imprime en este diagnóstico.
        print(f"Falló el diagnóstico ({type(exc).__name__}); no se validó equivalencia.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
