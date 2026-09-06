"""Punto de entrada del ejecutable de escritorio.

Se mantiene ``main_flet.py`` como implementación de la interfaz y este módulo
aplica únicamente adaptaciones propias del binario distribuible. En particular,
resuelve recursos incluidos por PyInstaller desde su directorio temporal y el
estado Terminado usa un icono de documento listo, distinto de las palomitas de
las validaciones de Abonos/Cargos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import flet as ft
import main_flet as _ui


def _desktop_resource_root() -> Path:
    """Devuelve la raíz real de recursos tanto en desarrollo como en PyInstaller."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parent.parent


# ``main_flet`` se importa como módulo de nivel superior dentro de PyInstaller.
# Allí su ``__file__`` ya no conserva ``app/main_flet.py`` y calcular
# ``parent.parent`` puede salir del bundle. Sobrescribir estas dos rutas evita
# que logos y demás recursos funcionen sólo al ejecutar desde el repositorio.
_ui.PROJECT_ROOT = _desktop_resource_root()
_ui.LOGO_PATH = _ui.PROJECT_ROOT / "assets" / "logo_gobierno_mexico.png"
main = _ui.main


_original_icon = ft.Icon


def _desktop_icon(*args, **kwargs):
    """Evita confundir el estado Terminado con una validación financiera."""
    icon = args[0] if args else kwargs.get("icon")
    size = kwargs.get("size")
    color = kwargs.get("color")

    if (
        icon == ft.Icons.CHECK_CIRCLE
        and size == 15
        and color == ft.Colors.GREEN
    ):
        replacement = ft.Icons.DESCRIPTION_OUTLINED
        if args:
            args = (replacement, *args[1:])
        else:
            kwargs["icon"] = replacement

    return _original_icon(*args, **kwargs)


ft.Icon = _desktop_icon


if __name__ == "__main__":
    ft.run(main)
