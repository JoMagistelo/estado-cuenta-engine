"""Explorer drop strip owned by the Flet window, without cross-process parenting.

An owned, nonactivating WS_POPUP avoids attaching a Python child HWND to the
Flutter renderer (which can reset DPI state or leave a grey rendering surface).
It follows the reserved 50-DIP area and hides on tab changes/minimize/dialogs.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


def pdf_drop_paths(paths) -> list[str]:
    """Validate individual local files, preserve Unicode and remove repeats."""
    accepted = []
    seen = set()
    for value in paths:
        path = Path(value).expanduser()
        if path.suffix.lower() != ".pdf" or not path.is_file():
            continue
        resolved = str(path.resolve())
        key = os.path.normcase(resolved)
        if key not in seen:
            accepted.append(resolved)
            seen.add(key)
    return accepted


class WindowsPdfDropZone:
    def __init__(self, title, on_files, on_error=None, *, parent_handle=None):
        self.title, self.on_files, self.on_error = title, on_files, on_error
        self.parent_handle = parent_handle
        self.visible = True
        self.enabled = True
        self.hwnd = None
        self.ready = False
        self.error = None
        self._closed = threading.Event()
        self._thread = None

    def start(self):
        if sys.platform != "win32":
            return False
        self._thread = threading.Thread(target=self._run_guarded, daemon=True, name="pdf-drop-lane")
        self._thread.start()
        return True

    def close(self):
        self._closed.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def _run_guarded(self):
        try:
            self._run()
        except Exception as error:
            self.error = str(error)
            if self.on_error:
                self.on_error(str(error))

    def _run(self):
        import ctypes as c
        from ctypes import wintypes as w

        u = c.WinDLL("user32", use_last_error=True)
        shell = c.WinDLL("shell32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        gdi = c.WinDLL("gdi32", use_last_error=True)
        proc_type = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        class WindowClass(c.Structure):
            _fields_ = [("style", w.UINT), ("proc", proc_type), ("cls_extra", c.c_int),
                        ("wnd_extra", c.c_int), ("instance", w.HINSTANCE), ("icon", w.HICON),
                        ("cursor", w.HANDLE), ("background", w.HBRUSH),
                        ("menu", w.LPCWSTR), ("name", w.LPCWSTR)]

        class Paint(c.Structure):
            _fields_ = [("dc", w.HDC), ("erase", w.BOOL), ("rect", w.RECT),
                        ("restore", w.BOOL), ("update", w.BOOL), ("reserved", c.c_byte * 32)]

        class ProcessEntry(c.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD),
                        ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                        ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
                        ("exe", w.WCHAR * 260)]

        def bind(lib, name, result, *args):
            f = getattr(lib, name)
            f.restype, f.argtypes = result, args
            return f

        bind(kernel, "GetModuleHandleW", w.HMODULE, w.LPCWSTR)
        bind(kernel, "CreateToolhelp32Snapshot", w.HANDLE, w.DWORD, w.DWORD)
        bind(kernel, "Process32FirstW", w.BOOL, w.HANDLE, c.POINTER(ProcessEntry))
        bind(kernel, "Process32NextW", w.BOOL, w.HANDLE, c.POINTER(ProcessEntry))
        bind(kernel, "CloseHandle", w.BOOL, w.HANDLE)
        enum_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        bind(u, "EnumWindows", w.BOOL, enum_type, w.LPARAM)
        bind(u, "GetWindowTextW", c.c_int, w.HWND, w.LPWSTR, c.c_int)
        bind(u, "GetClassNameW", c.c_int, w.HWND, w.LPWSTR, c.c_int)
        bind(u, "GetWindowThreadProcessId", w.DWORD, w.HWND, c.POINTER(w.DWORD))
        bind(u, "RegisterClassW", w.ATOM, c.POINTER(WindowClass))
        bind(u, "UnregisterClassW", w.BOOL, w.LPCWSTR, w.HINSTANCE)
        bind(u, "CreateWindowExW", w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
             c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
        bind(u, "DefWindowProcW", c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        bind(u, "DestroyWindow", w.BOOL, w.HWND)
        bind(u, "IsWindow", w.BOOL, w.HWND)
        bind(u, "GetClientRect", w.BOOL, w.HWND, c.POINTER(w.RECT))
        bind(u, "ClientToScreen", w.BOOL, w.HWND, c.POINTER(w.POINT))
        bind(u, "IsWindowVisible", w.BOOL, w.HWND)
        bind(u, "IsIconic", w.BOOL, w.HWND)
        bind(u, "IsWindowEnabled", w.BOOL, w.HWND)
        bind(u, "GetForegroundWindow", w.HWND)
        bind(u, "GetAncestor", w.HWND, w.HWND, w.UINT)
        bind(u, "SetWindowPos", w.BOOL, w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT)
        bind(u, "ShowWindow", w.BOOL, w.HWND, c.c_int)
        bind(u, "BeginPaint", w.HDC, w.HWND, c.POINTER(Paint))
        bind(u, "EndPaint", w.BOOL, w.HWND, c.POINTER(Paint))
        bind(u, "FillRect", c.c_int, w.HDC, c.POINTER(w.RECT), w.HBRUSH)
        bind(u, "DrawTextW", c.c_int, w.HDC, w.LPCWSTR, c.c_int, c.POINTER(w.RECT), w.UINT)
        bind(u, "PeekMessageW", w.BOOL, c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT)
        bind(u, "TranslateMessage", w.BOOL, c.POINTER(w.MSG))
        bind(u, "DispatchMessageW", c.c_ssize_t, c.POINTER(w.MSG))
        bind(shell, "DragAcceptFiles", None, w.HWND, w.BOOL)
        bind(shell, "DragQueryFileW", w.UINT, w.HANDLE, w.UINT, w.LPWSTR, w.UINT)
        bind(shell, "DragFinish", None, w.HANDLE)
        bind(gdi, "CreateSolidBrush", w.HBRUSH, w.DWORD)
        bind(gdi, "DeleteObject", w.BOOL, w.HGDIOBJ)
        bind(gdi, "SetBkMode", c.c_int, w.HDC, c.c_int)
        bind(gdi, "SetTextColor", w.DWORD, w.HDC, w.DWORD)

        def find_parent():
            if self.parent_handle:
                return self.parent_handle
            parents = {}
            snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
            if snapshot == c.c_void_p(-1).value:
                raise c.WinError(c.get_last_error())
            try:
                entry = ProcessEntry()
                entry.dwSize = c.sizeof(entry)
                ok = kernel.Process32FirstW(snapshot, c.byref(entry))
                while ok:
                    parents[entry.pid] = entry.parent
                    ok = kernel.Process32NextW(snapshot, c.byref(entry))
            finally:
                kernel.CloseHandle(snapshot)
            found, flutter_matches = [], []

            @enum_type
            def visit(hwnd, unused):
                title = c.create_unicode_buffer(512)
                u.GetWindowTextW(hwnd, title, 512)
                if title.value != self.title or not u.IsWindowVisible(hwnd):
                    return True
                window_class = c.create_unicode_buffer(256)
                u.GetClassNameW(hwnd, window_class, 256)
                if "FLUTTER" in window_class.value.upper():
                    flutter_matches.append(hwnd)
                pid = w.DWORD()
                u.GetWindowThreadProcessId(hwnd, c.byref(pid))
                current, seen = pid.value, set()
                while current and current not in seen:
                    if current == os.getpid():
                        found.append(hwnd)
                        break
                    seen.add(current)
                    current = parents.get(current, 0)
                return True

            u.EnumWindows(visit, 0)
            if len(found) == 1:
                return found[0]
            # The cached Flet launcher can exit after starting its real client,
            # so its intermediate PID is no longer in the process snapshot.
            # Accept only one visible Flutter window with this exact app title.
            return flutter_matches[0] if not found and len(flutter_matches) == 1 else None

        parent = None
        for attempt in range(300):
            if self._closed.is_set():
                return
            parent = find_parent()
            if parent:
                break
            self._closed.wait(0.2)
        if not parent:
            raise RuntimeError("No se encontró la ventana para recibir PDFs arrastrados")
        previous_dpi = None
        if hasattr(u, "GetWindowDpiAwarenessContext") and hasattr(u, "SetThreadDpiAwarenessContext"):
            bind(u, "GetWindowDpiAwarenessContext", w.HANDLE, w.HWND)
            bind(u, "SetThreadDpiAwarenessContext", w.HANDLE, w.HANDLE)
            context = u.GetWindowDpiAwarenessContext(parent)
            if context:
                previous_dpi = u.SetThreadDpiAwarenessContext(context)
        brush = gdi.CreateSolidBrush(0x00ECF0E8)

        @proc_type
        def procedure(hwnd, message, wp, lp):
            if message == 0x0233:  # WM_DROPFILES
                try:
                    paths = []
                    for index in range(shell.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                        size = shell.DragQueryFileW(wp, index, None, 0)
                        buffer = c.create_unicode_buffer(size + 1)
                        shell.DragQueryFileW(wp, index, buffer, size + 1)
                        paths.append(buffer.value)
                    if self.enabled and self.visible:
                        self.on_files(paths)
                finally:
                    shell.DragFinish(wp)
                return 0
            if message == 0x000F:  # WM_PAINT
                paint = Paint()
                dc = u.BeginPaint(hwnd, c.byref(paint))
                rect = w.RECT()
                u.GetClientRect(hwnd, c.byref(rect))
                u.FillRect(dc, c.byref(rect), brush)
                gdi.SetBkMode(dc, 1)
                gdi.SetTextColor(dc, 0x003A4D1F)
                text = "Arrastra aquí tus estados de cuenta PDF · Se añadirán al lote actual"
                u.DrawTextW(dc, text, -1, c.byref(rect), 0x25)  # centered / single line
                u.EndPaint(hwnd, c.byref(paint))
                return 0
            return u.DefWindowProcW(hwnd, message, wp, lp)

        instance = kernel.GetModuleHandleW(None)
        class_name = "EnginePdfDrop_" + str(id(self))
        window_class = WindowClass(0, procedure, 0, 0, instance, None, None, brush, None, class_name)
        if not u.RegisterClassW(c.byref(window_class)):
            gdi.DeleteObject(brush)
            raise c.WinError(c.get_last_error())
        try:
            # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_ACCEPTFILES;
            # WS_POPUP, NOT WS_CHILD. hWndParent is its owner, not a parent.
            self.hwnd = u.CreateWindowExW(0x08000090, class_name, "Carga PDF", 0x80000000,
                                         0, 0, 300, 44, parent, None, instance, None)
            if not self.hwnd:
                raise c.WinError(c.get_last_error())
            shell.DragAcceptFiles(self.hwnd, True)
            self.ready = True
            message = w.MSG()
            last_geometry = None
            while not self._closed.is_set() and u.IsWindow(parent) and u.IsWindow(self.hwnd):
                rect = w.RECT()
                u.GetClientRect(parent, c.byref(rect))
                scale = 1.0
                if hasattr(u, "GetDpiForWindow"):
                    bind(u, "GetDpiForWindow", w.UINT, w.HWND)
                    scale = u.GetDpiForWindow(parent) / 96 or 1.0
                point = w.POINT(0, 0)
                u.ClientToScreen(parent, c.byref(point))
                foreground = u.GetForegroundWindow()
                active = foreground == parent or foreground == self.hwnd
                geometry = (point.x + int(14 * scale), point.y + rect.bottom - int(64 * scale),
                            max(10, rect.right - int(28 * scale)), int(44 * scale),
                            self.visible and self.enabled and active and u.IsWindowVisible(parent)
                            and not u.IsIconic(parent) and u.IsWindowEnabled(parent))
                if geometry != last_geometry:
                    u.SetWindowPos(self.hwnd, 0, *geometry[:4], 0x10)
                    u.ShowWindow(self.hwnd, 4 if geometry[-1] else 0)  # SW_SHOWNOACTIVATE
                    last_geometry = geometry
                while u.PeekMessageW(c.byref(message), None, 0, 0, 1):
                    u.TranslateMessage(c.byref(message))
                    u.DispatchMessageW(c.byref(message))
                self._closed.wait(0.05)
        finally:
            if self.hwnd and u.IsWindow(self.hwnd):
                shell.DragAcceptFiles(self.hwnd, False)
                u.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.ready = False
            u.UnregisterClassW(class_name, instance)
            gdi.DeleteObject(brush)
            if previous_dpi:
                u.SetThreadDpiAwarenessContext(previous_dpi)
