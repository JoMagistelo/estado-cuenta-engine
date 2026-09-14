from __future__ import annotations

from typing import Any

from PIL import Image

from parsers.hsbc.ocr_summary_rescue import _ocr_crop


def _word(text: str, x0: float, x1: float, top: float) -> dict[str, Any]:
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + 6.0,
        "doctop": top,
        "page": 1,
    }


def test_hsbc_summary_rescue_reocr_only_left_summary_table(monkeypatch) -> None:
    page_width = 612.0
    image = Image.new("L", (2550, 3300), "white")
    resumen = _word("Resumen", 118.56, 150.72, 266.4)
    saldos = _word("Saldos", 164.16, 187.68, 266.4)
    existing = [resumen, _word("de", 153.36, 161.52, 266.4), saldos]

    # Coordenadas PDF que el segundo pase debe recuperar dentro de la columna
    # monetaria real del Resumen de Saldos.
    recovered = [
        ("$15,116.04", 207.0, 284.0),
        ("$156,759.19", 201.0, 301.0),
        ("$0.00", 221.0, 318.5),
        ("$123,970.67", 202.0, 334.8),
        ("$0.00", 221.0, 352.6),
        ("$0.00", 221.0, 370.1),
        ("$47,904.56", 205.0, 388.3),
        ("$47,904.56", 205.0, 426.7),
        ("$0.00", 221.0, 444.0),
        ("$25,971.21", 206.9, 462.0),
    ]

    pixel_to_pdf = page_width / image.width
    header_left = 118.56
    header_right = 187.68
    header_top = 266.4
    crop_left = max(0.0, header_left - 80.0)
    crop_right = min(page_width * 0.44, header_right + 85.0)
    crop_top = max(0.0, header_top - 8.0)
    crop_bottom = min(792.0, header_top + 210.0)
    px0 = int(crop_left / pixel_to_pdf)
    py0 = int(crop_top / pixel_to_pdf)

    data = {
        "text": [item[0] for item in recovered],
        "left": [round(x / pixel_to_pdf) - px0 for _, x, _ in recovered],
        "top": [round(y / pixel_to_pdf) - py0 for _, _, y in recovered],
        "width": [120] * len(recovered),
        "height": [28] * len(recovered),
        "conf": [91] * len(recovered),
    }
    calls: list[str] = []

    def fake_ocr(crop, *, lang, config, output_type, timeout):
        calls.append(config)
        assert crop.width == int(crop_right / pixel_to_pdf) - px0
        assert crop.height == int(crop_bottom / pixel_to_pdf) - py0
        return data

    monkeypatch.setattr(
        "parsers.hsbc.ocr_summary_rescue.pytesseract.image_to_data",
        fake_ocr,
    )

    extra = _ocr_crop(
        image,
        page_width=page_width,
        page_height=792.0,
        logical_page=1,
        doctop_offset=0.0,
        resumen=resumen,
        saldos=saldos,
        existing=existing,
    )

    assert calls == ["--oem 3 --psm 6 -c preserve_interword_spaces=1"]
    assert len(extra) == len(recovered)
    assert {word["text"] for word in extra} >= {"$15,116.04", "$156,759.19", "$123,970.67"}
    assert all(word["page"] == 1 for word in extra)
    assert all(188.68 <= (word["x0"] + word["x1"]) / 2.0 <= 252.68 for word in extra)
