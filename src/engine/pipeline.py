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

    results: list[ProcessingResult] = []

    for index, pdf_path in enumerate(pdf_paths):

        file_name = (
            file_names[index]
            if file_names is not None
            else Path(pdf_path).name
        )

        # ====================================================
        # 1. SOLO TEXTO
        # ====================================================

        text_stage = ReaderManager.read_text_stage(
            pdf_path,
            start_page=0,
        )

        document = text_stage.document
        processing_method = "Digital"

        # ====================================================
        # 2. ¿HAY TEXTO EXTRAÍBLE?
        # ====================================================

        if not text_stage.has_extractable_text:

            # ------------------------------------------------
            # SIN TEXTO
            # → OCR DIRECTO
            # ------------------------------------------------

            processing_method = "OCR"

            document = ReaderManager.read_ocr(
                pdf_path,
                start_page=0,
            )

        else:

            # ------------------------------------------------
            # HAY TEXTO
            # → VERIFICAR SU CALIDAD
            # ------------------------------------------------

            document_type = detect_document_type(
                document
            )

            # =================================================
            # 3A. TEXTO ÚTIL
            # =================================================

            if (
                document_type
                == DocumentType.PDF_DIGITAL
            ):

                document.spatial_words = (
                    ReaderManager.read_spatial_words(
                        pdf_path,
                        start_page=0,
                    )
                )

            # =================================================
            # 3B. TEXTO SOSPECHOSO
            # =================================================

            else:

                spatial_words = (
                    ReaderManager.read_spatial_words(
                        pdf_path,
                        start_page=0,
                    )
                )

                document.spatial_words = spatial_words

                document_type = detect_document_type(
                    document
                )

                # ------------------------------------------------
                # Las spatial_words son válidas:
                # → DIGITAL
                #
                # Las spatial_words también son basura:
                # → OCR
                # ------------------------------------------------

                if (
                    document_type
                    == DocumentType.PDF_IMAGEN
                ):

                    processing_method = "OCR"

                    document = ReaderManager.read_ocr(
                        pdf_path,
                        start_page=0,
                    )

                # ------------------------------------------------
                # Si sigue siendo DIGITAL, document ya contiene
                # las spatial_words que acabamos de extraer.
                # NO las volvemos a leer.
                # ------------------------------------------------

        # ====================================================
        # 4. AJUSTE POR PÁGINAS INICIALES VACÍAS
        # ====================================================
        #
        # Esto solamente aplica al camino digital.
        #
        # No se ejecuta para OCR.
        #
        # ====================================================

        if processing_method == "Digital":

            initial_empty_pages = (
                text_stage.initial_empty_pages
            )

            if initial_empty_pages != 0:

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

        # ====================================================
        # 5. DETECCIÓN DE BANCO
        # ====================================================

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

        # ====================================================
        # 6. PARSER
        # ====================================================

        estado_cuenta, document = (
            process_single_statement(
                document=document,
                bank_key=bank_key,
            )
        )

        # ====================================================
        # 7. VALIDACIONES
        # ====================================================

        validaciones = []

        if (
            estado_cuenta.movimientos
            and estado_cuenta.resumen_financiero
        ):

            validaciones = validar_movimientos(
                movimientos=estado_cuenta.movimientos,
                resumen=estado_cuenta.resumen_financiero,
            )

        # ====================================================
        # 8. RESULTADO
        # ====================================================

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