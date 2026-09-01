# tests/test_extract_otros_productos_words.py

from pathlib import Path

from readers.reader_manager import ReaderManager

from parsers.cetes.extractors.productos import (
    extract_otros_productos_words
)


ROOT = Path(__file__).resolve().parents[3]

PDF_PATH = ROOT / "data" / "12 Inversion Cetes_Jul25_OOMM851003HJCRLR08.pdf"



def main():

    print()
    print("=" * 60)
    print("PRUEBA PARSER OTROS PRODUCTOS CETES (WORDS)")
    print("=" * 60)


    print()
    print("PDF:")
    print(PDF_PATH)



    if not PDF_PATH.exists():

        raise FileNotFoundError(
            f"No existe el PDF: {PDF_PATH}"
        )



    # 1. Leer PDF usando el ReaderManager para obtener los words

    document = ReaderManager.read(PDF_PATH)

    spatial_words = document.spatial_words


    print()
    print("PALABRAS CON COORDENADAS EXTRAIDAS:")
    print(len(spatial_words))


    if not spatial_words:

        raise ValueError(
            "No se extrajeron palabras con coordenadas del PDF."
        )



    # 2. Ejecutar parser de Otros Productos

    otros_productos = extract_otros_productos_words(
        spatial_words
    )



    print()
    print("=" * 60)
    print("OTROS PRODUCTOS EXTRAÍDOS")
    print("=" * 60)



    print()
    print("-" * 60)


    print(
        "Contrato:",
        otros_productos.contrato
    )


    print(
        "Producto:",
        otros_productos.producto
    )


    print(
        "Tasa interés anual:",
        otros_productos.tasa_interes_anual
    )


    print(
        "GAT nominal anual:",
        otros_productos.gat_nominal_anual
    )


    print(
        "GAT real anual:",
        otros_productos.gat_real_anual
    )


    print(
        "Total comisiones:",
        otros_productos.total_comisiones
    )



    print()
    print("=" * 60)
    print("PRUEBA FINALIZADA")
    print("=" * 60)



if __name__ == "__main__":

    main()