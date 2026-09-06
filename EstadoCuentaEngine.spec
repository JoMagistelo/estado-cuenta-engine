# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PyInstaller.utils.hooks import collect_all


# PyInstaller expone SPECPATH durante la ejecución del spec. Anclar las rutas
# al propio archivo evita que el resultado dependa del directorio de trabajo.
PROJECT_ROOT = Path(SPECPATH).resolve()
TESSERACT_DIR = PROJECT_ROOT / "vendor" / "tesseract"
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "logo_gobierno_mexico.png"
RUNTIME_HOOK = PROJECT_ROOT / "scripts" / "pyinstaller_splash_runtime.py"
BUILD_DIR = PROJECT_ROOT / "build"
SPLASH_PATH = BUILD_DIR / "splash_institucional.png"
ICON_PATH = BUILD_DIR / "extractor_movimientos.ico"
VERSION_INFO_PATH = BUILD_DIR / "windows_version_info.txt"

APP_VERSION = (2, 4, 1, 0)


def _font(size: int, *, bold: bool = False):
    candidates = (
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered_text(draw, text: str, y: int, font, fill: str, width: int) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    draw.text(((width - text_width) / 2, y), text, font=font, fill=fill)


def _build_splash() -> Path:
    """Genera el splash en build/ sin agregar binarios derivados al repo."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 760, 390
    canvas = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)

    if LOGO_PATH.is_file():
        with Image.open(LOGO_PATH) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((430, 125), Image.Resampling.LANCZOS)
            x = (width - logo.width) // 2
            canvas.paste(logo, (x, 45), logo)

    _centered_text(
        draw,
        "Extractor de Movimientos Financieros",
        205,
        _font(28, bold=True),
        "#163A2C",
        width,
    )
    _centered_text(
        draw,
        "Dirección General de Evaluación de Confianza",
        248,
        _font(16),
        "#4D5358",
        width,
    )

    # El área inferior queda reservada para el indicador dinámico enviado por
    # ``pyi_splash.update_text``. Antes se dibujaba aquí una barra fija que no
    # podía reflejar el avance real del arranque.
    draw.rounded_rectangle(
        (108, 292, 652, 330),
        radius=10,
        fill="#F3F6F4",
        outline="#DDE8E2",
        width=1,
    )
    draw.rectangle((0, height - 8, width, height), fill="#B08D57")

    canvas.save(SPLASH_PATH, format="PNG", optimize=True)
    return SPLASH_PATH


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


splash_image = _build_splash()
app_icon = _build_icon()
version_info = _build_version_info()

extra_datas = []
extra_binaries = []
extra_hiddenimports = []
for package in ("paddle", "paddleocr"):
    datas, binaries, hiddenimports = _optional_runtime(package)
    extra_datas.extend(datas)
    extra_binaries.extend(binaries)
    extra_hiddenimports.extend(hiddenimports)


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
        *extra_datas,
    ],
    hiddenimports=extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(RUNTIME_HOOK)],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

splash = Splash(
    str(splash_image),
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(122, 304),
    text_size=12,
    text_color="#163A2C",
    text_default="[##--------------------]   8%  Iniciando aplicación...",
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
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
