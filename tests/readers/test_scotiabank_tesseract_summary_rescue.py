from __future__ import annotations

from PIL import Image
import pytest

from parsers.scotiabank.extractors.resumen import extract_resumen_financiero_words
from readers.models import DocumentData
from readers.reader_manager import ReaderManager
from readers.scotiabank_summary_ocr import (
    _find_summary_candidate,
    _normalize_summary_money,
    recover_scotiabank_summary_page,
)
from readers.tesseract_pdf_reader import TesseractPDFReader


def _word(
    text: str,
    x0: float,
    x1: float,
    top: float,
    *,
    page: int = 1,
) -> dict[str, object]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 7.0,
        "doctop": top,
        "page": page,
        "confidence": 90.0,
    }


def _scotiabank_summary_without_amounts(page: int = 1) -> list[dict[str, object]]:
    return [
        _word("Scotiabank", 420.0, 570.0, 39.0, page=page),
        _word("Resumen", 118.56, 150.72, 266.4, page=page),
        _word("de", 153.36, 161.52, 266.4, page=page),
        _word("Saldos", 164.16, 187.68, 266.4, page=page),
        _word("Comportamiento", 244.0, 310.0, 266.4, page=page),
        _word("Intereses", 75.84, 104.88, 318.48, page=page),
        _word("recibidos", 106.56, 136.32, 318.72, page=page),
        _word("Retiros", 155.76, 176.40, 334.80, page=page),
        _word("Comisiones", 114.72, 149.52, 352.56, page=page),
        _word("cobradas|", 151.20, 179.04, 352.56, page=page),
        _word("Impuestos", 147.84, 178.56, 370.08, page=page),
        _word("Saldo", 110.88, 127.44, 388.32, page=page),
        _word("final", 129.60, 140.88, 388.32, page=page),
        _word("cuenta", 158.40, 178.32, 388.56, page=page),
        _word("Sobregiro", 319.68, 354.96, 427.68, page=page),
        _word("Saldo", 86.40, 102.96, 426.72, page=page),
        _word("final", 104.88, 116.40, 426.72, page=page),
        _word("cuenta", 118.08, 137.76, 426.96, page=page),
        _word("inversiones!", 145.68, 178.80, 426.72, page=page),
        _word("Sdo.", 106.08, 119.28, 457.68, page=page),
        _word("Prom.", 121.92, 138.96, 457.68, page=page),
        _word("Cta.", 166.56, 178.08, 457.68, page=page),
        _word("$25,971.21", 202.80, 230.40, 461.76, page=page),
    ]


def _ocr_data_for_missing_amounts(
    *,
    page_width: float = 612.0,
    image_width: int = 2550,
    title_y: float = 269.9,
) -> dict[str, list[object]]:
    pixel_to_pdf = page_width / image_width
    px0 = int((page_width * 0.30) / pixel_to_pdf)
    py0 = int((title_y - 1.0) / pixel_to_pdf)
    recovered = [
        ("$15,116.04}", 198.0, 282.0),
        ("$156,759.19}", 198.0, 300.0),
        ("$0.00}", 210.0, 318.0),
        ("$123,970.67)", 198.0, 336.0),
        ("$0.00)", 210.0, 354.0),
        ("$0.00)", 210.0, 372.0),
        ("$47,904.56}", 198.0, 390.0),
        ("$47,904.56}", 198.0, 426.0),
        ("$0.00}", 210.0, 444.0),
        ("$25,971.21", 203.0, 462.0),
    ]
    return {
        "text": [item[0] for item in recovered],
        "left": [round(x / pixel_to_pdf) - px0 for _, x, _ in recovered],
        "top": [round(y / pixel_to_pdf) - py0 for _, _, y in recovered],
        "width": [150] * len(recovered),
        "height": [30] * len(recovered),
        "conf": [90] * len(recovered),
    }


def test_scotiabank_tesseract_recovers_printed_summary_amounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    words = _scotiabank_summary_without_amounts()
    image = Image.new("L", (2550, 3300), "white")
    calls: list[str] = []

    def fake_ocr(crop, *, lang, config, output_type, timeout):
        calls.append(config)
        assert crop.size[0] < image.width
        assert crop.size[1] < image.height
        return _ocr_data_for_missing_amounts()

    monkeypatch.setattr(
        "readers.scotiabank_summary_ocr.pytesseract.image_to_data",
        fake_ocr,
    )
    extra = recover_scotiabank_summary_page(
        image,
        words,
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
    )

    assert calls == ["--oem 3 --psm 11"]
    assert all(word["page"] == 1 for word in extra)
    assert all(word["source"] == "scotiabank_summary_tesseract_retry" for word in extra)

    summary = extract_resumen_financiero_words(words + extra)
    assert summary.saldo_anterior == pytest.approx(15116.04)
    assert summary.depositos_abonos == pytest.approx(156759.19)
    assert summary.retiros_cargos == pytest.approx(123970.67)
    assert summary.saldo_final == pytest.approx(47904.56)
    assert summary.saldo_global == pytest.approx(47904.56)
    assert summary.saldo_promedio == pytest.approx(25971.21)


def test_scotiabank_tesseract_skips_complete_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    words = _scotiabank_summary_without_amounts()
    words.extend(
        [
            _word("$15,116.04", 198.0, 238.0, 282.0),
            _word("$156,759.19", 198.0, 238.0, 300.0),
            _word("$123,970.67", 198.0, 238.0, 336.0),
            _word("$47,904.56", 198.0, 238.0, 390.0),
        ]
    )

    def unexpected(*args, **kwargs):
        pytest.fail("No debe releer un resumen que ya contiene sus importes")

    monkeypatch.setattr(
        "readers.scotiabank_summary_ocr.pytesseract.image_to_data",
        unexpected,
    )
    assert recover_scotiabank_summary_page(
        Image.new("L", (2550, 3300), "white"),
        words,
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
    ) == []


def test_scotiabank_tesseract_requires_summary_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    words = [
        _word("Scotiabank", 420.0, 570.0, 39.0),
        _word("Resumen", 118.0, 150.0, 266.0),
        _word("Saldos", 164.0, 188.0, 266.0),
    ]

    def unexpected(*args, **kwargs):
        pytest.fail("No debe ejecutar OCR sobre una portada o publicidad")

    monkeypatch.setattr(
        "readers.scotiabank_summary_ocr.pytesseract.image_to_data",
        unexpected,
    )
    assert recover_scotiabank_summary_page(
        Image.new("L", (2550, 3300), "white"),
        words,
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
    ) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$47,904.56}", "$47,904.56"),
        ("$47,90456", "$47,904.56"),
        ("$4790456", "$47,904.56"),
        ("$156,759.19)", "$156,759.19"),
        ("-$12397067", "-$123,970.67"),
    ],
)
def test_scotiabank_summary_retry_normalizes_only_preserved_digits(
    raw: str,
    expected: str,
) -> None:
    assert _normalize_summary_money(raw) == expected


def test_reader_manager_adds_scotiabank_retry_to_tesseract_words(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    primary = DocumentData(
        spatial_words=_scotiabank_summary_without_amounts(),
        metadata={"reader": "tesseract", "ocr": True},
    )
    recovered = [_word("$15,116.04", 198.0, 238.0, 282.0)]
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"fixture")

    monkeypatch.setattr(
        TesseractPDFReader,
        "read",
        classmethod(lambda cls, file_path, start_page=0: primary),
    )
    monkeypatch.setattr(
        "readers.reader_manager.recover_scotiabank_summary_words",
        lambda file_path, words, start_page=0: recovered,
    )

    result = ReaderManager.read_ocr_engine(
        source,
        engine="tesseract",
    )

    assert result is primary
    assert recovered[0] in result.spatial_words
    assert result.metadata["reader"] == "tesseract"
    assert result.metadata["ocr"] is True


def test_scotiabank_retry_locates_summary_after_preliminary_pages() -> None:
    advertisement = [
        _word("Scotiabank", 420.0, 570.0, 39.0, page=1),
        _word("Resumen", 118.0, 150.0, 266.0, page=1),
        _word("Saldos", 164.0, 188.0, 266.0, page=1),
        _word("Saldo", 80.0, 105.0, 300.0, page=1),
    ]
    notice = [
        _word("Scotiabank", 420.0, 570.0, 39.0, page=2),
        _word("Seguridad", 80.0, 130.0, 180.0, page=2),
    ]
    statement = _scotiabank_summary_without_amounts(page=3)

    candidate = _find_summary_candidate([*advertisement, *notice, *statement])

    assert candidate is not None
    assert candidate[0] == 3
