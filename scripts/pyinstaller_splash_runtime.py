"""Runtime hook del ejecutable institucional.

Mantiene visible el splash de PyInstaller durante el arranque real de Flet,
actualiza un indicador de progreso textual mientras continúan las importaciones
y lo cierra únicamente después de que ``main(page)`` construyó la interfaz.
Fuera de un ejecutable PyInstaller el módulo no altera el comportamiento.
"""

from __future__ import annotations

import threading


_progress_lock = threading.Lock()
_progress_stop = threading.Event()
_progress_percent = 8
_progress_message = "Preparando entorno institucional..."


def _splash_module():
    try:
        import pyi_splash
    except ImportError:
        return None
    return pyi_splash


def _format_progress(percent: int, message: str) -> str:
    cells = 22
    filled = max(0, min(cells, round(cells * percent / 100)))
    bar = "#" * filled + "-" * (cells - filled)
    return f"[{bar}] {percent:>3}%  {message}"


def _update_splash(message: str | None = None, percent: int | None = None) -> None:
    global _progress_message, _progress_percent

    with _progress_lock:
        if message is not None:
            _progress_message = message
        if percent is not None:
            _progress_percent = max(_progress_percent, min(int(percent), 100))
        text = _format_progress(_progress_percent, _progress_message)

    splash = _splash_module()
    if splash is None:
        return
    try:
        if splash.is_alive():
            splash.update_text(text)
    except (ConnectionError, RuntimeError):
        pass


def _animate_progress() -> None:
    """Mantiene movimiento visual sin fingir una duración fija de arranque."""
    global _progress_percent

    while not _progress_stop.wait(0.35):
        with _progress_lock:
            if _progress_percent >= 92:
                continue
            step = 2 if _progress_percent < 56 else 1
            _progress_percent = min(92, _progress_percent + step)
            text = _format_progress(_progress_percent, _progress_message)

        splash = _splash_module()
        if splash is None:
            return
        try:
            if splash.is_alive():
                splash.update_text(text)
            else:
                return
        except (ConnectionError, RuntimeError):
            return


def _close_splash() -> None:
    _progress_stop.set()
    splash = _splash_module()
    if splash is None:
        return
    try:
        if splash.is_alive():
            splash.close()
    except (ConnectionError, RuntimeError):
        pass


_update_splash("Preparando entorno institucional...", 8)
threading.Thread(
    target=_animate_progress,
    name="institutional-splash-progress",
    daemon=True,
).start()

try:
    import flet
except ImportError:
    flet = None

if flet is not None:
    _update_splash("Inicializando componentes de escritorio...", 46)
    _original_run = flet.run

    def _run_with_splash(main, *args, **kwargs):
        def _wrapped_main(page):
            _update_splash("Construyendo ventana principal...", 74)
            try:
                return main(page)
            finally:
                _update_splash("Interfaz lista", 100)
                _close_splash()

        try:
            return _original_run(_wrapped_main, *args, **kwargs)
        finally:
            _close_splash()

    flet.run = _run_with_splash
