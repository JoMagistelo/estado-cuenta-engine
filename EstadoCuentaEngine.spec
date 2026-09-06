# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# PyInstaller expone SPECPATH durante la ejecución del spec. Anclar las rutas
# al propio archivo evita que el resultado dependa del directorio de trabajo.
PROJECT_ROOT = Path(SPECPATH).resolve()
TESSERACT_DIR = PROJECT_ROOT / "vendor" / "tesseract"
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "logo_gobierno_mexico.png"
RUNTIME_HOOK = PROJECT_ROOT / "scripts" / "pyinstaller_splash_runtime.py"
SPLASH_PATH = PROJECT_ROOT / "build" / "splash_institucional.png"


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
    SPLASH_PATH.parent.mkdir(parents=True, exist_ok=True)
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

    # Indicador visual indeterminado; el texto inferior sí se actualiza desde
    # el bootloader/runtime hook mientras se prepara la interfaz Flet.
    bar_x, bar_y, bar_w, bar_h = 115, 300, 530, 9
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=5,
        fill="#E8F0EC",
    )
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + 185, bar_y + bar_h),
        radius=5,
        fill="#1F4D3A",
    )
    draw.rectangle((0, height - 8, width, height), fill="#B08D57")

    canvas.save(SPLASH_PATH, format="PNG", optimize=True)
    return SPLASH_PATH


splash_image = _build_splash()


a = Analysis(
    [str(PROJECT_ROOT / "app" / "main_flet.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        (
            str(TESSERACT_DIR),
            "vendor/tesseract",
        ),
        (
            str(ASSETS_DIR),
            "assets",
        ),
    ],
    hiddenimports=[],
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
    text_pos=(70, 345),
    text_size=12,
    text_color="#163A2C",
    text_default="Iniciando aplicación…",
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
