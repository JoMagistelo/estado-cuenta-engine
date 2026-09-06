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

GOB_GREEN = "#1F4D3A"
GOB_GREEN_LIGHT = "#E8F0EC"
GOB_GOLD = "#B08D57"
GOB_GOLD_LIGHT = "#F4EEE5"
GOB_CREAM = "#F7F4EE"
BUTTON_TEXT = "#FFFFFF"
APP_VERSION = "2.1"
PROCESSING_UI_POLL_INTERVAL = 0.20
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "assets" / "logo_gobierno_mexico.png"
PRIMARY_VALIDATIONS = ("Total depósitos / abonos", "Total retiros / cargos")

MOVEMENT_COLUMNS = [
    ("fecha_corte", "Fecha Corte"),
    ("numero_cuenta", "Número de Cuenta"),
    ("numero_movimiento", "No. Movimiento"),
    ("fecha_operacion", "Fecha Operación"),
    ("fecha_liquidacion", "Fecha Liquidación"),
    ("concepto", "Concepto"),
    ("concepto_original", "Concepto Original"),
    ("cargo", "Cargo"),
    ("abono", "Abono"),
    ("saldo_operacion", "Saldo Operación"),
    ("saldo_liquidacion", "Saldo Liquidación"),
    ("tipo_operacion", "Tipo"),
    ("beneficiario", "Beneficiario"),
    ("cuenta_beneficiario", "Cuenta Benef."),
    ("clabe_beneficiario", "CLABE Benef."),
    ("rfc", "RFC"),
    ("referencia", "Referencia"),
    ("clave_rastreo", "Clave Rastreo"),
    ("autorizacion", "Autorización"),
    ("hora_operacion", "Hora"),
    ("sucursal", "Sucursal"),
    ("caja", "Caja"),
]

MONEY_MOVEMENT_FIELDS = {"cargo", "abono", "saldo_operacion", "saldo_liquidacion"}


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
    return {"tesseract": "Tesseract", "paddleocr": "PaddleOCR"}.get(normalized, "OCR")


def format_elapsed(seconds: float) -> str:
    seconds = max(float(seconds or 0.0), 0.0)
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def main(page: ft.Page):
    page.title = "Extractor de Movimientos Financieros"

    # Maximizada respeta el área útil de Windows (incluida la barra de tareas).
    # El tamaño restaurado es deliberadamente más bajo para equipos con DPI alto.
    page.window.width = 1180
    page.window.height = 660
    page.window.min_width = 920
    page.window.min_height = 560
    page.window.maximized = True

    page.padding = 16
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    results: list[Any] = []
    processing_items: list[dict[str, Any]] = []
    event_queue: Queue = Queue()
    settings = {
        "ocr_primary_engine": normalize_ocr_engine(os.getenv("OCR_PRIMARY_ENGINE", "tesseract"))
    }
    state: dict[str, Any] = {
        "running": False,
        "batch_id": 0,
        "started_at": None,
        "elapsed_seconds": 0.0,
        "selected_index": None,
    }

    status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    timer_text = ft.Text("00:00.0", size=12, weight=ft.FontWeight.BOLD)
    loading_ring = ft.ProgressRing(width=18, height=18, visible=False)
    summary_view = ft.Container(visible=False)
    audit_view = ft.Column(spacing=10)
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

    def symbol(item) -> str:
        return "—" if item is None else ("✅" if item.correcto else "❌")

    def metric(title: str, value: str, *, compact: bool = False):
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
                        size=11 if compact else 13,
                        weight=ft.FontWeight.BOLD,
                        max_lines=3,
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

    def section(title: str):
        return ft.Text(title, size=15, weight=ft.FontWeight.BOLD)

    def reset_scroll():
        async def _reset():
            try:
                await page.scroll_to(offset=0, duration=0)
            except Exception:
                pass

        page.run_task(_reset)

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
                return f"{label} ↪ fallback"
            if getattr(result, "fallback_attempted", False):
                return f"{label} · revisado"
            return label
        return "Detectando"

    def select_item(index: int):
        if not (0 <= index < len(processing_items)):
            return
        item = processing_items[index]
        result = item.get("result")
        if item.get("status") != "completed" or result is None:
            return
        state["selected_index"] = index
        update_summary()
        render_result(result)
        page.update()

    def processed_row(index: int, item: dict[str, Any]):
        result = item.get("result")
        status = item.get("status")
        selected = state.get("selected_index") == index
        if status == "completed" and result is not None:
            abonos = symbol(validation(result, PRIMARY_VALIDATIONS[0]))
            cargos = symbol(validation(result, PRIMARY_VALIDATIONS[1]))
        elif status == "error":
            abonos = cargos = "⚠️"
        else:
            abonos = cargos = "⏳"

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        ft.Text(
                            item.get("file_name", ""),
                            size=10,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        expand=True,
                    ),
                    ft.Container(
                        ft.Text(process_label(item), size=9, weight=ft.FontWeight.W_500),
                        width=120,
                    ),
                    ft.Container(ft.Text(abonos, size=11), width=36, alignment=ft.Alignment.CENTER),
                    ft.Container(ft.Text(cargos, size=11), width=36, alignment=ft.Alignment.CENTER),
                ],
                spacing=5,
            ),
            padding=ft.Padding.symmetric(horizontal=7, vertical=6),
            bgcolor=GOB_GREEN_LIGHT if selected else None,
            border=ft.Border.all(1, GOB_GREEN if selected else ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
            on_click=(lambda e, i=index: select_item(i)) if status == "completed" and result else None,
        )

    def processed_panel(
        title: str,
        icon: str,
        indexed_items: list[tuple[int, dict[str, Any]]],
    ):
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        ft.Text(
                            f"{icon} {title} ({len(indexed_items)})",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                        ),
                        expand=True,
                    ),
                    ft.Container(ft.Text("Motor", size=8), width=120),
                    ft.Container(ft.Text("A", size=8), width=36, alignment=ft.Alignment.CENTER),
                    ft.Container(ft.Text("C", size=8), width=36, alignment=ft.Alignment.CENTER),
                ],
                spacing=5,
            ),
            padding=ft.Padding.symmetric(horizontal=7, vertical=5),
            bgcolor=GOB_CREAM,
            border_radius=6,
        )
        rows = [processed_row(i, item) for i, item in indexed_items]
        if not rows:
            rows = [
                ft.Container(
                    ft.Text("Sin archivos", size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=7,
                )
            ]
        return ft.Container(
            content=ft.Column([header, *rows], spacing=3, scroll=ft.ScrollMode.AUTO),
            height=176,
            padding=7,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            expand=True,
        )

    def update_summary():
        if not processing_items:
            summary_view.visible = False
            summary_view.content = None
            return

        digital = [
            (i, x)
            for i, x in enumerate(processing_items)
            if x.get("processing_method") == "Digital"
        ]
        ocr = [
            (i, x)
            for i, x in enumerate(processing_items)
            if x.get("processing_method") == "OCR"
        ]
        classifying = sum(1 for x in processing_items if not x.get("processing_method"))
        note = "Haz clic en un archivo terminado para abrir su auditoría · A=abonos · C=cargos"
        if classifying:
            note += f" · {classifying} clasificando"

        summary_view.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Archivos procesados", size=14, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(note, size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                    ]
                ),
                ft.Row(
                    [
                        processed_panel("Digitales", "📄", digital),
                        processed_panel("OCR", "🔎", ocr),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=5,
        )
        summary_view.visible = True

    def update_status():
        total = len(processing_items)
        completed = sum(1 for x in processing_items if x.get("status") == "completed")
        errors = sum(1 for x in processing_items if x.get("status") == "error")
        pending = total - completed - errors
        if pending > 0:
            status_text.value = (
                f"Procesando {completed} de {total} archivos"
                + (f" · {errors} con error" if errors else "")
            )
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

    def update_timer() -> bool:
        old = timer_text.value
        if state["running"] and state["started_at"] is not None:
            state["elapsed_seconds"] = time.perf_counter() - state["started_at"]
        timer_text.value = format_elapsed(state["elapsed_seconds"])
        return old != timer_text.value

    def movement_cell(field_name: str, value: Any):
        text_value = format_money(value) if field_name in MONEY_MOVEMENT_FIELDS else safe_value(value)
        widths = {
            "fecha_corte": 90,
            "numero_cuenta": 120,
            "numero_movimiento": 75,
            "fecha_operacion": 95,
            "fecha_liquidacion": 95,
            "concepto": 240,
            "concepto_original": 240,
            "cargo": 95,
            "abono": 95,
            "saldo_operacion": 105,
            "saldo_liquidacion": 105,
            "tipo_operacion": 110,
            "beneficiario": 180,
            "cuenta_beneficiario": 145,
            "clabe_beneficiario": 155,
            "rfc": 125,
            "referencia": 140,
            "clave_rastreo": 170,
            "autorizacion": 130,
            "hora_operacion": 80,
            "sucursal": 90,
            "caja": 75,
        }
        return ft.DataCell(
            ft.Container(
                ft.Text(
                    text_value,
                    size=9,
                    max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    selectable=True,
                ),
                width=widths.get(field_name, 110),
            )
        )

    def movements_table(
        movements,
        *,
        fecha_corte_documento: str | None = None,
        numero_cuenta_documento: str | None = None,
    ):
        data_columns = [
            ft.DataColumn(ft.Text(label, size=9, weight=ft.FontWeight.BOLD))
            for _, label in MOVEMENT_COLUMNS
        ]
        rows = []
        for i, mov in enumerate(movements, 1):
            cells = []
            for field_name, _ in MOVEMENT_COLUMNS:
                if field_name == "fecha_corte":
                    value = fecha_corte_documento
                elif field_name == "numero_cuenta":
                    value = numero_cuenta_documento
                elif field_name == "numero_movimiento":
                    value = i
                else:
                    value = getattr(mov, field_name, None)
                cells.append(movement_cell(field_name, value))
            rows.append(ft.DataRow(cells=cells))

        table = ft.DataTable(
            columns=data_columns,
            rows=rows,
            column_spacing=8,
            heading_row_height=34,
            data_row_min_height=38,
            data_row_max_height=72,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            vertical_lines=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            horizontal_lines=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
        )
        return ft.Column(
            controls=[ft.Row(controls=[table], scroll=ft.ScrollMode.ALWAYS)],
            scroll=ft.ScrollMode.ALWAYS,
            height=360,
            spacing=0,
        )

    def validation_card(result, name: str, short_name: str):
        item = validation(result, name)
        if item is None:
            text, color, detail = "—", ft.Colors.ON_SURFACE_VARIANT, "No se pudo calcular"
        elif item.correcto:
            text, color, detail = "✅", ft.Colors.GREEN, "Conciliación correcta"
        else:
            text, color = "❌", ft.Colors.RED
            detail = (
                f"Esperado {format_money(item.esperado)} · "
                f"Obtenido {format_money(item.obtenido)} · "
                f"Diferencia {format_money(item.diferencia)}"
            )
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(text, size=15),
                    ft.Column(
                        [
                            ft.Text(short_name, size=10, weight=ft.FontWeight.BOLD, color=color),
                            ft.Text(detail, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=1,
                        tight=True,
                    ),
                ],
                spacing=7,
            ),
            padding=8,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=7,
            expand=True,
        )

    def secondary_validation_row(item):
        icon = "✅" if item.correcto else "❌"
        color = ft.Colors.GREEN if item.correcto else ft.Colors.RED
        detail = (
            f"Esperado: {format_money(item.esperado)}   ·   "
            f"Obtenido: {format_money(item.obtenido)}   ·   "
            f"Diferencia: {format_money(item.diferencia)}"
        )
        controls = [
            ft.Row(
                [
                    ft.Text(icon, size=12),
                    ft.Text(item.nombre, size=9, weight=ft.FontWeight.BOLD, color=color),
                    ft.Container(expand=True),
                    ft.Text(detail, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=6,
            )
        ]
        if getattr(item, "mensaje", None):
            controls.append(
                ft.Text(
                    safe_value(item.mensaje),
                    size=8,
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )
        return ft.Container(
            ft.Column(controls, spacing=2, tight=True),
            padding=7,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
        )

    def metrics_rows(entries: list[tuple[str, str]], per_row: int = 4):
        rows: list[ft.Control] = []
        for start in range(0, len(entries), per_row):
            chunk = entries[start : start + per_row]
            controls = [metric(title, value, compact=True) for title, value in chunk]
            while len(controls) < per_row:
                controls.append(ft.Container(expand=True))
            rows.append(ft.Row(controls, spacing=7))
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
        process_text = (
            "Digital" if method == "Digital" else engine_label(getattr(result, "ocr_engine", None))
        )

        audit_view.controls.extend(
            [
                ft.Row(
                    [
                        ft.Text(f"🔍 {result.file_name}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{str(result.bank_key).upper()} · {process_text}",
                            size=10,
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
                    spacing=7,
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
                fallback_text = (
                    f"Primario: {primary} · sin fallback: ambas validaciones principales pasaron"
                )
            audit_view.controls.append(
                ft.Container(
                    ft.Text(f"⚙️ {fallback_text}", size=9, color=GOB_GREEN),
                    padding=7,
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
                title=ft.Text(
                    "📌 Datos de la cuenta · todos los campos",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                ),
                expanded=False,
                controls=[ft.Container(ft.Column(metrics_rows(account_entries, 3), spacing=7), padding=7)],
            )
        )

        audit_view.controls.extend(
            [
                section("📊 Resumen financiero"),
                ft.Row(
                    [
                        metric("Saldo anterior", format_money(getattr(rf, "saldo_anterior", None))),
                        metric(
                            "Depósitos / Abonos",
                            format_money(getattr(rf, "depositos_abonos", None)),
                        ),
                        metric(
                            "Retiros / Cargos",
                            format_money(getattr(rf, "retiros_cargos", None)),
                        ),
                        metric("Saldo final", format_money(getattr(rf, "saldo_final", None))),
                    ],
                    spacing=7,
                ),
                ft.Row(
                    [
                        validation_card(result, PRIMARY_VALIDATIONS[0], "Validación abonos"),
                        validation_card(result, PRIMARY_VALIDATIONS[1], "Validación cargos"),
                    ],
                    spacing=7,
                ),
            ]
        )

        all_validations = list(getattr(result, "validaciones", []) or [])
        secondary_validations = [
            item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS
        ]
        correct_count = sum(1 for item in all_validations if item.correcto)
        audit_view.controls.append(
            ft.Text(
                f"Integridad financiera: {correct_count}/{len(all_validations)} validaciones correctas",
                size=9,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )
        audit_view.controls.append(
            ft.Text(
                f"Otras validaciones financieras ({len(secondary_validations)})",
                size=10,
                weight=ft.FontWeight.BOLD,
            )
        )
        if secondary_validations:
            audit_view.controls.extend(secondary_validation_row(item) for item in secondary_validations)
        else:
            audit_view.controls.append(
                ft.Text(
                    "No existen validaciones adicionales para este resultado.",
                    size=8,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        summary_entries = [
            ("Saldo promedio", format_money(getattr(rf, "saldo_promedio", None))),
            ("Días del periodo", safe_value(getattr(rf, "dias_periodo", None))),
            (
                "Tasa bruta anual",
                format_optional_float(getattr(rf, "tasa_bruta_anual", None), suffix="%"),
            ),
            (
                "Saldo promedio gravable",
                format_money(getattr(rf, "saldo_promedio_gravable", None)),
            ),
            ("Intereses a favor", format_money(getattr(rf, "intereses_a_favor", None))),
            ("ISR retenido", format_money(getattr(rf, "isr_retenido", None))),
            ("Cheques pagados", safe_value(getattr(rf, "cheques_pagados", None))),
            ("Manejo de cuenta", format_money(getattr(rf, "manejo_cuenta", None))),
            ("Cargos objetados", format_money(getattr(rf, "cargos_objetados", None))),
            ("Abonos objetados", format_money(getattr(rf, "abonos_objetados", None))),
            (
                "Saldo promedio mínimo mensual",
                format_money(getattr(rf, "saldo_promedio_minimo_mensual", None)),
            ),
            ("Saldo global", format_money(getattr(rf, "saldo_global", None))),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    "📈 Resumen financiero ampliado · todos los campos",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Container(ft.Column(metrics_rows(summary_entries, 4), spacing=7), padding=7)],
            )
        )

        other_entries = [
            ("Contrato", safe_value(getattr(op, "contrato", None))),
            ("Producto", safe_value(getattr(op, "producto", None))),
            (
                "Tasa interés anual",
                format_optional_float(getattr(op, "tasa_interes_anual", None), suffix="%"),
            ),
            (
                "GAT nominal anual",
                format_optional_float(getattr(op, "gat_nominal_anual", None), suffix="%"),
            ),
            (
                "GAT real anual",
                format_optional_float(getattr(op, "gat_real_anual", None), suffix="%"),
            ),
            (
                "Total comisiones",
                format_optional_float(getattr(op, "total_comisiones", None), prefix="$"),
            ),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    "💰 Otros productos y comisiones · todos los campos",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Container(ft.Column(metrics_rows(other_entries, 3), spacing=7), padding=7)],
            )
        )

        audit_view.controls.extend(
            [
                section(f"📑 Movimientos ({len(movements)})"),
                ft.Text(
                    "La tabla expone todas las variables del modelo Movimiento. "
                    "Usa las barras horizontal y vertical para navegar.",
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
                    ft.Text("⚠️ No se encontraron movimientos.", size=10),
                    padding=8,
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
        order_text = ft.Text("", size=10, color=ft.Colors.ON_SURFACE_VARIANT)

        def refresh_order(_=None):
            primary = normalize_ocr_engine(selector.value)
            order_text.value = (
                f"Orden: {engine_label(primary)} → {engine_label(secondary_ocr_engine(primary))} "
                "sólo si falla Abonos o Cargos"
            )
            page.update()

        def save(_):
            settings["ocr_primary_engine"] = normalize_ocr_engine(selector.value)
            settings_badge.value = f"OCR: {engine_label(settings['ocr_primary_engine'])}"
            page.pop_dialog()
            page.update()

        selector.on_select = refresh_order
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configuración de procesamiento", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("El motor seleccionado procesa primero cada PDF OCR.", size=10),
                    selector,
                    order_text,
                    ft.Container(
                        ft.Text(
                            "El motor secundario NO procesa archivos que ya conciliaron correctamente "
                            "las validaciones de depósitos/abonos y retiros/cargos.",
                            size=9,
                        ),
                        padding=8,
                        bgcolor=GOB_GREEN_LIGHT,
                        border_radius=6,
                    ),
                    ft.Text(
                        "Los PDFs digitales siguen usando el lector digital y nunca se envían a OCR.",
                        size=9,
                    ),
                ],
                spacing=9,
                tight=True,
            ),
            actions=[
                ft.OutlinedButton(content="Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.FilledButton(
                    content="Guardar",
                    bgcolor=GOB_GREEN,
                    color=BUTTON_TEXT,
                    on_click=save,
                ),
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
                    ft.Text("Ayuda y recomendaciones", weight=ft.FontWeight.BOLD, size=16),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Divider(),
                    ft.Text(
                        "Validaciones financieras",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GREEN,
                    ),
                    ft.Text(
                        "Estas validaciones comparan los totales de depósitos / abonos y retiros / cargos "
                        "contra la suma de los movimientos extraídos.",
                        size=10,
                    ),
                    ft.Text(
                        "Si una validación falla, revise primero los totales y conceptos del resumen "
                        "financiero. Algunos estados de cuenta pueden mostrar por separado intereses, "
                        "ISR, IVA o comisiones que deben considerarse al conciliar los movimientos.",
                        size=10,
                    ),
                    ft.Text(
                        "¿Qué hacer cuando una validación falla?",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Primero verifique que los totales del resumen sean correctos y revise si existen "
                        "intereses, ISR, IVA o comisiones que expliquen la diferencia. Si los totales son "
                        "correctos, revise después los montos de los movimientos.",
                        size=10,
                    ),
                    ft.Text(
                        "A y C en los paneles representan las validaciones principales de Abonos y Cargos. "
                        "Las demás validaciones se muestran debajo de esas dos en la auditoría.",
                        size=9,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Divider(),
                    ft.Text(
                        "Bancos y estados de cuenta habilitados",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GREEN,
                    ),
                    ft.Text("BBVA Digital", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• Libretón Básico\n• Libretón Nómina\n• Libretón Premium", size=10),
                    ft.Text("Banorte Digital y Escaneado", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "• Nómina Banorte\n• Nómina Banorte sin chequera\n• Enlace Negocios",
                        size=10,
                    ),
                    ft.Text("Banamex Digital", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• Mi Cuenta\n• Cuenta Base\n• Cuenta Prioriti", size=10),
                    ft.Text("HSBC Digital y Escaneado", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• Ahorro y Debito", size=10),
                    ft.Text("Scotiabank Digital", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• Nomina Clasic", size=10),
                    ft.Text("Banca Mifel", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• Cuenta Alavista", size=10),
                    ft.Text("CETESDIRECTO Digital", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text("• cetesdirecto", size=10),
                    ft.Text("MercadoPago Digital", size=10, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Próximamente PDFs Escaneados",
                        size=9,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GOLD,
                    ),
                    ft.Divider(),
                    ft.Container(
                        ft.Text(
                            "Nota: la lista de formatos habilitados se actualizará conforme se incorporen "
                            "nuevos modelos de estados de cuenta.",
                            size=8,
                        ),
                        bgcolor=GOB_CREAM,
                        padding=10,
                        border_radius=8,
                    ),
                ],
                spacing=7,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                height=520,
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

    def processing_worker(
        paths: list[str],
        names: list[str],
        batch_id: int,
        primary_engine: str,
    ):
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

    def handle_event(event) -> bool:
        index = getattr(event, "index", None)
        if not isinstance(index, int) or not (0 <= index < len(processing_items)):
            return False
        item = processing_items[index]
        if event.kind == "started":
            item.update(status="processing", processing_method=event.processing_method, error=None)
            return True
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
            return True
        if event.kind == "error":
            item.update(
                status="error",
                processing_method=event.processing_method,
                result=None,
                error=str(event.error or "Error desconocido"),
            )
            return True
        return False

    def finish_controls():
        state["running"] = False
        if state["started_at"] is not None:
            state["elapsed_seconds"] = time.perf_counter() - state["started_at"]
        loading_ring.visible = False
        upload_button.disabled = False
        config_button.disabled = False
        update_timer()

    async def poller():
        while True:
            changed = update_timer()
            try:
                while True:
                    message = event_queue.get_nowait()
                    kind, batch_id = message[0], message[1]
                    if batch_id != state["batch_id"]:
                        continue
                    if kind == "event":
                        changed = handle_event(message[2]) or changed
                        update_summary()
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
                        update_summary()
                        changed = True
                    elif kind == "finished":
                        finish_controls()
                        update_summary()
                        update_status()
                        changed = True
            except Empty:
                pass
            except Exception as ex:
                status_text.value = f"❌ Error actualizando interfaz: {ex}"
                status_text.color = ft.Colors.RED
                changed = True
            if changed:
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
        timer_text.value = "00:00.0"
        audit_section.visible = True
        export_section.visible = True
        update_summary()
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
            paths = [f.path for f in selected if f.path]
            names = [f.name for f in selected if f.path]
            if not paths:
                status_text.value = "❌ No fue posible obtener las rutas de los PDFs."
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
                page.update()

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
        f"OCR: {engine_label(settings['ocr_primary_engine'])}",
        size=9,
        weight=ft.FontWeight.BOLD,
        color=GOB_GREEN,
    )

    header: list[ft.Control] = []
    if LOGO_PATH.exists():
        header.append(
            ft.Container(
                ft.Image(src=str(LOGO_PATH), width=150, height=78, fit=ft.BoxFit.CONTAIN),
                width=158,
                height=82,
                alignment=ft.Alignment.CENTER,
            )
        )
    header.append(
        ft.Column(
            [
                ft.Text(
                    "Secretaría Anticorrupción y Buen Gobierno",
                    size=11,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text(
                    "Dirección General de Evaluación de Confianza",
                    size=9,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text(
                    "Departamento de Investigación de Antecedentes",
                    size=8,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=1,
            expand=True,
        )
    )

    audit_section = ft.Column(
        [ft.Divider(height=10), summary_view, ft.Divider(height=10), audit_view],
        spacing=5,
        visible=False,
    )
    export_section = ft.Column(
        [
            ft.Divider(),
            ft.Row(
                [
                    ft.Text("📤 Exportación", size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Un solo Excel con todos los resultados terminados.",
                        size=9,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(expand=True),
                    export_button,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=20),
        ],
        spacing=4,
        visible=False,
    )

    app_content = ft.Column(
        [
            ft.Row(header, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=8),
            ft.Row(
                [
                    ft.Text(
                        "📄 Extractor de Movimientos Financieros",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        ft.Text(
                            f"Versión {APP_VERSION}",
                            size=9,
                            weight=ft.FontWeight.BOLD,
                        ),
                        bgcolor=GOB_GOLD_LIGHT,
                        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                        border_radius=12,
                    ),
                    settings_badge,
                    config_button,
                    help_button,
                ],
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(
                ft.Row(
                    [
                        upload_button,
                        loading_ring,
                        ft.Text("⏱", size=13),
                        timer_text,
                        ft.Container(width=6),
                        status_text,
                    ],
                    spacing=7,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=8),
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
