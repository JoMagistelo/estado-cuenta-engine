from __future__ import annotations

from pathlib import Path

from readers.reader_manager import ReaderManager



def test_pdf_table_reader():


    ruta_pdf = "data/estado_bbva2.pdf"



    print("\n================================")
    print(" TEST PDF TABLE READER")
    print("================================\n")



    # ---------------------------------------
    # 1. Validar archivo
    # ---------------------------------------

    if not Path(ruta_pdf).exists():

        raise FileNotFoundError(
            f"No existe el archivo: {ruta_pdf}"
        )



    # ---------------------------------------
    # 2. Leer documento completo
    # ---------------------------------------

    document = ReaderManager.read(
        ruta_pdf
    )



    tables = document.tables



    print(
        f"Tablas encontradas: {len(tables)}"
    )



    # ---------------------------------------
    # 3. Validaciones básicas
    # ---------------------------------------

    assert tables, (
        "PDFTableReader no devolvió tablas"
    )


    assert isinstance(
        tables,
        list
    )


    assert isinstance(
        tables[0],
        list
    )



    # ---------------------------------------
    # 4. Mostrar tablas crudas
    # ---------------------------------------

    for index, table in enumerate(
        tables[:5]
    ):


        print("\n================================")
        print(
            f"TABLA {index + 1}"
        )
        print(
            f"Filas: {len(table)}"
        )
        print("================================")


        for row in table[:10]:

            print(row)



    # ---------------------------------------
    # 5. Verificar que NO fue limpiada
    # ---------------------------------------

    tabla_texto = str(
        tables[0]
    )


    print("\n================================")
    print("MUESTRA CRUDA")
    print("================================")

    print(
        tabla_texto[:500]
    )



    print("\n================================")
    print(" TEST FINALIZADO CORRECTAMENTE")
    print("================================\n")




if __name__ == "__main__":

    test_pdf_table_reader()