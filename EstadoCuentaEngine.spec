# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path.cwd()

TESSERACT_DIR = (
    PROJECT_ROOT
    / "vendor"
    / "tesseract"
)


a = Analysis(
    ["app/main_flet.py"],
    pathex=[
        str(PROJECT_ROOT / "src"),
    ],
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
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(
    a.pure
)

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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)