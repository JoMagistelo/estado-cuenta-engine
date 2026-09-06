from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from engine.ocr_fallback_policy import normalize_ocr_engine
from engine.pipeline import process_bank_statements_incremental
from exporters.excel import export_batch_excel
from exporters.excel.batch_exporter import pending_ocr_selection_files

APP_VERSION = '2.4'
PROCESSING_UI_POLL_INTERVAL = 0.2
TIMER_REFRESH_SECONDS = 1.0
MOVEMENT_PAGE_SIZE = 60
SELECTOR_ENGINE_WIDTH = 150
SELECTOR_STATUS_WIDTH = 54
SELECTOR_TIME_WIDTH = 64
SELECTOR_VALIDATION_WIDTH = 58

GOB_GREEN = '#1F4D3A'
GOB_GREEN_DARK = '#163A2C'
GOB_GREEN_LIGHT = '#E8F0EC'
GOB_GOLD = '#B08D57'
GOB_GOLD_LIGHT = '#F4EEE5'
GOB_CREAM = '#F7F4EE'
ROW_ALT = '#FAFAF8'
BUTTON_TEXT = '#FFFFFF'
DANGER = '#A63D40'

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / 'assets' / 'logo_gobierno_mexico.png'
PRIMARY_VALIDATIONS = ('Total depósitos / abonos', 'Total retiros / cargos')
MOVEMENT_COLUMNS: list[tuple[str, str, int]] = [
    ('fecha_corte', 'Fecha Corte', 92),
    ('numero_cuenta', 'Número de Cuenta', 118),
    ('numero_movimiento', 'No. Mov.', 70),
    ('fecha_operacion', 'Fecha Operación', 98),
    ('fecha_liquidacion', 'Fecha Liquidación', 100),
    ('concepto', 'Concepto', 220),
    ('cargo', 'Cargo', 98),
    ('abono', 'Abono', 98),
    ('saldo_operacion', 'Saldo Operación', 110),
    ('saldo_liquidacion', 'Saldo Liquidación', 110),
    ('tipo_operacion', 'Tipo', 118),
    ('beneficiario', 'Beneficiario', 175),
    ('cuenta_beneficiario', 'Cuenta Benef.', 145),
    ('clabe_beneficiario', 'CLABE Benef.', 155),
    ('rfc', 'RFC', 125),
    ('referencia', 'Referencia', 140),
    ('clave_rastreo', 'Clave Rastreo', 165),
    ('autorizacion', 'Autorización', 125),
    ('hora_operacion', 'Hora', 78),
    ('__bank__', 'Banco', 95),
    ('caja', 'Caja', 72),
    ('concepto_original', 'Concepto Original', 230),
]
MONEY_MOVEMENT_FIELDS = {'cargo', 'abono', 'saldo_operacion', 'saldo_liquidacion'}
FINAL_STATUSES = {'completed', 'error', 'cancelled'}


def safe_value(value: Any) -> str:
    return 'N/A' if value is None or value == '' else str(value)


def format_money(value: Any) -> str:
    if value is None:
        return 'N/A'
    try:
        return f'${float(value):,.2f}'
    except (TypeError, ValueError):
        return str(value)


def format_optional_float(
    value: Any,
    *,
    suffix: str = '',
    prefix: str = '',
    na_value: str = 'N/A',
) -> str:
    if value is None:
        return na_value
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f'{prefix}{numeric_value:,.2f}{suffix}'


def engine_label(engine: str | None) -> str:
    normalized = normalize_ocr_engine(engine, default='')
    return {'tesseract': 'Tesseract', 'paddleocr': 'PaddleOCR'}.get(normalized, 'OCR')


def format_elapsed(seconds: float) -> str:
    seconds = max(int(seconds or 0), 0)
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def format_seconds(seconds: Any) -> str:
    if seconds is None:
        return '—'
    try:
        value = max(float(seconds), 0.0)
    except (TypeError, ValueError):
        return '—'
    return f'{value:.1f} s'


def numeric(value: Any) -> float:
    try:
        return max(float(value or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def main(page: ft.Page):
    page.title = 'Extractor de Movimientos Financieros'
    page.window.width = 1180
    page.window.height = 660
    page.window.min_width = 920
    page.window.min_height = 560
    page.window.maximized = True
    page.window.prevent_close = True
    page.padding = 14
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    results: list[Any] = []
    processing_items: list[dict[str, Any]] = []
    event_queue: Queue = Queue()
    selector_rows: dict[int, ft.Container] = {}
    settings = {
        'ocr_primary_engine': normalize_ocr_engine(
            os.getenv('OCR_PRIMARY_ENGINE', 'tesseract')
        )
    }
    state: dict[str, Any] = {
        'running': False,
        'batch_id': 0,
        'started_at': None,
        'elapsed_seconds': 0.0,
        'selected_index': None,
        'last_timer_refresh': 0.0,
        'cancel_event': threading.Event(),
        'stop_requested': False,
        'loading_dialog_open': False,
        'close_dialog_open': False,
        'close_after_stop': False,
    }

    status_text = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    timer_text = ft.Text('00:00', size=11, weight=ft.FontWeight.BOLD)
    loading_ring = ft.ProgressRing(width=18, height=18, visible=False)
    audit_view = ft.Column(spacing=9)
    digital_groups_view = ft.Column(
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
    ocr_groups_view = ft.Column(
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
    classifying_view = ft.Column(spacing=3, height=62, scroll=ft.ScrollMode.AUTO)
    classifying_shell = ft.Container(
        content=classifying_view,
        padding=6,
        bgcolor=GOB_CREAM,
        border_radius=7,
        visible=False,
    )
    selector_filter = ft.TextField(
        hint_text='Filtrar PDF, banco o estado',
        width=420,
        height=38,
        text_size=11,
        prefix_icon=ft.Icons.SEARCH,
    )
    export_button = ft.FilledButton(
        content='Generar Excel',
        icon=ft.Icons.DOWNLOAD,
        disabled=True,
        bgcolor=GOB_GOLD,
        color=BUTTON_TEXT,
    )
    stop_button = ft.OutlinedButton(
        content='Detener',
        icon=ft.Icons.STOP_CIRCLE,
        visible=False,
        disabled=False,
        icon_color=DANGER,
    )

    def validation(result, name: str):
        if result is None:
            return None
        for item in getattr(result, 'validaciones', []) or []:
            if item.nombre == name:
                return item
        return None

    def validation_symbol(item) -> str:
        return '—' if item is None else '✅' if item.correcto else '❌'

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

    def process_label(item: dict[str, Any]) -> str:
        method = item.get('processing_method')
        result = item.get('result')
        if method == 'Digital':
            return 'Digital'
        if method == 'OCR':
            if result is None:
                requested = item.get('requested_ocr_engine') or settings['ocr_primary_engine']
                return engine_label(requested)

            requested = getattr(result, 'ocr_requested_primary_engine', None)
            primary = getattr(result, 'ocr_primary_engine', None)
            secondary = getattr(result, 'ocr_secondary_engine', None)
            if requested and primary and requested != primary:
                return f'{engine_label(requested)} ↯ {engine_label(primary)}'

            if getattr(result, 'fallback_attempted', False) and secondary:
                available = set(result.available_ocr_engines())
                marker = '✓' if secondary in available else '⚠'
                return f'{engine_label(primary)} → {engine_label(secondary)} {marker}'

            return engine_label(getattr(result, 'ocr_engine', None) or primary)
        return 'Detectando'

    def bank_key_for_item(item: dict[str, Any]) -> str:
        result = item.get('result')
        if result is None:
            status = item.get('status')
            if status == 'processing':
                return 'PROCESANDO'
            if status == 'error':
                return 'ERROR'
            if status == 'cancelled':
                return 'CANCELADO'
            return 'PENDIENTE'
        return str(getattr(result, 'bank_key', 'desconocido') or 'desconocido').upper()

    def status_text_for_item(item: dict[str, Any]) -> str:
        return {
            'classifying': 'Detectando tipo',
            'processing': 'Procesando',
            'completed': 'Terminado',
            'error': 'Error',
            'cancelled': 'Cancelado',
        }.get(str(item.get('status')), 'Pendiente')

    def status_control(item: dict[str, Any]) -> ft.Control:
        status = item.get('status')
        if status in {'classifying', 'processing'}:
            return ft.ProgressRing(width=13, height=13)
        if status == 'completed':
            return ft.Icon(ft.Icons.CHECK_CIRCLE, size=15, color=ft.Colors.GREEN)
        if status == 'error':
            return ft.Icon(ft.Icons.ERROR_OUTLINE, size=15, color=ft.Colors.RED)
        if status == 'cancelled':
            return ft.Icon(ft.Icons.BLOCK, size=15, color=ft.Colors.ON_SURFACE_VARIANT)
        return ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=15)

    def item_matches_filter(item: dict[str, Any]) -> bool:
        query = (selector_filter.value or '').strip().lower()
        if not query:
            return True
        haystack = ' '.join(
            [
                str(item.get('file_name') or ''),
                process_label(item),
                bank_key_for_item(item),
                status_text_for_item(item),
                str(item.get('error') or ''),
            ]
        ).lower()
        return query in haystack

    def selector_row_content(index: int, item: dict[str, Any]) -> ft.Row:
        result = item.get('result')
        abonos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))
        cargos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))
        elapsed = format_seconds(item.get('elapsed_seconds'))
        return ft.Row(
            [
                ft.Container(
                    ft.Text(
                        item.get('file_name', ''),
                        size=9,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    expand=True,
                ),
                ft.Container(
                    ft.Text(process_label(item), size=8, weight=ft.FontWeight.W_500),
                    width=SELECTOR_ENGINE_WIDTH,
                    alignment=ft.Alignment.CENTER_LEFT,
                ),
                ft.Container(
                    status_control(item),
                    width=SELECTOR_STATUS_WIDTH,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    ft.Text(elapsed, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                    width=SELECTOR_TIME_WIDTH,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    ft.Text(abonos, size=10),
                    width=SELECTOR_VALIDATION_WIDTH,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    ft.Text(cargos, size=10),
                    width=SELECTOR_VALIDATION_WIDTH,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            spacing=4,
        )

    def make_selector_row(index: int, item: dict[str, Any]) -> ft.Container:
        selected = state.get('selected_index') == index
        completed = item.get('status') == 'completed' and item.get('result') is not None
        row = ft.Container(
            content=selector_row_content(index, item),
            padding=ft.Padding.symmetric(horizontal=7, vertical=5),
            border=ft.Border.all(1, GOB_GREEN if selected else ft.Colors.OUTLINE_VARIANT),
            bgcolor=GOB_GREEN_LIGHT if selected else None,
            border_radius=6,
            on_click=(lambda e, i=index: select_item(i)) if completed else None,
        )
        selector_rows[index] = row
        return row

    def panel_header(title: str) -> ft.Container:
        def heading(text: str, width: int) -> ft.Container:
            return ft.Container(
                ft.Text(
                    text,
                    size=8,
                    weight=ft.FontWeight.W_600,
                    color=GOB_GREEN_DARK,
                    text_align=ft.TextAlign.CENTER,
                ),
                width=width,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            ft.Row(
                [
                    ft.Text(title, size=11, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    heading('Motor', SELECTOR_ENGINE_WIDTH),
                    heading('Estado', SELECTOR_STATUS_WIDTH),
                    heading('Tiempo', SELECTOR_TIME_WIDTH),
                    heading('Abonos', SELECTOR_VALIDATION_WIDTH),
                    heading('Cargos', SELECTOR_VALIDATION_WIDTH),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=7, vertical=5),
            bgcolor=GOB_GOLD_LIGHT,
            border_radius=6,
        )

    def selector_panel(title: str, groups_view: ft.Column) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    panel_header(title),
                    ft.Container(content=groups_view, expand=True),
                ],
                spacing=4,
                expand=True,
            ),
            height=260,
            padding=6,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            expand=True,
        )


    def rebuild_selector(*, update: bool = True) -> None:
        selector_rows.clear()
        digital_groups_view.controls.clear()
        ocr_groups_view.controls.clear()
        classifying_view.controls.clear()

        visible_items = [
            (index, item)
            for index, item in enumerate(processing_items)
            if item_matches_filter(item)
        ]
        unclassified = [
            (index, item)
            for index, item in visible_items
            if item.get('processing_method') not in {'Digital', 'OCR'}
        ]
        if unclassified:
            for _index, item in unclassified:
                icon: ft.Control
                if item.get('status') == 'error':
                    icon = ft.Icon(ft.Icons.ERROR_OUTLINE, size=14, color=ft.Colors.RED)
                elif item.get('status') == 'cancelled':
                    icon = ft.Icon(ft.Icons.BLOCK, size=14)
                else:
                    icon = ft.ProgressRing(width=12, height=12)
                classifying_view.controls.append(
                    ft.Row(
                        [
                            icon,
                            ft.Text(
                                item.get('file_name', ''),
                                size=8,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Container(expand=True),
                            ft.Text(status_text_for_item(item), size=8),
                        ],
                        spacing=6,
                    )
                )
        classifying_shell.visible = bool(unclassified)

        for method, groups_view in (
            ('Digital', digital_groups_view),
            ('OCR', ocr_groups_view),
        ):
            method_items = [
                (index, item)
                for index, item in visible_items
                if item.get('processing_method') == method
            ]
            grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
            for index, item in method_items:
                grouped.setdefault(bank_key_for_item(item), []).append((index, item))
            for bank in sorted(grouped):
                rows_view = ft.Column(spacing=3)
                for index, item in grouped[bank]:
                    rows_view.controls.append(make_selector_row(index, item))
                group_control = ft.Container(
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
                                        ft.Text(f'{len(grouped[bank])} archivo(s)', size=8),
                                    ]
                                ),
                                bgcolor=GOB_CREAM,
                                padding=ft.Padding.symmetric(horizontal=7, vertical=4),
                                border_radius=5,
                            ),
                            rows_view,
                        ],
                        spacing=3,
                    ),
                    padding=4,
                )
                groups_view.controls.append(group_control)
            if not grouped:
                groups_view.controls.append(
                    ft.Text('Sin archivos en este filtro.', size=8, color=ft.Colors.ON_SURFACE_VARIANT)
                )

        if update:
            for control in (
                digital_groups_view,
                ocr_groups_view,
                classifying_shell,
            ):
                try:
                    control.update()
                except Exception:
                    pass

    def show_result_loading(file_name: str) -> None:
        audit_view.controls[:] = [
            ft.Container(
                ft.Row(
                    [
                        ft.ProgressRing(width=18, height=18),
                        ft.Text(f'Cargando vista de {file_name}...', size=9),
                    ],
                    spacing=8,
                ),
                padding=10,
                bgcolor=GOB_CREAM,
                border_radius=7,
            )
        ]
        try:
            audit_view.update()
        except Exception:
            pass

    def select_item(index: int):
        if not 0 <= index < len(processing_items):
            return
        item = processing_items[index]
        result = item.get('result')
        if item.get('status') != 'completed' or result is None:
            return
        if state.get('selected_index') == index:
            return
        state['selected_index'] = index
        show_result_loading(item.get('file_name', ''))
        rebuild_selector()
        render_result(result)

    selector_filter.on_change = lambda e: rebuild_selector()

    def update_status(*, direct_update: bool = True):
        total = len(processing_items)
        completed = sum(item.get('status') == 'completed' for item in processing_items)
        errors = sum(item.get('status') == 'error' for item in processing_items)
        cancelled = sum(item.get('status') == 'cancelled' for item in processing_items)
        active_or_pending = total - completed - errors - cancelled
        scanned_active = sum(
            item.get('status') == 'processing' and item.get('processing_method') == 'OCR'
            for item in processing_items
        )
        if state['stop_requested'] and active_or_pending > 0:
            status_text.value = f'Deteniendo · {completed} resultado(s) conservado(s)'
            if scanned_active:
                status_text.value += ' · finalizando OCR ya iniciado'
            status_text.color = DANGER
        elif active_or_pending > 0:
            status_text.value = f'Procesando {completed} de {total} archivos'
            if scanned_active:
                status_text.value += f' · {scanned_active} escaneado(s) en OCR'
            if errors:
                status_text.value += f' · {errors} con error'
            status_text.color = ft.Colors.ON_SURFACE
        elif total and state['stop_requested']:
            status_text.value = f'⏹ Detenido · {completed} resultado(s) conservado(s)'
            if cancelled:
                status_text.value += f' · {cancelled} omitido(s)'
            status_text.color = DANGER
        elif total and errors == 0:
            status_text.value = f'✅ {completed} archivos procesados correctamente'
            status_text.color = ft.Colors.GREEN
        elif completed:
            status_text.value = f'✅ {completed} correctos · ⚠️ {errors} con error'
            status_text.color = ft.Colors.ERROR
        elif errors:
            status_text.value = f'❌ No fue posible procesar {errors} archivos'
            status_text.color = ft.Colors.RED
        if direct_update:
            try:
                status_text.update()
            except Exception:
                pass

    def movement_value(
        movement,
        field_name: str,
        index: int,
        fecha_corte_documento: str | None,
        numero_cuenta_documento: str | None,
        bank_key: str,
    ) -> Any:
        if field_name == 'fecha_corte':
            return fecha_corte_documento
        if field_name == 'numero_cuenta':
            return numero_cuenta_documento
        if field_name == 'numero_movimiento':
            return index
        if field_name == '__bank__':
            return bank_key.upper()
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
            height=38,
            padding=ft.Padding.symmetric(horizontal=5, vertical=4),
            alignment=ft.Alignment.CENTER_LEFT,
            border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

    def movements_table(
        movements,
        *,
        fecha_corte_documento: str | None = None,
        numero_cuenta_documento: str | None = None,
        bank_key: str = '',
    ) -> ft.Control:
        total_width = sum(width for _, _, width in MOVEMENT_COLUMNS)
        header = ft.Row(
            [movement_cell(name, label, width, header=True) for name, label, width in MOVEMENT_COLUMNS],
            spacing=0,
        )
        body = ft.Column(spacing=0, height=292, scroll=ft.ScrollMode.AUTO)
        filter_field = ft.TextField(
            hint_text='Filtrar movimientos',
            width=245,
            height=38,
            text_size=11,
            prefix_icon=ft.Icons.SEARCH,
        )
        cargo_total_text = ft.Text('$0.00', size=10, weight=ft.FontWeight.BOLD)
        abono_total_text = ft.Text('$0.00', size=10, weight=ft.FontWeight.BOLD)
        page_label = ft.Text('', size=8, color=ft.Colors.ON_SURFACE_VARIANT)
        previous_button = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip='Página anterior')
        next_button = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='Página siguiente')
        page_state = {'page': 0}

        def total_chip(label: str, value_control: ft.Text, *, accent: str) -> ft.Container:
            return ft.Container(
                ft.Row(
                    [
                        ft.Text(label, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                        value_control,
                    ],
                    spacing=5,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                bgcolor=GOB_CREAM,
                border=ft.Border.only(left=ft.BorderSide(3, accent)),
                border_radius=6,
            )

        cargo_chip = total_chip('Cargos', cargo_total_text, accent=GOB_GOLD)
        abono_chip = total_chip('Abonos', abono_total_text, accent=GOB_GREEN)

        def searchable_text(original_index: int, movement) -> str:
            values: list[str] = []
            for field_name, _label, _width in MOVEMENT_COLUMNS:
                value = movement_value(
                    movement,
                    field_name,
                    original_index,
                    fecha_corte_documento,
                    numero_cuenta_documento,
                    bank_key,
                )
                values.append(safe_value(value))
            return ' '.join(values).lower()

        def filtered_entries() -> list[tuple[int, Any]]:
            query = (filter_field.value or '').strip().lower()
            entries = list(enumerate(movements, 1))
            if not query:
                return entries
            return [
                (original_index, movement)
                for original_index, movement in entries
                if query in searchable_text(original_index, movement)
            ]

        def rebuild_page(*, update: bool = True) -> None:
            entries = filtered_entries()
            cargo_total = sum(numeric(getattr(movement, 'cargo', 0.0)) for _, movement in entries)
            abono_total = sum(numeric(getattr(movement, 'abono', 0.0)) for _, movement in entries)
            cargo_total_text.value = format_money(cargo_total)
            abono_total_text.value = format_money(abono_total)

            total_pages = max(1, (len(entries) + MOVEMENT_PAGE_SIZE - 1) // MOVEMENT_PAGE_SIZE)
            page_state['page'] = min(page_state['page'], total_pages - 1)
            start = page_state['page'] * MOVEMENT_PAGE_SIZE
            chunk = entries[start:start + MOVEMENT_PAGE_SIZE]
            rows: list[ft.Control] = []
            for display_position, (original_index, movement) in enumerate(chunk, start=1):
                cells = []
                for field_name, _label, width in MOVEMENT_COLUMNS:
                    value = movement_value(
                        movement,
                        field_name,
                        original_index,
                        fecha_corte_documento,
                        numero_cuenta_documento,
                        bank_key,
                    )
                    cells.append(movement_cell(field_name, value, width))
                rows.append(
                    ft.Container(
                        ft.Row(cells, spacing=0),
                        bgcolor=ROW_ALT if display_position % 2 == 0 else None,
                        border=ft.Border.only(
                            bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
                        ),
                    )
                )
            body.controls = rows or [
                ft.Container(
                    ft.Text('Sin movimientos que coincidan con el filtro.', size=9),
                    padding=10,
                )
            ]
            first_visible = start + 1 if entries else 0
            last_visible = min(start + MOVEMENT_PAGE_SIZE, len(entries))
            page_label.value = (
                f'{first_visible}-{last_visible} de {len(entries)} · '
                f'Página {page_state["page"] + 1}/{total_pages}'
            )
            previous_button.disabled = page_state['page'] <= 0
            next_button.disabled = page_state['page'] >= total_pages - 1
            if update:
                for control in (
                    body,
                    cargo_total_text,
                    abono_total_text,
                    page_label,
                    previous_button,
                    next_button,
                ):
                    try:
                        control.update()
                    except Exception:
                        pass

        def previous_page(_):
            page_state['page'] = max(0, page_state['page'] - 1)
            rebuild_page()

        def next_page(_):
            page_state['page'] += 1
            rebuild_page()

        def filter_changed(_):
            page_state['page'] = 0
            rebuild_page()

        previous_button.on_click = previous_page
        next_button.on_click = next_page
        filter_field.on_change = filter_changed
        rebuild_page(update=False)

        table_surface = ft.Container(
            ft.Column([header, body], spacing=0),
            width=total_width,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        toolbar = ft.Row(
            [
                filter_field,
                ft.Text(
                    f'{len(movements)} movimiento(s)',
                    size=8,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(expand=True),
                cargo_chip,
                abono_chip,
                previous_button,
                page_label,
                next_button,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Column(
            [
                toolbar,
                ft.Container(
                    ft.Row([table_surface], scroll=ft.ScrollMode.ALWAYS, spacing=0),
                    padding=ft.Padding.only(bottom=3),
                ),
            ],
            spacing=4,
        )

    def validation_card(result, name: str, short_name: str) -> ft.Container:
        item = validation(result, name)
        if item is None:
            icon = '—'
            color = ft.Colors.ON_SURFACE_VARIANT
            detail = 'No se pudo calcular'
        elif item.correcto:
            icon = '✅'
            color = ft.Colors.GREEN
            detail = 'Conciliación correcta'
        else:
            icon = '❌'
            color = ft.Colors.RED
            detail = (
                f'Esperado {format_money(item.esperado)} · '
                f'Obtenido {format_money(item.obtenido)} · '
                f'Diferencia {format_money(item.diferencia)}'
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
        icon = '✅' if item.correcto else '❌'
        color = ft.Colors.GREEN if item.correcto else ft.Colors.RED
        detail = (
            f'Esperado: {format_money(item.esperado)} · '
            f'Obtenido: {format_money(item.obtenido)} · '
            f'Diferencia: {format_money(item.diferencia)}'
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
        if getattr(item, 'mensaje', None):
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
            chunk = entries[start:start + per_row]
            controls = [metric(title, value, compact=True) for title, value in chunk]
            while len(controls) < per_row:
                controls.append(ft.Container(expand=True))
            rows.append(ft.Row(controls, spacing=6))
        return rows

    def candidate_stats(candidate) -> str:
        return (
            f'{candidate.movement_count} mov. · '
            f'{candidate.validation_failed}/{candidate.validation_total} validaciones con falla'
        )

    def preview_ocr_candidate(result, engine: str):
        if engine == getattr(result, 'selected_ocr_engine', None):
            return
        try:
            result.preview_ocr_engine(engine)
        except Exception as ex:
            status_text.value = f'❌ No fue posible mostrar OCR: {ex}'
            status_text.color = ft.Colors.RED
            status_text.update()
            return
        rebuild_selector()
        render_result(result)

    def choose_ocr_candidate(result, engine: str):
        try:
            result.select_ocr_engine(engine)
        except Exception as ex:
            status_text.value = f'❌ No fue posible elegir OCR: {ex}'
            status_text.color = ft.Colors.RED
            status_text.update()
            return
        status_text.value = f'✅ {engine_label(engine)} elegido para {result.file_name}'
        status_text.color = GOB_GREEN
        rebuild_selector()
        render_result(result)

    def ocr_candidate_selector(result) -> ft.Control | None:
        review = getattr(result, 'ocr_review', None)
        if review is None:
            return None
        engines = list(getattr(result, 'available_ocr_engines')())
        if len(engines) < 2:
            return None
        active = result.selected_ocr_engine
        confirmed = result.confirmed_ocr_engine
        recommended = result.recommended_ocr_engine
        columns: list[ft.Control] = []
        for engine in engines:
            candidate = review.get_candidate(engine)
            is_active = engine == active
            is_confirmed = engine == confirmed
            badges: list[ft.Control] = []
            if is_active:
                badges.append(ft.Text('Vista actual', size=8, color=GOB_GREEN))
            if is_confirmed:
                badges.append(ft.Text('✓ Elegido para Excel', size=8, color=GOB_GREEN_DARK))
            columns.append(
                ft.Container(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(engine_label(engine), size=10, weight=ft.FontWeight.BOLD),
                                    ft.Container(expand=True),
                                    *badges,
                                ],
                                spacing=6,
                            ),
                            ft.Text(
                                candidate_stats(candidate),
                                size=8,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Row(
                                [
                                    ft.TextButton(
                                        content='Ver resultado',
                                        icon=ft.Icons.VISIBILITY_OUTLINED,
                                        disabled=is_active,
                                        on_click=lambda e, eng=engine: preview_ocr_candidate(result, eng),
                                    ),
                                    ft.OutlinedButton(
                                        content=(
                                            'Elegido para Excel'
                                            if is_confirmed
                                            else 'Elegir para Excel'
                                        ),
                                        icon=(
                                            ft.Icons.CHECK_CIRCLE
                                            if is_confirmed
                                            else ft.Icons.DONE
                                        ),
                                        disabled=is_confirmed,
                                        on_click=lambda e, eng=engine: choose_ocr_candidate(result, eng),
                                    ),
                                ],
                                spacing=5,
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=8,
                    border=ft.Border.all(
                        1, GOB_GREEN if is_confirmed else ft.Colors.OUTLINE_VARIANT
                    ),
                    bgcolor=GOB_GREEN_LIGHT if is_confirmed else None,
                    border_radius=7,
                    expand=True,
                )
            )

        guidance = (
            '⚠️ Debes elegir uno de los dos resultados antes de generar el Excel.'
            if confirmed is None
            else f'✓ Para exportación se conservará {engine_label(confirmed)}.'
        )
        return ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text('Comparación OCR', size=10, weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            ft.Text(
                                f'Sugerencia automática: {engine_label(recommended)}',
                                size=8,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ]
                    ),
                    ft.Text(
                        'Puedes revisar ambos motores. La sugerencia automática no se guarda por defecto: la elección para Excel siempre es manual.',
                        size=8,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Row(columns, spacing=7),
                    ft.Text(
                        guidance,
                        size=8,
                        weight=ft.FontWeight.W_600,
                        color=DANGER if confirmed is None else GOB_GREEN,
                    ),
                ],
                spacing=5,
            ),
            padding=8,
            bgcolor=GOB_CREAM,
            border_radius=7,
        )

    def ocr_execution_card(result) -> ft.Container:
        requested = getattr(result, 'ocr_requested_primary_engine', None)
        primary = getattr(result, 'ocr_primary_engine', None)
        secondary = getattr(result, 'ocr_secondary_engine', None)
        review = getattr(result, 'ocr_review', None)
        available = set(result.available_ocr_engines()) if review is not None else set()

        lines: list[ft.Control] = [
            ft.Text(
                f'Motor solicitado en Configuración: {engine_label(requested or primary)}',
                size=8,
                weight=ft.FontWeight.BOLD,
            )
        ]

        if requested and primary and requested != primary:
            lines.append(
                ft.Text(
                    f'{engine_label(requested)} no pudo iniciar; el PDF fue recuperado con {engine_label(primary)}.',
                    size=8,
                    color=DANGER,
                )
            )
        elif primary:
            lines.append(
                ft.Text(
                    f'Motor primario ejecutado: {engine_label(primary)}',
                    size=8,
                    color=GOB_GREEN,
                )
            )

        if getattr(result, 'fallback_attempted', False) and secondary:
            if secondary in available:
                lines.append(
                    ft.Text(
                        f'Fallback ejecutado: {engine_label(secondary)} · candidato disponible para revisión.',
                        size=8,
                        color=GOB_GREEN,
                        weight=ft.FontWeight.BOLD,
                    )
                )
            else:
                error_type = getattr(review, 'paddle_error_type', None) if review is not None else None
                suffix = f' · error {error_type}' if error_type else ''
                error_message = ''
                if review is not None and primary in available:
                    try:
                        primary_candidate = review.get_candidate(primary)
                        error_message = str(
                            (primary_candidate.document.metadata or {}).get(
                                'ocr_fallback_error_message',
                                '',
                            )
                            or ''
                        ).strip()
                    except Exception:
                        error_message = ''
                detail = f' · {error_message}' if error_message else ''
                lines.append(
                    ft.Text(
                        f'Fallback intentado: {engine_label(secondary)} · no produjo candidato{suffix}{detail}.',
                        size=8,
                        color=DANGER,
                        weight=ft.FontWeight.BOLD,
                    )
                )
        else:
            lines.append(
                ft.Text(
                    'Fallback: no requerido por las validaciones del motor principal.',
                    size=8,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        if len(available) > 1:
            lines.append(
                ft.Text(
                    'Hay dos resultados reales en memoria. Puedes alternarlos y elegir cuál se exportará.',
                    size=8,
                    color=GOB_GREEN_DARK,
                )
            )

        return ft.Container(
            ft.Column(lines, spacing=3, tight=True),
            padding=7,
            bgcolor=GOB_GREEN_LIGHT,
            border_radius=6,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )


    def beneficiary_analytics(
        movements,
    ) -> list[tuple[str, float, float, int, int]]:
        grouped: dict[str, list[float]] = {}
        for movement in movements:
            name = getattr(movement, 'beneficiario', None) or 'Sin beneficiario'
            values = grouped.setdefault(str(name), [0.0, 0.0, 0.0, 0.0])
            cargo = numeric(getattr(movement, 'cargo', 0.0))
            abono = numeric(getattr(movement, 'abono', 0.0))
            values[0] += cargo
            values[1] += abono
            if cargo > 0:
                values[2] += 1
            if abono > 0:
                values[3] += 1
        rows = [
            (name, values[0], values[1], int(values[2]), int(values[3]))
            for name, values in grouped.items()
        ]
        rows.sort(key=lambda item: item[1] + item[2], reverse=True)
        return rows[:8]

    def bank_analytics() -> list[tuple[str, float, float]]:
        grouped: dict[str, list[float]] = {}
        for result in results:
            bank = str(getattr(result, 'bank_key', 'N/A') or 'N/A').upper()
            values = grouped.setdefault(bank, [0.0, 0.0])
            estado = getattr(result, 'estado_cuenta', None)
            for movement in getattr(estado, 'movimientos', None) or []:
                values[0] += numeric(getattr(movement, 'cargo', 0.0))
                values[1] += numeric(getattr(movement, 'abono', 0.0))
        rows = [(bank, values[0], values[1]) for bank, values in grouped.items()]
        rows.sort(key=lambda item: item[1] + item[2], reverse=True)
        return rows[:8]

    def analytics_bar_card(
        title: str,
        rows: list[tuple],
        *,
        show_counts: bool = False,
    ) -> ft.Container:
        if not rows:
            return ft.Container(
                ft.Column(
                    [
                        ft.Text(title, size=10, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            'Sin datos suficientes',
                            size=8,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ]
                ),
                padding=9,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=7,
                expand=True,
            )
        maximum = max(max(float(row[1]), float(row[2])) for row in rows) or 1.0
        controls: list[ft.Control] = [
            ft.Text(title, size=10, weight=ft.FontWeight.BOLD),
            ft.Row(
                [
                    ft.Text('■ Cargos', size=8, color=GOB_GOLD),
                    ft.Text('■ Abonos', size=8, color=GOB_GREEN),
                ],
                spacing=12,
            ),
        ]
        for row in rows:
            label, cargo, abono = row[:3]
            cargo_count = int(row[3]) if len(row) > 3 else 0
            abono_count = int(row[4]) if len(row) > 4 else 0
            cargo_width = max(2, int(180 * cargo / maximum))
            abono_width = max(2, int(180 * abono / maximum))
            label_controls: list[ft.Control] = []
            if show_counts:
                label_controls.append(
                    ft.Container(
                        ft.Text(
                            f'C {cargo_count} · A {abono_count}',
                            size=7,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        width=58,
                    )
                )
            label_controls.append(
                ft.Text(
                    str(label),
                    size=8,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                )
            )
            controls.append(
                ft.Column(
                    [
                        ft.Row(label_controls, spacing=4),
                        ft.Row(
                            [
                                ft.Container(width=cargo_width, height=7, bgcolor=GOB_GOLD, border_radius=3),
                                ft.Text(format_money(cargo), size=7, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=5,
                        ),
                        ft.Row(
                            [
                                ft.Container(width=abono_width, height=7, bgcolor=GOB_GREEN, border_radius=3),
                                ft.Text(format_money(abono), size=7, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=5,
                        ),
                    ],
                    spacing=2,
                )
            )
        return ft.Container(
            ft.Column(controls, spacing=6),
            padding=9,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=7,
            expand=True,
        )

    def flow_frequency_card(movements) -> ft.Container:
        cargo_count = sum(numeric(getattr(movement, 'cargo', 0.0)) > 0 for movement in movements)
        abono_count = sum(numeric(getattr(movement, 'abono', 0.0)) > 0 for movement in movements)
        maximum = max(cargo_count, abono_count, 1)

        def flow_row(label: str, count: int, color: str):
            return ft.Row(
                [
                    ft.Text(label, size=8, width=55),
                    ft.Container(
                        width=max(3, int(240 * count / maximum)),
                        height=10,
                        bgcolor=color,
                        border_radius=4,
                    ),
                    ft.Text(str(count), size=8),
                ],
                spacing=6,
            )

        return ft.Container(
            ft.Column(
                [
                    ft.Text('Frecuencia de movimientos', size=10, weight=ft.FontWeight.BOLD),
                    flow_row('Cargos', cargo_count, GOB_GOLD),
                    flow_row('Abonos', abono_count, GOB_GREEN),
                    ft.Text(
                        f'Total: {len(movements)} movimiento(s)',
                        size=8,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=7,
            ),
            padding=9,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=7,
            expand=True,
        )

    def analytics_section(movements) -> ft.Control:
        beneficiary = analytics_bar_card(
            'Cargos y abonos por beneficiario · Top 8',
            beneficiary_analytics(movements),
            show_counts=True,
        )
        banks = analytics_bar_card(
            'Cargos y abonos por banco · lote procesado',
            bank_analytics(),
        )
        flow = flow_frequency_card(movements)
        return ft.Column(
            [
                section('📊 Análisis visual'),
                ft.Row([beneficiary, banks], spacing=7, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([flow], spacing=7),
            ],
            spacing=7,
        )

    def render_result(result):
        audit_view.controls.clear()
        if result is None:
            try:
                audit_view.update()
            except Exception:
                pass
            return
        estado = getattr(result, 'estado_cuenta', None)
        if estado is None:
            audit_view.controls.append(ft.Text('⚠️ Resultado sin estado de cuenta.'))
            audit_view.update()
            return
        dc = getattr(estado, 'datos_cuenta', None)
        rf = getattr(estado, 'resumen_financiero', None)
        op = getattr(estado, 'otros_productos', None)
        movements = getattr(estado, 'movimientos', None) or []
        method = getattr(result, 'processing_method', 'Digital')
        process_text = (
            'Digital' if method == 'Digital' else engine_label(getattr(result, 'ocr_engine', None))
        )
        audit_view.controls.extend(
            [
                ft.Row(
                    [
                        ft.Text(f'🔍 {result.file_name}', size=15, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(
                            f'{str(result.bank_key).upper()} · {process_text}',
                            size=9,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]
                ),
                ft.Row(
                    [
                        metric(
                            'Periodo',
                            f"{safe_value(getattr(dc, 'periodo_inicio', None))} al "
                            f"{safe_value(getattr(dc, 'periodo_fin', None))}",
                        ),
                        metric('Cliente', safe_value(getattr(dc, 'nombre_cliente', None))),
                        metric('Cuenta', safe_value(getattr(dc, 'numero_cuenta', None))),
                        metric('CLABE', safe_value(getattr(dc, 'clabe', None))),
                    ],
                    spacing=6,
                ),
            ]
        )
        if method == 'OCR':
            audit_view.controls.append(ocr_execution_card(result))
            candidate_selector = ocr_candidate_selector(result)
            if candidate_selector is not None:
                audit_view.controls.append(candidate_selector)

        audit_view.controls.extend(
            [
                ft.Row(
                    [
                        metric('Saldo anterior', format_money(getattr(rf, 'saldo_anterior', None))),
                        metric('Depósitos / Abonos', format_money(getattr(rf, 'depositos_abonos', None))),
                        metric('Retiros / Cargos', format_money(getattr(rf, 'retiros_cargos', None))),
                        metric('Saldo final', format_money(getattr(rf, 'saldo_final', None))),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        validation_card(result, PRIMARY_VALIDATIONS[0], 'Validación abonos'),
                        validation_card(result, PRIMARY_VALIDATIONS[1], 'Validación cargos'),
                    ],
                    spacing=6,
                ),
            ]
        )

        all_validations = list(getattr(result, 'validaciones', []) or [])
        secondary_validations = [
            item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS
        ]
        correct_count = sum(item.correcto for item in all_validations)
        audit_view.controls.append(
            ft.Text(
                f'Integridad financiera: {correct_count}/{len(all_validations)} validaciones correctas',
                size=8,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

        secondary_controls = (
            [secondary_validation_row(item) for item in secondary_validations]
            if secondary_validations
            else [ft.Text('No existen validaciones adicionales para este resultado.', size=8)]
        )
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    f'🔎 Otras validaciones financieras ({len(secondary_validations)})',
                    size=9,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[
                    ft.Container(
                        ft.Column(secondary_controls, spacing=5),
                        padding=6,
                    )
                ],
            )
        )

        account_entries = [
            ('Producto principal', safe_value(getattr(dc, 'producto_principal', None))),
            ('Periodo inicio', safe_value(getattr(dc, 'periodo_inicio', None))),
            ('Periodo fin', safe_value(getattr(dc, 'periodo_fin', None))),
            ('Fecha de corte', safe_value(getattr(dc, 'fecha_corte', None))),
            ('Número de cuenta', safe_value(getattr(dc, 'numero_cuenta', None))),
            ('Número de cliente', safe_value(getattr(dc, 'numero_cliente', None))),
            ('CLABE', safe_value(getattr(dc, 'clabe', None))),
            ('Nombre del cliente', safe_value(getattr(dc, 'nombre_cliente', None))),
            ('RFC', safe_value(getattr(dc, 'rfc', None))),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    '📌 Datos de la cuenta · todos los campos',
                    size=9,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Container(ft.Column(metrics_rows(account_entries, 3), spacing=6), padding=6)],
            )
        )

        summary_entries = [
            ('Saldo promedio', format_money(getattr(rf, 'saldo_promedio', None))),
            ('Días del periodo', safe_value(getattr(rf, 'dias_periodo', None))),
            ('Tasa bruta anual', format_optional_float(getattr(rf, 'tasa_bruta_anual', None), suffix='%')),
            ('Saldo promedio gravable', format_money(getattr(rf, 'saldo_promedio_gravable', None))),
            ('Intereses a favor', format_money(getattr(rf, 'intereses_a_favor', None))),
            ('ISR retenido', format_money(getattr(rf, 'isr_retenido', None))),
            ('Cheques pagados', safe_value(getattr(rf, 'cheques_pagados', None))),
            ('Manejo de cuenta', format_money(getattr(rf, 'manejo_cuenta', None))),
            ('Cargos objetados', format_money(getattr(rf, 'cargos_objetados', None))),
            ('Abonos objetados', format_money(getattr(rf, 'abonos_objetados', None))),
            (
                'Saldo promedio mínimo mensual',
                format_money(getattr(rf, 'saldo_promedio_minimo_mensual', None)),
            ),
            ('Saldo global', format_money(getattr(rf, 'saldo_global', None))),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    '📈 Detalle financiero · todos los campos',
                    size=9,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Container(ft.Column(metrics_rows(summary_entries, 4), spacing=6), padding=6)],
            )
        )
        other_entries = [
            ('Contrato', safe_value(getattr(op, 'contrato', None))),
            ('Producto', safe_value(getattr(op, 'producto', None))),
            ('Tasa interés anual', format_optional_float(getattr(op, 'tasa_interes_anual', None), suffix='%')),
            ('GAT nominal anual', format_optional_float(getattr(op, 'gat_nominal_anual', None), suffix='%')),
            ('GAT real anual', format_optional_float(getattr(op, 'gat_real_anual', None), suffix='%')),
            ('Total comisiones', format_optional_float(getattr(op, 'total_comisiones', None), prefix='$')),
        ]
        audit_view.controls.append(
            ft.ExpansionTile(
                title=ft.Text(
                    '💰 Otros productos y comisiones · todos los campos',
                    size=9,
                    weight=ft.FontWeight.BOLD,
                ),
                controls=[ft.Container(ft.Column(metrics_rows(other_entries, 3), spacing=6), padding=6)],
            )
        )
        audit_view.controls.append(section(f'📑 Movimientos ({len(movements)})'))
        if movements:
            audit_view.controls.append(
                movements_table(
                    movements,
                    fecha_corte_documento=getattr(dc, 'fecha_corte', None),
                    numero_cuenta_documento=getattr(dc, 'numero_cuenta', None),
                    bank_key=str(result.bank_key),
                )
            )
            audit_view.controls.append(analytics_section(movements))
        else:
            audit_view.controls.append(
                ft.Container(
                    ft.Text('⚠️ No se encontraron movimientos.', size=9),
                    padding=7,
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    border_radius=6,
                )
            )
        try:
            audit_view.update()
        except Exception:
            pass

    def show_settings(e=None):
        if state['running']:
            return
        current = settings['ocr_primary_engine']
        selector = ft.Dropdown(
            label='Motor OCR principal',
            value=current,
            width=300,
            options=[
                ft.DropdownOption(key='tesseract', text='Tesseract'),
                ft.DropdownOption(key='paddleocr', text='PaddleOCR'),
            ],
        )

        def save(_):
            settings['ocr_primary_engine'] = normalize_ocr_engine(selector.value)
            page.pop_dialog()
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text('Configuración', weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    selector,
                    ft.Text(
                        'El motor principal sólo define el orden de procesamiento OCR. Si se ejecutan ambos motores, la elección del resultado que se exporta siempre la hace el usuario.',
                        size=9,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        'El segundo motor se ejecuta si el resultado principal tiene cualquier validación con tache, faltan validaciones clave o no se detectan movimientos.',
                        size=8,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.TextButton(content='Cancelar', on_click=lambda ev: page.pop_dialog()),
                ft.FilledButton(content='Guardar', bgcolor=GOB_GREEN, color=BUTTON_TEXT, on_click=save),
            ],
        )
        page.show_dialog(dialog)

    def show_help(e=None):
        dialog = ft.AlertDialog(
            modal=False,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=GOB_GREEN, size=22),
                    ft.Text('Ayuda', weight=ft.FontWeight.BOLD, size=15),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text('Validaciones financieras', size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        'Las columnas Abonos y Cargos muestran de forma explícita el resultado de las dos conciliaciones principales.',
                        size=9,
                    ),
                    ft.Divider(),
                    ft.Text('Selección OCR', size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        'Cuando existen resultados de Tesseract y PaddleOCR puedes revisar ambos. Ninguno queda elegido para el Excel hasta que pulses “Elegir para Excel”.',
                        size=9,
                    ),
                    ft.Divider(),
                    ft.Text('Estados durante el procesamiento', size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        'Los PDFs aparecen en cuanto se clasifica su tipo. Coloca el cursor sobre la lista Digital u OCR y usa la rueda del mouse para recorrerla.',
                        size=9,
                    ),
                    ft.Divider(),
                    ft.Text('Bancos y estados de cuenta habilitados', size=11, weight=ft.FontWeight.BOLD, color=GOB_GREEN),
                    ft.Text(
                        'BBVA Digital · Banorte Digital/Escaneado · Banamex Digital · HSBC Digital/Escaneado · Scotiabank Digital · Mifel · CETESDIRECTO · MercadoPago',
                        size=9,
                    ),
                ],
                spacing=7,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                height=360,
            ),
            actions=[ft.TextButton(content='Cerrar', on_click=lambda ev: page.pop_dialog())],
        )
        page.show_dialog(dialog)

    def close_loading_dialog():
        if not state['loading_dialog_open']:
            return
        state['loading_dialog_open'] = False
        try:
            page.pop_dialog()
            page.update()
        except Exception:
            pass

    def request_stop(_=None, *, close_after: bool = False):
        if not state['running'] or state['stop_requested']:
            return
        state['stop_requested'] = True
        state['close_after_stop'] = state['close_after_stop'] or close_after
        state['cancel_event'].set()
        stop_button.disabled = True
        try:
            stop_button.update()
        except Exception:
            pass
        update_status()
        rebuild_selector()
        close_loading_dialog()

    stop_button.on_click = request_stop

    def show_loading_dialog():
        logo = (
            ft.Image(src=str(LOGO_PATH), width=120, height=55, fit=ft.BoxFit.CONTAIN)
            if LOGO_PATH.exists()
            else ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=38, color=GOB_GREEN)
        )
        dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text('Procesando estados de cuenta', weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Row(
                        [logo, ft.ProgressRing(width=26, height=26)],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        'Los PDFs aparecerán en Resultados disponibles en cuanto se clasifique su tipo. Puedes cerrar esta ventana y revisar los resultados mientras continúa el lote.',
                        size=9,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton(
                    content='Ver procesamiento',
                    on_click=lambda ev: close_loading_dialog(),
                ),
                ft.OutlinedButton(
                    content='Detener',
                    icon=ft.Icons.STOP_CIRCLE,
                    icon_color=DANGER,
                    on_click=lambda ev: request_stop(ev),
                ),
            ],
        )
        state['loading_dialog_open'] = True
        page.show_dialog(dialog)

    async def close_window_after_finish():
        page.window.prevent_close = False
        await page.window.close()

    def show_close_guard():
        if state['close_dialog_open']:
            return
        state['close_dialog_open'] = True

        def keep_working(_):
            state['close_dialog_open'] = False
            page.pop_dialog()
            page.update()

        def stop_and_close(_):
            state['close_dialog_open'] = False
            page.pop_dialog()
            request_stop(close_after=True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text('Procesamiento en curso'),
            content=ft.Text(
                'Para proteger los resultados ya obtenidos, la aplicación no se cerrará mientras el lote está trabajando.',
                size=10,
            ),
            actions=[
                ft.TextButton(content='Seguir trabajando', on_click=keep_working),
                ft.OutlinedButton(content='Detener y cerrar', on_click=stop_and_close),
            ],
        )
        page.show_dialog(dialog)

    async def on_window_event(e):
        if e.type != ft.WindowEventType.CLOSE:
            return
        if state['running']:
            show_close_guard()
            return
        page.window.prevent_close = False
        await page.window.close()

    page.window.on_event = on_window_event

    def processing_worker(
        paths: list[str],
        names: list[str],
        batch_id: int,
        primary_engine: str,
        cancel_event: threading.Event,
    ):
        try:
            for event in process_bank_statements_incremental(
                paths,
                names,
                ocr_primary_engine=primary_engine,
                cancel_event=cancel_event,
            ):
                event_queue.put(('event', batch_id, event))
        except Exception as ex:
            event_queue.put(('worker_error', batch_id, ex, traceback.format_exc()))
        finally:
            event_queue.put(('finished', batch_id))

    def finalize_item_duration(item: dict[str, Any]) -> None:
        started_at = item.get('processing_started_at')
        if isinstance(started_at, (int, float)):
            item['elapsed_seconds'] = max(time.perf_counter() - started_at, 0.0)

    def handle_event(event):
        index = getattr(event, 'index', None)
        if not isinstance(index, int) or not 0 <= index < len(processing_items):
            return
        item = processing_items[index]
        if event.kind == 'started':
            item.update(
                status='processing',
                processing_method=event.processing_method,
                processing_started_at=time.perf_counter(),
                elapsed_seconds=None,
                error=None,
            )
            rebuild_selector()
            return
        if event.kind == 'cancelled':
            finalize_item_duration(item)
            item.update(
                status='cancelled',
                processing_method=event.processing_method or item.get('processing_method'),
                result=None,
                error=None,
            )
            rebuild_selector()
            return
        if event.kind == 'completed':
            finalize_item_duration(item)
            item.update(
                status='completed',
                processing_method=event.processing_method,
                result=event.result,
                error=None,
            )
            if event.result is not None:
                results.append(event.result)
                export_button.disabled = False
                try:
                    export_button.update()
                except Exception:
                    pass
                first_result = state['selected_index'] is None
                if first_result:
                    state['selected_index'] = index
                rebuild_selector()
                if first_result:
                    render_result(event.result)
                close_loading_dialog()
            else:
                rebuild_selector()
            return
        if event.kind == 'error':
            finalize_item_duration(item)
            item.update(
                status='error',
                processing_method=event.processing_method or item.get('processing_method'),
                result=None,
                error=str(event.error or 'Error desconocido'),
            )
            rebuild_selector()

    def finish_controls():
        if state['stop_requested']:
            for item in processing_items:
                if item.get('status') not in FINAL_STATUSES:
                    item.update(status='cancelled', result=None, error=None)
        state['running'] = False
        if state['started_at'] is not None:
            state['elapsed_seconds'] = time.perf_counter() - state['started_at']
        timer_text.value = format_elapsed(state['elapsed_seconds'])
        loading_ring.visible = False
        upload_button.disabled = False
        config_button.disabled = False
        help_button.disabled = False
        stop_button.visible = False
        stop_button.disabled = False
        close_loading_dialog()
        rebuild_selector()
        for control in (
            timer_text,
            loading_ring,
            upload_button,
            config_button,
            help_button,
            stop_button,
        ):
            try:
                control.update()
            except Exception:
                pass
        if state['close_after_stop']:
            page.run_task(close_window_after_finish)

    async def poller():
        while True:
            try:
                while True:
                    message = event_queue.get_nowait()
                    kind, batch_id = message[0], message[1]
                    if batch_id != state['batch_id']:
                        continue
                    if kind == 'event':
                        handle_event(message[2])
                        update_status()
                    elif kind == 'worker_error':
                        ex, tb = message[2], message[3]
                        for item in processing_items:
                            if item.get('status') not in FINAL_STATUSES:
                                item.update(status='error', error=str(ex))
                        status_text.value = f'❌ Error de procesamiento: {ex}'
                        status_text.color = ft.Colors.RED
                        try:
                            status_text.update()
                        except Exception:
                            pass
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
                        try:
                            audit_view.update()
                        except Exception:
                            pass
                        rebuild_selector()
                        finish_controls()
                    elif kind == 'finished':
                        finish_controls()
                        update_status()
            except Empty:
                pass
            except Exception as ex:
                status_text.value = f'❌ Error actualizando interfaz: {ex}'
                status_text.color = ft.Colors.RED
                try:
                    status_text.update()
                except Exception:
                    pass

            now = time.perf_counter()
            if (
                state['running']
                and state['started_at'] is not None
                and now - state['last_timer_refresh'] >= TIMER_REFRESH_SECONDS
            ):
                state['last_timer_refresh'] = now
                state['elapsed_seconds'] = now - state['started_at']
                timer_text.value = format_elapsed(state['elapsed_seconds'])
                try:
                    timer_text.update()
                except Exception:
                    return
            await asyncio.sleep(PROCESSING_UI_POLL_INTERVAL)

    def initialize_batch(paths: list[str], names: list[str]):
        state['batch_id'] += 1
        state['running'] = True
        state['started_at'] = time.perf_counter()
        state['elapsed_seconds'] = 0.0
        state['selected_index'] = None
        state['last_timer_refresh'] = 0.0
        state['cancel_event'] = threading.Event()
        state['stop_requested'] = False
        state['close_after_stop'] = False
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
                    'file_name': name,
                    'processing_method': None,
                    'status': 'classifying',
                    'result': None,
                    'error': None,
                    'requested_ocr_engine': settings['ocr_primary_engine'],
                    'processing_started_at': None,
                    'elapsed_seconds': None,
                }
            )
        selector_filter.value = ''
        loading_ring.visible = True
        upload_button.disabled = True
        config_button.disabled = True
        help_button.disabled = False
        stop_button.visible = True
        stop_button.disabled = False
        export_button.disabled = True
        audit_view.controls.clear()
        status_text.value = 'Preparando estados de cuenta...'
        status_text.color = ft.Colors.ON_SURFACE
        timer_text.value = '00:00'
        audit_section.visible = True
        export_section.visible = True
        rebuild_selector(update=False)
        page.update()
        show_loading_dialog()

    def start_worker(paths: list[str], names: list[str]):
        page.run_thread(
            processing_worker,
            paths,
            names,
            state['batch_id'],
            settings['ocr_primary_engine'],
            state['cancel_event'],
        )

    async def pick_files(e):
        try:
            selected = await ft.FilePicker().pick_files(
                dialog_title='Selecciona estados de cuenta PDF',
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=['pdf'],
            )
            if not selected:
                return
            paths = [file.path for file in selected if file.path]
            names = [file.name for file in selected if file.path]
            if not paths:
                status_text.value = '❌ No fue posible obtener las rutas de los PDFs.'
                status_text.color = ft.Colors.RED
                status_text.update()
                return
            initialize_batch(paths, names)
            start_worker(paths, names)
        except Exception as ex:
            status_text.value = f'❌ Error al seleccionar archivos: {ex}'
            status_text.color = ft.Colors.RED
            try:
                status_text.update()
            except Exception:
                page.update()

    async def export_excel(e):
        if not results:
            return
        pending = pending_ocr_selection_files(list(results))
        if pending:
            status_text.value = (
                f'⚠️ Falta elegir Tesseract o PaddleOCR para {len(pending)} archivo(s) antes de exportar.'
            )
            status_text.color = DANGER
            first_pending = pending[0]
            pending_index = next(
                (
                    index
                    for index, item in enumerate(processing_items)
                    if item.get('file_name') == first_pending and item.get('result') is not None
                ),
                None,
            )
            if isinstance(pending_index, int):
                state['selected_index'] = pending_index
                rebuild_selector()
                render_result(processing_items[pending_index]['result'])
            try:
                status_text.update()
            except Exception:
                page.update()
            return

        path = await ft.FilePicker().save_file(
            dialog_title='Guardar reporte Excel',
            file_name='reporte_estados_de_cuenta.xlsx',
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['xlsx'],
        )
        if not path:
            return
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'
        snapshot = list(results)
        export_button.disabled = True
        status_text.value = 'Generando archivo Excel...'
        try:
            export_button.update()
            status_text.update()
        except Exception:
            page.update()

        def worker():
            try:
                export_batch_excel(snapshot, path)
                status_text.value = '✅ Archivo Excel exportado correctamente.'
                status_text.color = ft.Colors.GREEN
                try:
                    if sys.platform == 'win32':
                        subprocess.run(['explorer', '/select,', path])
                    elif sys.platform == 'darwin':
                        subprocess.run(['open', '-R', path])
                    else:
                        subprocess.run(['xdg-open', os.path.dirname(path)])
                except Exception:
                    pass
            except Exception as ex:
                status_text.value = f'❌ Error al exportar Excel: {ex}'
                status_text.color = ft.Colors.RED
            finally:
                export_button.disabled = False
                try:
                    export_button.update()
                    status_text.update()
                except Exception:
                    pass

        page.run_thread(worker)

    upload_button = ft.FilledButton(
        content='Seleccionar estados de cuenta PDF',
        icon=ft.Icons.UPLOAD_FILE,
        on_click=pick_files,
        bgcolor=GOB_GREEN,
        color=BUTTON_TEXT,
    )
    config_button = ft.IconButton(
        icon=ft.Icons.SETTINGS,
        tooltip='Configuración',
        icon_color=ft.Colors.ON_SURFACE_VARIANT,
        on_click=show_settings,
    )
    help_button = ft.IconButton(
        icon=ft.Icons.HELP_OUTLINE,
        tooltip='Ayuda',
        icon_color=ft.Colors.ON_SURFACE_VARIANT,
        on_click=show_help,
    )
    export_button.on_click = export_excel

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
                ft.Text('Secretaría Anticorrupción y Buen Gobierno', size=10, weight=ft.FontWeight.W_500),
                ft.Text('Dirección General de Evaluación de Confianza', size=9, weight=ft.FontWeight.W_500),
                ft.Text('Departamento de Investigación de Antecedentes', size=8, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=1,
            expand=True,
        )
    )

    results_selector = ft.Column(
        [
            ft.Row(
                [
                    ft.Text('Resultados disponibles', size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        'Los archivos aparecen mientras se procesan.',
                        size=8,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(expand=True),
                    selector_filter,
                    ],
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            classifying_shell,
            ft.Row(
                [
                    selector_panel('📄 PDFs digitales', digital_groups_view),
                    selector_panel('🖨️ PDFs escaneados (OCR)', ocr_groups_view),
                ],
                spacing=9,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        ],
        spacing=5,
    )
    audit_section = ft.Column(
        [ft.Divider(height=8), results_selector, ft.Divider(height=8), audit_view],
        spacing=4,
        visible=False,
    )
    export_section = ft.Column(
        [
            ft.Divider(),
            ft.Row(
                [
                    ft.Text('📤 Exportación', size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        'Incluye resultados terminados. Si un PDF tiene dos motores OCR, debes elegir explícitamente cuál conservar.',
                        size=8,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
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
                    ft.Text('📄 Extractor de Movimientos Financieros', size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Container(
                        ft.Text(f'Versión {APP_VERSION}', size=8, weight=ft.FontWeight.BOLD),
                        bgcolor=GOB_GOLD_LIGHT,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=11,
                    ),
                    config_button,
                    help_button,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(
                ft.Row(
                    [
                        upload_button,
                        stop_button,
                        loading_ring,
                        ft.Text('⏱', size=12),
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


if __name__ == '__main__':
    ft.run(main)
