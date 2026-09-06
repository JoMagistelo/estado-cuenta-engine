# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


# PyInstaller expone SPECPATH durante la ejecución del spec. Anclar las rutas
# al propio archivo evita que el resultado dependa del directorio de trabajo.
PROJECT_ROOT = Path(SPECPATH).resolve()
TESSERACT_DIR = PROJECT_ROOT / "vendor" / "tesseract"
MULTIPROCESSING_RUNTIME_HOOK = (
    PROJECT_ROOT / "packaging" / "pyi_rth_multiprocessing.py"
)


a = Analysis(
    [str(PROJECT_ROOT / "app" / "main_flet.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        (
            str(TESSERACT_DIR),
            "vendor/tesseract",
        ),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(MULTIPROCESSING_RUNTIME_HOOK)],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Extractor_de_Movimientos_Financieros",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
