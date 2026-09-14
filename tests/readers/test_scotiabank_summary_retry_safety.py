from __future__ import annotations

from pathlib import Path

from readers import scotiabank_summary_ocr as rescue


def test_scotiabank_summary_retry_never_breaks_primary_ocr(monkeypatch) -> None:
    def explode(_words):
        raise RuntimeError("secondary OCR failed")

    monkeypatch.setattr(rescue, "_find_summary_candidate", explode)

    assert rescue.recover_scotiabank_summary_words(
        Path("missing.pdf"),
        [{"text": "Resumen", "page": 1}],
    ) == []
