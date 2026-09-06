from __future__ import annotations


OCR_TESSERACT = "tesseract"
OCR_PADDLEOCR = "paddleocr"
SUPPORTED_OCR_ENGINES = (
    OCR_TESSERACT,
    OCR_PADDLEOCR,
)


def normalize_ocr_engine(engine: str | None) -> str:
    """Normaliza la preferencia de motor OCR con Tesseract como valor seguro."""
    normalized = str(engine or "").strip().lower()
    if normalized not in SUPPORTED_OCR_ENGINES:
        return OCR_TESSERACT
    return normalized


def secondary_ocr_engine(primary_engine: str | None) -> str:
    """Devuelve el motor alternativo al OCR primario solicitado."""
    primary = normalize_ocr_engine(primary_engine)
    if primary == OCR_PADDLEOCR:
        return OCR_TESSERACT
    return OCR_PADDLEOCR
