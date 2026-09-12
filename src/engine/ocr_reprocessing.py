from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

from engine.ocr_fallback_policy import normalize_ocr_engine, secondary_ocr_engine
from engine.statement_processor import process_single_statement_with_ocr_review
from models.ocr_review import OCRCandidate, OCRReview
from models.processing_result import ProcessingResult
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from validators.movimiento_validator import validar_movimientos


def _cancel_requested(cancel_event: Any | None) -> bool:
    if cancel_event is None:
        return False
    is_set = getattr(cancel_event, "is_set", None)
    return bool(callable(is_set) and is_set())


def _validations(estado_cuenta) -> list:
    movimientos = getattr(estado_cuenta, "movimientos", None) or []
    resumen = getattr(estado_cuenta, "resumen_financiero", None)
    if not movimientos or resumen is None:
        return []
    return validar_movimientos(
        movimientos=movimientos,
        resumen=resumen,
    )


def _primary_snapshot(result: ProcessingResult, engine: str) -> OCRCandidate:
    document = DocumentData(
        raw_text=result.raw_text,
        normalized_text=result.normalized_text,
        spatial_words=[],
        metadata={
            "ocr": True,
            "reader": engine,
            "source_path": result.source_pdf_path,
            "ocr_artifact_path": result.ocr_artifacts.get(engine),
        },
    )
    return OCRCandidate(
        engine=engine,
        estado_cuenta=result.estado_cuenta,
        document=document,
        validaciones=list(result.validaciones),
    )


def reprocess_with_secondary_ocr(
    result: ProcessingResult,
    *,
    artifact_dir: str | Path,
    cancel_event: Any | None = None,
) -> ProcessingResult:
    """Reprocesa exactamente un resultado OCR con el motor alternativo.

    Esta operación es explícita, acotada a un archivo y no participa en el
    procesamiento normal del lote. El motor secundario trabaja siempre sobre el
    PDF original; su salida se incrusta en un segundo PDF verificable y ese PDF
    se vuelve a leer antes de ejecutar el mismo parser bancario.

    La mutación de ``result`` ocurre únicamente después de completar OCR,
    proyección, parser y validaciones. Ante cualquier error se conserva intacto
    el resultado primario y se elimina el artefacto secundario incompleto.
    """
    if result.processing_method != "OCR":
        raise ValueError("Sólo los PDFs procesados mediante OCR pueden reprocesarse.")
    if _cancel_requested(cancel_event):
        raise CancelledError()

    source_path = Path(str(result.source_pdf_path or "")).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(
            "El PDF original ya no está disponible para ejecutar el reprocesado OCR."
        )

    primary_engine = normalize_ocr_engine(
        result.ocr_primary_engine or result.ocr_engine or "tesseract"
    )
    secondary_engine = secondary_ocr_engine(primary_engine)
    if secondary_engine in result.ocr_artifacts:
        raise ValueError(
            "Este archivo ya contiene un artefacto del motor OCR secundario."
        )

    primary_candidate = _primary_snapshot(result, primary_engine)
    secondary_document: DocumentData | None = None
    secondary_artifact: Path | None = None

    try:
        secondary_document = ReaderManager.read_ocr_for_parser(
            source_path,
            engine=secondary_engine,
            start_page=0,
            cancel_event=cancel_event,
            artifact_dir=artifact_dir,
        )
        artifact_value = (secondary_document.metadata or {}).get("ocr_artifact_path")
        if artifact_value:
            secondary_artifact = Path(str(artifact_value))

        if _cancel_requested(cancel_event):
            raise CancelledError()

        if cancel_event is None:
            secondary_estado, secondary_document, _ = (
                process_single_statement_with_ocr_review(
                    document=secondary_document,
                    bank_key=result.bank_key,
                )
            )
        else:
            secondary_estado, secondary_document, _ = (
                process_single_statement_with_ocr_review(
                    document=secondary_document,
                    bank_key=result.bank_key,
                    cancel_event=cancel_event,
                )
            )
        if _cancel_requested(cancel_event):
            raise CancelledError()

        secondary_validations = _validations(secondary_estado)
        secondary_candidate = OCRCandidate(
            engine=secondary_engine,
            estado_cuenta=secondary_estado,
            document=secondary_document,
            validaciones=secondary_validations,
        )

        if secondary_artifact is None or not secondary_artifact.is_file():
            raise RuntimeError(
                "El reprocesado terminó sin producir un PDF OCR secundario verificable."
            )

        # El reproceso es una decisión explícita del usuario, por eso el nuevo
        # candidato queda activo y confirmado de inmediato. No se reactiva la
        # antigua política de recomendación/fallback automático.
        review = OCRReview(
            candidates={
                primary_engine: primary_candidate,
                secondary_engine: secondary_candidate,
            },
            recommended_engine=secondary_engine,
            selected_engine=secondary_engine,
            confirmed_engine=secondary_engine,
            trigger_reasons=("reproceso_manual",),
        )

        # Preparar el estado completo antes de tocar el resultado compartido con
        # Flet. Desde este punto sólo quedan asignaciones en memoria: cualquier
        # fallo de OCR, proyección, parser, validación o artefacto ocurrió antes y
        # dejó el candidato primario exactamente como estaba.
        updated_artifacts = dict(result.ocr_artifacts)
        updated_artifacts[secondary_engine] = str(secondary_artifact.resolve())
        updated_validations = list(secondary_validations)

        result.ocr_review = review
        result.ocr_secondary_engine = secondary_engine
        result.ocr_engine = secondary_engine
        result.estado_cuenta = secondary_estado
        result.raw_text = secondary_document.raw_text
        result.normalized_text = secondary_document.normalized_text
        result.validaciones = updated_validations
        result.ocr_reprocessed = True
        result.fallback_attempted = False
        result.fallback_used = False
        result.ocr_artifacts = updated_artifacts
        return result
    except Exception:
        if secondary_artifact is not None:
            try:
                secondary_artifact.unlink(missing_ok=True)
            except OSError:
                pass
        raise
