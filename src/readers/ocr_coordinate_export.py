from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from readers.models import DocumentData


SPATIAL_WORD_FIELDS = (
    "text",
    "page",
    "x0",
    "x1",
    "top",
    "bottom",
    "doctop",
    "width",
    "height",
    "confidence",
)

SAFE_METADATA_FIELDS = (
    "reader",
    "ocr",
    "start_page",
    "dpi",
    "language",
    "device",
    "coordinate_space",
    "detection_model",
    "recognition_model",
    "mkldnn_enabled",
    "cpu_threads",
    "text_recognition_batch_size",
    "text_det_limit_side_len",
    "text_det_limit_type",
)


def spatial_words_for_debug(document: DocumentData) -> list[dict[str, Any]]:
    """Devuelve palabras OCR y coordenadas en un formato estable para diagnóstico.

    El formato es deliberadamente común para Tesseract y PaddleOCR, de modo que
    los mismos parsers/normalizadores puedan compararse contra ambos readers.
    """
    result: list[dict[str, Any]] = []

    for word in document.spatial_words or []:
        if not isinstance(word, dict):
            continue

        item = {
            field: word.get(field)
            for field in SPATIAL_WORD_FIELDS
            if field in word
        }

        if item.get("text") in (None, ""):
            continue

        result.append(item)

    return result


def build_coordinate_payload(
    document: DocumentData,
    *,
    engine: str,
    source_name: str,
) -> dict[str, Any]:
    """Construye el JSON técnico sin incluir raw_text completo ni ruta absoluta."""
    metadata = document.metadata or {}

    safe_metadata = {
        field: metadata.get(field)
        for field in SAFE_METADATA_FIELDS
        if field in metadata
    }

    words = spatial_words_for_debug(document)

    return {
        "engine": str(engine).strip().lower(),
        "source_name": Path(source_name).name,
        "metadata": safe_metadata,
        "word_count": len(words),
        "spatial_words": words,
    }


def write_coordinate_json(
    document: DocumentData,
    *,
    engine: str,
    source_name: str,
    output_path: str | Path,
) -> Path:
    """Escribe un diagnóstico local de palabras/coordenadas OCR en UTF-8."""
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = build_coordinate_payload(
        document,
        engine=engine,
        source_name=source_name,
    )

    destination.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return destination
