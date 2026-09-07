"""Punto de entrada del ejecutable de escritorio institucional.

El arranque del binario se divide en dos fases: PyInstaller muestra su splash
durante la extracción del one-file y, cuando el cliente Flet ya existe, esta
entrada muestra un modal nativo mientras se importa y construye la interfaz.
Así el usuario nunca depende de una ventana Tcl/Tk vacía para saber que la
aplicación sigue cargando.
"""

from __future__ import annotations

import sys
from pathlib import Path

import flet as ft


def _desktop_resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parent.parent


def _asset_path(name: str) -> Path:
    return _desktop_resource_root() / "assets" / name


_original_icon = ft.Icon


def _desktop_icon(*args, **kwargs):
    """Evita confundir el estado Terminado con una validación financiera."""
    icon = args[0] if args else kwargs.get("icon")
    size = kwargs.get("size")
    color = kwargs.get("color")

    if icon == ft.Icons.CHECK_CIRCLE and size == 15 and color == ft.Colors.GREEN:
        replacement = ft.Icons.DESCRIPTION_OUTLINED
        if args:
            args = (replacement, *args[1:])
        else:
            kwargs["icon"] = replacement

    return _original_icon(*args, **kwargs)


ft.Icon = _desktop_icon


def _show_native_startup_dialog(page: ft.Page) -> None:
    """Muestra feedback de arranque después de que el cliente Flet ya abrió."""
    page.title = "Extractor de Movimientos Financieros"
    icon_path = _asset_path("extractor_movimientos.ico")
    if sys.platform == "win32" and icon_path.is_file():
        page.window.icon = str(icon_path)

    logo_path = _asset_path("logo_gobierno_mexico.png")
    logo = (
        ft.Image(src=str(logo_path), width=170, height=72, fit=ft.BoxFit.CONTAIN)
        if logo_path.is_file()
        else ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=44, color="#1F4D3A")
    )
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cargando aplicación", weight=ft.FontWeight.BOLD),
        content=ft.Column(
            [
                ft.Row(
                    [logo, ft.ProgressRing(width=28, height=28)],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    "Preparando componentes, OCR y ventana principal...",
                    size=10,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )
    page.show_dialog(dialog)
    page.update()


def _close_native_startup_dialog(page: ft.Page) -> None:
    try:
        page.pop_dialog()
        page.update()
    except Exception:
        pass


def _desktop_main(page: ft.Page) -> None:
    """Carga la UI de forma diferida para que el modal nativo sea visible."""
    _show_native_startup_dialog(page)
    try:
        # Importar aquí, y no al cargar este módulo, permite que Flet pinte el
        # modal antes de importar el resto de la aplicación.
        import main_flet as ui

        ui.PROJECT_ROOT = _desktop_resource_root()
        ui.LOGO_PATH = ui.PROJECT_ROOT / "assets" / "logo_gobierno_mexico.png"
        ui.main(page)
    finally:
        _close_native_startup_dialog(page)


def _run_packaged_paddlex_self_test() -> bool:
    """Valida configs *y* metadata de dependencias OCR dentro del EXE."""
    if "--self-test-paddlex-pipeline" not in sys.argv:
        return False

    from paddlex.inference.pipelines import load_pipeline_config
    from paddlex.utils.deps import require_extra

    # Ésta es la misma comprobación que protege el constructor de OCRPipeline.
    # Detecta el caso donde los módulos sí existen pero PyInstaller omitió la
    # metadata ``.dist-info`` que PaddleX consulta mediante importlib.metadata.
    require_extra("ocr", obj_name="OCR", alt="ocr-core")
    config = load_pipeline_config("OCR")
    if not config:
        raise RuntimeError("PaddleX no pudo cargar la configuración de la pipeline OCR.")
    return True


def _run_packaged_paddleocr_runtime_self_test() -> bool:
    """Inicializa modelos locales y ejecuta predict() dentro del EXE real."""
    if "--self-test-paddleocr-runtime" not in sys.argv:
        return False

    from PIL import Image, ImageDraw
    from readers.paddleocr_pdf_reader import PaddleOCRPDFReader

    config = PaddleOCRPDFReader._load_config()
    engine = PaddleOCRPDFReader._get_engine(**config)
    image = Image.new("RGB", (720, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 82), "PRUEBA OCR 1234567890", fill="black")
    PaddleOCRPDFReader._read_page(
        engine=engine,
        image=image,
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
        text_det_limit_side_len=1200,
    )
    return True


if __name__ == "__main__":
    if _run_packaged_paddlex_self_test():
        raise SystemExit(0)
    if _run_packaged_paddleocr_runtime_self_test():
        raise SystemExit(0)
    ft.run(_desktop_main)
