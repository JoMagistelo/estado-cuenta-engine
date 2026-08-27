from pathlib import Path

from readers.reader_manager import ReaderManager
from parsers.hsbc.extractors.datos import extract_datos_cuenta_words


ROOT = Path(__file__).resolve().parents[3]

PDF_PATH = ROOT / "data" / "edo_hsbc.pdf"


def main():

    print()
    print("=" * 60)
    print("PRUEBA PARSER DATOS CUENTA HSBC (OCR)")
    print("=" * 60)

    print()
    print("PDF:")
    print(PDF_PATH)

    if not PDF_PATH.exists():

        raise FileNotFoundError(
            f"No existe el PDF: {PDF_PATH}"
        )

    # ========================================================
    # 1. LEER PDF MEDIANTE TESSERACT OCR
    # ========================================================
    #
    # ReaderManager.read_ocr() obtiene un DocumentData
    # cuyo spatial_words proviene directamente de
    # TesseractPDFReader.
    # ========================================================

    document = ReaderManager.read_ocr(
        PDF_PATH
    )

    spatial_words = document.spatial_words

    print()
    print("PALABRAS CON COORDENADAS EXTRAÍDAS POR OCR:")
    print(len(spatial_words))

    if not spatial_words:

        raise ValueError(
            "Tesseract no extrajo palabras con coordenadas del PDF."
        )

    # ========================================================
    # 2. EJECUTAR EXTRACTOR
    # ========================================================

    datos_cuenta = extract_datos_cuenta_words(
        spatial_words
    )

    # ========================================================
    # 3. MOSTRAR RESULTADOS
    # ========================================================

    print()
    print("=" * 60)
    print("DATOS DE CUENTA EXTRAÍDOS")
    print("=" * 60)

    print()
    print("-" * 60)

    print(
        "Producto principal:",
        datos_cuenta.producto_principal
    )

    print(
        "Periodo inicio:",
        datos_cuenta.periodo_inicio
    )

    print(
        "Periodo fin:",
        datos_cuenta.periodo_fin
    )

    print(
        "Fecha de corte:",
        datos_cuenta.fecha_corte
    )

    print(
        "Número de cuenta:",
        datos_cuenta.numero_cuenta
    )

    print(
        "Número de cliente:",
        datos_cuenta.numero_cliente
    )

    print(
        "RFC:",
        datos_cuenta.rfc
    )

    print(
        "CLABE:",
        datos_cuenta.clabe
    )

    print(
        "Nombre del cliente:",
        datos_cuenta.nombre_cliente
    )

    print()
    print("=" * 60)
    print("PRUEBA FINALIZADA")
    print("=" * 60)


if __name__ == "__main__":

    main()