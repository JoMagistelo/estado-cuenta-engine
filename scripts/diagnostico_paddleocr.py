from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from detectors.bank_detector import identify_bank_key
from engine.statement_processor import process_single_statement
from readers.reader_manager import ReaderManager
from validators.movimiento_validator import validar_movimientos


def _bool_text(value) -> str:
    if value is True:
        return "sí"
    if value is False:
        return "no"
    return "no aplica"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta un diagnóstico técnico del fallback OCR sin imprimir "
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

        estado, selected_document = process_single_statement(
            document=tesseract_document,
            bank_key=bank_key,
        )
    except Exception as exc:
        print(
            f"ERROR técnico durante el diagnóstico: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 4

    final_validations = []
    if estado.movimientos and estado.resumen_financiero:
        try:
            final_validations = validar_movimientos(
                movimientos=estado.movimientos,
                resumen=estado.resumen_financiero,
            )
        except Exception:
            final_validations = []

    metadata = selected_document.metadata or {}
    final_failed = sum(
        1 for validation in final_validations if not validation.correcto
    )

    print("=== Diagnóstico OCR controlado ===")
    print(f"Banco detectado: {bank_key}")
    print("OCR primario: tesseract")
    print(f"OCR seleccionado: {metadata.get('reader', 'desconocido')}")
    print(
        "Fallback PaddleOCR intentado: "
        f"{_bool_text(metadata.get('paddle_fallback_attempted'))}"
    )
    print(
        "PaddleOCR seleccionado: "
        f"{_bool_text(metadata.get('paddle_fallback_selected'))}"
    )

    if "tesseract_validation_total" in metadata:
        print(
            "Validaciones Tesseract: "
            f"{metadata.get('tesseract_validation_total', 0)} total / "
            f"{metadata.get('tesseract_validation_failed', 0)} fallidas"
        )

    if "paddle_validation_total" in metadata:
        print(
            "Validaciones PaddleOCR: "
            f"{metadata.get('paddle_validation_total', 0)} total / "
            f"{metadata.get('paddle_validation_failed', 0)} fallidas"
        )

    if metadata.get("paddle_fallback_error_type"):
        print(
            "Error técnico PaddleOCR: "
            f"{metadata['paddle_fallback_error_type']}"
        )

    if metadata.get("paddle_fallback_skipped"):
        print(
            "Fallback omitido por: "
            f"{metadata['paddle_fallback_skipped']}"
        )

    print(
        "Validaciones del resultado final: "
        f"{len(final_validations)} total / {final_failed} fallidas"
    )
    print("No se imprimieron datos personales ni valores financieros.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
