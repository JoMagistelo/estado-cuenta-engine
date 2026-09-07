from pathlib import Path


def test_main_window_opens_in_top_left_corner():
    source = Path("app/main_desktop.py").read_text(encoding="utf-8")
    prepare_block = source.split("def _prepare_main_window", 1)[1].split(
        "async def _show_startup_error", 1
    )[0]

    assert "page.window.left = 0" in prepare_block
    assert "page.window.top = 0" in prepare_block
