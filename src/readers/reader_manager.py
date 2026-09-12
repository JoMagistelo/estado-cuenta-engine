from __future__ import annotations

import os
import tempfile
import uuid
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

from readers.models import DocumentData

from .cancelable_ocr_reader import (
    read_paddle_cancelable,
    read_tesseract_cancelable,
)
from .ocr_searchable_pdf import OCR_LAYER_TAG, OCRSearchablePDFWriter
from .paddleocr_pdf_reader import PaddleOCRPDFReader
from .pdf_text_reader import PDFTextReader
from .pdf_word_reader import PDFWordReader
from .tesseract_pdf_reader import TesseractPDFReader


class PDFTextStageResult:
    """Resultado de la etapa inicial de lectura de texto."""

    __slots__ = (
        "document",
        "initial_empty_pages",
        "has_extractable_text",
    )

    def __init__(
        self,
        document: DocumentData,
        initial_empty_pages: int,
        has_extractable_text: bool,
    ) -> None:
        self.document = document
        self.initial_empty_pages = initial_empty_pages
        self.has_extractable_text = has_extractable_text


def _cancel_requested(cancel_event: Any | None) -> bool:
    if cancel_event is None:
        return False
    is_set = getattr(cancel_event, "is_set", None)
    return bool(callable(is_set) and is_set())


def _temporary_artifact_path() -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix="estado_cuenta_ocr_",
        suffix=".pdf",
    )
    os.close(descriptor)
    path = Path(raw_path)
    # El writer publica de forma atómica mediante os.replace(). No necesitamos
    # conservar el archivo vacío creado por mkstemp.
    path.unlink(missing_ok=True)
    return path


def _persistent_artifact_path(artifact_dir: str | Path, engine: str) -> Path:
    directory = Path(artifact_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"ocr_{engine}_{uuid.uuid4().hex}.pdf"


def _physical_page_words(
    words: list[dict[str, Any]],
    start_page: int,
) -> list[dict[str, Any]]:
    if start_page <= 0:
        return words

    shifted: list[dict[str, Any]] = []
    for word in words:
        item = dict(word)
        try:
            logical_page = int(item.get("page", 1) or 1)
        except (TypeError, ValueError):
            logical_page = 1
        item["page"] = logical_page + start_page
        shifted.append(item)
    return shifted


class ReaderManager:
    """Fachada de lectura digital y OCR utilizada por el pipeline.

    La lectura OCR nativa y la lectura que alimenta al parser son etapas
    distintas de forma intencional. Tesseract/PaddleOCR detectan texto y cajas;
    después ``read_ocr_for_parser`` incrusta ese resultado en un PDF verificable
    y vuelve a leerlo mediante ``PDFTextReader``/``PDFWordReader``. De este modo
    el parser recibe el mismo contrato espacial que un documento digital.
    """

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
        *,
        layer_tag: str | None = None,
    ) -> DocumentData:
        file_path = Path(file_path)
        raw_text = PDFTextReader.read(
            file_path,
            start_page=start_page,
            layer_tag=layer_tag,
        )
        spatial_words = PDFWordReader.read(
            file_path,
            start_page=start_page,
            layer_tag=layer_tag,
        )

        return DocumentData(
            raw_text=raw_text,
            normalized_text="",
            spatial_words=spatial_words,
            metadata={"start_page": start_page},
        )

    @staticmethod
    def read_text_stage(
        file_path: str | Path,
        start_page: int = 0,
    ) -> PDFTextStageResult:
        file_path = Path(file_path)
        result = PDFTextReader.read_stage(
            file_path,
            start_page=start_page,
        )

        document = DocumentData(
            raw_text=result.raw_text,
            normalized_text="",
            spatial_words=[],
            metadata={"start_page": start_page},
        )

        return PDFTextStageResult(
            document=document,
            initial_empty_pages=result.initial_empty_pages,
            has_extractable_text=result.has_extractable_text,
        )

    @staticmethod
    def read_spatial_words(
        file_path: str | Path,
        start_page: int = 0,
        *,
        layer_tag: str | None = None,
    ) -> list[dict]:
        file_path = Path(file_path)
        return PDFWordReader.read(
            file_path,
            start_page=start_page,
            layer_tag=layer_tag,
        )

    @staticmethod
    def read_ocr(
        file_path: str | Path,
        start_page: int = 0,
        cancel_event: Any | None = None,
    ) -> DocumentData:
        """Alias histórico de la salida OCR nativa de Tesseract."""
        return ReaderManager.read_ocr_engine(
            file_path,
            engine="tesseract",
            start_page=start_page,
            cancel_event=cancel_event,
        )

    @staticmethod
    def read_paddle_ocr(
        file_path: str | Path,
        start_page: int = 0,
        cancel_event: Any | None = None,
    ) -> DocumentData:
        """Ejecuta PaddleOCR y devuelve sus cajas nativas en puntos PDF."""
        if _cancel_requested(cancel_event):
            raise CancelledError()

        file_path = Path(file_path)
        if cancel_event is None:
            document = PaddleOCRPDFReader.read(
                file_path,
                start_page=start_page,
            )
        else:
            document = read_paddle_cancelable(
                file_path,
                start_page=start_page,
                cancel_event=cancel_event,
            )

        document.metadata = dict(document.metadata or {})
        document.metadata.setdefault("source_path", str(file_path.resolve()))
        document.metadata.setdefault("reader", "paddleocr")
        document.metadata.setdefault("ocr", True)
        return document

    @staticmethod
    def read_ocr_engine(
        file_path: str | Path,
        engine: str,
        start_page: int = 0,
        cancel_event: Any | None = None,
    ) -> DocumentData:
        """Ejecuta exactamente un motor OCR y conserva su salida espacial nativa."""
        if _cancel_requested(cancel_event):
            raise CancelledError()

        file_path = Path(file_path)
        normalized = str(engine or "").strip().lower()
        if normalized in {"paddle", "paddle_ocr"}:
            normalized = "paddleocr"
        elif normalized == "tess":
            normalized = "tesseract"

        if normalized == "tesseract":
            if cancel_event is None:
                document = TesseractPDFReader.read(
                    file_path,
                    start_page=start_page,
                )
            else:
                document = read_tesseract_cancelable(
                    file_path,
                    start_page=start_page,
                    cancel_event=cancel_event,
                )

            document.metadata = dict(document.metadata or {})
            document.metadata["source_path"] = str(file_path.resolve())
            document.metadata.setdefault("reader", "tesseract")
            document.metadata.setdefault("ocr", True)
            return document

        if normalized == "paddleocr":
            return ReaderManager.read_paddle_ocr(
                file_path,
                start_page=start_page,
                cancel_event=cancel_event,
            )

        raise ValueError(
            f"Motor OCR no soportado: {engine!r}. "
            "Use 'tesseract' o 'paddleocr'."
        )

    @staticmethod
    def project_ocr_document(
        file_path: str | Path,
        ocr_document: DocumentData,
        *,
        engine: str,
        start_page: int = 0,
        artifact_dir: str | Path | None = None,
    ) -> DocumentData:
        """Incrusta, verifica y vuelve a leer la salida OCR desde un PDF.

        Si ``artifact_dir`` se proporciona, el PDF verificado se conserva para
        descarga/reprocesado. Sin directorio persistente se usa un temporal que
        se elimina después de reconstruir ``DocumentData``; incluso en ese caso
        el parser sigue recibiendo datos leídos desde el PDF generado.
        """
        source_path = Path(file_path).expanduser().resolve()
        normalized_engine = str(engine or "").strip().lower()
        preserve_artifact = artifact_dir is not None
        artifact_path = (
            _persistent_artifact_path(artifact_dir, normalized_engine)
            if preserve_artifact
            else _temporary_artifact_path()
        )

        try:
            embedding_words = _physical_page_words(
                list(ocr_document.spatial_words or []),
                start_page,
            )
            OCRSearchablePDFWriter.write(
                source_pdf=source_path,
                spatial_words=embedding_words,
                output_pdf=artifact_path,
                verify=True,
            )

            canonical = ReaderManager.read(
                artifact_path,
                start_page=start_page,
                layer_tag=OCR_LAYER_TAG,
            )
            if _cancel_requested(None):  # pragma: no cover - claridad contractual
                raise CancelledError()

            metadata = dict(ocr_document.metadata or {})
            metadata.update(
                {
                    "start_page": start_page,
                    "source_path": str(source_path),
                    "reader": normalized_engine,
                    "ocr": True,
                    "coordinate_space": "pdf_points",
                    "canonical_reader": "pdfplumber",
                    "ocr_text_layer_tag": OCR_LAYER_TAG,
                    "ocr_text_layer_verified": True,
                    "ocr_native_word_count": len(ocr_document.spatial_words or []),
                    "ocr_canonical_word_count": len(canonical.spatial_words),
                }
            )
            if preserve_artifact:
                metadata["ocr_artifact_path"] = str(artifact_path)
            canonical.metadata = metadata
            return canonical
        except Exception:
            try:
                artifact_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            if not preserve_artifact:
                try:
                    artifact_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def read_ocr_for_parser(
        file_path: str | Path,
        engine: str,
        start_page: int = 0,
        cancel_event: Any | None = None,
        *,
        artifact_dir: str | Path | None = None,
    ) -> DocumentData:
        """OCR -> PDF con texto incrustado -> PDF readers canónicos."""
        document = ReaderManager.read_ocr_engine(
            file_path,
            engine=engine,
            start_page=start_page,
            cancel_event=cancel_event,
        )
        if _cancel_requested(cancel_event):
            raise CancelledError()
        return ReaderManager.project_ocr_document(
            file_path,
            document,
            engine=engine,
            start_page=start_page,
            artifact_dir=artifact_dir,
        )
