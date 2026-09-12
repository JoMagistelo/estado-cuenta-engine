from __future__ import annotations

from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter

from injectors.tesseract_pdf_injector import TesseractPDFInjector


class _FakeBitmap:
    def to_pil(self):
        return Image.new("RGB", (2550, 3300), "white")


class _FakePage:
    def render(self, scale):
        assert scale == TesseractPDFInjector.RENDER_DPI / 72.0
        return _FakeBitmap()


class _FakeDocument:
    def __init__(self, _path):
        self._pages = [_FakePage(), _FakePage()]
        self.closed = False

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, index):
        return self._pages[index]

    def close(self):
        self.closed = True


def _single_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    payload = BytesIO()
    writer.write(payload)
    return payload.getvalue()


def test_generates_one_searchable_pdf_with_all_pages(monkeypatch, tmp_path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"placeholder")
    output = tmp_path / "scan_texto_ocr.pdf"
    calls = []

    monkeypatch.setattr(
        "injectors.tesseract_pdf_injector.pdfium.PdfDocument",
        _FakeDocument,
    )
    monkeypatch.setattr(
        "injectors.tesseract_pdf_injector.TesseractPDFReader._configure_tesseract",
        lambda: (tmp_path / "tesseract.exe", tmp_path / "tessdata"),
    )

    def fake_pdf(image, *, extension, lang, config, timeout):
        calls.append((image.size, extension, lang, config, timeout))
        return _single_page_pdf()

    monkeypatch.setattr(
        "injectors.tesseract_pdf_injector.pytesseract.image_to_pdf_or_hocr",
        fake_pdf,
    )

    generated = TesseractPDFInjector.generate(source, output)

    assert generated == output
    assert output.is_file()
    assert len(PdfReader(output).pages) == 2
    assert len(calls) == 2
    assert all(call[1] == "pdf" for call in calls)
    assert all(call[2] == "spa" for call in calls)
    assert all("--dpi 300" in call[3] for call in calls)


def test_refuses_to_overwrite_source_pdf(tmp_path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"placeholder")

    try:
        TesseractPDFInjector.generate(source, source)
    except ValueError as exc:
        assert "ruta distinta" in str(exc)
    else:
        raise AssertionError("Se esperaba ValueError al intentar sobrescribir el original")
