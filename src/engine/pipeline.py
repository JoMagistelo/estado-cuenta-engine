from __future__ import annotations

from pathlib import Path

from engine.statement_processor import process_single_statement
from models.processing_result import ProcessingResult
from readers.reader_manager import ReaderManager

from detectors.bank_detector import identify_bank_key
from detectors.document_type_detector import (
    DocumentType,
    detect_document_type,
)
from validators.movimiento_validator import validar_movimientos


def process_bank_statements(
    pdf_paths: list[str],
    file_names: list[str] | None = None,
) -> list[ProcessingResult]:
    """
    Procesa múltiples estados de cuenta.

    El pipeline realiza una primera lectura únicamente de texto.
    Las palabras espaciales se extraen solo cuando el documento
    ha sido identificado como PDF digital o cuando son necesarias
    como respaldo para clasificar una extracción de texto dudosa.

    El PDF original nunca se modifica ni se reemplaza.

    La identificación del banco utiliza:

        1. CLABE
        2. Nombre del archivo como fallback

    Cuando ambas fuentes están disponibles, la CLABE tiene prioridad.

    Además, cada resultado registra el método utilizado:

        - "Digital"
        - "OCR"
    """

    results: list[ProcessingResult] = []

    for index, pdf_path in enumerate(pdf_paths):

        # ========================================================
        # NOMBRE DEL ARCHIVO
        # ========================================================

        file_name = (
            file_names[index]
            if file_names is not None
            else Path(pdf_path).name
        )

        # ========================================================
        # PRIMERA ETAPA: TEXTO
        # ========================================================

        text_stage = ReaderManager.read_text_stage(
            pdf_path,
            start_page=0,
        )

        document = text_stage.document
        spatial_words: list[dict] | None = None

        document_type = detect_document_type(
            document
        )

        # ========================================================
        # FALLBACK ESPACIAL
        # ========================================================

        if (
            document_type == DocumentType.PDF_IMAGEN
            and text_stage.has_extractable_text
        ):

            spatial_words = ReaderManager.read_spatial_words(
                pdf_path,
                start_page=0,
            )

            document.spatial_words = spatial_words

            document_type = detect_document_type(
                document
            )

        # ========================================================
        # MÉTODO DE PROCESAMIENTO
        # ========================================================
        #
        # Esta variable representa el método realmente utilizado
        # para producir el DocumentData que llegará al parser.
        #
        # PDF_IMAGEN confirmado -> OCR
        # cualquier otro caso   -> Digital
        #
        # El fallback espacial NO convierte el documento en OCR:
        # sigue siendo un PDF digital.
        # ========================================================

        processing_method = "Digital"

        # ========================================================
        # OCR
        # ========================================================

        if document_type == DocumentType.PDF_IMAGEN:

            processing_method = "OCR"

            document = ReaderManager.read_ocr(
                pdf_path,
                start_page=0,
            )

        # ========================================================
        # PDF DIGITAL
        # ========================================================

        else:

            initial_empty_pages = (
                text_stage.initial_empty_pages
            )

            if initial_empty_pages == 0:

                if spatial_words is None:

                    spatial_words = (
                        ReaderManager.read_spatial_words(
                            pdf_path,
                            start_page=0,
                        )
                    )

                document.spatial_words = spatial_words

            else:

                logical_text_stage = (
                    ReaderManager.read_text_stage(
                        pdf_path,
                        start_page=initial_empty_pages,
                    )
                )

                document = (
                    logical_text_stage.document
                )

                document.spatial_words = (
                    ReaderManager.read_spatial_words(
                        pdf_path,
                        start_page=initial_empty_pages,
                    )
                )

        # ========================================================
        # DETECCIÓN DE BANCO
        # ========================================================

        bank_key = identify_bank_key(
            raw_text=document.raw_text,
            file_name=file_name,
        )

        if not bank_key:

            raise ValueError(
                "No se pudo identificar la institución financiera "
                f"para el archivo '{file_name}'. "
                "No se encontró una CLABE bancaria válida ni "
                "una firma bancaria reconocible en el nombre del archivo."
            )

        # ========================================================
        # PARSER
        # ========================================================

        estado_cuenta, document = (
            process_single_statement(
                document=document,
                bank_key=bank_key,
            )
        )

        # ========================================================
        # VALIDACIONES
        # ========================================================

        validaciones = []

        if (
            estado_cuenta.movimientos
            and estado_cuenta.resumen_financiero
        ):

            validaciones = validar_movimientos(
                movimientos=estado_cuenta.movimientos,
                resumen=estado_cuenta.resumen_financiero,
            )

        # ========================================================
        # RESULTADO
        # ========================================================

        results.append(
            ProcessingResult(
                file_name=file_name,
                bank_key=bank_key,
                estado_cuenta=estado_cuenta,
                raw_text=document.raw_text,
                normalized_text=document.normalized_text,
                validaciones=validaciones,
                processing_method=processing_method,
            )
        )

    return results