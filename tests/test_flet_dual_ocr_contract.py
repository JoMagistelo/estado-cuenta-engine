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
    assert "confirmed = result.confirmed_ocr_engine" in source
    assert "if confirmed is None" in source
    assert "la elección para Excel siempre es manual" in source


def test_dual_ocr_comparison_replaces_execution_diagnostic_card():
    source = (Path(__file__).resolve().parents[1] / "app" / "main_flet.py").read_text(
        encoding="utf-8"
    )

    expected = """if method == 'OCR':
            candidate_selector = ocr_candidate_selector(result)
            if candidate_selector is not None:"""
    assert expected in source
    assert "audit_view.controls.append(candidate_selector)" in source
    assert """else:
                audit_view.controls.append(ocr_execution_card(result))""" in source
