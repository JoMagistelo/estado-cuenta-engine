from __future__ import annotations

from pathlib import Path

from engine.statement_processor import process_single_statement
from models.processing_result import ProcessingResult
from readers.reader_manager import ReaderManager
from readers.pdf_preprocessor import count_initial_empty_pages

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

    Flujo:

        PDF ORIGINAL
            ↓
        ReaderManager
            ↓
        detectar tipo de documento
            │
            ├── PDF IMAGEN
            │       ↓
            │   NO tocar PDF
            │       ↓
            │   OCR
            │
            └── PDF DIGITAL
                    ↓
              detectar páginas iniciales
              sin texto
                    ↓
              desplazamiento lógico
                    ↓
              página física 3
              se convierte en
              página lógica 1
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
        # PRIMERA LECTURA
        # =====================================================
        #
        # Se lee el PDF ORIGINAL.
        #
        # En esta etapa todavía NO sabemos si es:
        #
        #   - PDF digital
        #   - PDF imagen
        #
        # Por eso NO debemos eliminar ni desplazar páginas
        # todavía.
        #
        # =====================================================

        document = ReaderManager.read(
            pdf_path,
            start_page=0,
        )

        # =====================================================
        # DETECCIÓN DEL TIPO DE DOCUMENTO
        # =====================================================

        document_type = detect_document_type(
            document
        )

        # =====================================================
        # CASO: PDF IMAGEN / OCR
        # =====================================================

        if document_type == DocumentType.PDF_IMAGEN:

            # -------------------------------------------------
            # MUY IMPORTANTE:
            #
            # NO se llama:
            #
            # count_initial_empty_pages()
            #
            # NO se vuelve a escribir el PDF.
            #
            # El PDF original permanece intacto.
            # -------------------------------------------------

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

        # -----------------------------------------------------
        # Ahora sí podemos buscar páginas iniciales vacías.
        #
        # Esta función solamente inspecciona el PDF.
        #
        # NO crea ningún archivo.
        # -----------------------------------------------------

        initial_empty_pages = count_initial_empty_pages(
            pdf_path
        )

        # =====================================================
        # SEGUNDA LECTURA LÓGICA
        # =====================================================
        #
        # Ejemplo:
        #
        # página física 1 -> vacía
        # página física 2 -> vacía
        # página física 3 -> contenido
        #
        # initial_empty_pages = 2
        #
        # start_page=2
        #
        # entonces:
        #
        # física 3 -> lógica 1
        # física 4 -> lógica 2
        # física 5 -> lógica 3
        #
        # =====================================================

        if initial_empty_pages > 0:

            document = ReaderManager.read(
                pdf_path,
                start_page=initial_empty_pages,
            )

        else:

            document = ReaderManager.read(
                pdf_path,
                start_page=0,
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