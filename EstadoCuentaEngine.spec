# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import importlib.metadata as importlib_metadata
from PIL import Image, ImageDraw
from PyInstaller.utils.hooks import collect_all, copy_metadata


# PyInstaller expone SPECPATH durante la ejecución del spec. Anclar las rutas
# al propio archivo evita que el resultado dependa del directorio de trabajo.
PROJECT_ROOT = Path(SPECPATH).resolve()
TESSERACT_DIR = PROJECT_ROOT / "vendor" / "tesseract"
ASSETS_DIR = PROJECT_ROOT / "assets"
BUILD_DIR = PROJECT_ROOT / "build"
ICON_PATH = BUILD_DIR / "extractor_movimientos.ico"
VERSION_INFO_PATH = BUILD_DIR / "windows_version_info.txt"

APP_VERSION = (2, 4, 2, 0)



def _build_icon() -> Path:
    """Genera un icono institucional simple y legible para Windows."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    size = 512
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)

    draw.rounded_rectangle(
        (32, 32, 480, 480),
        radius=92,
        fill="#1F4D3A",
        outline="#B08D57",
        width=24,
    )
    draw.rounded_rectangle((142, 104, 370, 408), radius=24, fill="#FFFFFF")
    draw.rectangle((142, 104, 178, 408), fill="#B08D57")
    for y in (174, 232, 290, 348):
        draw.rounded_rectangle((212, y, 334, y + 18), radius=9, fill="#1F4D3A")

    icon.save(
        ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return ICON_PATH


def _build_version_info() -> Path:
    """Genera metadatos PE institucionales sin referencias al repositorio."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    major, minor, patch, build = APP_VERSION
    version = f"{major}.{minor}.{patch}.{build}"
    VERSION_INFO_PATH.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080A04B0',
        [
          StringStruct('CompanyName', 'Secretaría Anticorrupción y Buen Gobierno'),
          StringStruct('FileDescription', 'Extractor de Movimientos Financieros'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'Extractor_de_Movimientos_Financieros'),
          StringStruct('LegalCopyright', 'Gobierno de México'),
          StringStruct('OriginalFilename', 'Extractor_de_Movimientos_Financieros.exe'),
          StringStruct('ProductName', 'Extractor de Movimientos Financieros'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [2058, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return VERSION_INFO_PATH


def _optional_runtime(package_name: str):
    """Incluye paquetes OCR pesados sólo cuando están instalados en el build."""
    try:
        return collect_all(package_name)
    except Exception:
        return [], [], []


def _paddlex_ocr_metadata():
    """Copia metadatos que PaddleX consulta con ``importlib.metadata``.

    PaddleX 3.x decide si la pipeline OCR puede crearse leyendo los extras de su
    propia distribución y consultando la metadata de cada dependencia.
    PyInstaller puede congelar los módulos y, aun así, omitir sus ``.dist-info``;
    eso provoca un falso "OCR requires additional dependencies" únicamente en
    el EXE. Conservamos la metadata base instalada y, de forma estricta, la del
    extra ``ocr-core`` que PaddleOCR 3.7 declara como requisito.
    """
    try:
        import paddlex
    except ImportError:
        return []

    base_dependencies = set(paddlex.utils.deps.BASE_DEP_SPECS.keys())
    ocr_core_dependencies = set(
        paddlex.utils.deps.EXTRAS.get("ocr-core", {}).keys()
    )
    missing_ocr_core = []
    for dependency in sorted(ocr_core_dependencies):
        try:
            importlib_metadata.version(dependency)
        except importlib_metadata.PackageNotFoundError:
            missing_ocr_core.append(dependency)

    if missing_ocr_core:
        raise RuntimeError(
            "El entorno de build no tiene completo paddlex[ocr-core]. Faltan: "
            + ", ".join(missing_ocr_core)
        )

    metadata_names = {"paddlex", "paddleocr"}
    metadata_names.update(base_dependencies)
    metadata_names.update(ocr_core_dependencies)

    metadata_datas = []
    for dependency in sorted(metadata_names):
        try:
            importlib_metadata.version(dependency)
        except importlib_metadata.PackageNotFoundError:
            continue
        metadata_datas.extend(copy_metadata(dependency))
    return metadata_datas


app_icon = _build_icon()
version_info = _build_version_info()

extra_datas = []
extra_binaries = []
extra_hiddenimports = []
# PaddleOCR 3.x construye la canalización OCR a través de PaddleX y carga
# configuraciones YAML/JSON de forma dinámica. Si sólo se recogen ``paddle`` y
# ``paddleocr``, el EXE puede importar ambos paquetes pero fallar al crear
# ``PaddleOCR`` con "The pipeline (OCR) does not exist". Incluir PaddleX
# explícitamente conserva esos recursos dinámicos dentro del one-file.
for package in ("paddle", "paddleocr", "paddlex"):
    datas, binaries, hiddenimports = _optional_runtime(package)
    extra_datas.extend(datas)
    extra_binaries.extend(binaries)
    extra_hiddenimports.extend(hiddenimports)


# PaddleX comprueba los extras OCR mediante metadata de distribución en
# runtime. ``collect_all`` no garantiza que esos ``.dist-info`` queden dentro
# del one-file, por lo que se copian explícitamente.
extra_datas.extend(_paddlex_ocr_metadata())


a = Analysis(
    [str(PROJECT_ROOT / "app" / "main_desktop.py")],
    pathex=[str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "app")],
    binaries=extra_binaries,
    datas=[
        (
            str(TESSERACT_DIR),
            "vendor/tesseract",
        ),
        (
            str(ASSETS_DIR),
            "assets",
        ),
        (
            str(app_icon),
            "assets",
        ),
        *extra_datas,
    ],
    hiddenimports=extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# El splash de PyInstaller se deshabilita deliberadamente: su implementación
# usa Tcl/Tk y puede mostrar una ventana raíz `tk` en Windows. El feedback de
# arranque queda a cargo del modal Flet nativo de `app/main_desktop.py`.
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
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon),
    version=str(version_info),
)