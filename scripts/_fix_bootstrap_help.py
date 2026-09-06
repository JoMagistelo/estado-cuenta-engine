from pathlib import Path

path = Path("scripts/preparar_modelos_paddleocr.py")
text = path.read_text(encoding="utf-8")
old = '"%LOCALAPPDATA%\\\\EstadoCuentaEngine\\\\PaddleOCR en Windows."'
new = '"LOCALAPPDATA\\\\EstadoCuentaEngine\\\\PaddleOCR en Windows."'
if old not in text:
    raise SystemExit("bootstrap help pattern not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
