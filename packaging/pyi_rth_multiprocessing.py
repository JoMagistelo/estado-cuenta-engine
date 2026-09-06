"""Runtime hook PyInstaller para procesos PaddleOCR en Windows.

PyInstaller sustituye ``multiprocessing.freeze_support`` por una implementación
compatible con ejecutables congelados. Invocarla antes del entry point evita
que un worker ``spawn`` vuelva a iniciar la interfaz Flet como aplicación.
"""

import multiprocessing


multiprocessing.freeze_support()
