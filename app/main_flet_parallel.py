"""Interfaz Flet de producción con procesamiento OCR paralelo configurable.

Se ejecuta con: flet run app/main_flet_parallel.py
Reutiliza la interfaz institucional y añade aceleración segura por documento.
"""

from __future__ import annotations

import multiprocessing
import os
from importlib.metadata import PackageNotFoundError, version

import flet as ft

import main_flet as original_ui
from engine.live_result_order import LiveResultOrder
from engine.parallel_ocr_pipeline import (
    MAX_OCR_WORKERS,
    process_bank_statements_parallel_incremental,
)
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
    """Resume la configuración sin exponer detalles técnicos al usuario."""
    label = original_ui.engine_label(engine)
    return (f"{label} · velocidad {workers}/8" if enabled else f"{label} · velocidad normal")


def speed_description(level: int) -> str:
    """Convierte la concurrencia interna en una escala comprensible."""
    if level >= 8:
        return "Máxima"
    if level >= 6:
        return "Alta"
    if level >= 4:
        return "Media"
    return "Básica"


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


APP_VERSION = _project_version()


def main(page: ft.Page):
    # La aplicación inicia con la configuración validada como más rápida. El
    # pipeline sólo crea los trabajadores necesarios para los PDF escaneados.
    performance = {"enabled": True, "workers": MAX_OCR_WORKERS}
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
    original_ui.APP_VERSION = APP_VERSION
    # La versión de producción recomienda PaddleOCR sin anular una elección
    # administrada mediante variable de entorno.
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
            label="Lectura de documentos escaneados",
            value=original_settings["ocr_primary_engine"],
            width=360,
            options=[
                ft.DropdownOption(
                    key="paddleocr",
                    text="PaddleOCR · recomendado por mayor precisión",
                ),
                ft.DropdownOption(
                    key="tesseract",
                    text="Tesseract · alternativa si PaddleOCR falla",
                ),
            ],
        )
        toggle = ft.Switch(
            label="Procesar varios PDF escaneados al mismo tiempo",
            value=performance["enabled"],
            active_color=original_ui.GOB_GREEN,
        )
        count_text = ft.Text(
            f"Velocidad: {performance['workers']}/8 · "
            f"{speed_description(performance['workers'])}",
            size=10,
            weight=ft.FontWeight.BOLD,
        )
        worker_slider = ft.Slider(
            min=2,
            max=MAX_OCR_WORKERS,
            divisions=MAX_OCR_WORKERS - 2,
            value=performance["workers"],
            disabled=not performance["enabled"],
            label="Velocidad {value}/8",
            width=340,
        )

        def switch_changed(_):
            worker_slider.disabled = not bool(toggle.value)
            worker_slider.update()

        def slider_changed(_):
            count_text.value = (
                f"Velocidad: {int(worker_slider.value)}/8 · "
                f"{speed_description(int(worker_slider.value))}"
            )
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
                            "La configuración recomendada ya está seleccionada: PaddleOCR "
                            "ofrece la lectura más precisa y la velocidad 8/8 procesa "
                            "varios documentos al mismo tiempo.",
                            size=9,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "Usa Tesseract sólo si PaddleOCR no puede procesar un documento.",
                            size=8,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Velocidad de procesamiento",
                            weight=ft.FontWeight.BOLD,
                            size=12,
                        ),
                        toggle,
                        count_text,
                        worker_slider,
                        ft.Text(
                            "Mantén 8/8 para obtener el mejor rendimiento. Reduce la "
                            "velocidad únicamente si el equipo se vuelve lento o muestra "
                            "un aviso de memoria insuficiente.",
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
