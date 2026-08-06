from __future__ import annotations


from pathlib import Path


from engine.statement_processor import process_single_statement

from models.processing_result import ProcessingResult


from readers.reader_manager import ReaderManager


from detectors.bank_detector import identify_bank_key


from validators.movimiento_validator import validar_movimientos



def process_bank_statements(
    pdf_paths: list[str]
) -> list[ProcessingResult]:

    """
    Procesa múltiples estados de cuenta.

    Flujo:

    PDF
    ↓
    ReaderManager
    ↓
    DocumentData
    ↓
    Detección banco
    ↓
    Parser específico
    ↓
    Validadores financieros
    ↓
    ProcessingResult
    """


    results = []


    for pdf_path in pdf_paths:


        # =====================================================
        # LECTURA DEL DOCUMENTO
        # =====================================================

        document = ReaderManager.read(
            pdf_path
        )


        # =====================================================
        # DETECCIÓN BANCO
        # =====================================================

        bank_key = identify_bank_key(
            document.raw_text
        )


        if not bank_key:

            raise ValueError(
                "No se pudo identificar la institución financiera."
            )



        # =====================================================
        # PROCESAMIENTO PARSER
        # =====================================================

        estado_cuenta, document = process_single_statement(

            document=document,

            bank_key=bank_key

        )



        # =====================================================
        # VALIDACIONES
        # =====================================================

        validaciones = []


        if (
            estado_cuenta.movimientos
            and
            estado_cuenta.resumen_financiero
        ):

            validaciones = validar_movimientos(

                movimientos=estado_cuenta.movimientos,

                resumen=estado_cuenta.resumen_financiero

            )



        # =====================================================
        # RESULTADO FINAL
        # =====================================================

        result = ProcessingResult(

            file_name=Path(pdf_path).name,

            bank_key=bank_key,

            estado_cuenta=estado_cuenta,

            raw_text=document.raw_text,

            normalized_text=document.normalized_text,

            tables=document.tables,

            validaciones=validaciones

        )


        results.append(
            result
        )



    return results