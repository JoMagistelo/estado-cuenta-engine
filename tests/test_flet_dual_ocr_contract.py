from pathlib import Path


def test_flet_keeps_manual_dual_ocr_review_controls():
    source = (Path(__file__).resolve().parents[1] / "app" / "main_flet.py").read_text(
        encoding="utf-8"
    )

    assert "def ocr_candidate_selector(result)" in source
    assert "if len(engines) < 2:" in source
    assert "content='Ver resultado'" in source
    assert "'Elegir para Excel'" in source
    assert "result.preview_ocr_engine(engine)" in source
    assert "result.select_ocr_engine(engine)" in source
    assert "La elección para Excel siempre es manual" in source
