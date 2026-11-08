"""Construct the real Flet controls when the optional desktop extra is present."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_real_flet_workspace_construction(monkeypatch):
    ft = pytest.importorskip("flet")
    monkeypatch.syspath_prepend(str(Path("app").resolve()))
    import main_flet

    class Page:
        def __init__(self):
            self.window = SimpleNamespace()
            self.controls = []
        def add(self, *controls):
            self.controls.extend(controls)
        def update(self):
            pass
        def run_task(self, *args):
            pass

    # Native WM_DROPFILES is exercised separately, with a real HWND.
    monkeypatch.setattr(main_flet.WindowsPdfDropZone, "start", lambda self: False)
    page = Page()
    main_flet.main(page)
    tabs = next(c for c in page.controls[0].controls if isinstance(c, ft.Tabs))
    assert tabs.length == 2
    assert [t.label for t in tabs.content.controls[0].tabs] == ["Extracción de movimientos", "CEP Banxico"]
