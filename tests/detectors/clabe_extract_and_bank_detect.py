"""
Script de prueba para validar la extracción de CLABE
y la detección del banco mediante su prefijo CLABE.

Flujo:

    PDF
      ↓
    ReaderManager.read()
      ↓
    document.raw_text
      ↓
    extract_clabes()
      ↓
    CLABE
      ↓
    prefijo = CLABE[:3]
      ↓
    CLABE_PREFIX_TO_BANK
      ↓
    Banco detectado

IMPORTANTE:

La CLABE se extrae UNA SOLA VEZ.

No se utiliza:

    extract_clabe_prefixes(text)

ni:

    detect_by_clabe(text)

porque ambas funciones vuelven a ejecutar
la extracción de CLABE internamente.

Los tiempos no incluyen los print(), solamente
el procesamiento que se desea medir.
"""

from pathlib import Path
from time import perf_counter

from readers.pdf_text_reader import PDFTextReader
from extractors.clabe_extractor import extract_clabes
from detectors.clabe_detector import CLABE_PREFIX_TO_BANK


# ============================================================
# RUTA DEL PROYECTO
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PDF_PATHS = [
    ROOT / "data" / "estado_bbva.pdf",
    ROOT / "data" / "bbva_libreton_nomina.pdf",
    ROOT / "data" / "bbva_libreton_basico.pdf",
    ROOT / "data" / "bbva_libreton_premium.pdf",
]


# ============================================================
# ANÁLISIS DE UN PDF
# ============================================================

def analizar_pdf(pdf_path: Path):

    print()
    print("-" * 60)
    print("📄 PDF:")
    print(pdf_path)

    # ========================================================
    # INICIO DEL TIEMPO TOTAL DE PROCESAMIENTO
    # ========================================================
    #
    # A partir de aquí solamente medimos procesamiento,
    # no salida por consola.
    #

    total_start_time = perf_counter()

    # ========================================================
    # 1. TEXT READER
    # ========================================================

    read_start_time = perf_counter()

    reader = PDFTextReader()
    text = reader.read(pdf_path)

    read_duration = perf_counter() - read_start_time

    print("✅ PDF leído correctamente.")

    # ========================================================
    # 2. EXTRACCIÓN DE CLABE
    # ========================================================

    extract_start_time = perf_counter()

    clabes = extract_clabes(text)

    extract_duration = perf_counter() - extract_start_time

    print()
    print("--- 🔑 EXTRACCIÓN DE CLABE ---")
    print()

    if clabes:

        print("✅ CLABE extraída con éxito.")
        print(f"Cantidad de CLABEs encontradas: {len(clabes)}")

        for i, clabe in enumerate(clabes, start=1):
            print(f"CLABE #{i}: {clabe}")

    else:

        print("❌ No se encontró ninguna CLABE.")

    # ========================================================
    # 3. OBTENER PREFIJO
    # ========================================================
    #
    # IMPORTANTE:
    #
    # Aquí NO volvemos a llamar extract_clabes().
    #
    # La CLABE ya fue extraída.
    #

    prefix_start_time = perf_counter()

    prefixes = [
        clabe[:3]
        for clabe in clabes
    ]

    prefix_duration = perf_counter() - prefix_start_time

    print()
    print("--- 🏦 PREFIJOS CLABE ---")
    print()

    if prefixes:

        for i, prefix in enumerate(prefixes, start=1):
            print(f"CLABE #{i}: {prefix}")

    else:

        print("❌ No se pudieron obtener prefijos.")

    # ========================================================
    # 4. DETECTAR BANCO
    # ========================================================
    #
    # NO hacemos:
    #
    #     detect_by_clabe(text)
    #
    # porque eso volvería a ejecutar:
    #
    #     extract_clabe_prefixes(text)
    #
    # y después:
    #
    #     extract_clabes(text)
    #
    # Aquí solamente hacemos el lookup del prefijo
    # ya obtenido.
    #

    detect_start_time = perf_counter()

    bancos_encontrados = []

    for prefix in prefixes:

        bank_key = CLABE_PREFIX_TO_BANK.get(prefix)

        if bank_key:
            bancos_encontrados.append(bank_key)

    detect_duration = perf_counter() - detect_start_time

    print()
    print("--- 🏦 BANCO DETECTADO ---")
    print()

    if prefixes:

        for i, prefix in enumerate(prefixes, start=1):

            bank_key = CLABE_PREFIX_TO_BANK.get(prefix)

            print(f"CLABE #{i}:")
            print(f"  - Prefijo: {prefix}")

            if bank_key:
                print(f"  - Banco:   {bank_key}")
            else:
                print("  - Banco:   Desconocido")

    else:

        print("❌ No hay CLABE para detectar banco.")

    # ========================================================
    # FIN DEL TIEMPO TOTAL DE PROCESAMIENTO
    # ========================================================

    total_duration = perf_counter() - total_start_time

    # ========================================================
    # 5. TIEMPOS
    # ========================================================

    print()
    print("--- ⏱️ TIEMPOS ---")

    print(
        f"TextReader:           "
        f"{read_duration:.6f} s"
    )

    print(
        f"Extracción CLABE:     "
        f"{extract_duration:.6f} s"
    )

    print(
        f"Prefijo CLABE:        "
        f"{prefix_duration:.6f} s"
    )

    print(
        f"Detección banco:      "
        f"{detect_duration:.6f} s"
    )

    print("-" * 28)

    print(
        f"TOTAL PROCESAMIENTO:  "
        f"{total_duration:.6f} s"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("PRUEBA EXTRACCIÓN CLABE — DETECCIÓN DE BANCO")
    print("=" * 60)

    print()
    print(f"Se analizarán {len(PDF_PATHS)} archivos PDF.")

    for i, pdf_path in enumerate(PDF_PATHS, start=1):

        print()
        print("=" * 60)
        print(f"PROCESANDO ARCHIVO {i}/{len(PDF_PATHS)}")
        print("=" * 60)

        analizar_pdf(pdf_path)

    print()
    print("=" * 60)
    print("✨ Prueba finalizada para todos los archivos.")
    print("=" * 60)
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()