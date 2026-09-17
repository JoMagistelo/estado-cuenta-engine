"""Interfaz Flet experimental con OCR multiproceso configurable.

Se ejecuta con: flet run app/main_flet_parallel.py
No altera main_flet.py ni el EXE distribuido; reutiliza su interfaz íntegra.
"""

from __future__ import annotations

import multiprocessing

import flet as ft

import main_flet as original_ui
from engine.parallel_ocr_pipeline import process_bank_statements_parallel_incremental


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
    """Recupera el mismo diccionario de configuración que usa el lote original.

    El adaptador es explícitamente experimental; fallar con claridad si la
    interfaz base cambia es preferible a ejecutar con una configuración falsa.
    """
    cells = dict(zip(handler.__code__.co_freevars, handler.__closure__ or ()))
    if "settings" not in cells or "state" not in cells:
        raise RuntimeError("La configuración Flet original cambió: revisar adaptador OCR")
    return cells["settings"].cell_contents, cells["state"].cell_contents


def main(page: ft.Page):
    performance = {"enabled": False, "workers": 2}
    original_process = original_ui.process_bank_statements_incremental

    def process_with_selected_mode(*args, **kwargs):
        if not performance["enabled"]:
            yield from original_process(*args, **kwargs)
        else:
            # Flet toma los ajustes al arrancar el lote y deshabilita Configuración.
            yield from process_bank_statements_parallel_incremental(
                *args, **{**kwargs, "ocr_workers": performance["workers"]}
            )

    original_ui.process_bank_statements_incremental = process_with_selected_mode
    original_ui.main(page)

    found = _find_configuration(page.controls)
    if found is None:
        raise RuntimeError("No se encontró el botón Configuración de la interfaz Flet")
    config_button, config_row = found
    original_settings, state = _original_settings(config_button.on_click)
    mode_text = ft.Text("OCR estándar", size=8, color=ft.Colors.ON_SURFACE_VARIANT)
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
            mode_text.value = (
                f"OCR x{performance['workers']} procesos"
                if performance["enabled"]
                else "OCR estándar"
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
                            "El motor elegido es el único OCR del procesamiento normal. "
                            "Los PDF digitales conservan su ruta original.",
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
                            "Cada proceso carga sus propios modelos en RAM. "
                            "Dos procesos son el punto de partida; más procesos no "
                            "garantizan mayor velocidad. El modo estándar se conserva.",
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
