from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from readers.ocr_coordinate_export import write_coordinate_json
from readers.reader_manager import ReaderManager


def _default_output(pdf_path: Path, engine: str) -> Path:
    return (
        PROJECT_ROOT
        / "output"
        / "diagnostico_ocr"
        / f"{pdf_path.stem}_{engine}_coordenadas.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exporta palabras OCR y coordenadas espaciales a JSON para "
            "diagnóstico local de parsers. El JSON puede contener texto bancario."
        )
    )
    parser.add_argument("pdf", help="Ruta al PDF que se desea inspeccionar.")
    parser.add_argument(
        "--motor",
        choices=("tesseract", "paddleocr"),
        default="paddleocr",
        help="Reader OCR que se utilizará para generar las coordenadas.",
    )
    parser.add_argument(
        "--salida",
        help=(
            "Ruta del JSON de salida. Si se omite, se guarda en "
            "output/diagnostico_ocr/."
        ),
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=0,
        help="Página física inicial, usando índice base 0.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"ERROR: no existe el PDF indicado: {pdf_path}", file=sys.stderr)
        return 2

    start_page = max(int(args.start_page), 0)

    try:
        if args.motor == "tesseract":
            document = ReaderManager.read_ocr(
                pdf_path,
                start_page=start_page,
            )
        else:
            document = ReaderManager.read_paddle_ocr(
                pdf_path,
                start_page=start_page,
            )
    except Exception as exc:
        print(
            f"ERROR técnico ejecutando {args.motor}: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 3

    output_path = (
        Path(args.salida).expanduser()
        if args.salida
        else _default_output(pdf_path, args.motor)
    )

    destination = write_coordinate_json(
        document,
        engine=args.motor,
        source_name=pdf_path.name,
        output_path=output_path,
    )

    print("=== Coordenadas OCR exportadas ===")
    print(f"Motor: {args.motor}")
    print(f"Palabras: {len(document.spatial_words or [])}")
    print(f"JSON: {destination}")
    print(
        "Aviso: el JSON puede contener texto bancario; se guarda bajo output/ "
        "por defecto para mantenerlo fuera del control de versiones."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
