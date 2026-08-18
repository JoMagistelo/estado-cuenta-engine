from engine.pipeline import process_bank_statements


pdfs = [
    "data/estado_bbva.pdf",
    "data/estado_bbva2.pdf"
]


results = process_bank_statements(
    pdfs
)


for r in results:
    print(
        r.file_name,
        r.bank_key,
        r.estado_cuenta.datos_cuenta.nombre_cliente
    )