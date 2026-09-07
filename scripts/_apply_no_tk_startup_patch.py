from pathlib import Path
import re

spec = Path("EstadoCuentaEngine.spec")
text = spec.read_text(encoding="utf-8")
text = text.replace("from PIL import Image, ImageDraw, ImageFont\n", "from PIL import Image, ImageDraw\n")
text = text.replace('LOGO_PATH = ASSETS_DIR / "logo_gobierno_mexico.png"\n', "")
text = text.replace('RUNTIME_HOOK = PROJECT_ROOT / "scripts" / "pyinstaller_splash_runtime.py"\n', "")
text = text.replace('SPLASH_PATH = BUILD_DIR / "splash_institucional.png"\n', "")
text, count = re.subn(
    r"\ndef _font\(.*?\n\ndef _build_icon\(\) -> Path:\n",
    "\n\ndef _build_icon() -> Path:\n",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("No se encontró el bloque histórico de splash para eliminarlo")
text = text.replace("splash_image = _build_splash()\n", "")
text = text.replace('    runtime_hooks=[str(RUNTIME_HOOK)],\n', '    runtime_hooks=[],\n')
text, count = re.subn(
    r"\nsplash = Splash\(.*?\n\)\n\nexe = EXE\(\n",
    "\n# El splash de PyInstaller se deshabilita deliberadamente: su implementación\n# usa Tcl/Tk y puede mostrar una ventana raíz `tk` en Windows. El feedback de\n# arranque queda a cargo del modal Flet nativo de `app/main_desktop.py`.\nexe = EXE(\n",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("No se encontró la definición Splash de PyInstaller")
text = text.replace("    splash,\n    splash.binaries,\n", "")
if "Splash(" in text or "pyinstaller_splash_runtime" in text:
    raise RuntimeError("Quedaron referencias activas al splash Tcl/Tk")
spec.write_text(text, encoding="utf-8")
