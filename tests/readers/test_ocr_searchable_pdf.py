from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from readers.models import DocumentData
from readers.ocr_searchable_pdf import OCR_LAYER_TAG, OCRSearchablePDFWriter
from readers.pdf_text_reader import PDFTextReader
from readers.pdf_word_reader import PDFWordReader
from readers.reader_manager import ReaderManager


def _blank_pdf(path: Path, *, width: float = 300, height: float = 400, rotation: int = 0) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    if rotation:
        page.rotate(rotation)
    with path.open("wb") as file_handle:
        writer.write(file_handle)


def _assert_box(actual: dict, expected: dict) -> None:
    for field in ("x0", "x1", "top", "bottom"):
        assert float(actual[field]) == pytest.approx(float(expected[field]), abs=0.02)


def test_searchable_pdf_roundtrip_preserves_unicode_and_exact_word_boxes(tmp_path: Path):
    source = tmp_path / "scan.pdf"
    output = tmp_path / "scan_ocr.pdf"
    _blank_pdf(source)

    # Las dos primeras cajas se tocan a propósito: el escritor debe mantenerlas
    # como palabras independientes sin inventar un hueco espacial.
    words = [
        {"text": "DEPÓSITO", "x0": 20.0, "x1": 90.0, "top": 30.0, "bottom": 42.0, "page": 1},
        {"text": "Ñ", "x0": 90.0, "x1": 101.0, "top": 30.0, "bottom": 42.0, "page": 1},
        {"text": "漢字", "x0": 120.0, "x1": 155.0, "top": 70.0, "bottom": 84.0, "page": 1},
    ]

    OCRSearchablePDFWriter.write(source, words, output)

    projected = PDFWordReader.read(output, layer_tag=OCR_LAYER_TAG)
    assert [word["text"] for word in projected] == ["DEPÓSITO", "Ñ", "漢字"]
    assert len(projected) == len(words)
    for actual, expected in zip(projected, words):
        assert actual["page"] == expected["page"]
        _assert_box(actual, expected)

    text = PDFTextReader.read(output, layer_tag=OCR_LAYER_TAG)
    assert "DEPÓSITO" in text
    assert "Ñ" in text
    assert "漢字" in text


def test_searchable_pdf_normalizes_page_rotation_without_moving_ocr_geometry(tmp_path: Path):
    source = tmp_path / "rotated_scan.pdf"
    output = tmp_path / "rotated_scan_ocr.pdf"
    _blank_pdf(source, width=300, height=400, rotation=90)

    # PDFium ve la página rotada como 400 x 300. Las cajas OCR pertenecen a ese
    # espacio visual; el artefacto debe convertir /Rotate a contenido real.
    words = [
        {"text": "ROTADO", "x0": 40.0, "x1": 130.0, "top": 50.0, "bottom": 66.0, "page": 1},
    ]
    OCRSearchablePDFWriter.write(source, words, output)

    with output.open("rb") as file_handle:
        reader = PdfReader(file_handle)
        page = reader.pages[0]
        assert int(page.rotation or 0) == 0
        assert float(page.mediabox.width) == pytest.approx(400.0)
        assert float(page.mediabox.height) == pytest.approx(300.0)

    projected = PDFWordReader.read(output, layer_tag=OCR_LAYER_TAG)
    assert len(projected) == 1
    assert projected[0]["text"] == "ROTADO"
    _assert_box(projected[0], words[0])


def test_reader_manager_returns_only_verified_pdf_layer_to_parser(tmp_path: Path):
    source = tmp_path / "statement.pdf"
    artifacts = tmp_path / "artifacts"
    _blank_pdf(source)

    native = DocumentData(
        raw_text="OCR NATIVO",
        normalized_text="",
        spatial_words=[
            {"text": "HSBC", "x0": 30.0, "x1": 80.0, "top": 25.0, "bottom": 39.0, "page": 1},
            {"text": "MÉXICO", "x0": 90.0, "x1": 145.0, "top": 25.0, "bottom": 39.0, "page": 1},
        ],
        metadata={"reader": "tesseract", "ocr": True, "confidence_source": "native"},
    )

    canonical = ReaderManager.project_ocr_document(
        source,
        native,
        engine="tesseract",
        artifact_dir=artifacts,
    )

    artifact = Path(canonical.metadata["ocr_artifact_path"])
    assert artifact.is_file()
    assert canonical.metadata["ocr_text_layer_verified"] is True
    assert canonical.metadata["canonical_reader"] == "pdfplumber"
    assert canonical.metadata["ocr_native_word_count"] == 2
    assert canonical.metadata["ocr_canonical_word_count"] == 2
    assert [word["text"] for word in canonical.spatial_words] == ["HSBC", "MÉXICO"]
    assert "HSBC" in canonical.raw_text
