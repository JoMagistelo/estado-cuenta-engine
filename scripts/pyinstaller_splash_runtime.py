"""Runtime hook del ejecutable institucional.

Mantiene visible el splash de PyInstaller durante el arranque real de Flet y lo
cierra únicamente después de que ``main(page)`` construyó la interfaz. Fuera de
un ejecutable PyInstaller el módulo no altera el comportamiento de la app.
"""

from __future__ import annotations


def _splash_module():
    try:
        import pyi_splash
    except ImportError:
        return None
    return pyi_splash


def _update_splash(message: str) -> None:
    splash = _splash_module()
    if splash is None:
        return
    try:
        if splash.is_alive():
            splash.update_text(message)
    except (ConnectionError, RuntimeError):
        pass


def _close_splash() -> None:
    splash = _splash_module()
    if splash is None:
        return
    try:
        if splash.is_alive():
            splash.close()
    except (ConnectionError, RuntimeError):
        pass


_update_splash("Preparando interfaz institucional…")

try:
    import flet
except ImportError:
    flet = None

if flet is not None:
    _original_run = flet.run

    def _run_with_splash(main, *args, **kwargs):
        def _wrapped_main(page):
            _update_splash("Cargando ventana principal…")
            try:
                return main(page)
            finally:
                _update_splash("Interfaz lista")
                _close_splash()

        try:
            return _original_run(_wrapped_main, *args, **kwargs)
        finally:
            _close_splash()

    flet.run = _run_with_splash
