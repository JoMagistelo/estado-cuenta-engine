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
    assert [t.label for t in tabs.content.tabs] == ["Extracción de movimientos", "CEP Banxico"]
    # Both pages remain mounted, including while background extraction updates.
    body = page.controls[0].controls[-2]
    extraction, cep = body.controls
    assert extraction.visible and not cep.visible
    footer = page.controls[0].controls[-1]
    assert not footer.visible
    tabs.selected_index = 1
    tabs.on_change(SimpleNamespace(control=tabs))
    assert not extraction.visible and cep.visible and not footer.visible
    tabs.selected_index = 0
    tabs.on_change(SimpleNamespace(control=tabs))
    assert extraction.visible and not cep.visible


def test_normalize_is_explicit_and_txt_is_saved_as_plain_text(monkeypatch, tmp_path):
    import asyncio
    from io import BytesIO
    from openpyxl import Workbook

    pytest.importorskip("flet")
    monkeypatch.syspath_prepend(str(Path("app").resolve()))
    import cep_panel

    page = SimpleNamespace(update=lambda: None)
    panel = cep_panel.CepPanel(page, lambda: [], lambda: True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimientos"
    ws.append(["Banco", "Fecha de Operación", "Cargo", "Abono", "Concepto", "Clave de Rastreo",
               "CLABE del Beneficiario", "CLABE Titular", "Fecha de Corte"])
    holder = "002180032240946700"
    ws.append(["banamex", "03 ENE", 1.25, 0, "SPEI ENVIADO BANAMEX", "SYNTHETIC001", holder, holder, "14/01/2026"])
    data = BytesIO()
    wb.save(data)
    wb.close()
    panel.set_source(data.getvalue())
    panel.refresh()
    assert not panel.normalize_button.disabled
    assert panel.txt_button.disabled and panel.bundle is None
    asyncio.run(panel.normalize_excel())
    assert panel.bundle is not None and not panel.txt_button.disabled
    assert not hasattr(panel, "raw_button")

    target = tmp_path / "banxico.txt"
    async def save_file(**kwargs):
        assert kwargs["allowed_extensions"] == ["txt"]
        return str(target)
    monkeypatch.setattr(cep_panel.ft, "FilePicker", lambda: SimpleNamespace(save_file=save_file))
    asyncio.run(panel.save_txt(None))
    assert len(target.read_text().splitlines()) == 3
    assert not target.read_bytes().startswith(b"PK")
    assert target.read_text().splitlines()[0].startswith("2026-01-03,SYNTHETIC001,")
