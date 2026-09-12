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


def test_dual_ocr_comparison_is_the_only_ocr_result_card():
    source = (Path(__file__).resolve().parents[1] / "app" / "main_flet.py").read_text(
        encoding="utf-8"
    )

    expected = """if method == 'OCR':
            candidate_selector = ocr_candidate_selector(result)
            if candidate_selector is not None:"""
    assert expected in source
    assert "audit_view.controls.append(candidate_selector)" in source
    assert "ocr_execution_card" not in source
    assert "Motor solicitado en Configuración:" not in source


def test_flet_exposes_only_manual_ocr_artifact_and_reprocess_actions():
    source = (Path(__file__).resolve().parents[1] / "app" / "main_flet.py").read_text(
        encoding="utf-8"
    )

    assert "if item.get('processing_method') != 'OCR' or result is None:" in source
    assert "for engine in ordered_artifact_engines(result):" in source
    assert "Descargar PDF con texto incrustado" in source
    assert "tooltip='Reprocesar usando motor secundario'" in source
    assert "or bool(state['reprocess_cancel_events'])" in source
    assert "export_button.disabled = not results or busy" in source
    assert "Espera a que termine el reprocesado OCR antes de generar el Excel." in source
