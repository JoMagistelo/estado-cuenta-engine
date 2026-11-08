from __future__ import annotations

import sys

import pytest

from utils.windows_pdf_drop import (
    PDF_DROP_HEIGHT_DIP,
    WindowsPdfDropZone,
    drop_window_geometry,
    pdf_drop_paths,
)


def test_drop_accepts_existing_pdf_files_and_unicode_without_duplicates(tmp_path):
    pdf = tmp_path / "Estado de cuenta ñ.PDF"
    pdf.write_bytes(b"%PDF-1.4")
    other = tmp_path / "other.txt"
    other.write_text("not PDF")
    assert pdf_drop_paths([pdf, pdf, other, tmp_path, tmp_path / "missing.pdf"]) == [str(pdf.resolve())]


def test_dpi_drop_receiver_fits_the_reserved_footer_and_never_covers_export():
    for scale in (1.0, 1.25, 1.5, 2.0):
        width, height = 1400, 830
        x, y = 50, 40
        left, top, actual_width, actual_height = drop_window_geometry(
            width, height, x, y, scale
        )
        assert actual_height == round(PDF_DROP_HEIGHT_DIP * scale)
        assert actual_height >= 96
        assert left > x
        assert top >= y
        assert left + actual_width <= x + width
        assert top + actual_height < y + height
        # Exportación is outside the reserved native footer.
        assert top == y + height - round(14 * scale) - actual_height


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows Explorer drop lane")
def test_windows_native_lane_delivers_real_unicode_wm_dropfiles(tmp_path):
    import ctypes as c
    import struct
    import time
    from ctypes import wintypes as w

    user = c.WinDLL("user32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    user.CreateWindowExW.restype = w.HWND
    user.CreateWindowExW.argtypes = (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int,
        c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
    user.DestroyWindow.argtypes = (w.HWND,)
    user.PeekMessageW.argtypes = (c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT)
    user.TranslateMessage.argtypes = (c.POINTER(w.MSG),)
    user.DispatchMessageW.argtypes = (c.POINTER(w.MSG),)
    user.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    kernel.GlobalAlloc.restype = w.HGLOBAL
    kernel.GlobalAlloc.argtypes = (w.UINT, c.c_size_t)
    kernel.GlobalLock.restype = w.LPVOID
    kernel.GlobalLock.argtypes = (w.HGLOBAL,)
    kernel.GlobalUnlock.argtypes = (w.HGLOBAL,)
    parent = user.CreateWindowExW(0, "STATIC", "Engine drop test", 0x10CF0000,
                                   0, 0, 800, 600, None, None, None, None)
    assert parent, c.WinError(c.get_last_error())
    found, errors = [], []
    zone = WindowsPdfDropZone("unused", found.append, errors.append, parent_handle=parent)

    def until(predicate):
        deadline = time.monotonic() + 12
        message = w.MSG()
        while time.monotonic() < deadline:
            while user.PeekMessageW(c.byref(message), None, 0, 0, 1):
                user.TranslateMessage(c.byref(message))
                user.DispatchMessageW(c.byref(message))
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError(f"Native drop timeout: {errors}")

    try:
        zone.start()
        until(lambda: zone.hwnd or errors)
        assert not errors
        user.GetWindowLongW.argtypes = (w.HWND, c.c_int)
        user.GetWindowLongW.restype = c.c_long
        assert user.GetWindowLongW(zone.hwnd, -16) & 0x80000000  # WS_POPUP
        assert not user.GetWindowLongW(zone.hwnd, -16) & 0x40000000  # never WS_CHILD
        path = tmp_path / "Prueba Unicode ñ con espacios.pdf"
        path.write_bytes(b"%PDF-1.4")
        data = struct.pack("<IiiII", 20, 0, 0, 0, 1) + (str(path) + "\0\0").encode("utf-16-le")
        memory = kernel.GlobalAlloc(0x42, len(data))
        pointer = kernel.GlobalLock(memory)
        c.memmove(pointer, data, len(data))
        kernel.GlobalUnlock(memory)
        assert user.PostMessageW(zone.hwnd, 0x233, memory, 0)
        until(lambda: found or errors)
        assert not errors
        assert found == [[str(path)]]
    finally:
        zone.close()
        until(lambda: zone.hwnd is None)
        user.DestroyWindow(parent)


@pytest.mark.skipif(sys.platform != "win32", reason="Real Flet Windows client")
def test_window_discovery_and_drop_with_real_flet_client(tmp_path):
    """Exercise the launcher/client process boundary missing from the old test."""
    pytest.importorskip("flet")
    import ctypes as c
    import json
    import os
    import struct
    import subprocess
    import time
    from ctypes import wintypes as w
    from pathlib import Path

    probe = tmp_path / "flet_drop_probe.py"
    probe.write_text('''
import asyncio, json, sys, time
from pathlib import Path
import flet as ft
import main_flet
from utils.windows_pdf_drop import WindowsPdfDropZone

folder = Path(sys.argv[1])
async def main(page):
    found, errors = [], []
    zones = []
    def create_zone(title, on_files, on_error):
        zone = WindowsPdfDropZone("Engine synthetic drop probe", found.append, errors.append)
        zones.append(zone)
        return zone
    main_flet.WindowsPdfDropZone = create_zone
    main_flet.main(page)
    page.title = "Engine synthetic drop probe"
    page.update()
    zone = zones[0]
    async def monitor():
        start = time.monotonic()
        announced = False
        try:
            while time.monotonic() - start < 70:
                if errors:
                    (folder / "error.json").write_text(json.dumps(errors))
                    return
                if zone.ready and not announced:
                    (folder / "ready.json").write_text(json.dumps({"hwnd": zone.hwnd}))
                    announced = True
                if found:
                    (folder / "done.json").write_text(json.dumps(found))
                    return
                await asyncio.sleep(0.05)
        finally:
            zone.close()
            await page.window.destroy()
    page.run_task(monitor)
ft.run(main)
''', encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(Path("src").resolve()), str(Path("app").resolve()), env.get("PYTHONPATH", "")))
    env.pop("FLET_APP_HIDDEN", None)
    with (tmp_path / "probe.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(probe), str(tmp_path)], env=env,
                                   stdout=log, stderr=log)
        try:
            def wait_for(name, timeout=60):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if (tmp_path / "error.json").exists():
                        pytest.fail((tmp_path / "error.json").read_text())
                    target = tmp_path / name
                    if target.exists():
                        try:
                            return json.loads(target.read_text())
                        except json.JSONDecodeError:
                            pass
                    if process.poll() is not None:
                        pytest.fail("Flet exited before " + name + ": " + (tmp_path / "probe.log").read_text())
                    time.sleep(0.05)
                pytest.fail("Flet drop probe timed out: " + (tmp_path / "probe.log").read_text())
            hwnd = wait_for("ready.json")["hwnd"]
            path = tmp_path / "Synthetic Unicode ñ.pdf"
            path.write_bytes(b"%PDF-1.4")
            payload = struct.pack("<IiiII", 20, 0, 0, 0, 1) + (str(path) + "\0\0").encode("utf-16-le")
            kernel = c.WinDLL("kernel32", use_last_error=True)
            user = c.WinDLL("user32", use_last_error=True)
            kernel.GlobalAlloc.restype = w.HGLOBAL
            kernel.GlobalAlloc.argtypes = (w.UINT, c.c_size_t)
            kernel.GlobalLock.restype = w.LPVOID
            kernel.GlobalLock.argtypes = (w.HGLOBAL,)
            kernel.GlobalUnlock.argtypes = (w.HGLOBAL,)
            user.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
            memory = kernel.GlobalAlloc(0x42, len(payload))
            pointer = kernel.GlobalLock(memory)
            c.memmove(pointer, payload, len(payload))
            kernel.GlobalUnlock(memory)
            assert user.PostMessageW(hwnd, 0x233, memory, 0)
            assert wait_for("done.json", 15) == [[str(path)]]
            process.wait(timeout=15)
            assert process.returncode == 0
        finally:
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
