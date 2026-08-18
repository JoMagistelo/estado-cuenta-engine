"""
Script de prueba para validar la consistencia financiera de los movimientos
extraídos contra el resumen financiero de un estado de cuenta BBVA.

Este test utiliza exclusivamente extracción basada en WORDS
(coordenadas espaciales del PDF).

Flujo:
    PDF
      ↓
    ReaderManager
      ↓
    spatial_words
      ↓
    ├── extract_movimientos_words()
    └── extract_resumen_financiero_words()
      ↓
    validar_movimientos()
"""

from pathlib import Path

# ============================================================
# RUTA DEL PROYECTO
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PDF_PATH = ROOT / "data" / "edo_banamex2.pdf"


# ============================================================
# IMPORTACIONES
# ============================================================

from readers.reader_manager import ReaderManager

from parsers.banamex.extractors.movimientos import (
    extract_movimientos_words,
)

from parsers.banamex.extractors.resumen import (
    extract_resumen_financiero_words,
)

from validators import validar_movimientos


# ============================================================
# MAIN
# ============================================================

def main():
    """
    Ejecuta el proceso completo de extracción y validación
    utilizando exclusivamente spatial_words.
    """

    print("=" * 60)
    print("PRUEBA VALIDACIÓN FINANCIERA BBVA — WORDS")
    print("=" * 60)
    print()
    print(f"📄 PDF:")
    print(PDF_PATH)
    print()

    # ========================================================
    # 1. LEER EL PDF
    # ========================================================
    #
    # ReaderManager obtiene las palabras con sus coordenadas.
    #
    # NO utilizamos:
    #   - document.raw_text
    #   - normalize_text()
    #   - document.tables
    #
    # Todo el test trabaja exclusivamente con spatial_words.
    # ========================================================

    document = ReaderManager.read(PDF_PATH)

    spatial_words = document.spatial_words

    print(f"✅ Palabras espaciales extraídas: {len(spatial_words)}")
    print()

    # ========================================================
    # 2. EXTRAER MOVIMIENTOS
    # ========================================================
    #
    # Extractor basado exclusivamente en coordenadas espaciales.
    # ========================================================

    movimientos = extract_movimientos_words(
        spatial_words
    )

    print(f"✅ Movimientos extraídos: {len(movimientos)}")
    print()

    # ========================================================
    # 3. EXTRAER RESUMEN FINANCIERO
    # ========================================================
    #
    # IMPORTANTE:
    # Este extractor también trabaja exclusivamente con
    # spatial_words y coordenadas.
    #
    # Ya NO se utiliza:
    #   normalize_text()
    #   document.raw_text
    #   regex sobre texto completo
    # ========================================================

    resumen = extract_resumen_financiero_words(
        spatial_words
    )

    print("✅ Resumen financiero extraído.")
    print()

    # ========================================================
    # 4. VALIDACIÓN CRUZADA
    # ========================================================

    resultados = validar_movimientos(
        movimientos,
        resumen,
    )

    print()
    print("--- 📊 RESULTADOS DE VALIDACIÓN FINANCIERA ---")
    print()

    # ========================================================
    # 5. MOSTRAR RESULTADOS
    # ========================================================

    for r in resultados:

        print("=" * 60)

        print(f"Validación: {r.nombre}")

        if r.esperado is not None:
            print(f"  - Esperado:  {r.esperado:,.2f}")
        else:
            print("  - Esperado:  N/A")

        if r.obtenido is not None:
            print(f"  - Obtenido:  {r.obtenido:,.2f}")
        else:
            print("  - Obtenido:  N/A")

        if r.diferencia is not None:
            print(f"  - Diferencia: {r.diferencia:,.2f}")
        else:
            print("  - Diferencia: N/A")

        print(
            f"  - Correcto:  {'Sí' if r.correcto else 'No'}"
        )

        print("-" * 60)

    print()
    print("✨ Proceso de validación finalizado.")
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()