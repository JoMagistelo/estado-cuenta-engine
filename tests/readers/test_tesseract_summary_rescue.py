from __future__ import annotations

from PIL import Image
import pytest
from pypdf import PdfWriter

from parsers.bbva.extractors.resumen import extract_resumen_financiero_words
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from readers.tesseract_pdf_reader import TesseractPDFReader


def _word(text: str, x: float, y: float, *, page: int = 1) -> dict:
    return {"text": text, "x0": x, "x1": x + 30,
            "top": y, "bottom": y + 8, "page": page}


def _missing_amounts(page: int = 1) -> list[dict]:
    return [
        _word("BBVA", 25, 36, page=page),
        _word("Comportamiento", 312, 255, page=page),
        _word("Saldo", 312, 269, page=page),
        _word("Anterior", 345, 269, page=page),
        _word("Depósitos", 312, 284, page=page),
        _word("Abonos", 355, 284, page=page),
        _word("138,000.00", 541, 281, page=page),
        _word("Saldo", 312, 325, page=page),
        _word("Promedio", 349, 325, page=page),
        _word("Mínimo", 392, 325, page=page),
        _word("Mensual", 431, 325, page=page),
        _word("0.00", 570, 323, page=page),
    ]


def test_bbva_tesseract_retries_only_missing_summary_cells(monkeypatch, tmp_path) -> None:
    page = 2
    base = _missing_amounts(page)
    image = Image.new("L", (2550, 3300), "white")
    # PDF 612 pt / imagen 2550 px; recorte comienza cerca de (300, 243) pt.
    x_start = int((312 - 12) / .24)
    y_start = int((255 - 12) / .24)
    recovered = [
        ("2,671.26", 550, 266), ("Retiros", 312, 296),
        ("Cargos", 352, 296), ("139,139.16", 541, 295),
        ("Saldo", 312, 309), ("Final", 348, 309),
        ("1,532.10", 552, 309),
    ]
    data = {
        "text": [item[0] for item in recovered],
        "left": [round(x / .24) - x_start for _, x, _ in recovered],
        "top": [round(y / .24) - y_start for _, _, y in recovered],
        "width": [120] * len(recovered),
        "height": [32] * len(recovered),
        "conf": [89] * len(recovered),
    }
    calls: list[str] = []

    def fake_ocr(crop, *, lang, config, output_type, timeout):
        calls.append(config)
        assert crop.size[0] < image.width
        assert crop.size[1] < image.height
        return data

    monkeypatch.setattr("readers.tesseract_pdf_reader.pytesseract.image_to_data", fake_ocr)
    extra = TesseractPDFReader._recover_bbva_summary(image, base, page, 612, 792)

    assert calls == ["--oem 3 --psm 11"]
    assert all(word["page"] == 2 for word in extra)
    assert all(word["doctop"] == pytest.approx(792 + word["top"]) for word in extra)
    result = extract_resumen_financiero_words(base + extra)
    assert result.saldo_anterior == pytest.approx(2671.26)
    assert result.depositos_abonos == pytest.approx(138000.0)
    assert result.retiros_cargos == pytest.approx(139139.16)
    assert result.saldo_final == pytest.approx(1532.10)

    source = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with source.open("wb") as handle:
        writer.write(handle)
    canonical = ReaderManager.project_ocr_document(
        source,
        DocumentData(spatial_words=base + extra, metadata={"reader": "tesseract", "ocr": True}),
        engine="tesseract",
        artifact_dir=tmp_path / "artifacts",
    )
    assert canonical.metadata["ocr_text_layer_verified"] is True
    projected = extract_resumen_financiero_words(canonical.spatial_words)
    assert projected.saldo_anterior == pytest.approx(2671.26)
    assert projected.depositos_abonos == pytest.approx(138000)
    assert projected.retiros_cargos == pytest.approx(139139.16)
    assert projected.saldo_final == pytest.approx(1532.10)


def test_tesseract_does_not_retry_non_bbva_pages(monkeypatch) -> None:
    def unexpected(*args, **kwargs):
        pytest.fail("OCR de rescate en documento ajeno a BBVA")

    monkeypatch.setattr("readers.tesseract_pdf_reader.pytesseract.image_to_data", unexpected)
    words = [word for word in _missing_amounts() if word["text"] != "BBVA"]
    assert TesseractPDFReader._recover_bbva_summary(
        Image.new("L", (2550, 3300)), words, 1, 612, 0
    ) == []


def test_tesseract_recognizes_logo_split_into_b_and_bva(monkeypatch) -> None:
    calls = []

    def empty_rescue(*args, **kwargs):
        calls.append(True)
        return {key: [] for key in
                ("text", "left", "top", "width", "height", "conf")}

    monkeypatch.setattr(
        "readers.tesseract_pdf_reader.pytesseract.image_to_data",
        empty_rescue,
    )
    words = [w for w in _missing_amounts() if w["text"] != "BBVA"]
    words.extend([_word("B", 25, 36), _word("BVA", 57, 36)])
    assert TesseractPDFReader._recover_bbva_summary(
        Image.new("L", (2550, 3300)), words, 1, 612, 0
    ) == []
    assert len(calls) == 1
