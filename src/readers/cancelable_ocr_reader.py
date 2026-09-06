from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from readers.models import DocumentData
from readers.paddleocr_pdf_reader import PaddleOCRPDFReader
from readers.tesseract_pdf_reader import TesseractPDFReader


def _cancel_requested(cancel_event: Any | None) -> bool:
    if cancel_event is None:
        return False
    is_set = getattr(cancel_event, "is_set", None)
    return bool(callable(is_set) and is_set())


def _raise_if_cancelled(cancel_event: Any | None) -> None:
    if _cancel_requested(cancel_event):
        raise CancelledError()


def read_tesseract_cancelable(
    file_path: str | Path,
    *,
    start_page: int = 0,
    cancel_event: Any | None = None,
) -> DocumentData:
    """Tesseract con puntos de cancelación antes y después de cada página."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No existe el PDF: {file_path}")

    _raise_if_cancelled(cancel_event)
    tesseract_cmd, tessdata_dir = TesseractPDFReader._configure_tesseract()
    pdf = pdfium.PdfDocument(str(file_path))
    all_words: list[dict[str, Any]] = []
    text_pages: list[str] = []
    doctop_offset = 0.0

    for physical_index in range(start_page, len(pdf)):
        _raise_if_cancelled(cancel_event)
        page = pdf[physical_index]
        page_width, page_height = page.get_size()
        bitmap = page.render(scale=TesseractPDFReader.RENDER_DPI / 72)
        image = TesseractPDFReader._preprocess(bitmap.to_pil())
        logical_page = physical_index - start_page + 1
        words, page_text = TesseractPDFReader._read_page(
            image=image,
            logical_page=logical_page,
            page_width=page_width,
            doctop_offset=doctop_offset,
            tessdata_dir=tessdata_dir,
        )
        _raise_if_cancelled(cancel_event)
        all_words.extend(words)
        if logical_page <= TesseractPDFReader.MAX_TEXT_PAGES:
            text_pages.append(page_text)
        doctop_offset += page_height

    return DocumentData(
        raw_text="\n".join(text_pages),
        normalized_text="",
        spatial_words=all_words,
        metadata={
            "start_page": start_page,
            "reader": "tesseract",
            "ocr": True,
            "dpi": TesseractPDFReader.RENDER_DPI,
            "language": TesseractPDFReader.LANGUAGE,
            "tesseract_cmd": str(tesseract_cmd),
            "tessdata_dir": str(tessdata_dir),
        },
    )


def read_paddle_cancelable(
    file_path: str | Path,
    *,
    start_page: int = 0,
    cancel_event: Any | None = None,
) -> DocumentData:
    """PaddleOCR con puntos de cancelación antes y después de cada página."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No existe el PDF: {file_path}")

    _raise_if_cancelled(cancel_event)
    config = PaddleOCRPDFReader._load_config()
    engine = PaddleOCRPDFReader._get_engine(**config)
    dpi = PaddleOCRPDFReader._configured_dpi()
    text_det_limit_side_len = PaddleOCRPDFReader._configured_detection_side_len()
    pdf = pdfium.PdfDocument(str(file_path))
    all_words: list[dict[str, Any]] = []
    text_pages: list[str] = []
    doctop_offset = 0.0
    backend_recovered = False

    for physical_index in range(start_page, len(pdf)):
        _raise_if_cancelled(cancel_event)
        page = pdf[physical_index]
        page_width, page_height = page.get_size()
        bitmap = page.render(scale=dpi / 72.0)
        image = bitmap.to_pil().convert("RGB")
        logical_page = physical_index - start_page + 1
        engine, words, page_text, recovered_backend = (
            PaddleOCRPDFReader._read_page_with_backend_recovery(
                engine=engine,
                config=config,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
            )
        )
        if recovered_backend:
            config = {**config, "enable_mkldnn": False}
            backend_recovered = True
        _raise_if_cancelled(cancel_event)
        all_words.extend(words)
        if logical_page <= PaddleOCRPDFReader.MAX_TEXT_PAGES:
            text_pages.append(page_text)
        doctop_offset += page_height

    return DocumentData(
        raw_text="\n".join(text_pages),
        normalized_text="",
        spatial_words=all_words,
        metadata={
            "start_page": start_page,
            "source_path": str(file_path.resolve()),
            "reader": "paddleocr",
            "ocr": True,
            "dpi": dpi,
            "language": config["language"],
            "device": config["device"],
            "detection_model": config["detection_model_name"],
            "recognition_model": config["recognition_model_name"],
            "coordinate_space": "pdf_points",
            "network_model_downloads": False,
            "mkldnn_enabled": config["enable_mkldnn"],
            "mkldnn_backend_recovered": backend_recovered,
            "cpu_threads": config["cpu_threads"],
            "text_det_limit_side_len": text_det_limit_side_len,
            "text_det_limit_type": "max",
        },
    )
