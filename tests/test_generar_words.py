"""Exportación directa: datos ficticios y readers aislados, sin modelos OCR."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from readers.models import DocumentData


@pytest.fixture
def cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generar_words.py"
    spec = importlib.util.spec_from_file_location("generar_words_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% fixture sintetica; readers simulados\n")
    return path


def _must_not_run(*args, **kwargs):
    raise AssertionError("Se ejecutó un reader que no corresponde al modo solicitado.")


def test_json_keeps_all_native_fields_values_order_and_input_files(cli, tmp_path, monkeypatch):
    source = tmp_path / "PDFs con espacios"
    pdf = _pdf(source / "ejemplo.pdf")
    output = tmp_path / "salida"
    original_pdf = pdf.read_bytes()
    digital = [
        {
            "text": "segundo",
            "x0": 90.12345678901234,
            "x1": 110.0,
            "top": 1.2,
            "bottom": 9.8,
            "doctop": 793.2,
            "page": 2,
            "upright": True,
            "direction": "ltr",
            "width": 19.87654321098766,
            "height": 8.6,
            "campo_futuro": {"texto": "Árbol Ñ", "lista": [None, False, 0]},
        },
        {"text": "primero\noriginal", "x0": -0.0, "page": 1},
    ]
    ocr = [{"text": "Pádel", "confidence": 98.76543210987654, "x0": 13.25, "page": 3}]
    before_digital, before_ocr = copy.deepcopy(digital), copy.deepcopy(ocr)
    calls = []

    def read_digital(path, start_page):
        calls.append(("digital", path, start_page))
        return digital

    def read_paddle(path, start_page):
        calls.append(("paddleocr", path, start_page))
        return DocumentData(spatial_words=ocr)

    monkeypatch.setattr(cli.PDFWordReader, "read", read_digital)
    monkeypatch.setattr(cli.PaddleOCRPDFReader, "read", read_paddle)
    assert cli.main([str(source), "--salida", str(output)]) == 0
    digital_path = output / "ejemplo__readwords.json"
    ocr_path = output / "ejemplo__paddleocr_words.json"
    assert json.loads(digital_path.read_text(encoding="utf-8")) == before_digital
    assert json.loads(ocr_path.read_text(encoding="utf-8")) == before_ocr
    assert list(json.loads(digital_path.read_text(encoding="utf-8"))[0]) == list(digital[0])
    assert "Árbol Ñ" in digital_path.read_text(encoding="utf-8")
    assert "-0.0" in digital_path.read_text(encoding="utf-8")
    assert calls == [("digital", pdf.resolve(), 0), ("paddleocr", pdf.resolve(), 0)]
    assert digital == before_digital
    assert ocr == before_ocr
    assert pdf.read_bytes() == original_pdf


def test_nested_same_names_uppercase_pdf_and_empty_digital(cli, tmp_path, monkeypatch):
    source, output = tmp_path / "input", tmp_path / "out"
    _pdf(source / "a" / "igual.pdf")
    _pdf(source / "b" / "igual.PDF")
    (source / "ignorar.txt").write_text("no PDF")
    calls = []
    monkeypatch.setattr(cli.PDFWordReader, "read", lambda *args, **kwargs: [])

    def read_paddle(path, start_page):
        calls.append((path.parent.name, start_page))
        return DocumentData(spatial_words=[{"text": path.parent.name}])

    monkeypatch.setattr(cli.PaddleOCRPDFReader, "read", read_paddle)
    assert cli.main([str(source), "--salida", str(output)]) == 0
    assert calls == [("a", 0), ("b", 0)]
    assert not list(output.rglob("*__readwords.json"))
    assert json.loads((output / "a" / "igual__paddleocr_words.json").read_text()) == [{"text": "a"}]
    assert json.loads((output / "b" / "igual__paddleocr_words.json").read_text()) == [{"text": "b"}]


@pytest.mark.parametrize("mode", ["digital", "paddleocr"])
def test_only_requested_reader_runs(cli, tmp_path, monkeypatch, mode):
    source, output = tmp_path / "input", tmp_path / "out"
    _pdf(source / "ejemplo.pdf")
    monkeypatch.setattr(
        cli.PDFWordReader,
        "read",
        _must_not_run if mode == "paddleocr" else lambda *a, **k: [{"text": "digital"}],
    )
    monkeypatch.setattr(
        cli.PaddleOCRPDFReader,
        "read",
        _must_not_run if mode == "digital" else lambda *a, **k: DocumentData(spatial_words=[]),
    )
    assert cli.main([str(source), "--salida", str(output), "--modo", mode]) == 0
    files = list(output.glob("*.json"))
    assert len(files) == 1
    assert (
        files[0].name == f"ejemplo__{'readwords' if mode == 'digital' else 'paddleocr_words'}.json"
    )
    if mode == "paddleocr":
        assert json.loads(files[0].read_text()) == []


@pytest.mark.parametrize("failing_reader", ["digital", "paddleocr"])
def test_reader_error_keeps_other_output_and_continues_batch(
    cli, tmp_path, monkeypatch, failing_reader
):
    source, output = tmp_path / "input", tmp_path / "out"
    _pdf(source / "a.pdf")
    _pdf(source / "b.pdf")
    calls = []

    def read(mode, path):
        calls.append((mode, path.name))
        if mode == failing_reader and path.name == "a.pdf":
            raise RuntimeError("fallo controlado de lectura")
        return [{"text": mode}]

    monkeypatch.setattr(cli.PDFWordReader, "read", lambda p, **k: read("digital", p))
    monkeypatch.setattr(
        cli.PaddleOCRPDFReader,
        "read",
        lambda p, **k: DocumentData(spatial_words=read("paddleocr", p)),
    )
    assert cli.main([str(source), "--salida", str(output)]) == 1
    assert len(calls) == 4
    assert len(list(output.glob("*.json"))) == 3


def test_default_output_is_project_output_from_another_cwd(cli, tmp_path, monkeypatch):
    source = tmp_path / "input"
    _pdf(source / "ejemplo.pdf")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cli, "PROJECT_ROOT", project)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.PDFWordReader, "read", lambda *a, **k: [{"text": "original"}])
    assert cli.main([str(source), "--modo", "digital"]) == 0
    assert (project / "output" / "ejemplo__readwords.json").is_file()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("source_kind", ["missing", "empty", "file"])
def test_invalid_input_does_not_read_or_create_outputs(cli, tmp_path, monkeypatch, source_kind):
    source, output = tmp_path / "input", tmp_path / "out"
    if source_kind == "empty":
        source.mkdir()
    elif source_kind == "file":
        source.write_text("no es carpeta")
    monkeypatch.setattr(cli.PDFWordReader, "read", _must_not_run)
    monkeypatch.setattr(cli.PaddleOCRPDFReader, "read", _must_not_run)
    assert cli.main([str(source), "--salida", str(output)]) == 2
    assert not output.exists()


def test_bad_native_value_is_not_coerced_and_previous_json_is_kept(cli, tmp_path, monkeypatch):
    source, output = tmp_path / "input", tmp_path / "out"
    _pdf(source / "ejemplo.pdf")
    output.mkdir()
    path = output / "ejemplo__readwords.json"
    path.write_text('[{"text": "previo"}]', encoding="utf-8")
    monkeypatch.setattr(cli.PDFWordReader, "read", lambda *a, **k: [{"text": object()}])
    assert cli.main([str(source), "--salida", str(output), "--modo", "digital"]) == 1
    assert json.loads(path.read_text()) == [{"text": "previo"}]
    assert list(output.iterdir()) == [path]


def test_real_digital_pdf_exports_exact_pdfwordreader_result(cli, tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    source, output = tmp_path / "input", tmp_path / "out"
    source.mkdir()
    pdf = source / "digital.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 350 Td (PALABRA DIGITAL) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    with pdf.open("wb") as handle:
        writer.write(handle)
    original_pdf = pdf.read_bytes()
    expected = cli.PDFWordReader.read(pdf, start_page=0)
    assert [w["text"] for w in expected] == ["PALABRA", "DIGITAL"]
    assert cli.main([str(source), "--salida", str(output), "--modo", "digital"]) == 0
    result = json.loads((output / "digital__readwords.json").read_text(encoding="utf-8"))
    assert result == expected
    assert pdf.read_bytes() == original_pdf
