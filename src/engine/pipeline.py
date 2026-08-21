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

    Flujo optimizado:

        PDF ORIGINAL
            ↓
        lectura inicial SOLO de texto
            ↓
        detectar tipo de documento
            │
            ├── PDF IMAGEN
            │       ↓
            │   no ejecutar PDFWordReader
            │
            └── PDF DIGITAL
                    ↓
              determinar páginas iniciales vacías
                    ↓
              PDFWordReader
                    ↓
              detectar banco
                    ↓
              parser
                    ↓
              validaciones
                    ↓
              ProcessingResult

    IMPORTANTE:

    Nunca se crea un PDF nuevo.

    Nunca se modifica el PDF original.

    La optimización consiste únicamente en evitar la extracción
    de palabras espaciales cuando el documento no las necesita.
    """

    results: list[ProcessingResult] = []

    for index, pdf_path in enumerate(pdf_paths):

        # =====================================================
        # NOMBRE DEL ARCHIVO ORIGINAL
        # =====================================================

        file_name = (
            file_names[index]
            if file_names is not None
            else Path(pdf_path).name
        )

        # =====================================================
        # PRIMERA ETAPA
        # =====================================================
        #
        # Solo lectura de texto.
        #
        # Esta operación además obtiene:
        #
        #   - raw_text
        #   - initial_empty_pages
        #   - has_extractable_text
        #
        # Todavía NO extraemos todas las palabras espaciales.
        #
        # =====================================================

        text_stage = ReaderManager.read_text_stage(
            pdf_path,
            start_page=0,
        )

        document = text_stage.document

        # =====================================================
        # PRIMERA DETECCIÓN
        # =====================================================
        #
        # Si raw_text ya es utilizable, detect_document_type()
        # puede determinar directamente que es PDF_DIGITAL.
        #
        # Si raw_text no es utilizable, todavía debemos
        # distinguir:
        #
        #   A) PDF realmente imagen
        #   B) PDF digital con fuente mal codificada
        #   C) PDF digital cuyo contenido empieza después
        #      de las primeras MAX_PAGES
        #
        # Para esos casos consultamos has_extractable_text.
        #
        # =====================================================

        document_type = detect_document_type(
            document
        )

        # =====================================================
        # SI RAW TEXT FALLA
        # =====================================================
        #
        # En este punto document.spatial_words está vacío
        # intencionalmente.
        #
        # Si existe texto extraíble en alguna página, debemos
        # conservar el comportamiento anterior del detector:
        #
        #       raw_text + spatial_words
        #
        # Por eso solamente en este escenario ejecutamos
        # PDFWordReader completo.
        #
        # =====================================================

        if document_type == DocumentType.PDF_IMAGEN:

            if text_stage.has_extractable_text:

                # -------------------------------------------------
                # Existe texto en el PDF, pero raw_text no fue
                # suficiente para determinarlo.
                #
                # Leemos palabras espaciales para conservar el
                # fallback original del detector.
                # -------------------------------------------------

                spatial_words = ReaderManager.read_spatial_words(
                    pdf_path,
                    start_page=0,
                )

                document.spatial_words = spatial_words

                document_type = detect_document_type(
                    document
                )

        # =====================================================
        # CASO: PDF IMAGEN
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

        initial_empty_pages = (
            text_stage.initial_empty_pages
        )

        # =====================================================
        # PREPARAR DOCUMENTO FINAL
        # =====================================================
        #
        # CASO 1:
        #
        # No hay páginas iniciales vacías.
        #
        # La lectura de texto que ya hicimos corresponde
        # exactamente a start_page=0.
        #
        # Por tanto NO volvemos a extraer raw_text.
        #
        # Solamente extraemos las palabras espaciales.
        #
        # =====================================================

        if initial_empty_pages == 0:

            spatial_words = ReaderManager.read_spatial_words(
                pdf_path,
                start_page=0,
            )

            document.spatial_words = spatial_words

        # =====================================================
        # CASO 2:
        #
        # Existen páginas iniciales vacías.
        #
        # Ahora sí debemos crear la representación lógica:
        #
        # física 3 → lógica 1
        #
        # Para ello necesitamos volver a leer desde
        # initial_empty_pages.
        #
        # =====================================================

        else:

            document = ReaderManager.read(
                pdf_path,
                start_page=initial_empty_pages,
            )

        # =====================================================
        # DETECCIÓN DE BANCO
        # =====================================================

        bank_key = identify_bank_key(
            document.raw_text
        )

        if not bank_key:

            raise ValueError(
                "No se pudo identificar la institución financiera."
            )

        # =====================================================
        # PROCESAMIENTO DEL PARSER
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
            and estado_cuenta.resumen_financiero
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