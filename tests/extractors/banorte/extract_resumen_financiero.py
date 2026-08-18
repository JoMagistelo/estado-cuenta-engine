from pathlib import Path

from readers.reader_manager import ReaderManager
from parsers.banorte.extractors.resumen import (
    extract_resumen_financiero_words
)


ROOT = Path(__file__).resolve().parents[3]

PDF_PATH = ROOT / "data" / "edo_banorte.pdf"


def main():

    print()
    print("=" * 60)
    print("PRUEBA PARSER RESUMEN FINANCIERO BBVA (WORDS)")
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

    # 2. Ejecutar nuevo extractor de resumen financiero

    resumen_financiero = extract_resumen_financiero_words(
        spatial_words
    )

    print()
    print("=" * 60)
    print("RESUMEN FINANCIERO EXTRAÍDO")
    print("=" * 60)

    print()
    print("-" * 60)

    print(
        "Saldo promedio:",
        resumen_financiero.saldo_promedio
    )

    print(
        "Días del periodo:",
        resumen_financiero.dias_periodo
    )

    print(
        "Tasa bruta anual:",
        resumen_financiero.tasa_bruta_anual
    )

    print(
        "Saldo promedio gravable:",
        resumen_financiero.saldo_promedio_gravable
    )

    print(
        "Intereses a favor:",
        resumen_financiero.intereses_a_favor
    )

    print(
        "ISR retenido:",
        resumen_financiero.isr_retenido
    )

    print(
        "Cheques pagados:",
        resumen_financiero.cheques_pagados
    )

    print(
        "Manejo de cuenta:",
        resumen_financiero.manejo_cuenta
    )

    print(
        "Cargos objetados:",
        resumen_financiero.cargos_objetados
    )

    print(
        "Abonos objetados:",
        resumen_financiero.abonos_objetados
    )

    print(
        "Saldo anterior:",
        resumen_financiero.saldo_anterior
    )

    print(
        "Depósitos / Abonos:",
        resumen_financiero.depositos_abonos
    )

    print(
        "Retiros / Cargos:",
        resumen_financiero.retiros_cargos
    )

    print(
        "Saldo final:",
        resumen_financiero.saldo_final
    )

    print(
        "Saldo promedio mínimo mensual:",
        resumen_financiero.saldo_promedio_minimo_mensual
    )

    print(
        "Saldo global:",
        resumen_financiero.saldo_global
    )

    print()
    print("=" * 60)
    print("PRUEBA FINALIZADA")
    print("=" * 60)


if __name__ == "__main__":
    main()