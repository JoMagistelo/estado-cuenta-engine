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


def test_movement_totals_are_clickable_view_filters_only():
    source = Path("app/main_flet.py").read_text(encoding="utf-8")

    assert "from utils.result_state import (" in source
    assert "movement_matches_kind," in source
    assert "active_kind: dict[str, str | None] = {'value': None}" in source
    assert "cargo_chip.on_click = lambda e: toggle_kind('cargo')" in source
    assert "abono_chip.on_click = lambda e: toggle_kind('abono')" in source
    assert "active_kind['value'] = None if active_kind['value'] == kind else kind" in source
    assert "snapshot = list(results)" in source
