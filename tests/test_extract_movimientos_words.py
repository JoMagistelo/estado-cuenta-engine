from pathlib import Path

from readers.reader_manager import ReaderManager
from parsers.bbva.extractors.movimientos_words import extract_movimientos_words



ROOT = Path(__file__).resolve().parent.parent


PDF_PATH = ROOT / "data" / "estado_bbva2.pdf"



def main():

    print()
    print("=" * 60)
    print("PRUEBA PARSER MOVIMIENTOS BBVA (WORDS)")
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
        raise ValueError("No se extrajeron palabras con coordenadas del PDF.")



    # 2. Ejecutar nuevo parser de words

    movimientos = extract_movimientos_words(
        spatial_words
    )



    print()
    print("=" * 60)
    print("TOTAL MOVIMIENTOS:")
    print(len(movimientos))
    print("=" * 60)



    for index, mov in enumerate(
        movimientos,
        start=1
    ):


        print()
        print("-" * 60)

        print(
            f"MOVIMIENTO {index}"
        )


        print(
            "Fecha operación:",
            mov.fecha_operacion
        )


        print(
            "Fecha liquidación:",
            mov.fecha_liquidacion
        )


        print(
            "Concepto:"
        )

        print(
            mov.concepto[:200]
        )


        print(
            "Referencia:",
            mov.referencia
        )


        print(
            "RFC:",
            mov.rfc
        )


        print(
            "Autorización:",
            mov.autorizacion
        )


        print(
            "Hora:",
            mov.hora_operacion
        )


        print(
            "Cargo:",
            mov.cargo
        )


        print(
            "Abono:",
            mov.abono
        )


        print(
            "Saldo operación:",
            mov.saldo_operacion
        )


        print(
            "Saldo liquidación:",
            mov.saldo_liquidacion
        )




if __name__ == "__main__":

    main()