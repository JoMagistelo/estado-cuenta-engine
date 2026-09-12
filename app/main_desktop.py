"""Punto de entrada del ejecutable de escritorio institucional.

El binario one-file evita el splash Tcl/Tk de PyInstaller. En cuanto el cliente
Flet está disponible, esta entrada construye una ventana de arranque compacta
y centrada, la muestra antes de importar la UI pesada y la mantiene visible
hasta que la interfaz principal queda preparada.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import flet as ft


GOB_GREEN = "#1F4D3A"
GOB_GREEN_DARK = "#163A2C"
GOB_GOLD = "#B08D57"
GOB_CREAM = "#F7F4EE"
DANGER = "#A63D40"

STARTUP_WIDTH = 680
STARTUP_HEIGHT = 420
PADDLEOCR_MODEL_NAMES = (
    "PP-OCRv5_mobile_det",
    "latin_PP-OCRv5_mobile_rec",
)


def _desktop_resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parent.parent


def _asset_path(name: str) -> Path:
    return _desktop_resource_root() / "assets" / name


def _bundled_paddle_model_root() -> Path | None:
    """Devuelve el root PaddleOCR extraído del one-file, si está completo."""
    if not getattr(sys, "frozen", False) or not getattr(sys, "_MEIPASS", None):
        return None

    root = _desktop_resource_root() / "models" / "paddleocr"
    if all((root / model_name).is_dir() for model_name in PADDLEOCR_MODEL_NAMES):
        return root.resolve()
    return None


def _configure_offline_runtime() -> Path | None:
    """Fuerza operación local y prioriza los modelos incluidos en el EXE."""
    # PaddleX no debe consultar fuentes de modelos durante el procesamiento.
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"

    # Algunas dependencias transitivas conocen repositorios Hugging Face. Estos
    # flags convierten el runtime de escritorio en un consumidor estrictamente
    # local aunque una dependencia intente resolver recursos por nombre.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    bundled_root = _bundled_paddle_model_root()
    if bundled_root is None:
        return None

    # Un EXE portable debe comportarse igual en cualquier computadora. Si el
    # sistema destino conserva variables antiguas, no deben desviar al reader
    # hacia modelos externos, ProgramData o una instalación previa.
    os.environ.pop("PADDLEOCR_TEXT_DETECTION_MODEL_DIR", None)
    os.environ.pop("PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR", None)
    os.environ["PADDLEOCR_MODEL_ROOT"] = str(bundled_root)
    return bundled_root


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


def _configure_startup_window(page: ft.Page) -> None:
    """Configura la primera superficie visible sin mostrar una ventana vacía."""
    page.title = "Extractor de Movimientos Financieros"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = GOB_CREAM

    icon_path = _asset_path("extractor_movimientos.ico")
    if sys.platform == "win32" and icon_path.is_file():
        page.window.icon = str(icon_path)

    page.window.width = STARTUP_WIDTH
    page.window.height = STARTUP_HEIGHT
    page.window.min_width = STARTUP_WIDTH
    page.window.min_height = STARTUP_HEIGHT
    # No fijamos max_width/max_height durante el splash: en Windows/Flet esos
    # límites pueden sobrevivir a la transición y dejar la ventana principal
    # marcada como maximizada aunque siga físicamente limitada al tamaño previo.
    # resizable=False y maximizable=False ya mantienen fijo este arranque.
    page.window.maximized = False
    page.window.prevent_close = False
    page.window.resizable = False
    page.window.maximizable = False
    page.window.always_on_top = True
    page.window.bgcolor = GOB_CREAM
    page.window.progress_bar = 0.08


def _startup_logo() -> ft.Control:
    logo_path = _asset_path("logo_gobierno_mexico.png")
    if logo_path.is_file():
        return ft.Image(
            src=str(logo_path),
            width=220,
            height=86,
            fit=ft.BoxFit.CONTAIN,
        )
    return ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=52, color=GOB_GREEN)


def _build_startup_surface(
    page: ft.Page,
) -> tuple[ft.ProgressBar, ft.Text, ft.Text]:
    """Construye un splash Flet nativo que ocupa toda la ventana de arranque."""
    progress = ft.ProgressBar(
        value=0.08,
        bar_height=5,
        color=GOB_GREEN,
        bgcolor="#DED8CF",
    )
    status = ft.Text(
        "Preparando entorno de trabajo…",
        size=12,
        weight=ft.FontWeight.W_600,
        color=GOB_GREEN_DARK,
    )
    detail = ft.Text(
        "Inicializando recursos de la aplicación.",
        size=9,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )

    page.add(
        ft.Column(
            [
                ft.Container(height=6, bgcolor=GOB_GOLD),
                ft.Container(
                    content=ft.Column(
                        [
                            _startup_logo(),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Extractor de Movimientos Financieros",
                                        size=22,
                                        weight=ft.FontWeight.BOLD,
                                        color=GOB_GREEN_DARK,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        "Secretaría Anticorrupción y Buen Gobierno",
                                        size=10,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        "Dirección General de Evaluación de Confianza",
                                        size=9,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                spacing=2,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Container(height=6),
                            progress,
                            ft.Row(
                                [
                                    ft.ProgressRing(
                                        width=24,
                                        height=24,
                                        stroke_width=2.6,
                                        color=GOB_GREEN,
                                    ),
                                    ft.Column([status, detail], spacing=2, expand=True),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Divider(height=12),
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.SHIELD_OUTLINED,
                                        size=15,
                                        color=GOB_GREEN,
                                    ),
                                    ft.Text(
                                        "Preparando componentes locales y la interfaz institucional.",
                                        size=8,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=6,
                            ),
                        ],
                        spacing=10,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    padding=ft.Padding.symmetric(horizontal=46, vertical=28),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
    )
    return progress, status, detail


def _update_startup_progress(
    page: ft.Page,
    progress: ft.ProgressBar,
    status: ft.Text,
    detail: ft.Text,
    *,
    value: float,
    message: str,
    detail_message: str,
) -> None:
    progress.value = value
    status.value = message
    detail.value = detail_message
    page.window.progress_bar = value
    page.update()


def _prepare_main_window(page: ft.Page) -> None:
    """Restaura capacidades normales antes de entregar la página a main_flet."""
    page.window.resizable = True
    page.window.maximizable = True
    page.window.always_on_top = False
    page.window.progress_bar = None
    page.window.max_width = None
    page.window.max_height = None
    # La ventana principal debe aparecer alineada con el escritorio, no conservar
    # la posición centrada que usa únicamente el splash de inicio.
    page.window.left = 0
    page.window.top = 0
    page.window.bgcolor = None
    page.bgcolor = None


async def _show_startup_error(page: ft.Page, ex: Exception) -> None:
    """Deja un error legible si el arranque falla en un ejecutable sin consola."""
    page.clean()
    _configure_startup_window(page)
    page.window.always_on_top = False
    page.window.progress_bar = None
    page.window.prevent_close = False
    page.window.on_event = None

    async def close_error(_):
        await page.window.close()

    page.add(
        ft.Column(
            [
                ft.Container(height=6, bgcolor=DANGER),
                ft.Container(
                    content=ft.Column(
                        [
                            _startup_logo(),
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=34, color=DANGER),
                            ft.Text(
                                "No fue posible iniciar la aplicación",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=DANGER,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "La interfaz no terminó de cargarse. "
                                "Cierra la aplicación y vuelve a intentarlo.",
                                size=10,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"{type(ex).__name__}: {ex}",
                                    size=9,
                                    selectable=True,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                padding=12,
                                bgcolor="#EFE9E1",
                                border_radius=8,
                            ),
                            ft.OutlinedButton(
                                content="Cerrar aplicación",
                                icon=ft.Icons.CLOSE,
                                on_click=close_error,
                            ),
                        ],
                        spacing=10,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=46, vertical=24),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
    )
    await page.window.center()
    page.window.visible = True
    page.update()


async def _desktop_main(page: ft.Page) -> None:
    """Muestra primero el splash y carga la UI pesada sin bloquear su pintado."""
    _configure_startup_window(page)
    progress, status, detail = _build_startup_surface(page)

    # FLET_APP_HIDDEN evita el flash blanco del visor. La ventana se posiciona,
    # recibe contenido y sólo entonces se hace visible.
    await page.window.center()
    page.window.visible = True
    page.window.focused = True
    page.update()
    await asyncio.sleep(0.10)

    try:
        _configure_offline_runtime()

        _update_startup_progress(
            page,
            progress,
            status,
            detail,
            value=0.26,
            message="Inicializando aplicación…",
            detail_message="Comprobando recursos locales de escritorio.",
        )

        _update_startup_progress(
            page,
            progress,
            status,
            detail,
            value=0.42,
            message="Cargando motor de extracción…",
            detail_message="Preparando lectores, validadores y exportadores.",
        )

        # main_flet importa el grafo funcional completo. Ejecutarlo fuera del
        # hilo del loop mantiene animada y responsiva la ventana de arranque.
        ui = await asyncio.to_thread(importlib.import_module, "main_flet")

        _update_startup_progress(
            page,
            progress,
            status,
            detail,
            value=0.82,
            message="Preparando interfaz principal…",
            detail_message="Construyendo el espacio de trabajo.",
        )
        await asyncio.sleep(0)

        ui.PROJECT_ROOT = _desktop_resource_root()
        ui.LOGO_PATH = ui.PROJECT_ROOT / "assets" / "logo_gobierno_mexico.png"

        _update_startup_progress(
            page,
            progress,
            status,
            detail,
            value=0.94,
            message="Finalizando inicio…",
            detail_message="La aplicación está casi lista.",
        )

        # No se envía un frame vacío: el siguiente update sustituye el splash
        # por la UI principal en la misma transición.
        page.controls.clear()
        _prepare_main_window(page)
        ui.main(page)
    except Exception as ex:
        await _show_startup_error(page, ex)


def _run_packaged_paddlex_self_test() -> bool:
    """Valida configs *y* metadata de dependencias OCR dentro del EXE."""
    if "--self-test-paddlex-pipeline" not in sys.argv:
        return False

    _configure_offline_runtime()

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


def _execute_paddleocr_runtime_self_test(config: dict) -> None:
    """Ejecuta una inferencia sintética sin información bancaria."""
    from PIL import Image, ImageDraw
    from readers.paddleocr_pdf_reader import PaddleOCRPDFReader

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


def _execute_searchable_pdf_runtime_self_test() -> None:
    """Comprueba dentro del binario la proyección PDF que consume el parser."""
    from pypdf import PdfWriter
    from readers.ocr_searchable_pdf import OCR_LAYER_TAG, OCRSearchablePDFWriter
    from readers.pdf_word_reader import PDFWordReader

    expected = {
        "text": "PRUEBA-Ñ",
        "x0": 24.0,
        "x1": 96.0,
        "top": 30.0,
        "bottom": 42.0,
        "page": 1,
    }
    with tempfile.TemporaryDirectory(prefix="estado_cuenta_pdf_selftest_") as raw_dir:
        directory = Path(raw_dir)
        source = directory / "source.pdf"
        projected_pdf = directory / "projected.pdf"

        writer = PdfWriter()
        writer.add_blank_page(width=300.0, height=400.0)
        with source.open("wb") as file_handle:
            writer.write(file_handle)

        OCRSearchablePDFWriter.write(source, [expected], projected_pdf, verify=True)
        words = PDFWordReader.read(projected_pdf, layer_tag=OCR_LAYER_TAG)

    if len(words) != 1 or words[0].get("text") != expected["text"]:
        raise RuntimeError(
            "El ejecutable no pudo recuperar la capa OCR etiquetada del PDF generado."
        )
    for field in ("x0", "x1", "top", "bottom"):
        if abs(float(words[0][field]) - float(expected[field])) > 0.02:
            raise RuntimeError(
                "El ejecutable alteró la geometría durante el round-trip del PDF OCR."
            )


def _run_packaged_paddleocr_runtime_self_test() -> bool:
    """Inicializa modelos locales y ejecuta predict() dentro del EXE real."""
    if "--self-test-paddleocr-runtime" not in sys.argv:
        return False

    _configure_offline_runtime()

    from readers.paddleocr_pdf_reader import PaddleOCRPDFReader

    config = PaddleOCRPDFReader._load_config()
    _execute_paddleocr_runtime_self_test(config)
    _execute_searchable_pdf_runtime_self_test()
    return True


def _run_packaged_portable_paddleocr_runtime_self_test() -> bool:
    """Demuestra que PaddleOCR funciona exclusivamente con modelos del one-file."""
    if "--self-test-portable-paddleocr-runtime" not in sys.argv:
        return False

    bundled_root = _configure_offline_runtime()
    if bundled_root is None:
        raise RuntimeError(
            "El ejecutable no contiene models/paddleocr con los dos modelos requeridos."
        )

    from readers.paddleocr_pdf_reader import PaddleOCRPDFReader

    config = PaddleOCRPDFReader._load_config()
    expected_root = bundled_root.resolve()
    for key in ("detection_model_dir", "recognition_model_dir"):
        resolved = Path(config[key]).resolve()
        try:
            resolved.relative_to(expected_root)
        except ValueError as exc:
            raise RuntimeError(
                f"{key} no fue resuelto desde el bundle portable: {resolved}"
            ) from exc

    _execute_paddleocr_runtime_self_test(config)
    _execute_searchable_pdf_runtime_self_test()
    return True


if __name__ == "__main__":
    if _run_packaged_paddlex_self_test():
        raise SystemExit(0)
    if _run_packaged_portable_paddleocr_runtime_self_test():
        raise SystemExit(0)
    if _run_packaged_paddleocr_runtime_self_test():
        raise SystemExit(0)
    ft.run(_desktop_main, view=ft.AppView.FLET_APP_HIDDEN)
