from __future__ import annotations

from pathlib import Path

from readers.pdf_text_reader import PDFTextReader


class _FakePage:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.extract_calls = 0

    def extract_text(self):
        self.extract_calls += 1
        return self.text


class _FakePDF:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_read_stage_inspects_scanned_pages_only_once(monkeypatch) -> None:
    pages = [_FakePage(None) for _ in range(9)]
    fake_pdf = _FakePDF(pages)

    monkeypatch.setattr(
        "readers.pdf_text_reader.pdfplumber.open",
        lambda _path: fake_pdf,
    )

    result = PDFTextReader.read_stage(Path("scan.pdf"))

    assert result.raw_text == ""
    assert result.initial_empty_pages == 9
    assert result.has_extractable_text is False
    assert [page.extract_calls for page in pages] == [1] * 9


def test_read_stage_keeps_searching_after_initial_window_without_rereading(monkeypatch) -> None:
    pages = [
        _FakePage(None),
        _FakePage(None),
        _FakePage(None),
        _FakePage(None),
        _FakePage(None),
        _FakePage(None),
        _FakePage("CONTENIDO DIGITAL"),
        _FakePage("NO NECESARIO"),
    ]
    fake_pdf = _FakePDF(pages)

    monkeypatch.setattr(
        "readers.pdf_text_reader.pdfplumber.open",
        lambda _path: fake_pdf,
    )

    result = PDFTextReader.read_stage(Path("delayed-digital.pdf"))

    assert result.raw_text == ""
    assert result.initial_empty_pages == 6
    assert result.has_extractable_text is True
    assert [page.extract_calls for page in pages] == [1, 1, 1, 1, 1, 1, 1, 0]
