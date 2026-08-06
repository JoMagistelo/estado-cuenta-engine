import sys
import os


sys.path.append(
    os.path.abspath(
        "src"
    )
)


from readers.pdf_text_reader import PDFTextReader
from utils.text_normalizer import normalize_text

from parsers.bbva.extractors.movimientos_text import extract_movimientos
from parsers.bbva.extractors.resumen import extract_resumen_financiero

from validators import validar_movimientos



texto = normalize_text(
    PDFTextReader.read(
        "data/estado_bbva3.pdf"
    )
)


movimientos = extract_movimientos(
    texto
)


resumen = extract_resumen_financiero(
    texto
)



resultados = validar_movimientos(
    movimientos,
    resumen
)



for r in resultados:

    print("="*50)

    print(r.nombre)

    print(
        "Esperado:",
        r.esperado
    )

    print(
        "Obtenido:",
        r.obtenido
    )

    print(
        "Diferencia:",
        r.diferencia
    )

    print(
        "OK:",
        r.correcto
    )