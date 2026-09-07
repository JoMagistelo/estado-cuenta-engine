from pathlib import Path


def test_flet_movements_table_renders_every_filtered_movement():
    source = Path("app/main_flet.py").read_text(encoding="utf-8")

    assert "MOVEMENT_PAGE_SIZE" not in source
    assert "previous_button" not in source
    assert "next_button" not in source
    assert "enumerate(entries, start=1)" in source
    assert "rebuild_rows(update=False)" in source


def test_flet_window_opens_at_current_size_and_can_be_maximized():
    source = Path("app/main_flet.py").read_text(encoding="utf-8")
    desktop_source = Path("app/main_desktop.py").read_text(encoding="utf-8")

    assert "page.window.width = 1180" in source
    assert "page.window.height = 660" in source
    assert "page.window.max_width = None" in source
    assert "page.window.max_height = None" in source
    assert "page.window.resizable = True" in source
    assert "page.window.maximizable = True" in source
    assert "page.window.maximized = False" in source

    # El splash queda fijo por resizable/maximizable=False, sin imponer límites
    # máximos que Windows pueda conservar al pasar a la ventana principal.
    assert "page.window.max_width = STARTUP_WIDTH" not in desktop_source
    assert "page.window.max_height = STARTUP_HEIGHT" not in desktop_source
