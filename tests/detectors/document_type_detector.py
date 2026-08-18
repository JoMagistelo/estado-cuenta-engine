from __future__ import annotations

from pathlib import Path

from readers.reader_manager import ReaderManager

from detectors.document_type_detector import (
    DocumentType,
    detect_document_type,
)

def pedir_pdfs() -> list[Path]:
    """
    Permite introducir múltiples rutas de PDFs.

    Se termina escribiendo una línea vacía.
    """

    print()
    print("=" * 70)
    print(" SELECCIÓN DE PDFs PARA PRUEBA DEL DETECTOR")
    print("=" * 70)

    print()
    print("Introduce la ruta completa de cada PDF.")
    print("Puedes introducir tantos como quieras.")
    print()
    print("Ejemplo:")
    print(
        r"C:\Proyectos\estado-cuenta-engine\data\edo_bbva.pdf"
    )
    print()
    print("Cuando termines, presiona ENTER sobre una línea vacía.")
    print()

    pdf_paths: list[Path] = []

    while True:

        ruta = input("PDF: ").strip()

        if not ruta:
            break

        # Permite copiar rutas entre comillas desde Windows.
        ruta = ruta.strip('"').strip("'")

        pdf_path = Path(ruta)

        if not pdf_path.exists():
            print()
            print(
                f"  [ERROR] No existe:"
            )
            print(
                f"  {pdf_path}"
            )
            print()
            continue

        if not pdf_path.is_file():
            print()
            print(
                f"  [ERROR] La ruta no es un archivo:"
            )
            print(
                f"  {pdf_path}"
            )
            print()
            continue

        if pdf_path.suffix.lower() != ".pdf":
            print()
            print(
                f"  [ERROR] El archivo no parece ser PDF:"
            )
            print(
                f"  {pdf_path}"
            )
            print()
            continue

        pdf_paths.append(
            pdf_path.resolve()
        )

        print(
            f"  [OK] Agregado: {pdf_path.name}"
        )

    return pdf_paths


def analizar_pdf(pdf_path: Path) -> None:
    """
    Lee un PDF mediante ReaderManager y ejecuta el detector.
    """

    print()
    print("-" * 70)
    print(f"PDF: {pdf_path.name}")
    print("-" * 70)

    print()
    print("Ruta:")
    print(pdf_path)

    try:

        # ====================================================
        # READER MANAGER
        # ====================================================

        print()
        print("Leyendo PDF...")

        document = ReaderManager.read(
            pdf_path
        )

        # ====================================================
        # INFORMACIÓN DE EXTRACCIÓN
        # ====================================================

        raw_text = getattr(
            document,
            "raw_text",
            ""
        )

        spatial_words = getattr(
            document,
            "spatial_words",
            []
        )

        print()
        print("EXTRACCIÓN")
        print("-" * 70)

        print(
            "Caracteres raw_text:",
            len(raw_text)
            if isinstance(raw_text, str)
            else 0
        )

        print(
            "Spatial words:",
            len(spatial_words)
            if spatial_words
            else 0
        )

        # ====================================================
        # MOSTRAR MUESTRA DE RAW TEXT
        # ====================================================

        if isinstance(raw_text, str) and raw_text.strip():

            muestra = raw_text.strip()

            if len(muestra) > 300:
                muestra = muestra[:300] + "..."

            print()
            print("MUESTRA RAW TEXT")
            print("-" * 70)
            print(muestra)

        else:

            print()
            print("MUESTRA RAW TEXT")
            print("-" * 70)
            print("[SIN TEXTO]")

        # ====================================================
        # MUESTRA SPATIAL WORDS
        # ====================================================

        if spatial_words:

            print()
            print("PRIMERAS 10 SPATIAL WORDS")
            print("-" * 70)

            for word in spatial_words[:10]:

                if isinstance(word, dict):

                    print(
                        repr(
                            word.get(
                                "text",
                                ""
                            )
                        )
                    )

                else:

                    print(
                        repr(word)
                    )

        # ====================================================
        # DETECTOR
        # ====================================================

        document_type = detect_document_type(
            document
        )

        print()
        print("=" * 70)

        print(
            "RESULTADO DEL DETECTOR"
        )

        print("=" * 70)

        print()

        print(
            "Tipo detectado:",
            document_type.value
        )

        print()

        if document_type == DocumentType.PDF_DIGITAL:

            print(
                ">>> PDF DIGITAL"
            )

            print(
                ">>> El texto extraído parece utilizable."
            )

            print(
                ">>> Puede continuar con el procesamiento normal."
            )

        elif document_type == DocumentType.PDF_IMAGEN:

            print(
                ">>> PDF IMAGEN / TEXTO NO UTILIZABLE"
            )

            print(
                ">>> Debe enviarse al flujo OCR."
            )

        print()

    except Exception as exc:

        print()
        print("=" * 70)
        print("ERROR PROCESANDO PDF")
        print("=" * 70)

        print()
        print(
            type(exc).__name__,
            ":",
            exc
        )

        print()


def main():

    print()
    print("=" * 70)
    print(" TEST DEL DETECTOR DE DOCUMENTOS")
    print("=" * 70)

    pdf_paths = pedir_pdfs()

    if not pdf_paths:

        print()
        print(
            "No se seleccionaron PDFs."
        )

        return

    print()
    print("=" * 70)
    print(
        f" PDFs SELECCIONADOS: {len(pdf_paths)}"
    )
    print("=" * 70)

    for index, pdf_path in enumerate(
        pdf_paths,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(pdf_paths)}]"
        )

        analizar_pdf(
            pdf_path
        )

    # ========================================================
    # RESUMEN FINAL
    # ========================================================

    print()
    print()
    print("=" * 70)
    print(" TEST FINALIZADO")
    print("=" * 70)

    print()


if __name__ == "__main__":
    main()