from __future__ import annotations

from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from pathlib import Path

from engine.ocr_execution import normalize_ocr_engine
from engine.statement_processor import process_single_statement_with_ocr_review
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from readers.reader_manager import ReaderManager

from detectors.bank_detector import identify_bank_key
from detectors.document_type_detector import (
    DocumentType,
    detect_document_type,
)
from validators.movimiento_validator import validar_movimientos


# ============================================================
# DOCUMENTO PREPARADO
# ============================================================


@dataclass(slots=True)
class PreparedStatement:
    """
    Documento preparado para su procesamiento final.

    La preparación determina si el documento debe procesarse
    mediante:

        - Digital
        - OCR

    Para documentos Digital ya contiene las spatial_words.

    Para documentos OCR todavía NO ejecuta Tesseract.
    """

    file_name: str
    pdf_path: str
    document: DocumentData | None
    processing_method: str


# ============================================================
# EVENTO DE PROCESAMIENTO INCREMENTAL
# ============================================================


@dataclass(slots=True)
class ProcessingEvent:
    """
    Evento emitido por process_bank_statements_incremental().

    kind:

        started
            El método de procesamiento ya fue determinado.

        completed
            El archivo terminó correctamente.

        error
            El archivo no pudo procesarse.
    """

    kind: str

    index: int

    file_name: str

    processing_method: str | None = None

    result: ProcessingResult | None = None

    error: Exception | None = None


# ============================================================
# UTILIDADES
# ============================================================


def _rebase_spatial_words(
    spatial_words: list[dict],
    start_page: int,
) -> list[dict]:
    """
    Reconvierte spatial_words obtenidas desde la página física 1
    para que la primera página con contenido sea la página lógica 1.

    Esto evita volver a ejecutar PDFWordReader únicamente para
    cambiar la numeración lógica de las páginas.

    Ejemplo:

        start_page = 2

        página física 3 -> lógica 1
        página física 4 -> lógica 2

    Las páginas anteriores al start_page se descartan.
    """

    if start_page <= 0:
        return spatial_words

    rebased_words: list[dict] = []

    for word in spatial_words:

        try:
            page = int(
                word.get(
                    "page",
                    1,
                )
                or 1
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if page <= start_page:
            continue

        rebased_word = dict(word)

        rebased_word["page"] = (
            page - start_page
        )

        rebased_words.append(
            rebased_word
        )

    return rebased_words


def _get_file_name(
    pdf_path: str,
    file_names: list[str] | None,
    index: int,
) -> str:
    """
    Obtiene el nombre visible del archivo.
    """

    return (
        file_names[index]
        if file_names is not None
        else Path(pdf_path).name
    )


# ============================================================
# PREPARACIÓN DE UN DOCUMENTO
# ============================================================


def _prepare_statement(
    pdf_path: str,
    file_name: str,
) -> PreparedStatement:
    """
    Ejecuta únicamente la etapa necesaria para determinar
    cómo debe procesarse el documento.

    Flujo:

        PDF
         ↓
        read_text_stage()
         ↓
        ¿hay texto extraíble?
         ├── NO → OCR
         │
         └── SÍ
               ↓
          ¿texto útil?
             ├── SÍ
             │    ↓
             │  spatial_words
             │    ↓
             │  Digital
             │
             └── NO
                  ↓
             spatial_words
                  ↓
             ¿spatial_words útiles?
                ├── SÍ → Digital
                └── NO → OCR

    IMPORTANTE:
    Esta función NO ejecuta OCR.

    Eso permite que los documentos OCR esperen en su propio
    procesamiento mientras los Digitales continúan.
    """

    # ========================================================
    # 1. SOLO TEXTO
    # ========================================================

    text_stage = ReaderManager.read_text_stage(
        pdf_path,
        start_page=0,
    )

    document = text_stage.document

    # ========================================================
    # 2. ¿HAY TEXTO EXTRAÍBLE?
    # ========================================================

    if not text_stage.has_extractable_text:

        return PreparedStatement(
            file_name=file_name,
            pdf_path=pdf_path,
            document=None,
            processing_method="OCR",
        )

    # ========================================================
    # 3. ¿EL TEXTO ES UTILIZABLE?
    # ========================================================

    document_type = detect_document_type(
        document
    )

    # ========================================================
    # TEXTO ÚTIL
    # ========================================================

    if (
        document_type
        == DocumentType.PDF_DIGITAL
    ):

        spatial_words = (
            ReaderManager.read_spatial_words(
                pdf_path,
                start_page=0,
            )
        )

        # -----------------------------------------------
        # PÁGINAS INICIALES VACÍAS
        # -----------------------------------------------

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

            spatial_words = _rebase_spatial_words(
                spatial_words,
                initial_empty_pages,
            )

        document.spatial_words = spatial_words

        return PreparedStatement(
            file_name=file_name,
            pdf_path=pdf_path,
            document=document,
            processing_method="Digital",
        )

    # ========================================================
    # TEXTO SOSPECHOSO
    # ========================================================

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

    # ========================================================
    # LAS SPATIAL_WORDS SON ÚTILES
    # ========================================================

    if (
        document_type
        == DocumentType.PDF_DIGITAL
    ):

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
                _rebase_spatial_words(
                    spatial_words,
                    initial_empty_pages,
                )
            )

        return PreparedStatement(
            file_name=file_name,
            pdf_path=pdf_path,
            document=document,
            processing_method="Digital",
        )

    # ========================================================
    # LAS SPATIAL_WORDS TAMBIÉN SON INÚTILES
    # ========================================================

    return PreparedStatement(
        file_name=file_name,
        pdf_path=pdf_path,
        document=None,
        processing_method="OCR",
    )


# ============================================================
# PROCESAMIENTO FINAL
# ============================================================


def _process_prepared_statement(
    prepared: PreparedStatement,
    ocr_primary_engine: str = "tesseract",
) -> ProcessingResult:
    """
    Ejecuta el procesamiento final de un documento previamente
    clasificado.

    Digital:
        utiliza el DocumentData ya preparado.

    OCR:
        ejecuta Tesseract como motor primario y, cuando corresponde,
        conserva también el candidato PaddleOCR para revisión.
    """

    document = prepared.document
    ocr_primary_engine = normalize_ocr_engine(ocr_primary_engine)
    allow_secondary_review = True

    # ========================================================
    # OCR
    # ========================================================

    if prepared.processing_method == "OCR":

        if ocr_primary_engine == "paddleocr":
            try:
                document = ReaderManager.read_paddle_ocr(
                    prepared.pdf_path,
                    start_page=0,
                )
            except Exception as primary_exc:
                # Una preferencia de usuario no debe provocar la
                # pérdida del documento si PaddleOCR falla.
                document = ReaderManager.read_ocr(
                    prepared.pdf_path,
                    start_page=0,
                )
                allow_secondary_review = False
                document.metadata.update(
                    {
                        "ocr_primary_requested": "paddleocr",
                        "ocr_primary_error_type": type(primary_exc).__name__,
                        "ocr_primary_fallback_engine": "tesseract",
                    }
                )
        else:
            document = ReaderManager.read_ocr(
                prepared.pdf_path,
                start_page=0,
            )

        document.metadata["ocr_primary_requested"] = ocr_primary_engine

    # ========================================================
    # DIGITAL
    # ========================================================

    if document is None:

        raise RuntimeError(
            "El documento no contiene un DocumentData válido "
            f"para el método '{prepared.processing_method}'."
        )

    # ========================================================
    # DETECCIÓN DE BANCO
    # ========================================================

    bank_key = identify_bank_key(
        raw_text=document.raw_text,
        file_name=prepared.file_name,
    )

    if not bank_key:

        raise ValueError(
            "No se pudo identificar la institución financiera "
            f"para el archivo '{prepared.file_name}'. "
            "No se encontró una CLABE bancaria válida ni "
            "una firma bancaria reconocible en el nombre del archivo."
        )

    # ========================================================
    # PARSER + REVISIÓN OCR
    # ========================================================

    estado_cuenta, document, ocr_review = (
        process_single_statement_with_ocr_review(
            document=document,
            bank_key=bank_key,
            allow_secondary=allow_secondary_review,
        )
    )

    # ========================================================
    # VALIDACIONES DEL CANDIDATO SELECCIONADO
    # ========================================================

    if ocr_review is not None:
        selected_candidate = ocr_review.get_candidate(
            ocr_review.selected_engine
        )
        validaciones = list(selected_candidate.validaciones)
    else:
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

    return ProcessingResult(
        file_name=prepared.file_name,
        bank_key=bank_key,
        estado_cuenta=estado_cuenta,
        raw_text=document.raw_text,
        normalized_text=document.normalized_text,
        validaciones=validaciones,
        processing_method=prepared.processing_method,
        ocr_review=ocr_review,
    )


# ============================================================
# API SECUENCIAL EXISTENTE
# ============================================================


def process_bank_statements(
    pdf_paths: list[str],
    file_names: list[str] | None = None,
    ocr_primary_engine: str = "tesseract",
) -> list[ProcessingResult]:
    """
    Procesa múltiples estados de cuenta de forma secuencial.

    Esta función conserva la API existente.

    La nueva ejecución concurrente utiliza
    process_bank_statements_incremental().
    """

    results: list[ProcessingResult] = []

    for index, pdf_path in enumerate(
        pdf_paths
    ):

        file_name = _get_file_name(
            pdf_path,
            file_names,
            index,
        )

        prepared = _prepare_statement(
            pdf_path=pdf_path,
            file_name=file_name,
        )

        result = _process_prepared_statement(
            prepared,
            ocr_primary_engine=ocr_primary_engine,
        )

        results.append(
            result
        )

    return results


# ============================================================
# API CONCURRENTE E INCREMENTAL
# ============================================================


def process_bank_statements_incremental(
    pdf_paths: list[str],
    file_names: list[str] | None = None,
    classification_workers: int = 2,
    digital_workers: int = 4,
    ocr_workers: int = 1,
    ocr_primary_engine: str = "tesseract",
):
    """
    Procesa múltiples estados de cuenta de forma concurrente
    y produce resultados incrementalmente.

    Arquitectura:

        clasificación
              │
        ┌─────┴─────┐
        │           │
     Digital       OCR
        │           │
     workers      worker
        │           │
        └─────┬─────┘
              │
          resultados

    Los documentos Digital pueden terminar y producir
    resultados mientras Tesseract continúa procesando
    documentos OCR.

    El OCR se limita por defecto a un worker para evitar que
    varios procesos pesados de Tesseract/Paddle compitan entre sí.
    """

    total = len(pdf_paths)
    ocr_primary_engine = normalize_ocr_engine(ocr_primary_engine)

    if total == 0:
        return

    classification_workers = max(
        1,
        min(
            classification_workers,
            total,
        ),
    )

    digital_workers = max(
        1,
        min(
            digital_workers,
            total,
        ),
    )

    ocr_workers = max(
        1,
        min(
            ocr_workers,
            total,
        ),
    )

    with (
        ThreadPoolExecutor(
            max_workers=classification_workers,
            thread_name_prefix="statement-classifier",
        ) as classification_executor,
        ThreadPoolExecutor(
            max_workers=digital_workers,
            thread_name_prefix="statement-digital",
        ) as digital_executor,
        ThreadPoolExecutor(
            max_workers=ocr_workers,
            thread_name_prefix="statement-ocr",
        ) as ocr_executor,
    ):

        future_map = {}

        # ====================================================
        # INICIAR CLASIFICACIÓN
        # ====================================================

        for index, pdf_path in enumerate(
            pdf_paths
        ):

            file_name = _get_file_name(
                pdf_path,
                file_names,
                index,
            )

            future = classification_executor.submit(
                _prepare_statement,
                pdf_path,
                file_name,
            )

            future_map[future] = (
                "classification",
                index,
                file_name,
                None,
            )

        # ====================================================
        # PROCESAR EVENTOS
        # ====================================================

        while future_map:

            done, _ = wait(
                future_map.keys(),
                return_when=FIRST_COMPLETED,
            )

            for future in done:

                (
                    future_type,
                    index,
                    file_name,
                    prepared,
                ) = future_map.pop(
                    future
                )

                # =========================================
                # CLASIFICACIÓN TERMINADA
                # =========================================

                if future_type == "classification":

                    try:

                        prepared = future.result()

                    except Exception as ex:

                        yield ProcessingEvent(
                            kind="error",
                            index=index,
                            file_name=file_name,
                            processing_method=None,
                            error=ex,
                        )

                        continue

                    # -------------------------------------
                    # INFORMAR MÉTODO
                    # -------------------------------------

                    yield ProcessingEvent(
                        kind="started",
                        index=index,
                        file_name=file_name,
                        processing_method=(
                            prepared.processing_method
                        ),
                    )

                    # -------------------------------------
                    # ENVIAR AL POOL CORRESPONDIENTE
                    # -------------------------------------

                    if (
                        prepared.processing_method
                        == "OCR"
                    ):

                        processing_future = (
                            ocr_executor.submit(
                                _process_prepared_statement,
                                prepared,
                                ocr_primary_engine,
                            )
                        )

                    else:

                        processing_future = (
                            digital_executor.submit(
                                _process_prepared_statement,
                                prepared,
                                ocr_primary_engine,
                            )
                        )

                    future_map[
                        processing_future
                    ] = (
                        "processing",
                        index,
                        file_name,
                        prepared,
                    )

                # =========================================
                # PROCESAMIENTO TERMINADO
                # =========================================

                else:

                    try:

                        result = future.result()

                    except Exception as ex:

                        method = (
                            prepared.processing_method
                            if prepared is not None
                            else None
                        )

                        yield ProcessingEvent(
                            kind="error",
                            index=index,
                            file_name=file_name,
                            processing_method=method,
                            error=ex,
                        )

                        continue

                    yield ProcessingEvent(
                        kind="completed",
                        index=index,
                        file_name=file_name,
                        processing_method=(
                            prepared.processing_method
                        ),
                        result=result,
                    )