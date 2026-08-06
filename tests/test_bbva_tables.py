from __future__ import annotations

from pathlib import Path

from readers.reader_manager import ReaderManager
from utils.text_normalizer import normalize_text

from parsers.bbva.extractors.tables_parser import extract_bbva_tables


def test_bbva_tables():
    ruta_pdf = "data/estado_bbva2.pdf"

    print("\n================================")
    print(" PRUEBA PARSER TABLAS BBVA")
    print("================================\n")


    if not Path(ruta_pdf).exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_pdf}")

    document = ReaderManager.read(ruta_pdf)

    print(f"Tablas encontradas: {len(document.tables)}")
    assert document.tables, "ReaderManager no devolvió tablas"


    text = normalize_text(document.raw_text)

    resultado = extract_bbva_tables(
        tables=document.tables,
        text=text,
    )

    assert "datos_cuenta" in resultado
    assert "resumen_financiero" in resultado
    assert "otros_productos" in resultado

    datos = resultado["datos_cuenta"]
    resumen = resultado["resumen_financiero"]
    otros = resultado["otros_productos"]

    print("\n====== DATOS CUENTA ======")
    print(datos)

    print("\n====== RESUMEN ======")
    print(resumen)

    print("\n====== OTROS PRODUCTOS ======")
    print(otros)

    assert datos.numero_cuenta is not None
    assert datos.numero_cliente is not None
    assert datos.clabe is not None

    assert resumen.dias_periodo > 0
    assert resumen.saldo_final >= 0

    print("\n================================")
    print(" TEST FINALIZADO CORRECTAMENTE")
    print("================================\n")


if __name__ == "__main__":
    test_bbva_tables()