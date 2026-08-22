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
    """

    results: list[ProcessingResult] = []

    for index, pdf_path in enumerate(pdf_paths):
        file_name = (
            file_names[index]
            if file_names is not None
            else Path(pdf_path).name
        )

        # Primera etapa: texto, páginas iniciales vacías y presencia
        # de texto extraíble. No se ejecuta PDFWordReader aquí.
        text_stage = ReaderManager.read_text_stage(
            pdf_path,
            start_page=0,
        )

        document = text_stage.document
        spatial_words: list[dict] | None = None

        document_type = detect_document_type(document)

        # Si el texto no es confiable pero existe texto extraíble,
        # usamos las palabras espaciales para conservar el fallback
        # que tenía el detector original.
        if (
            document_type == DocumentType.PDF_IMAGEN
            and text_stage.has_extractable_text
        ):
            spatial_words = ReaderManager.read_spatial_words(
                pdf_path,
                start_page=0,
            )
            document.spatial_words = spatial_words
            document_type = detect_document_type(document)

        if document_type == DocumentType.PDF_IMAGEN:
            document = ReaderManager.read_ocr(
                pdf_path,
                start_page=0,
            )

        else:
            initial_empty_pages = text_stage.initial_empty_pages

            if initial_empty_pages == 0:
                if spatial_words is None:
                    spatial_words = ReaderManager.read_spatial_words(
                        pdf_path,
                        start_page=0,
                    )

                document.spatial_words = spatial_words

            else:
                logical_text_stage = ReaderManager.read_text_stage(
                    pdf_path,
                    start_page=initial_empty_pages,
                )

                document = logical_text_stage.document
                document.spatial_words = ReaderManager.read_spatial_words(
                    pdf_path,
                    start_page=initial_empty_pages,
                )

        bank_key = identify_bank_key(document.raw_text)

        if not bank_key:
            raise ValueError(
                "No se pudo identificar la institución financiera."
            )

        estado_cuenta, document = process_single_statement(
            document=document,
            bank_key=bank_key,
        )

        validaciones = []

        if (
            estado_cuenta.movimientos
            and estado_cuenta.resumen_financiero
        ):
            validaciones = validar_movimientos(
                movimientos=estado_cuenta.movimientos,
                resumen=estado_cuenta.resumen_financiero,
            )

        results.append(
            ProcessingResult(
                file_name=file_name,
                bank_key=bank_key,
                estado_cuenta=estado_cuenta,
                raw_text=document.raw_text,
                normalized_text=document.normalized_text,
                validaciones=validaciones,
            )
        )

    return results
