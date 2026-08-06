from engine.pipeline import process_bank_statements
from mappers.estado_cuenta_tables import estado_cuenta_to_tables

pdfs = [
    "data/estado_bbva.pdf",
    "data/estado_bbva2.pdf"
]

results = process_bank_statements(pdfs)

print("\nRESULTADOS:", len(results))

for i, r in enumerate(results):

    print("\n=========================")
    print("RESULTADO", i + 1)
    print("=========================")

    print(r)

    print()

    print(r.estado_cuenta)

    print()

    print(r.estado_cuenta.datos_cuenta)

    print()

    print(r.estado_cuenta.otros_productos)

    print()

    print(r.estado_cuenta.resumen_financiero)

    print()

    print("MOVIMIENTOS:", len(r.estado_cuenta.movimientos))


print("\n=========================")

mappers = estado_cuenta_to_tables(results)

print("\nTABLAS")

for nombre, filas in mappers.items():

    print()

    print(nombre)

    print("filas:", len(filas))

    if filas:

        print("columnas:", len(filas[0]))

        print(filas[0])

    else:

        print("VACIA")