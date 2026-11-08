from __future__ import annotations

import sys

import pytest

from utils.windows_pdf_drop import WindowsPdfDropZone, pdf_drop_paths


def test_drop_accepts_existing_pdf_files_and_unicode_without_duplicates(tmp_path):
    pdf = tmp_path / "Estado de cuenta ñ.PDF"
    pdf.write_bytes(b"%PDF-1.4")
    other = tmp_path / "other.txt"
    other.write_text("not PDF")
    assert pdf_drop_paths([pdf, pdf, other, tmp_path, tmp_path / "missing.pdf"]) == [str(pdf.resolve())]


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
