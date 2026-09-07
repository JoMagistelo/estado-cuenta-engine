from pathlib import Path


SOURCE = Path("app/main_flet.py").read_text(encoding="utf-8")


def test_result_rows_expose_full_filename_only_as_hover_feedback():
    assert "file_name = str(item.get('file_name') or '')" in SOURCE
    assert "tooltip=file_name or None" in SOURCE


def test_processing_dialog_has_visual_timer_progress_and_completion_notice():
    assert "loading_dialog_timer_text" in SOURCE
    assert "loading_dialog_progress_bar" in SOURCE
    assert "TIEMPO TRANSCURRIDO" in SOURCE
    assert "Procesamiento activo" in SOURCE
    assert "Te avisaremos con un sonido cuando el lote haya terminado." in SOURCE


def test_completion_sound_uses_only_windows_standard_library():
    assert "def play_completion_sound()" in SOURCE
    assert "if sys.platform != 'win32':" in SOURCE
    assert "import winsound" in SOURCE
    assert "winsound.MessageBeep(winsound.MB_ICONASTERISK)" in SOURCE


def test_single_ocr_execution_diagnostic_card_is_not_present():
    assert "Motor solicitado en Configuración:" not in SOURCE
    assert "def ocr_execution_card" not in SOURCE


def test_processing_dialog_is_not_closed_after_first_completed_file():
    completed_block = SOURCE.split("if event.kind == 'completed':", 1)[1].split(
        "if event.kind == 'error':", 1
    )[0]
    finish_block = SOURCE.split("def finish_controls():", 1)[1].split(
        "async def poller():", 1
    )[0]

    assert "close_loading_dialog()" not in completed_block
    assert "close_loading_dialog()" in finish_block
