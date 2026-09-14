import ast
from pathlib import Path


SOURCE = Path("app/main_flet.py").read_text(encoding="utf-8")


def test_main_flet_remains_valid_python():
    ast.parse(SOURCE)


def test_add_more_button_is_visible_only_when_session_has_results():
    assert "content='Añadir más estados de cuenta'" in SOURCE
    assert "on_click=pick_more_files" in SOURCE
    assert "add_more_button.visible = has_results" in SOURCE
    assert "add_more_button.disabled = state['running'] or busy or not has_results" in SOURCE


def test_append_mode_preserves_current_results_and_ocr_artifacts():
    initialize_block = SOURCE.split("def initialize_batch(", 1)[1].split(
        "def start_worker(", 1
    )[0]
    fresh_only = initialize_block.split("if not append:", 1)[1].split(
        "state['batch_start_index'] = len(processing_items)", 1
    )[0]

    assert "append: bool = False" in initialize_block
    assert "clear_ocr_artifacts()" in fresh_only
    assert "results.clear()" in fresh_only
    assert "processing_items.clear()" in fresh_only
    assert "audit_view.controls.clear()" in fresh_only
    assert "state['batch_start_index'] = len(processing_items)" in initialize_block


def test_incremental_pipeline_events_are_offset_for_appended_files():
    assert "index_offset: int" in SOURCE
    assert "event_queue.put(('event', batch_id, index_offset, event))" in SOURCE
    assert "index = index_offset + event_index" in SOURCE
    assert "handle_event(message[3], index_offset=message[2])" in SOURCE


def test_excel_export_keeps_using_all_accumulated_results():
    assert "snapshot = list(results)" in SOURCE
