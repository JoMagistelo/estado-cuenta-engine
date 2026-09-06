from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from engine.ocr_fallback_policy import normalize_ocr_engine, secondary_ocr_engine
from engine.pipeline import process_bank_statements_incremental
from exporters.excel import export_batch_excel

APP_VERSION = "2.2"
PROCESSING_UI_POLL_INTERVAL = 0.25
TIMER_REFRESH_SECONDS = 1.0

GOB_GREEN = "#1F4D3A"
GOB_GREEN_DARK = "#163A2C"
GOB_GREEN_LIGHT = "#E8F0EC"
GOB_GOLD = "#B08D57"
GOB_GOLD_LIGHT = "#F4EEE5"
GOB_CREAM = "#F7F4EE"
ROW_ALT = "#FAFAF8"
BUTTON_TEXT = "#FFFFFF"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "assets" / "logo_gobierno_mexico.png"

PRIMARY_VALIDATIONS = (
    "Total depósitos / abonos",
    "Total retiros / cargos",
)

MOVEMENT_COLUMNS: list[tuple[str, str, int]] = [
    ("fecha_corte", "Fecha Corte", 92),
    ("numero_cuenta", "Número de Cuenta", 118),
    ("numero_movimiento", "No. Mov.", 70),
    ("fecha_operacion", "Fecha Operación", 98),
    ("fecha_liquidacion", "Fecha Liquidación", 100),
    ("concepto", "Concepto", 220),
    ("concepto_original", "Concepto Original", 220),
    ("cargo", "Cargo", 98),
    ("abono", "Abono", 98),
    ("saldo_operacion", "Saldo Operación", 110),
    ("saldo_liquidacion", "Saldo Liquidación", 110),
    ("tipo_operacion", "Tipo", 110),
    ("beneficiario", "Beneficiario", 175),
    ("cuenta_beneficiario", "Cuenta Benef.", 145),
    ("clabe_beneficiario", "CLABE Benef.", 155),
    ("rfc", "RFC", 125),
    ("referencia", "Referencia", 140),
    ("clave_rastreo", "Clave Rastreo", 165),
    ("autorizacion", "Autorización", 125),
    ("hora_operacion", "Hora", 78),
    ("sucursal", "Sucursal", 88),
    ("caja", "Caja", 72),
]

MONEY_MOVEMENT_FIELDS = {
    "cargo",
    "abono",
    "saldo_operacion",
    "saldo_liquidacion",
}


def safe_value(value: Any) -> str:
    return "N/A" if value is None or value == "" else str(value)


def format_money(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_optional_float(
    value: Any,
    *,
    suffix: str = "",
    prefix: str = "",
    na_value: str = "N/A",
) -> str:
    if value is None:
        return na_value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{prefix}{numeric:,.2f}{suffix}"


def engine_label(engine: str | None) -> str:
    normalized = normalize_ocr_engine(engine, default="")
    return {
        "tesseract": "Tesseract",
        "paddleocr": "PaddleOCR",
    }.get(normalized, "OCR")


def format_elapsed(seconds: float) -> str:
    seconds = max(int(seconds or 0), 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def main(page: ft.Page):
    page.title = "Extractor de Movimientos Financieros"
    page.window.width = 1180
    page.window.height = 660
    page.window.min_width = 920
    page.window.min_height = 560
    page.window.maximized = True
    page.padding = 14
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    results: list[Any] = []
    processing_items: list[dict[str, Any]] = []
    event_queue: Queue = Queue()

    settings = {
        "ocr_primary_engine": normalize_ocr_engine(
            os.getenv("OCR_PRIMARY_ENGINE", "tesseract")
        )
    }
    state: dict[str, Any] = {
        "running": False,
        "batch_id": 0,
        "started_at": None,
        "elapsed_seconds": 0.0,
        "selected_index": None,
        "selector_signature": None,
        "last_timer_refresh": 0.0,
    }

    status_text = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    timer_text = ft.Text("00:00", size=11, weight=ft.FontWeight.BOLD)
    loading_ring = ft.ProgressRing(width=18, height=18, visible=False)
    selector_view = ft.Container(visible=False)
    audit_view = ft.Column(spacing=9)

    export_button = ft.FilledButton(
        content="Generar Excel",
        icon=ft.Icons.DOWNLOAD,
        disabled=True,
        bgcolor=GOB_GOLD,
        color=BUTTON_TEXT,
    )

    def validation(result, name: str):
        for item in getattr(result, "validaciones", []) or []:
            if item.nombre == name:
                return item
        return None

    def validation_symbol(item) -> str:
        return "—" if item is None else ("✅" if item.correcto else "❌")

    def metric(title: str, value: str, *, compact: bool = False) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        title,
                        size=8 if compact else 9,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        value,
                        size=10 if compact else 13,
                        weight=ft.FontWeight.BOLD,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=1 if compact else 2,
                tight=True,
            ),
            padding=7 if compact else 9,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=7,
            expand=True,
        )

    def section(title: str) -> ft.Text:
        return ft.Text(title, size=14, weight=ft.FontWeight.BOLD)

    async def _reset_scroll_async():
        try:
            await page.scroll_to(offset=0, duration=0)
        except Exception:
            pass

    def reset_scroll():
        page.run_task(_reset_scroll_async)

    def process_label(item: dict[str, Any]) -> str:
        method = item.get("processing_method")
        result = item.get("result")
        if method == "Digital":
            return "Digital"
        if method == "OCR":
            if result is None:
                return engine_label(settings["ocr_primary_engine"])
            label = engine_label(getattr(result, "ocr_engine", None))
            if getattr(result, "fallback_used", False):
                return f"{label} · fallback"
            if getattr(result, "fallback_attempted", False):
                return f"{label} · revisado"
            return label
        return "Detectando"

    def bank_key_for_item(item: dict[str, Any]) -> str:
        result = item.get("result")
        if result is None:
            return "PENDIENTE"
        return str(getattr(result, "bank_key", "desconocido") or "desconocido").upper()

    def completed_signature() -> tuple:
        signature = []
        for index, item in enumerate(processing_items):
            result = item.get("result")
            if item.get("status") == "completed" and result is not None:
                signature.append(
                    (
                        index,
                        item.get("file_name"),
                        item.get("processing_method"),
                        bank_key_for_item(item),
                        getattr(result, "ocr_engine", None),
                        getattr(result, "fallback_used", False),
                    )
                )
        return tuple(signature)

    def select_item(index: int):
        if not (0 <= index < len(processing_items)):
            return
        item = processing_items[index]
        result = item.get("result")
        if item.get("status") != "completed" or result is None:
            return
        state["selected_index"] = index
        render_result(result)
        update_selector(force=True)
        page.update()

    def selector_row(index: int, item: dict[str, Any]) -> ft.Container:
        result = item.get("result")
        selected = state.get("selected_index") == index
        abonos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))
        cargos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))
        method = item.get("processing_method")
        method_text = "Digital" if method == "Digital" else process_label(item)

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        ft.Text(
                            item.get("file_name", ""),
                            size=9,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        ft.Text(method_text, size=8, weight=ft.FontWeight.W_500),
                        width=115,
                    ),
                    ft.Container(
                        ft.Text(abonos, size=10),
                        width=34,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        ft.Text(cargos, size=10),
                        width=34,
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=7, vertical=5),
            bgcolor=GOB_GREEN_LIGHT if selected else None,
            border=ft.Border.all(
                1,
                GOB_GREEN if selected else ft.Colors.OUTLINE_VARIANT,
            ),
            border_radius=6,
            on_click=lambda e, i=index: select_item(i),
        )

    def bank_group(bank: str, indexed_items: list[tuple[int, dict[str, Any]]]) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        ft.Row(
                            [
                                ft.Text(
                                    bank,
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                    color=GOB_GREEN_DARK,
                                ),
                                ft.Container(expand=True),
                                ft.Text(f"{len(indexed_items)} archivo(s)", size=8),
                            ]
                        ),
                        bgcolor=GOB_CREAM,
                        padding=ft.Padding.symmetric(horizontal=7, vertical=4),
                        border_radius=5,
                    ),
                    *[selector_row(index, item) for index, item in indexed_items],
                ],
                spacing=3,
            ),
            padding=4,
        )

    def selector_panel(
        title: str,
        indexed_items: list[tuple[int, dict[str, Any]]],
    ) -> ft.Container:
        grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for index, item in indexed_items:
            grouped.setdefault(bank_key_for_item(item), []).append((index, item))

        controls: list[ft.Control] = [
            ft.Container(
                ft.Row(
                    [
                        ft.Text(title, size=11, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text("Motor", size=8),
                        ft.Container(width=46),
                        ft.Text("A", size=8),
                        ft.Text("C", size=8),
                    ],
                    spacing=5,
                ),
                padding=ft.Padding.symmetric(horizontal=7, vertical=5),
                bgcolor=GOB_GOLD_LIGHT,
                border_radius=6,
            )
        ]
        if not indexed_items:
            controls.append(
                ft.Container(
                    ft.Text("Sin resultados terminados", size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=8,
                )
            )
        else:
            for bank in sorted(grouped):
                controls.append(bank_group(bank, grouped[bank]))

        return ft.Container(
            content=ft.Column(
                controls,
                spacing=3,
                scroll=ft.ScrollMode.AUTO,
            ),
            height=235,
            padding=6,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            expand=True,
        )

    def update_selector(*, force: bool = False):
        signature = completed_signature()
        if not force and signature == state.get("selector_signature"):
            return
        state["selector_signature"] = signature

        completed = [
            (i, item)
            for i, item in enumerate(processing_items)
            if item.get("status") == "completed" and item.get("result") is not None
        ]
        digital = [(i, item) for i, item in completed if item.get("processing_method") == "Digital"]
        scanned = [(i, item) for i, item in completed if item.get("processing_method") == "OCR"]

        selector_view.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Resultados disponibles", size=13, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(
                            "Puedes revisar un archivo terminado mientras los demás siguen procesándose.",
                            size=8,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ]
                ),
                ft.Row(
                    [
                        selector_panel("📄 PDFs digitales", digital),
                        selector_panel("🖨️ PDFs escaneados (OCR)", scanned),
                    ],
                    spacing=9,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=5,
        )
        selector_view.visible = True

    def update_status():
        total = len(processing_items)
        completed = sum(1 for item in processing_items if item.get("status") == "completed")
        errors = sum(1 for item in processing_items if item.get("status") == "error")
        pending = total - completed - errors
        scanned_pending = sum(
            1
            for item in processing_items
            if item.get("status") == "processing" and item.get("processing_method") == "OCR"
        )

        if pending > 0:
            status_text.value = f"Procesando {completed} de {total} archivos"
            if scanned_pending:
                status_text.value += f" · {scanned_pending} PDF(s) escaneado(s) en OCR"
            if errors:
                status_text.value += f" · {errors} con error"
            status_text.color = ft.Colors.ON_SURFACE
        elif total and errors == 0:
            status_text.value = f"✅ {completed} archivos procesados correctamente"
            status_text.color = ft.Colors.GREEN
        elif completed:
            status_text.value = f"✅ {completed} correctos · ⚠️ {errors} con error"
            status_text.color = ft.Colors.ERROR
        elif errors:
            status_text.value = f"❌ No fue posible procesar {errors} archivos"
            status_text.color = ft.Colors.RED

    def movement_value(
        movement,
        field_name: str,
        index: int,
        fecha_corte_documento: str | None,
        numero_cuenta_documento: str | None,
    ) -> Any:
        if field_name == "fecha_corte":
            return fecha_corte_documento
        if field_name == "numero_cuenta":
            return numero_cuenta_documento
        if field_name == "numero_movimiento":
            return index
        return getattr(movement, field_name, None)

    def movement_cell(field_name: str, value: Any, width: int, *, header: bool = False):
        if header:
            return ft.Container(
                ft.Text(
                    str(value),
                    size=8,
                    weight=ft.FontWeight.BOLD,
                    color=BUTTON_TEXT,
                    text_align=ft.TextAlign.CENTER,
                ),
                width=width,
                height=32,
                padding=ft.Padding.symmetric(horizontal=5, vertical=7),
                bgcolor=GOB_GREEN_DARK,
                alignment=ft.Alignment.CENTER,
                border=ft.Border.only(right=ft.BorderSide(1, GOB_GREEN)),
            )

        text_value = format_money(value) if field_name in MONEY_MOVEMENT_FIELDS else safe_value(value)
        return ft.Container(
            ft.Text(
                text_value,
                size=8,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                selectable=True,
            ),
            width=width,
            height=40,
            padding=ft.Padding.symmetric(horizontal=5, vertical=5),
            alignment=ft.Alignment.CENTER_LEFT,
            border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

    def movements_table(
        movements,
        *,
        fecha_corte_documento: str | None = None,
        numero_cuenta_documento: str | None = None,
    ) -> ft.Container:
        total_width = sum(width for _, _, width in MOVEMENT_COLUMNS)
        header = ft.Row(
            [movement_cell(name, label, width, header=True) for name, label, width in MOVEMENT_COLUMNS],
            spacing=0,
        )

        body_rows: list[ft.Control] = []
        for index, movement in enumerate(movements, 1):
            cells = []
            for field_name, _label, width in MOVEMENT_COLUMNS:
                value = movement_value(
                    movement,
                    field_name,
                    index,
                    fecha_corte_documento,
                    numero_cuenta_documento,
                )
                cells.append(movement_cell(field_name, value, width))
            body_rows.append(
                ft.Container(
                    ft.Row(cells, spacing=0),
                    bgcolor=ROW_ALT if index % 2 == 0 else None,
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                )
            )

        body = ft.Column(
            body_rows,
            spacing=0,
            height=300,
            scroll=ft.ScrollMode.ALWAYS,
        )
        table_surface = ft.Container(
            ft.Column([header, body], spacing=0),
            width=total_width,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        return ft.Container(
            ft.Row([table_surface], scroll=ft.ScrollMode.ALWAYS, spacing=0),
            padding=ft.Padding.only(bottom=3),
        )

    def validation_card(result, name: str, short_name: str) -> ft.Container:
        item = validation(result, name)
        if item is None:
            icon, color, detail = "—", ft.Colors.ON_SURFACE_VARIANT, "No se pudo calcular"
        elif item.correcto:
            icon, color, detail = "✅", ft.Colors.GREEN, "Conciliación correcta"
        else:
            icon, color = "❌", ft.Colors.RED
            detail = (
                f"Esperado {format_money(item.esperado)} · "
                f"Obtenido {format_money(item.obtenido)} · "
                f"Diferencia {format_money(item.diferencia)}"
            )
        return ft.Container(
            ft.Row(
                [
                    ft.Text(icon, size=14),
                    ft.Column(
                        [
                            ft.Text(short_name, size=9, weight=ft.FontWeight.BOLD, color=color),
                            ft.Text(detail, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=1,
                        tight=True,
                    ),
                ],
                spacing=6,
            ),
            padding=7,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=7,
            expand=True,
        )

    def secondary_validation_row(item) -> ft.Container:
        icon = "✅" if item.correcto else "❌"
        color = ft.Colors.GREEN if item.correcto else ft.Colors.RED
        detail = (
            f"Esperado: {format_money(item.esperado)} · "
            f"Obtenido: {format_money(item.obtenido)} · "
            f"Diferencia: {format_money(item.diferencia)}"
        )
        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(icon, size=11),
                    ft.Text(item.nombre, size=8, weight=ft.FontWeight.BOLD, color=color),
                    ft.Container(expand=True),
                    ft.Text(detail, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=5,
            )
        ]
        if getattr(item, "mensaje", None):
            controls.append(
                ft.Text(
                    safe_value(item.mensaje),
                    size=7,
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )
        return ft.Container(
            ft.Column(controls, spacing=1, tight=True),
            padding=6,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
        )

    def metrics_rows(entries: list[tuple[str, str]], per_row: int = 4) -> list[ft.Control]:
        rows: list[ft.Control] = []
        for start in range(0, len(entries), per_row):
            chunk = entries[start : start + per_row]
            controls = [metric(title, value, compact=True) for title, value in chunk]
            while len(controls) < per_row:
                controls.append(ft.Container(expand=True))
            rows.append(ft.Row(controls, spacing=6))
        return rows

    def render_result(result):
        audit_view.controls.clear()
        if result is None:
            return

        estado = getattr(result, "estado_cuenta", None)
        if estado is None:
            audit_view.controls.append(ft.Text("⚠️ Resultado sin estado de cuenta."))
            return

        dc = getattr(estado, "datos_cuenta", None)
        rf = getattr(estado, "resumen_financiero", None)
        op = getattr(estado, "otros_productos", None)
        movements = getattr(estado, "movimientos", None) or []
        method = getattr(result, "processing_method", "Digital")
        process_text = "Digital" if method == "Digital" else engine_label(getattr(result, "ocr_engine", None))

        audit_view.controls.extend(
            [
                ft.Row(
                    [
                        ft.Text(f"🔍 {result.file_name}", size=15, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{str(result.bank_key).upper()} · {process_text}",
                            size=9,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]
                ),
                ft.Row(
                    [
                        metric(
                            "Periodo",
                            f"{safe_value(getattr(dc, 'periodo_inicio', None))} al "
                            f"{safe_value(getattr(dc, 'periodo_fin', None))}",
                        ),
                        metric("Cliente", safe_value(getattr(dc, "nombre_cliente", None))),
                        metric("Cuenta", safe_value(getattr(dc, "numero_cuenta", None))),
                        metric("CLABE", safe_value(getattr(dc, "clabe", None))),
                    ],
                    spacing=6,
                ),
            ]
        )

        if method == "OCR":
            primary = engine_label(getattr(result, "ocr_primary_engine", None))
            secondary = (
                engine_label(getattr(result, "ocr_secondary_engine", None))
                if getattr(result, "ocr_secondary_engine", None)
                else ""
            )
            if getattr(result, "fallback_attempted", False):
                fallback_text = f"Primario: {primary} · Secundario: {secondary} · " + (
                    "se usó el secundario"
                    if getattr(result, "fallback_used", False)
                    else "se conservó el primario"
                )
            else:
                fallback_text = f"Primario: {primary} · sin fallback: ambas validaciones principales pasaron"
            audit_view.controls.append(
                ft.Container(
                    ft.Text(f"⚙️ {fallback_text}", size=8, color=GOB_GREEN),
                    padding=6,
                    bgcolor=GOB_GREEN_LIGHT,
                    border_radius=6,
                )
            )

        account_entries = [
            ("Producto principal", safe_value(getattr(dc, "producto_principal", None))),
            ("Periodo inicio", safe_value(getattr(dc, "periodo_inicio", None))),
            ("Periodo fin", safe_value(getattr(dc, "periodo_fin", None))),
            ("Fecha de corte", safe_value(getattr(dc, "fecha_corte", None))),
            ("Número de cuenta", safe_value(getattr(dc, "numero_cuenta", None))),
            ("Número de cliente", safe_value(getattr(dc, "numero_cliente", None))),
            ("CLABE", safe_value(getattr(dc, "clabe", None))),
            ("Nombre del cliente", safe_value(getattr(dc, "nombre_cliente", None))),
            ("RFC", safe_value(getattr(dc, "rfc", None))),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text("📌 Datos de la cuenta · todos los campos", size=9, weight=ft.FontWeight.BOLD),
                controls=[ft.Container(ft.Column(metrics_rows(account_entries, 3), spacing=6), padding=6)],
            )
        )

        audit_view.controls.extend(
            [
                section("📊 Resumen financiero"),
                ft.Row(
                    [
                        metric("Saldo anterior", format_money(getattr(rf, "saldo_anterior", None))),
                        metric("Depósitos / Abonos", format_money(getattr(rf, "depositos_abonos", None))),
                        metric("Retiros / Cargos", format_money(getattr(rf, "retiros_cargos", None))),
                        metric("Saldo final", format_money(getattr(rf, "saldo_final", None))),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        validation_card(result, PRIMARY_VALIDATIONS[0], "Validación abonos"),
                        validation_card(result, PRIMARY_VALIDATIONS[1], "Validación cargos"),
                    ],
                    spacing=6,
                ),
            ]
        )

        all_validations = list(getattr(result, "validaciones", []) or [])
        secondary_validations = [item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS]
        correct_count = sum(1 for item in all_validations if item.correcto)
        audit_view.controls.append(
            ft.Text(
                f"Integridad financiera: {correct_count}/{len(all_validations)} validaciones correctas",
                size=8,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )
        audit_view.controls.append(
            ft.Text(
                f"Otras validaciones financieras ({len(secondary_validations)})",
                size=9,
                weight=ft.FontWeight.BOLD,
            )
        )
        if secondary_validations:
            audit_view.controls.extend(secondary_validation_row(item) for item in secondary_validations)
        else:
            audit_view.controls.append(
                ft.Text("No existen validaciones adicionales para este resultado.", size=8)
            )

        summary_entries = [
            ("Saldo promedio", format_money(getattr(rf, "saldo_promedio", None))),
            ("Días del periodo", safe_value(getattr(rf, "dias_periodo", None))),
            ("Tasa bruta anual", format_optional_float(getattr(rf, "tasa_bruta_anual", None), suffix="%")),
            ("Saldo promedio gravable", format_money(getattr(rf, "saldo_promedio_gravable", None))),
            ("Intereses a favor", format_money(getattr(rf, "intereses_a_favor", None))),
            ("ISR retenido", format_money(getattr(rf, "isr_retenido", None))),
            ("Cheques pagados", safe_value(getattr(rf, "cheques_pagados", None))),
            ("Manejo de cuenta", format_money(getattr(rf, "manejo_cuenta", None))),
            ("Cargos objetados", format_money(getattr(rf, "cargos_objetados", None))),
            ("Abonos objetados", format_money(getattr(rf, "abonos_objetados", None))),
            ("Saldo promedio mínimo mensual", format_money(getattr(rf, "saldo_promedio_minimo_mensual", None))),
            ("Saldo global", format_money(getattr(rf, "saldo_global", None))),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text("📈 Resumen financiero ampliado · todos los campos", size=9, weight=ft.FontWeight.BOLD),
                controls=[ft.Container(ft.Column(metrics_rows(summary_entries, 4), spacing=6), padding=6)],
            )
        )

        other_entries = [
            ("Contrato", safe_value(getattr(op, "contrato", None))),
            ("Producto", safe_value(getattr(op, "producto", None))),
            ("Tasa interés anual", format_optional_float(getattr(op, "tasa_interes_anual", None), suffix="%")),
            ("GAT nominal anual", format_optional_float(getattr(op, "gat_nominal_anual", None), suffix="%")),
            ("GAT real anual", format_optional_float(getattr(op, "gat_real_anual", None), suffix="%")),
            ("Total comisiones", format_optional_float(getattr(op, "total_comisiones", None), prefix="$")),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text("💰 Otros productos y comisiones · todos los campos", size=9, weight=ft.FontWeight.BOLD),
                controls=[ft.Container(ft.Column(metrics_rows(other_entries, 3), spacing=6), padding=6)],
            )
        )

        audit_view.controls.extend(
            [
                section(f"📑 Movimientos ({len(movements)})"),
                ft.Text(
                    "Encabezados fijos · filas compactas · desplazamiento horizontal y vertical.",
                    size=8,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                movements_table(
                    movements,
                    fecha_corte_documento=getattr(dc, "fecha_corte", None),
                    numero_cuenta_documento=getattr(dc, "numero_cuenta", None),
                )
                if movements
                else ft.Container(
                    ft.Text("⚠️ No se encontraron movimientos.", size=9),
                    padding=7,
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    border_radius=6,
                ),
            ]
        )
        reset_scroll()

    def show_settings(e=None):
        if state["running"]:
            return
        current = settings["ocr_primary_engine"]
        selector = ft.Dropdown(
            label="Motor OCR principal",
            value=current,
            width=300,
            options=[
                ft.DropdownOption(key="tesseract", text="Tesseract"),
                ft.DropdownOption(key="paddleocr", text="PaddleOCR"),
            ],
        )
        order_text = ft.Text("", size=9, color=ft.Colors.ON_SURFACE_VARIANT)

        def refresh_order(_=None):
            primary = normalize_ocr_engine(selector.value)
            order_text.value = (
                f"Orden: {engine_label(primary)} → {engine_label(secondary_ocr_engine(primary))} "
                "sólo si falla Abonos o Cargos"
            )
            page.update()

        def save(_):
            settings["ocr_primary_engine"] = normalize_ocr_engine(selector.value)
            settings_badge.value = f"OCR principal: {engine_label(settings['ocr_primary_engine'])}"
            page.pop_dialog()
            page.update()

        selector.on_select = refresh_order
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configuración de procesamiento", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Container(
                        ft.Text(
                            "Recomendación: mantenga la configuración predeterminada (Tesseract como motor principal) "
                            "salvo que el área técnica indique un cambio. PaddleOCR puede tardar más en CPU.",
                            size=9,
                            weight=ft.FontWeight.W_500,
                            color=GOB_GREEN_DARK,
                        ),
                        padding=9,
                        bgcolor=GOB_GOLD_LIGHT,
                        border_radius=7,
                    ),
                    selector,
                    order_text,
                    ft.Text(
                        "El motor secundario NO procesa archivos que ya conciliaron correctamente las dos "
                        "validaciones principales de depósitos/abonos y retiros/cargos.",
                        size=9,
                    ),
                    ft.Text(
                        "Los PDFs digitales no entran a OCR. OCR se utiliza únicamente para PDFs escaneados o "
                        "sin texto digital utilizable.",
                        size=9,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.OutlinedButton(content="Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.FilledButton(content="Guardar", bgcolor=GOB_GREEN, color=BUTTON_TEXT, on_click=save),
            ],
        )
        refresh_order()
        page.show_dialog(dialog)

    def show_help(e=None):
        dialog = ft.AlertDialog(
            modal=False,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=GOB_GREEN, size=22),
                    ft.Text("Ayuda y recomendaciones", weight=ft.FontWeight.BOLD, size=15),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text("PDFs digitales y escaneados", size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        "Digital significa que el PDF contiene texto utilizable. PDFs escaneados (OCR) son imágenes "
                        "o documentos cuyo texto no puede leerse directamente y requieren un motor OCR.",
                        size=9,
                    ),
                    ft.Divider(),
                    ft.Text("Validaciones financieras", size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        "Las validaciones comparan los totales de depósitos/abonos y retiros/cargos contra la suma "
                        "de los movimientos extraídos. A y C en el selector representan esas dos conciliaciones.",
                        size=9,
                    ),
                    ft.Text(
                        "Si una validación falla, revise primero resumen financiero, intereses, ISR, IVA, comisiones "
                        "y después los movimientos extraídos.",
                        size=9,
                    ),
                    ft.Divider(),
                    ft.Text("Bancos y estados de cuenta habilitados", size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text("BBVA Digital", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Libretón Básico\n• Libretón Nómina\n• Libretón Premium", size=9),
                    ft.Text("Banorte Digital y Escaneado", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Nómina Banorte\n• Nómina Banorte sin chequera\n• Enlace Negocios", size=9),
                    ft.Text("Banamex Digital", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Mi Cuenta\n• Cuenta Base\n• Cuenta Prioriti", size=9),
                    ft.Text("HSBC Digital y Escaneado", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Ahorro y Debito", size=9),
                    ft.Text("Scotiabank Digital", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Nomina Clasic", size=9),
                    ft.Text("Banca Mifel", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• Cuenta Alavista", size=9),
                    ft.Text("CETESDIRECTO Digital", size=9, weight=ft.FontWeight.BOLD),
                    ft.Text("• cetesdirecto", size=9),
                    ft.Text("MercadoPago Digital", size=9, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        ft.Text(
                            "La lista de formatos habilitados se actualiza conforme se incorporan nuevos modelos.",
                            size=8,
                        ),
                        bgcolor=GOB_CREAM,
                        padding=8,
                        border_radius=7,
                    ),
                ],
                spacing=6,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                height=500,
            ),
            actions=[
                ft.FilledButton(
                    content="Cerrar",
                    icon=ft.Icons.CLOSE,
                    bgcolor=GOB_GREEN,
                    color=BUTTON_TEXT,
                    on_click=lambda ev: page.pop_dialog(),
                )
            ],
        )
        page.show_dialog(dialog)

    def processing_worker(paths: list[str], names: list[str], batch_id: int, primary_engine: str):
        try:
            for event in process_bank_statements_incremental(
                paths,
                names,
                ocr_primary_engine=primary_engine,
            ):
                event_queue.put(("event", batch_id, event))
        except Exception as ex:
            event_queue.put(("worker_error", batch_id, ex, traceback.format_exc()))
        finally:
            event_queue.put(("finished", batch_id))

    def handle_event(event) -> tuple[bool, bool]:
        index = getattr(event, "index", None)
        if not isinstance(index, int) or not (0 <= index < len(processing_items)):
            return False, False
        item = processing_items[index]

        if event.kind == "started":
            item.update(status="processing", processing_method=event.processing_method, error=None)
            return True, False

        if event.kind == "completed":
            item.update(
                status="completed",
                processing_method=event.processing_method,
                result=event.result,
                error=None,
            )
            if event.result is not None:
                results.append(event.result)
                export_button.disabled = False
                if state["selected_index"] is None:
                    state["selected_index"] = index
                    render_result(event.result)
            return True, True

        if event.kind == "error":
            item.update(
                status="error",
                processing_method=event.processing_method,
                result=None,
                error=str(event.error or "Error desconocido"),
            )
            return True, False

        return False, False

    def finish_controls():
        state["running"] = False
        if state["started_at"] is not None:
            state["elapsed_seconds"] = time.perf_counter() - state["started_at"]
        timer_text.value = format_elapsed(state["elapsed_seconds"])
        loading_ring.visible = False
        upload_button.disabled = False
        config_button.disabled = False

    async def poller():
        while True:
            page_changed = False
            selector_changed = False

            try:
                while True:
                    message = event_queue.get_nowait()
                    kind, batch_id = message[0], message[1]
                    if batch_id != state["batch_id"]:
                        continue

                    if kind == "event":
                        changed, completed_changed = handle_event(message[2])
                        page_changed = page_changed or changed
                        selector_changed = selector_changed or completed_changed
                        update_status()
                    elif kind == "worker_error":
                        ex, tb = message[2], message[3]
                        for item in processing_items:
                            if item.get("status") not in {"completed", "error"}:
                                item.update(status="error", error=str(ex))
                        status_text.value = f"❌ Error de procesamiento: {ex}"
                        status_text.color = ft.Colors.RED
                        audit_view.controls[:] = [
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Text(str(ex), weight=ft.FontWeight.BOLD),
                                        ft.Text(tb, size=8, selectable=True),
                                    ]
                                ),
                                padding=8,
                                bgcolor=ft.Colors.ERROR_CONTAINER,
                                border_radius=6,
                            )
                        ]
                        finish_controls()
                        page_changed = True
                    elif kind == "finished":
                        finish_controls()
                        update_status()
                        page_changed = True

            except Empty:
                pass
            except Exception as ex:
                status_text.value = f"❌ Error actualizando interfaz: {ex}"
                status_text.color = ft.Colors.RED
                page_changed = True

            if selector_changed:
                update_selector()

            now = time.perf_counter()
            if state["running"] and state["started_at"] is not None:
                if now - state["last_timer_refresh"] >= TIMER_REFRESH_SECONDS:
                    state["last_timer_refresh"] = now
                    state["elapsed_seconds"] = now - state["started_at"]
                    timer_text.value = format_elapsed(state["elapsed_seconds"])
                    try:
                        timer_text.update()
                    except Exception:
                        return

            if page_changed:
                try:
                    page.update()
                except Exception:
                    return

            await asyncio.sleep(PROCESSING_UI_POLL_INTERVAL)

    def initialize_batch(paths: list[str], names: list[str]):
        state["batch_id"] += 1
        state["running"] = True
        state["started_at"] = time.perf_counter()
        state["elapsed_seconds"] = 0.0
        state["selected_index"] = None
        state["selector_signature"] = None
        state["last_timer_refresh"] = 0.0

        results.clear()
        processing_items.clear()
        try:
            while True:
                event_queue.get_nowait()
        except Empty:
            pass

        for name in names:
            processing_items.append(
                {
                    "file_name": name,
                    "processing_method": None,
                    "status": "classifying",
                    "result": None,
                    "error": None,
                }
            )

        loading_ring.visible = True
        upload_button.disabled = True
        config_button.disabled = True
        export_button.disabled = True
        audit_view.controls.clear()
        status_text.value = "Preparando estados de cuenta..."
        status_text.color = ft.Colors.ON_SURFACE
        timer_text.value = "00:00"
        audit_section.visible = True
        export_section.visible = True
        update_selector(force=True)
        update_status()
        page.update()

    def start_worker(paths: list[str], names: list[str]):
        page.run_thread(
            processing_worker,
            paths,
            names,
            state["batch_id"],
            settings["ocr_primary_engine"],
        )

    async def pick_files(e):
        try:
            selected = await ft.FilePicker().pick_files(
                dialog_title="Selecciona estados de cuenta PDF",
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
            )
            if not selected:
                return
            paths = [file.path for file in selected if file.path]
            names = [file.name for file in selected if file.path]
            if not paths:
                status_text.value = "❌ No fue posible obtener las rutas de los PDFs."
                status_text.color = ft.Colors.RED
                page.update()
                return
            initialize_batch(paths, names)
            start_worker(paths, names)
        except Exception as ex:
            status_text.value = f"❌ Error al seleccionar archivos: {ex}"
            status_text.color = ft.Colors.RED
            page.update()

    async def export_excel(e):
        if not results:
            return
        path = await ft.FilePicker().save_file(
            dialog_title="Guardar reporte Excel",
            file_name="reporte_estados_de_cuenta.xlsx",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        snapshot = list(results)
        export_button.disabled = True
        status_text.value = "Generando archivo Excel..."
        page.update()

        def worker():
            try:
                export_batch_excel(snapshot, path)
                status_text.value = "✅ Archivo Excel exportado correctamente."
                status_text.color = ft.Colors.GREEN
                try:
                    if sys.platform == "win32":
                        subprocess.run(["explorer", "/select,", path])
                    elif sys.platform == "darwin":
                        subprocess.run(["open", "-R", path])
                    else:
                        subprocess.run(["xdg-open", os.path.dirname(path)])
                except Exception:
                    pass
            except Exception as ex:
                status_text.value = f"❌ Error al exportar Excel: {ex}"
                status_text.color = ft.Colors.RED
            finally:
                export_button.disabled = False
                try:
                    page.update()
                except Exception:
                    pass

        page.run_thread(worker)

    upload_button = ft.FilledButton(
        content="Seleccionar estados de cuenta PDF",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=pick_files,
        bgcolor=GOB_GREEN,
        color=BUTTON_TEXT,
    )
    config_button = ft.OutlinedButton(
        content="Configuración",
        icon=ft.Icons.SETTINGS,
        on_click=show_settings,
    )
    help_button = ft.OutlinedButton(
        content="Ayuda",
        icon=ft.Icons.HELP_OUTLINE,
        on_click=show_help,
    )
    export_button.on_click = export_excel

    settings_badge = ft.Text(
        f"OCR principal: {engine_label(settings['ocr_primary_engine'])}",
        size=8,
        weight=ft.FontWeight.BOLD,
        color=GOB_GREEN,
    )

    header: list[ft.Control] = []
    if LOGO_PATH.exists():
        header.append(
            ft.Container(
                ft.Image(src=str(LOGO_PATH), width=145, height=72, fit=ft.BoxFit.CONTAIN),
                width=152,
                height=76,
                alignment=ft.Alignment.CENTER,
            )
        )
    header.append(
        ft.Column(
            [
                ft.Text("Secretaría Anticorrupción y Buen Gobierno", size=10, weight=ft.FontWeight.W_500),
                ft.Text("Dirección General de Evaluación de Confianza", size=9, weight=ft.FontWeight.W_500),
                ft.Text("Departamento de Investigación de Antecedentes", size=8, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=1,
            expand=True,
        )
    )

    audit_section = ft.Column(
        [ft.Divider(height=8), selector_view, ft.Divider(height=8), audit_view],
        spacing=4,
        visible=False,
    )
    export_section = ft.Column(
        [
            ft.Divider(),
            ft.Row(
                [
                    ft.Text("📤 Exportación", size=13, weight=ft.FontWeight.BOLD),
                    ft.Text("Un solo Excel con todos los resultados terminados.", size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(expand=True),
                    export_button,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=18),
        ],
        spacing=3,
        visible=False,
    )

    app_content = ft.Column(
        [
            ft.Row(header, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=7),
            ft.Row(
                [
                    ft.Text("📄 Extractor de Movimientos Financieros", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Container(
                        ft.Text(f"Versión {APP_VERSION}", size=8, weight=ft.FontWeight.BOLD),
                        bgcolor=GOB_GOLD_LIGHT,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=11,
                    ),
                    settings_badge,
                    config_button,
                    help_button,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(
                "PDFs digitales se leen directamente. PDFs escaneados (OCR) usan el motor configurado.",
                size=8,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Container(
                ft.Row(
                    [
                        upload_button,
                        loading_ring,
                        ft.Text("⏱", size=12),
                        timer_text,
                        ft.Container(width=5),
                        status_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=7),
            ),
            audit_section,
            export_section,
        ],
        spacing=0,
    )

    page.run_task(poller)
    page.add(app_content)


if __name__ == "__main__":
    ft.run(main)
