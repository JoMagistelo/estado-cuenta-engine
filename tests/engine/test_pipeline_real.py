from engine.pipeline import process_bank_statements


pdfs = [
    "data/edo_banamex2.pdf"
]


resultados = process_bank_statements(
    pdfs
)


print("======================")
print("RESULTADOS")
print("======================")


print(
    len(resultados)
)


for resultado in resultados:

    print(
        "BANCO:",
        resultado.bank_key
    )

    print(
        "CLIENTE:",
        resultado.estado_cuenta.datos_cuenta.nombre_cliente
    )

    print(
        "CLABE:",
        resultado.estado_cuenta.datos_cuenta.clabe
    )