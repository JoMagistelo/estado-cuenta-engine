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


# ============================================================
# EXCEPCIÓN: OCR PENDIENTE
# ============================================================


class OCRNotImplementedError(Exception):
    """
    Se utiliza cuando el motor detecta que el documento
    es un PDF basado en imagen y todavía no se ha
    implementado la extracción mediante OCR.
    """

    pass


# ============================================================
# PROCESAMIENTO DE ESTADOS DE CUENTA
# ============================================================


def process_bank_statements(
    pdf_paths: list[str],
    file_names: list[str] | None = None,
) -> list[ProcessingResult]:
    """
    Procesa múltiples estados de cuenta.

    Flujo actual:

    PDF
        ↓
    ReaderManager
        ↓
    Detección tipo de documento
        │
        ├── PDF DIGITAL
        │       ↓
        │   Detección banco
        │       ↓
        │   Parser específico
        │       ↓
        │   Validadores
        │       ↓
        │   ProcessingResult
        │
        └── PDF IMAGEN
                ↓
        OCR pendiente
                ↓
        ProcessingResult individual
                ↓
        Continúa con el siguiente archivo

    ReaderManager proporciona actualmente:

        raw_text
            → texto de las primeras 2 páginas

        spatial_words
            → palabras con coordenadas de todo el documento

    Las tablas ya no forman parte de DocumentData.
    """

    results = []

    for index, pdf_path in enumerate(pdf_paths):

        # =====================================================
        # NOMBRE DEL ARCHIVO
        # =====================================================

        file_name = (
            file_names[index]
            if file_names is not None
            else Path(pdf_path).name
        )

        # =====================================================
        # LECTURA DEL DOCUMENTO
        # =====================================================

        document = ReaderManager.read(
            pdf_path
        )

        # =====================================================
        # DETECCIÓN DEL TIPO DE DOCUMENTO
        # =====================================================
        #
        # Este paso ocurre ANTES de detectar el banco.
        #
        # =====================================================

        document_type = detect_document_type(
            document
        )

        # =====================================================
        # CASO: PDF IMAGEN
        # =====================================================
        #
        # IMPORTANTE:
        #
        # NO se lanza la excepción hacia afuera de
        # process_bank_statements().
        #
        # El problema original era que el "raise" abortaba
        # todo el procesamiento de la lista de archivos.
        #
        # Ahora se genera un resultado individual para este
        # archivo y el ciclo continúa con el siguiente PDF.
        #
        # =====================================================

        if document_type == DocumentType.PDF_IMAGEN:

            result = ProcessingResult(
                file_name=file_name,
                bank_key="imagen_no_procesada",
                estado_cuenta=None,
                raw_text=document.raw_text,
                normalized_text=document.normalized_text,
                validaciones=[],
            )

            results.append(
                result
            )

            continue

        # =====================================================
        # CASO: PDF DIGITAL
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
            bank_key=bank_key,
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
                resumen=estado_cuenta.resumen_financiero,
            )

        # =====================================================
        # RESULTADO FINAL
        # =====================================================

        result = ProcessingResult(
            file_name=file_name,

            bank_key=bank_key,

            estado_cuenta=estado_cuenta,

            raw_text=document.raw_text,

            normalized_text=document.normalized_text,

            validaciones=validaciones,
        )

        results.append(
            result
        )

    return results