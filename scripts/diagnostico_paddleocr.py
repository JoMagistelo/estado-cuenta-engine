from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from detectors.bank_detector import identify_bank_key
from engine.statement_processor import process_single_statement_with_ocr_review
from readers.reader_manager import ReaderManager


def _engine_label(engine: str | None) -> str:
    labels = {
        "tesseract": "Tesseract",
        "paddleocr": "PaddleOCR",
    }
    normalized = str(engine or "").strip().lower()
    return labels.get(normalized, normalized or "desconocido")


def _print_candidate(candidate) -> None:
    print(
        f"{_engine_label(candidate.engine)}: "
        f"{candidate.movement_count} movimientos / "
        f"{candidate.validation_total} validaciones / "
        f"{candidate.validation_failed} fallidas"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta un diagnóstico técnico de Tesseract/PaddleOCR sin imprimir "
            "contenido financiero ni datos personales."
        )
    )
    parser.add_argument("pdf", help="Ruta al estado de cuenta PDF a evaluar.")
    parser.add_argument(
        "--nombre",
        help=(
            "Nombre lógico del archivo para detección bancaria. "
            "Si se omite, se usa el nombre del PDF."
        ),
    )
    parser.add_argument(
        "--motor",
        choices=("recomendado", "tesseract", "paddleocr"),
        default="recomendado",
        help=(
            "Motor cuya salida se considera seleccionada para el diagnóstico. "
            "Por defecto se utiliza la recomendación automática."
        ),
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"ERROR: no existe el PDF indicado: {pdf_path}", file=sys.stderr)
        return 2

    visible_name = args.nombre or pdf_path.name

    try:
        tesseract_document = ReaderManager.read_ocr(pdf_path, start_page=0)
        bank_key = identify_bank_key(
            raw_text=tesseract_document.raw_text,
            file_name=visible_name,
        )
        if not bank_key:
            print("ERROR: no se pudo identificar el banco.", file=sys.stderr)
            return 3

        _, _, review = process_single_statement_with_ocr_review(
            document=tesseract_document,
            bank_key=bank_key,
        )
    except Exception as exc:
        print(
            f"ERROR técnico durante el diagnóstico: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 4

    print("=== Diagnóstico OCR controlado ===")
    print(f"Banco detectado: {bank_key}")
    print("OCR primario: Tesseract")

    if review is None:
        print("Segundo OCR: no requerido o no habilitado")
        print("Resultado seleccionado: Tesseract")
        print("No se imprimieron datos personales ni valores financieros.")
        return 0

    if review.trigger_reasons:
        print("Motivos de revisión: " + ", ".join(review.trigger_reasons))

    for engine in review.available_engines():
        _print_candidate(review.get_candidate(engine))

    print(
        "Recomendación automática: "
        f"{_engine_label(review.recommended_engine)}"
    )

    if review.paddle_error_type:
        print(
            "PaddleOCR no produjo candidato: "
            f"{review.paddle_error_type}"
        )

    requested_engine = (
        review.recommended_engine
        if args.motor == "recomendado"
        else args.motor
    )

    if requested_engine not in review.available_engines():
        print(
            f"ERROR: {_engine_label(requested_engine)} no está disponible "
            "para este documento.",
            file=sys.stderr,
        )
        return 5

    selected = review.select(requested_engine)
    print(f"Resultado seleccionado: {_engine_label(selected.engine)}")
    print(
        "Resultado seleccionado: "
        f"{selected.movement_count} movimientos / "
        f"{selected.validation_total} validaciones / "
        f"{selected.validation_failed} fallidas"
    )
    print("No se imprimieron datos personales ni valores financieros.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
