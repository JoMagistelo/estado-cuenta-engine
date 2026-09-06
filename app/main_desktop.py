"""Punto de entrada del ejecutable de escritorio.

Se mantiene ``main_flet.py`` como implementación de la interfaz y este módulo
aplica únicamente adaptaciones propias del binario distribuible. En particular,
el estado Terminado usa un icono de documento listo, distinto de las palomitas
de las validaciones de Abonos/Cargos.
"""

from __future__ import annotations

import os

import flet as ft

from main_flet import main


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
    try:
        ft.run(main)
    finally:
        # ThreadPoolExecutor usa hilos no-daemon. Si el usuario cerró la ventana
        # durante un OCR nativo, no dejamos un proceso invisible esperando ese
        # último frame/página. La ventana ya aplicó su flujo Detener y cerrar.
        os._exit(0)
