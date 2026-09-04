from __future__ import annotations

from readers.paddleocr_pdf_reader import PaddleOCRPDFReader


def test_split_recognition_into_words_keeps_word_schema():
    words = PaddleOCRPDFReader._split_recognition_into_words(
        text="SALDO FINAL 13,478.19",
        pdf_box=(100.0, 200.0, 300.0, 212.0),
        logical_page=2,
        doctop_offset=792.0,
        confidence=96.5,
    )

    assert [word["text"] for word in words] == [
        "SALDO",
        "FINAL",
        "13,478.19",
    ]

    for word in words:
        assert set(
            (
                "text",
                "x0",
                "x1",
                "top",
                "bottom",
                "doctop",
                "width",
                "height",
                "upright",
                "direction",
                "page",
                "confidence",
            )
        ).issubset(word)

        assert word["page"] == 2
        assert word["top"] == 200.0
        assert word["bottom"] == 212.0
        assert word["doctop"] == 992.0
        assert word["confidence"] == 96.5


def test_split_recognition_into_words_preserves_left_to_right_order():
    words = PaddleOCRPDFReader._split_recognition_into_words(
        text="01 PAGO NOMINA 1,250.00",
        pdf_box=(40.0, 100.0, 400.0, 112.0),
        logical_page=1,
        doctop_offset=0.0,
        confidence=90.0,
    )

    assert [word["text"] for word in words] == [
        "01",
        "PAGO",
        "NOMINA",
        "1,250.00",
    ]

    assert all(
        previous["x0"] < following["x0"]
        for previous, following in zip(
            words,
            words[1:],
        )
    )


def test_result_field_supports_mapping_result():
    result = {
        "rec_texts": ["HSBC"],
        "rec_scores": [0.99],
        "rec_boxes": [[10, 20, 30, 40]],
    }

    assert PaddleOCRPDFReader._result_field(
        result,
        "rec_texts",
        [],
    ) == ["HSBC"]
