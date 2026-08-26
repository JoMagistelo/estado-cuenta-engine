from __future__ import annotations

import json
from pathlib import Path

from readers.pdf_text_reader import PDFTextReader


def test_spatial_extraction():
    ruta_pdf = "data/12.1_Nómina_Banorte_dic_23.pdf"

    print("\n========================================================")
    print(" 🛠️ TEST PDF WORD READER (RAW)")
    print("========================================================\n")

    pdf_path = Path(ruta_pdf)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {ruta_pdf}"
        )

    print(f"Leyendo documento: {ruta_pdf}...\n")

    # ===========================
    # SOLO EL READER
    # ===========================
    spatial_words = PDFTextReader.read(pdf_path)

    print(f"Total de palabras: {len(spatial_words)}")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    ruta_json = output_dir / f"{pdf_path.stem}_raw_text.json"

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(
            spatial_words,
            f,
            indent=4,
            ensure_ascii=False
        )

    print("\nPrimeras 10 palabras:\n")

    for word in spatial_words[:10]:
        print(word)

    print(f"\nJSON guardado en:\n{ruta_json}")

    print("\n========================================================")
    print(" TEST FINALIZADO")
    print("========================================================\n")


if __name__ == "__main__":
    test_spatial_extraction()