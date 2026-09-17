"""Interfaz Flet experimental con OCR multiproceso configurable.

Se ejecuta con: flet run app/main_flet_parallel.py
No altera main_flet.py ni el EXE distribuido; reutiliza su interfaz íntegra.
"""

from __future__ import annotations

import multiprocessing
import os
from importlib.metadata import PackageNotFoundError, version

import flet as ft

import main_flet as original_ui
from engine.live_result_order import LiveResultOrder
from engine.parallel_ocr_pipeline import process_bank_statements_parallel_incremental
from engine.pipeline import process_bank_statements_incremental as standard_incremental


def _find_configuration(controls):
    """Localiza el botón original sin recrear ni modificar la UI bancaria."""
    for control in controls:
        if isinstance(control, ft.IconButton) and control.tooltip == "Configuración":
            return control, None
        children = getattr(control, "controls", None)
        if children:
            for child in children:
                if isinstance(child, ft.IconButton) and child.tooltip == "Configuración":
                    return child, control
            found = _find_configuration(children)
            if found is not None:
                return found
        content = getattr(control, "content", None)
        if content is not None:
            found = _find_configuration([content])
            if found is not None:
                return found
    return None


def _original_settings(handler):
    """Obtiene la configuración real usada por la interfaz base.

    Si Flet cambia su contrato, aborta en lugar de simular una configuración.
    """
    cells = dict(zip(handler.__code__.co_freevars, handler.__closure__ or ()))
    if "settings" not in cells or "state" not in cells:
        raise RuntimeError("La configuración Flet original cambió: revisar adaptador OCR")
    return cells["settings"].cell_contents, cells["state"].cell_contents


def mode_description(*, enabled: bool, workers: int, engine: str) -> str:
    """Muestra motor y concurrencia reales; evita comparar motores diferentes."""
    label = original_ui.engine_label(engine)
    return (f"{label} · paralelo x{workers}" if enabled else f"{label} · estándar")


def _project_version() -> str:
    """Prioriza la versión del código actual frente a metadatos de venv obsoletos."""
    import tomllib

    project_file = original_ui.PROJECT_ROOT / "pyproject.toml"
    if project_file.is_file():
        with project_file.open("rb") as stream:
            return str(tomllib.load(stream)["project"]["version"])
    try:
        return version("extractor-de-movimientos-financieros")
    except PackageNotFoundError:
        return original_ui.APP_VERSION


def main(page: ft.Page):
    # El modo turbo es la configuración de prueba inicial, no una promesa de
    # rendimiento: cuatro modelos simultáneos requieren más RAM/CPU.
    performance = {"enabled": True, "workers": 4}
    result_order = LiveResultOrder()
    original_export = original_ui.export_batch_excel
    original_replace = original_ui.replace_result_reference

    def export_in_selection_order(results, *args, **kwargs):
        # Se ordena sólo el snapshot del Excel, nunca los eventos de la interfaz.
        return original_export(result_order.ordered(results), *args, **kwargs)

    def replace_preserving_order(results, previous, updated):
        # El reprocesado manual reemplaza el objeto; su posición sigue siendo la
        # del PDF original incluso si terminó antes que otros documentos.
        outcome = original_replace(results, previous, updated)
        result_order.transfer(previous, updated)
        return outcome

    original_ui.export_batch_excel = export_in_selection_order
    original_ui.replace_result_reference = replace_preserving_order

    def process_with_selected_mode(*args, **kwargs):
        paths = args[0] if args else kwargs["pdf_paths"]
        if not state["append_mode"]:
            result_order.reset()
        batch_start = result_order.reserve_batch(len(paths))
        if not performance["enabled"]:
            events = standard_incremental(*args, **kwargs)
        else:
            events = process_bank_statements_parallel_incremental(
                *args, **{**kwargs, "ocr_workers": performance["workers"]}
            )
        # Los resultados digitales y OCR se publican al terminar, sin esperar a
        # índices anteriores. El índice se utiliza únicamente al exportar.
        for event in events:
            if event.kind == "completed" and event.result is not None:
                result_order.register(event.result, batch_start + event.index)
            yield event

    original_ui.process_bank_statements_incremental = process_with_selected_mode
    original_ui.APP_VERSION = _project_version()
    # main_flet.py usa Tesseract si no existe OCR_PRIMARY_ENGINE. La entrada
    # experimental propone PaddleOCR por defecto sin anular una elección
    # explícita del usuario mediante variable de entorno.
    os.environ.setdefault("OCR_PRIMARY_ENGINE", "paddleocr")
    original_ui.main(page)

    found = _find_configuration(page.controls)
    if found is None:
        raise RuntimeError("No se encontró el botón Configuración de la interfaz Flet")
    config_button, config_row = found
    original_settings, state = _original_settings(config_button.on_click)
    mode_text = ft.Text(
        mode_description(
            enabled=performance["enabled"],
            workers=performance["workers"],
            engine=original_settings["ocr_primary_engine"],
        ),
        size=8,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    if isinstance(config_row, ft.Row):
        position = config_row.controls.index(config_button)
        config_row.controls.insert(position, mode_text)

    def show_combined_settings(_=None):
        if state["running"] or state["reprocess_cancel_events"]:
            return
        selector = ft.Dropdown(
            label="Motor OCR activo",
            value=original_settings["ocr_primary_engine"],
            width=300,
            options=[
                ft.DropdownOption(key="tesseract", text="Tesseract"),
                ft.DropdownOption(key="paddleocr", text="PaddleOCR"),
            ],
        )
        toggle = ft.Switch(
            label="Activar procesamiento OCR paralelo (experimental)",
            value=performance["enabled"],
            active_color=original_ui.GOB_GREEN,
        )
        count_text = ft.Text(
            f"Procesos OCR simultáneos: {performance['workers']}", size=10
        )
        worker_slider = ft.Slider(
            min=2,
            max=4,
            divisions=2,
            value=performance["workers"],
            disabled=not performance["enabled"],
            label="{value} procesos",
            width=290,
        )

        def switch_changed(_):
            worker_slider.disabled = not bool(toggle.value)
            worker_slider.update()

        def slider_changed(_):
            count_text.value = f"Procesos OCR simultáneos: {int(worker_slider.value)}"
            count_text.update()

        toggle.on_change = switch_changed
        worker_slider.on_change = slider_changed

        def save(_):
            original_settings["ocr_primary_engine"] = original_ui.normalize_ocr_engine(
                selector.value
            )
            performance["enabled"] = bool(toggle.value)
            performance["workers"] = int(worker_slider.value)
            mode_text.value = mode_description(
                enabled=performance["enabled"],
                workers=performance["workers"],
                engine=original_settings["ocr_primary_engine"],
            )
            page.pop_dialog()
            page.update()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Configuración", weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    [
                        selector,
                        ft.Text(
                            "El benchmark de 7:43 usó PaddleOCR; para comparar resultados "
                            "se debe usar el mismo motor en ambas pruebas.",
                            size=9,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "El motor secundario sólo se ejecuta cuando eliges "
                            "reprocesar un PDF OCR terminado.",
                            size=8,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Divider(),
                        ft.Text("Rendimiento OCR", weight=ft.FontWeight.BOLD, size=12),
                        toggle,
                        count_text,
                        worker_slider,
                        ft.Text(
                            "Turbo inicia activado con cuatro procesos. Cada uno carga "
                            "sus propios modelos en RAM; cuatro procesos pueden ser más "
                            "lentos que dos o agotar memoria. Reduce el deslizador o "
                            "desactiva el modo para volver al procesamiento estándar.",
                            size=9,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                ),
                actions=[
                    ft.TextButton(content="Cancelar", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton(
                        content="Guardar",
                        bgcolor=original_ui.GOB_GREEN,
                        color=original_ui.BUTTON_TEXT,
                        on_click=save,
                    ),
                ],
            )
        )

    config_button.on_click = show_combined_settings
    page.update()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    ft.run(main)
