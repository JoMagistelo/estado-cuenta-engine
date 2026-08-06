from engine.pipeline import process_bank_statements
from exporters.excel.batch_exporter import export_batch_excel


pdfs = [
    "data/estado_bbva.pdf",
    "data/estado_bbva2.pdf"
]


results = process_bank_statements(
    pdfs
)


print("RESULTADOS:")
print(len(results))


export_batch_excel(
    results,
    "output/debug.xlsx"
)


print("EXPORTADO")