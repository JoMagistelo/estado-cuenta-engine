from __future__ import annotations

import json

from readers.models import DocumentData
from readers.ocr_coordinate_export import (
    build_coordinate_payload,
    write_coordinate_json,
)


def _sample_document() -> DocumentData:
    return DocumentData(
        raw_text="dato sensible que no debe duplicarse como raw_text",
        spatial_words=[
            {
                "text": "ABONO",
                "page": 2,
                "x0": 100.5,
                "x1": 145.5,
                "top": 220.0,
                "bottom": 232.0,
                "doctop": 1012.0,
                "width": 45.0,
                "height": 12.0,
                "confidence": 98.4,
                "campo_interno": "no exportar",
            },
            {
                "text": "",
                "page": 2,
                "x0": 1.0,
            },
        ],
        metadata={
            "reader": "paddleocr",
            "ocr": True,
            "dpi": 300,
            "coordinate_space": "pdf_points",
            "source_path": "C:/privado/estado.pdf",
        },
    )


def test_coordinate_payload_uses_common_spatial_word_schema():
    payload = build_coordinate_payload(
        _sample_document(),
        engine="paddleocr",
        source_name="C:/privado/estado.pdf",
    )

    assert payload["engine"] == "paddleocr"
    assert payload["source_name"] == "estado.pdf"
    assert payload["word_count"] == 1
    assert payload["metadata"]["coordinate_space"] == "pdf_points"
    assert "source_path" not in payload["metadata"]
    assert payload["spatial_words"][0] == {
        "text": "ABONO",
        "page": 2,
        "x0": 100.5,
        "x1": 145.5,
        "top": 220.0,
        "bottom": 232.0,
        "doctop": 1012.0,
        "width": 45.0,
        "height": 12.0,
        "confidence": 98.4,
    }


def test_write_coordinate_json_creates_inspectable_utf8_output(tmp_path):
    destination = write_coordinate_json(
        _sample_document(),
        engine="paddleocr",
        source_name="estado.pdf",
        output_path=tmp_path / "paddle_coords.json",
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert destination.is_file()
    assert payload["word_count"] == 1
    assert payload["spatial_words"][0]["text"] == "ABONO"
    assert "raw_text" not in payload
