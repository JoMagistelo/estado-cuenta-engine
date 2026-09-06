# ============================================================
# main_flet.py
# ============================================================
#
# Empaquetado:
#
# flet pack app\main_flet.py --name EstadoCuentaEngine
# pyinstaller EstadoCuentaEngine.spec
#
# ============================================================

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft


# ============================================================
# PATH SRC
# ============================================================

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
        )
    )
)


from engine.pipeline import (
    process_bank_statements_incremental,
)
from exporters.excel import export_batch_excel
from exporters.export_snapshot import snapshot_results_for_export


# ============================================================
# IDENTIDAD VISUAL
# ============================================================

GOB_GREEN = "#1F4D3A"
GOB_GREEN_DARK = "#163A2C"
GOB_GREEN_LIGHT = "#E8F0EC"

GOB_GOLD = "#B08D57"
GOB_GOLD_LIGHT = "#F4EEE5"

GOB_CREAM = "#F7F4EE"

BUTTON_TEXT = "#FFFFFF"


# ============================================================
# ASSETS
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

LOGO_PATH = (
    PROJECT_ROOT
    / "assets"
    / "logo_gobierno_mexico.png"
)


# ============================================================
# CONFIGURACIÓN DE ACTUALIZACIÓN DE UI
# ============================================================
#
# El procesamiento de PDFs ocurre en un hilo independiente.
#
# Ese hilo NO modifica controles de Flet.
#
# Los eventos se colocan en una Queue y el hilo/event-loop
# de Flet los consume periódicamente.
#
# 0.20 segundos proporciona una interfaz suficientemente
# fluida sin generar actualizaciones innecesarias.
#
# ============================================================

PROCESSING_UI_POLL_INTERVAL = 0.20


# ============================================================
# UTILIDADES
# ============================================================

def format_optional_float(
    value,
    format_str: str = "{:,.2f}",
    suffix: str = "",
    prefix: str = "",
    na_value: str = "N/A",
) -> str:

    if value is None:
        return na_value

    if isinstance(value, str):
        try:
            numeric_value = float(
                value.replace(",", "")
            )
        except (ValueError, TypeError):
            return value
    else:
        numeric_value = value

    formatted_value = format_str.format(
        numeric_value
    )

    return (
        f"{prefix}"
        f"{formatted_value}"
        f"{suffix}"
    )


def create_metric(
    title: str,
    value: str,
    delta: str | None = None,
) -> ft.Container:

    controls = [
        ft.Text(
            title,
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500,
        ),
        ft.Text(
            value,
            size=16,
            weight=ft.FontWeight.BOLD,
        ),
    ]

    if delta is not None:

        if delta.startswith("-"):
            delta_color = ft.Colors.ERROR

        elif delta.startswith("0.00"):
            delta_color = (
                ft.Colors.ON_SURFACE_VARIANT
            )

        else:
            delta_color = ft.Colors.GREEN

        controls.append(
            ft.Text(
                delta,
                size=12,
                color=delta_color,
                weight=ft.FontWeight.W_500,
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=controls,
            spacing=2,
        ),
        padding=15,
        border=ft.Border.all(
            1,
            ft.Colors.OUTLINE_VARIANT,
        ),
        border_radius=8,
        expand=True,
    )


def create_section_title(
    title: str,
    icon: str | None = None,
) -> ft.Text:

    if icon:
        title = f"{icon} {title}"

    return ft.Text(
        title,
        size=18,
        weight=ft.FontWeight.BOLD,
    )


def safe_value(
    value: Any,
) -> str:

    if value is None or value == "":
        return "N/A"

    return str(value)


def format_money(
    value: Any,
) -> str:

    if value is None:
        return "N/A"

    try:
        return f"${float(value):,.2f}"
    except (
        ValueError,
        TypeError,
    ):
        return str(value)


# ============================================================
# APP
# ============================================================

def main(page: ft.Page):

    # ========================================================
    # CONFIGURACIÓN
    # ========================================================

    page.title = (
        "Extractor de Movimientos Financieros"
    )

    page.window.width = 1100
    page.window.height = 800
    page.padding = 18
    page.theme_mode = ft.ThemeMode.LIGHT

    page.scroll = ft.ScrollMode.AUTO


    # ========================================================
    # ESTADO
    # ========================================================

    results: list[Any] = []

    processing_items: list[
        dict[str, Any]
    ] = []


    # ========================================================
    # ESTADO INTERNO DEL PROCESAMIENTO
    # ========================================================
    #
    # processing_event_queue:
    #
    #   Worker -> Queue -> UI
    #
    # El worker nunca modifica directamente los controles
    # de Flet.
    #
    # ========================================================

    processing_event_queue: Queue = Queue()

    processing_state = {
        "running": False,
        "batch_id": 0,
    }


    # ========================================================
    # CONTROLES DINÁMICOS
    # ========================================================

    status_text = ft.Text(
        "",
        size=14,
    )

    loading_ring = ft.ProgressRing(
        width=20,
        height=20,
        visible=False,
    )

    ocr_primary_selector = ft.Dropdown(
        label="Motor OCR principal",
        value="tesseract",
        width=260,
        options=[
            ft.DropdownOption(
                key="tesseract",
                text="Tesseract primero",
            ),
            ft.DropdownOption(
                key="paddleocr",
                text="PaddleOCR primero",
            ),
        ],
    )

    dropdown_files = ft.Dropdown(
        label=(
            "Selecciona el estado de cuenta "
            "que deseas revisar"
        ),
        width=390,
        visible=False,
    )

    processing_summary_view = ft.Container(
        width=650,
        visible=False,
    )

    auditoria_view = ft.Column(
        spacing=20,
    )

    export_button = ft.FilledButton(
        content="Generar Reporte Excel",
        icon=ft.Icons.DOWNLOAD,
        disabled=True,
        bgcolor=GOB_GOLD,
        color=BUTTON_TEXT,
    )


    # ========================================================
    # FEEDBACK / AYUDA
    # ========================================================

    def show_feedback(e=None):

        feedback_dialog = ft.AlertDialog(

            modal=False,

            title=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.INFO_OUTLINE,
                        color=GOB_GREEN,
                        size=22,
                    ),
                    ft.Text(
                        "Ayuda y recomendaciones",
                        weight=ft.FontWeight.BOLD,
                        size=16,
                    ),
                ],
                spacing=8,
            ),

            content=ft.Column(
                controls=[

                    ft.Divider(),

                    ft.Text(
                        "Validaciones financieras",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GREEN,
                    ),

                    ft.Text(
                        "Estas validaciones comparan los totales de "
                        "depósitos / abonos y retiros / cargos contra "
                        "la suma de los movimientos extraídos."
                    ),

                    ft.Text(
                        "Si una validación falla, revise primero los "
                        "totales y conceptos del resumen financiero. "
                        "Algunos estados de cuenta pueden mostrar por "
                        "separado intereses, ISR, IVA o comisiones que "
                        "deben considerarse al conciliar los movimientos."
                    ),

                    ft.Text(
                        "¿Qué hacer cuando una validación falla?",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "Primero verifique que los totales del resumen "
                        "sean correctos y revise si existen intereses, "
                        "ISR, IVA o comisiones que expliquen la diferencia. "
                        "Si los totales son correctos, revise después los "
                        "montos de los movimientos y corrija en Excel "
                        "cualquier extracción incorrecta."
                    ),

                    ft.Divider(),

                    ft.Text(
                        "Bancos y estados de cuenta habilitados",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GREEN,
                    ),

                    ft.Text(
                        "Actualmente se procesan estados "
                        "de cuenta digitales de:",
                    ),

                    ft.Text(
                        "BBVA Digital",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Libretón Básico\n"
                        "• Libretón Nómina\n"
                        "• Libretón Premium",
                    ),

                    ft.Text(
                        "Banorte Digital y Escaneado",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Nómina Banorte\n"
                        "• Nómina Banorte sin chequera\n"
                        "• Enlace Negocios",
                    ),

                    ft.Text(
                        "Banamex Digital",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Mi Cuenta\n"
                        "• Cuenta Base\n"
                        "• Cuenta Prioriti",
                    ),

                    ft.Text(
                        "HSBC Digital y Escaneado",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Ahorro y Debito",
                    ),

                    ft.Text(
                        "Scotiabank Digital",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Nomina Clasic\n",
                    ),


                    ft.Text(
                        "Banca Mifel",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• Cuenta Alavista\n",
                    ),

                    ft.Text(
                        "CETESDIRECTO Digital",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "• cetesdirecto\n",
                    ),

                    ft.Text(
                        "MercadoPago Digital",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                    ),

                    ft.Text(
                        "Próximamente PDFs Escaneados",
                        size=9,
                        weight=ft.FontWeight.BOLD,
                        color=GOB_GOLD,
                    ),

                    ft.Divider(),

                    ft.Container(
                        content=ft.Text(
                            "Nota: la lista de formatos "
                            "habilitados se actualizará "
                            "conforme se incorporen "
                            "nuevos modelos de estados "
                            "de cuenta.",
                            size=8,
                        ),
                        bgcolor=GOB_CREAM,
                        padding=12,
                        border_radius=8,
                    ),
                ],
                spacing=8,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),

            actions=[
                ft.FilledButton(
                    content="Cerrar",
                    icon=ft.Icons.CLOSE,
                    bgcolor=GOB_GREEN,
                    color=BUTTON_TEXT,
                    on_click=(
                        lambda e:
                        page.pop_dialog()
                    ),
                ),
            ],

            actions_alignment=(
                ft.MainAxisAlignment.END
            ),
        )

        page.show_dialog(
            feedback_dialog
        )


    # ========================================================
    # SCROLL
    # ========================================================

    async def reset_page_scroll_async():

        try:
            await page.scroll_to(
                offset=0,
                duration=0,
            )
        except Exception:
            pass


    def reset_page_scroll():

        page.run_task(
            reset_page_scroll_async
        )


    # ========================================================
    # VALIDACIONES
    # ========================================================

    def get_validation_result(
        result,
        validation_name: str,
    ):

        for validacion in result.validaciones:

            if (
                validacion.nombre
                == validation_name
            ):
                return validacion

        return None


    def create_validation_status(
        validacion,
    ) -> ft.Container:

        if validacion is None:

            return ft.Container(
                content=ft.Text(
                    "—",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=(
                        ft.Colors
                        .ON_SURFACE_VARIANT
                    ),
                    text_align=ft.TextAlign.CENTER,
                ),
                bgcolor=(
                    ft.Colors
                    .SURFACE_CONTAINER_LOW
                ),
                padding=8,
                border_radius=6,
                alignment=ft.Alignment.CENTER,
            )

        if validacion.correcto:

            return ft.Container(
                content=ft.Text(
                    "✅",
                    size=16,
                    text_align=(
                        ft.TextAlign.CENTER
                    ),
                ),
                bgcolor=ft.Colors.GREEN_50,
                padding=8,
                border_radius=6,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Text(
                "❌",
                size=16,
                text_align=ft.TextAlign.CENTER,
            ),
            bgcolor=ft.Colors.RED_50,
            padding=8,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
        )


    def create_pending_validation_status():

        return ft.Container(
            content=ft.Text(
                "⏳",
                size=16,
                text_align=ft.TextAlign.CENTER,
            ),
            bgcolor=ft.Colors.AMBER_50,
            padding=8,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
        )


    def create_error_validation_status():

        return ft.Container(
            content=ft.Text(
                "⚠️",
                size=16,
                text_align=ft.TextAlign.CENTER,
            ),
            bgcolor=ft.Colors.RED_50,
            padding=8,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
        )


    # ========================================================
    # ESTADO DEL MÉTODO
    # ========================================================

    def create_processing_method_status(
        processing_method: str,
    ) -> ft.Container:

        if (
            processing_method.upper()
            == "OCR"
        ):

            return ft.Container(
                content=ft.Text(
                    "OCR",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=ft.Colors.BLUE_50,
                padding=ft.Padding.symmetric(
                    horizontal=8,
                    vertical=6,
                ),
                border_radius=6,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Text(
                "Digital",
                size=12,
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=ft.Colors.GREEN_50,
            padding=ft.Padding.symmetric(
                horizontal=8,
                vertical=6,
            ),
            border_radius=6,
            alignment=ft.Alignment.CENTER,
        )


    def create_processing_state_status():

        return ft.Container(
            content=ft.Text(
                "Detectando",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=(
                    ft.Colors.ON_SURFACE_VARIANT
                ),
            ),
            bgcolor=(
                ft.Colors
                .SURFACE_CONTAINER_LOW
            ),
            padding=ft.Padding.symmetric(
                horizontal=8,
                vertical=6,
            ),
            border_radius=6,
            alignment=ft.Alignment.CENTER,
        )


    # ========================================================
    # TABLA DE PROCESAMIENTO
    # ========================================================

    def create_processing_summary(
        items,
    ) -> ft.Container:

        rows = []

        for item in items:

            status = item.get(
                "status"
            )

            result = item.get(
                "result"
            )

            processing_method = item.get(
                "processing_method"
            )

            # ------------------------------------------------
            # MÉTODO
            # ------------------------------------------------

            if processing_method:

                process_control = (
                    create_processing_method_status(
                        processing_method
                    )
                )

            else:

                process_control = (
                    create_processing_state_status()
                )

            # ------------------------------------------------
            # VALIDACIONES
            # ------------------------------------------------

            if (
                status == "completed"
                and result
            ):

                validacion_abonos = (
                    get_validation_result(
                        result,
                        "Total depósitos / abonos",
                    )
                )

                validacion_cargos = (
                    get_validation_result(
                        result,
                        "Total retiros / cargos",
                    )
                )

                abonos_control = (
                    create_validation_status(
                        validacion_abonos
                    )
                )

                cargos_control = (
                    create_validation_status(
                        validacion_cargos
                    )
                )

            elif status == "error":

                abonos_control = (
                    create_error_validation_status()
                )

                cargos_control = (
                    create_error_validation_status()
                )

            else:

                abonos_control = (
                    create_pending_validation_status()
                )

                cargos_control = (
                    create_pending_validation_status()
                )

            rows.append(
                ft.DataRow(
                    cells=[

                        ft.DataCell(
                            content=ft.Text(
                                item.get(
                                    "file_name",
                                    "",
                                ),
                                size=12,
                            )
                        ),

                        ft.DataCell(
                            content=process_control
                        ),

                        ft.DataCell(
                            content=abonos_control
                        ),

                        ft.DataCell(
                            content=cargos_control
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[

                ft.DataColumn(
                    label=ft.Text(
                        "Archivo",
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    )
                ),

                ft.DataColumn(
                    label=ft.Text(
                        "Proceso",
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    )
                ),

                ft.DataColumn(
                    label=ft.Text(
                        "Abonos",
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    )
                ),

                ft.DataColumn(
                    label=ft.Text(
                        "Cargos",
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    )
                ),
            ],
            rows=rows,
            border=ft.Border.all(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            vertical_lines=ft.BorderSide(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            horizontal_lines=ft.BorderSide(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            column_spacing=18,
        )

        return ft.Container(
            content=ft.Column(
                controls=[

                    ft.Text(
                        "Archivos procesados",
                        size=18,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    ),

                    ft.Row(
                        controls=[table],
                        scroll=(
                            ft.ScrollMode.AUTO
                        ),
                    ),
                ],
                spacing=8,
            ),
            padding=10,
            border=ft.Border.all(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            border_radius=8,
        )


    def update_processing_summary():

        if not processing_items:

            processing_summary_view.content = None
            processing_summary_view.visible = False

            return

        processing_summary_view.content = (
            create_processing_summary(
                processing_items
            )
        )

        processing_summary_view.visible = True


    # ========================================================
    # SELECTOR
    # ========================================================
    #
    # IMPORTANTE:
    #
    # El selector continúa mostrando exclusivamente resultados
    # ya terminados.
    #
    # ========================================================

    def update_dropdown():

        dropdown_files.options = [

            ft.DropdownOption(
                key=str(index),
                text=result.file_name,
            )

            for index, result
            in enumerate(results)
        ]

        if results:

            dropdown_files.visible = True

            export_button.disabled = False

        else:

            dropdown_files.visible = False

            export_button.disabled = True


    # ========================================================
    # ESTADO GENERAL
    # ========================================================

    def update_processing_status():

        total = len(
            processing_items
        )

        completed = sum(
            1
            for item in processing_items
            if item.get("status")
            == "completed"
        )

        errors = sum(
            1
            for item in processing_items
            if item.get("status")
            == "error"
        )

        pending = (
            total
            - completed
            - errors
        )

        ocr_pending = sum(
            1
            for item in processing_items
            if (
                item.get("status")
                == "processing"
                and
                item.get(
                    "processing_method"
                )
                == "OCR"
            )
        )

        if pending > 0:

            status_text.value = (
                f"Procesando "
                f"{completed} de "
                f"{total} archivos"
            )

            if ocr_pending:

                status_text.value += (
                    f" · {ocr_pending} "
                    f"OCR en segundo plano"
                )

            if errors:

                status_text.value += (
                    f" · {errors} con error"
                )

            status_text.color = (
                ft.Colors.ON_SURFACE
            )

            return

        # ====================================================
        # LOTE TERMINADO
        # ====================================================

        if errors == 0:

            status_text.value = (
                f"✅ {completed} "
                f"estados de cuenta "
                f"procesados correctamente."
            )

            status_text.color = (
                ft.Colors.GREEN
            )

        elif completed > 0:

            status_text.value = (
                f"✅ {completed} "
                f"estados de cuenta "
                f"procesados correctamente."
                f" ⚠️ {errors} con error."
            )

            status_text.color = (
                ft.Colors.ERROR
            )

        else:

            status_text.value = (
                f"❌ No fue posible "
                f"procesar los "
                f"{errors} archivos "
                f"seleccionados."
            )

            status_text.color = (
                ft.Colors.RED
            )


    # ========================================================
    # RENDER IMAGEN
    # ========================================================

    def render_image_document(
        result,
    ):

        auditoria_view.controls.clear()

        auditoria_view.controls.extend(

            [

                ft.Container(
                    content=ft.Column(
                        controls=[

                            ft.Text(
                                "🖼️ Se detectó que "
                                "este documento es "
                                "una imagen o un PDF "
                                "escaneado.",
                                weight=(
                                    ft.FontWeight.BOLD
                                ),
                                color=(
                                    ft.Colors
                                    .ON_ERROR_CONTAINER
                                ),
                            ),
                        ],
                    ),
                    bgcolor=(
                        ft.Colors
                        .ERROR_CONTAINER
                    ),
                    padding=15,
                    border_radius=8,
                ),

                ft.Container(
                    content=ft.Column(
                        controls=[

                            ft.Text(
                                "🚧 El motor detectó "
                                "correctamente que "
                                "el archivo es un "
                                "PDF basado en imagen.",
                                color=(
                                    ft.Colors
                                    .ON_SECONDARY_CONTAINER
                                ),
                            ),

                            ft.Text(
                                "La extracción de "
                                "datos mediante OCR "
                                "está pendiente de "
                                "implementación.",
                                color=(
                                    ft.Colors
                                    .ON_SECONDARY_CONTAINER
                                ),
                            ),
                        ],
                    ),
                    bgcolor=(
                        ft.Colors
                        .SECONDARY_CONTAINER
                    ),
                    padding=15,
                    border_radius=8,
                ),

                ft.Container(
                    content=ft.Column(
                        controls=[

                            ft.Text(
                                "Estado del "
                                "procesamiento",
                                weight=(
                                    ft.FontWeight.BOLD
                                ),
                            ),

                            ft.Text(
                                "📄 Tipo: PDF "
                                "basado en imagen"
                            ),

                            ft.Text(
                                "🖼️ Detección: "
                                "correcta"
                            ),

                            ft.Text(
                                "🔎 OCR: pendiente "
                                "de implementación"
                            ),

                            ft.Text(
                                "🏦 Detección de "
                                "banco: pendiente "
                                "de OCR"
                            ),

                            ft.Text(
                                "📊 Extracción "
                                "financiera: "
                                "pendiente de OCR"
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=15,
                ),
            ]
        )


    # ========================================================
    # TABLA DE MOVIMIENTOS
    # ========================================================

    def create_movements_table(
        movimientos,
        fecha_corte_documento: str | None = None,
        numero_cuenta_documento: str | None = None,
    ) -> ft.Column:

        columnas_mostrar = [

            "fecha_corte",
            "numero_cuenta",
            "numero_movimiento",
            "fecha_operacion",
            "fecha_liquidacion",
            "concepto",
            "cargo",
            "abono",
            "saldo_operacion",
            "saldo_liquidacion",
            "tipo_operacion",
            "beneficiario",
            "cuenta_beneficiario",
            "clabe_beneficiario",
            "rfc",
            "referencia",
            "clave_rastreo",
            "autorizacion",
            "hora_operacion",
        ]

        columnas_existentes: list[str] = []

        if movimientos:

            movimiento_prueba = movimientos[0]

            for columna in columnas_mostrar:

                if (
                    columna
                    == "numero_movimiento"
                ):

                    columnas_existentes.append(
                        columna
                    )

                elif (
                    columna
                    == "fecha_corte"
                    and fecha_corte_documento
                ):

                    columnas_existentes.append(
                        columna
                    )

                elif (
                    columna
                    == "numero_cuenta"
                    and numero_cuenta_documento
                ):

                    columnas_existentes.append(
                        columna
                    )

                elif hasattr(
                    movimiento_prueba,
                    columna,
                ):

                    columnas_existentes.append(
                        columna
                    )

        nombres = {

            "fecha_corte":
                "Fecha Corte",

            "numero_cuenta":
                "Número de Cuenta",

            "fecha_operacion":
                "Fecha Operación",

            "fecha_liquidacion":
                "Fecha Liquidación",

            "concepto":
                "Concepto",

            "numero_movimiento":
                "No. Movimiento",

            "cargo":
                "Cargo",

            "abono":
                "Abono",

            "saldo_operacion":
                "Saldo Operación",

            "saldo_liquidacion":
                "Saldo Liquidación",

            "tipo_operacion":
                "Tipo",

            "beneficiario":
                "Beneficiario",

            "cuenta_beneficiario":
                "Cuenta Benef.",

            "clabe_beneficiario":
                "CLABE",

            "rfc":
                "RFC",

            "referencia":
                "Referencia",

            "clave_rastreo":
                "Clave Rastreo",

            "autorizacion":
                "Autorización",

            "hora_operacion":
                "Hora",
        }

        columns = []

        for columna in columnas_existentes:

            columns.append(
                ft.DataColumn(
                    label=ft.Text(
                        nombres.get(
                            columna,
                            columna
                            .replace(
                                "_",
                                " ",
                            )
                            .title(),
                        ),
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    )
                )
            )

        rows = []

        for index, movimiento in enumerate(
            movimientos,
            start=1,
        ):

            cells = []

            for columna in columnas_existentes:

                if (
                    columna
                    == "numero_movimiento"
                ):

                    value = index

                elif (
                    columna
                    == "fecha_corte"
                ):

                    value = (
                        fecha_corte_documento
                    )

                elif (
                    columna
                    == "numero_cuenta"
                ):

                    value = (
                        numero_cuenta_documento
                    )

                else:

                    value = getattr(
                        movimiento,
                        columna,
                        None,
                    )

                if columna in {

                    "cargo",
                    "abono",
                    "saldo_operacion",
                    "saldo_liquidacion",

                }:

                    text_value = format_money(
                        value
                    )

                else:

                    text_value = safe_value(
                        value
                    )

                cells.append(
                    ft.DataCell(
                        content=ft.Text(
                            text_value,
                            size=11,
                        )
                    )
                )

            rows.append(
                ft.DataRow(
                    cells=cells,
                )
            )

        table = ft.DataTable(
            columns=columns,
            rows=rows,
            border=ft.Border.all(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            vertical_lines=ft.BorderSide(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            horizontal_lines=ft.BorderSide(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            column_spacing=14,
        )

        return ft.Column(

            controls=[

                ft.Row(
                    controls=[table],
                    scroll=(
                        ft.ScrollMode.ALWAYS
                    ),
                )
            ],

            scroll=(
                ft.ScrollMode.ALWAYS
            ),

            height=350,
        )


    # ========================================================
    # COMPARACIÓN Y SELECCIÓN OCR
    # ========================================================

    def ocr_engine_label(
        engine: str | None,
    ) -> str:

        labels = {
            "tesseract": "Tesseract",
            "paddleocr": "PaddleOCR",
        }

        normalized = (
            str(engine or "")
            .strip()
            .lower()
        )

        return labels.get(
            normalized,
            normalized or "OCR",
        )


    def create_ocr_review_controls(
        result,
    ) -> ft.Container | None:

        review = getattr(
            result,
            "ocr_review",
            None,
        )

        if review is None:
            return None

        engines = list(
            result.available_ocr_engines()
        )

        if len(engines) < 2:
            return None

        selected_engine = (
            result.selected_ocr_engine
            or engines[0]
        )

        recommended_engine = (
            result.recommended_ocr_engine
            or "tesseract"
        )

        def on_ocr_engine_change(e):

            engine = str(
                e.control.value or ""
            ).strip().lower()

            if engine not in engines:
                return

            result.select_ocr_engine(
                engine
            )

            update_processing_summary()

            render_result(
                result
            )

        selector = ft.Dropdown(
            label=(
                "Resultado OCR mostrado y "
                "usado para exportación"
            ),
            value=selected_engine,
            width=330,
            options=[
                ft.DropdownOption(
                    key=engine,
                    text=ocr_engine_label(
                        engine
                    ),
                )
                for engine in engines
            ],
        )

        selector.on_select = (
            on_ocr_engine_change
        )

        candidate_cards = []

        for engine in engines:

            candidate = (
                review.get_candidate(
                    engine
                )
            )

            badges = []

            if engine == recommended_engine:

                badges.append(
                    ft.Text(
                        "Recomendado",
                        size=10,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                        color=GOB_GREEN,
                    )
                )

            if engine == selected_engine:

                badges.append(
                    ft.Text(
                        "Mostrando / se exportará",
                        size=10,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                        color=GOB_GOLD,
                    )
                )

            candidate_cards.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                ocr_engine_label(
                                    engine
                                ),
                                size=15,
                                weight=(
                                    ft.FontWeight.BOLD
                                ),
                            ),
                            *badges,
                            ft.Text(
                                "Movimientos: "
                                f"{candidate.movement_count}",
                                size=12,
                            ),
                            ft.Text(
                                "Validaciones: "
                                f"{candidate.validation_total}",
                                size=12,
                            ),
                            ft.Text(
                                "Taches: "
                                f"{candidate.validation_failed}",
                                size=12,
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=12,
                    border=ft.Border.all(
                        1,
                        ft.Colors.OUTLINE_VARIANT,
                    ),
                    border_radius=8,
                    expand=True,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "🔎 Comparación OCR",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Cuando ambos motores están disponibles puedes "
                        "alternar el resultado que deseas revisar. La "
                        "selección actual es también la que se utilizará "
                        "al generar el Excel.",
                        size=12,
                        color=(
                            ft.Colors
                            .ON_SURFACE_VARIANT
                        ),
                    ),
                    selector,
                    ft.Row(
                        controls=candidate_cards,
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            padding=15,
            bgcolor=GOB_GREEN_LIGHT,
            border=ft.Border.all(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            border_radius=10,
        )


    # ========================================================
    # RENDER RESULTADO
    # ========================================================

    def render_result(
        result,
    ):

        auditoria_view.controls.clear()

        if result is None:

            page.update()
            reset_page_scroll()

            return

        ocr_review_controls = (
            create_ocr_review_controls(
                result
            )
        )

        if ocr_review_controls is not None:

            auditoria_view.controls.append(
                ocr_review_controls
            )

        estado = (
            result.estado_cuenta
        )

        # ====================================================
        # DOCUMENTO IMAGEN
        # ====================================================

        if (
            result.bank_key
            == "imagen_no_procesada"
        ):

            render_image_document(
                result
            )

            page.update()
            reset_page_scroll()

            return

        # ====================================================
        # DOCUMENTO DIGITAL
        # ====================================================

        auditoria_view.controls.append(

            ft.Text(
                f"Banco Detectado: "
                f"{result.bank_key.upper()}",
                size=20,
                weight=(
                    ft.FontWeight.BOLD
                ),
            )
        )

        dc = (

            estado.datos_cuenta

            if estado is not None

            else None
        )

        # ====================================================
        # MÉTRICAS PRINCIPALES
        # ====================================================

        periodo = (

            f"{dc.periodo_inicio} "
            f"al "
            f"{dc.periodo_fin}"

            if dc

            else "N/A"
        )

        cliente = (

            dc.nombre_cliente or "N/A"

            if dc

            else "N/A"
        )

        cuenta = (

            dc.numero_cuenta or "N/A"

            if dc

            else "N/A"
        )

        clabe = (

            dc.clabe or "N/A"

            if dc

            else "N/A"
        )

        auditoria_view.controls.append(

            ft.Row(
                controls=[

                    create_metric(
                        "Periodo",
                        periodo,
                    ),

                    create_metric(
                        "Cliente",
                        cliente,
                    ),

                    create_metric(
                        "Cuenta",
                        cuenta,
                    ),

                    create_metric(
                        "CLABE",
                        clabe,
                    ),
                ]
            )
        )

        # ====================================================
        # 1. DATOS DE LA CUENTA
        # ====================================================

        auditoria_view.controls.append(
            create_section_title(
                "1. Datos de la Cuenta",
                "📌",
            )
        )

        if dc:

            rf = (
                estado.resumen_financiero
            )

            dias_periodo = (

                safe_value(
                    rf.dias_periodo
                )

                if rf

                else "N/A"
            )

            tasa_bruta = (

                f"{safe_value(
                    rf.tasa_bruta_anual
                )}%"

                if rf

                else "N/A"
            )

            datos_cuenta = ft.Container(

                content=ft.Row(

                    controls=[

                        ft.Column(
                            controls=[

                                ft.Text(
                                    f"Producto: "
                                    f"{safe_value(
                                        dc.producto_principal
                                    )}"
                                ),

                                ft.Text(
                                    f"No. Cliente: "
                                    f"{safe_value(
                                        dc.numero_cliente
                                    )}"
                                ),
                            ],
                            expand=True,
                        ),

                        ft.Column(
                            controls=[

                                ft.Text(
                                    f"RFC: "
                                    f"{safe_value(
                                        dc.rfc
                                    )}"
                                ),

                                ft.Text(
                                    f"Fecha de Corte: "
                                    f"{safe_value(
                                        dc.fecha_corte
                                    )}"
                                ),
                            ],
                            expand=True,
                        ),

                        ft.Column(
                            controls=[

                                ft.Text(
                                    f"Días del Periodo: "
                                    f"{dias_periodo}"
                                ),

                                ft.Text(
                                    f"Tasa Bruta Anual: "
                                    f"{tasa_bruta}"
                                ),
                            ],
                            expand=True,
                        ),
                    ]
                ),

                padding=15,

                border=ft.Border.all(
                    1,
                    ft.Colors.OUTLINE_VARIANT,
                ),

                border_radius=8,
            )

            auditoria_view.controls.append(
                datos_cuenta
            )

        else:

            auditoria_view.controls.append(

                ft.Container(
                    content=ft.Text(
                        "⚠️ No se encontraron "
                        "datos de la cuenta."
                    ),
                    bgcolor=(
                        ft.Colors
                        .ERROR_CONTAINER
                    ),
                    padding=15,
                    border_radius=8,
                )
            )

        # ====================================================
        # 2. RESUMEN FINANCIERO
        # ====================================================

        auditoria_view.controls.append(

            create_section_title(
                "2. Resumen Financiero",
                "📊",
            )
        )

        rf = (
            estado.resumen_financiero
        )

        if rf:

            saldo_anterior = (
                rf.saldo_anterior or 0
            )

            saldo_final = (
                rf.saldo_final or 0
            )

            delta_val = (
                saldo_final
                - saldo_anterior
            )

            auditoria_view.controls.append(

                ft.Row(

                    controls=[

                        create_metric(
                            "Saldo Anterior",
                            format_money(
                                rf.saldo_anterior
                            ),
                        ),

                        create_metric(
                            "Depósitos / Abonos",
                            format_money(
                                rf.depositos_abonos
                            ),
                        ),

                        create_metric(
                            "Retiros / Cargos",
                            format_money(
                                rf.retiros_cargos
                            ),
                        ),

                        create_metric(
                            "Saldo Final",
                            format_money(
                                rf.saldo_final
                            ),
                            f"{delta_val:,.2f}",
                        ),
                    ]
                )
            )

            auditoria_view.controls.append(

                ft.Row(

                    controls=[

                        create_metric(
                            "Saldo Promedio",
                            format_money(
                                rf.saldo_promedio
                            ),
                        ),

                        create_metric(
                            "Intereses a Favor",
                            format_money(
                                rf.intereses_a_favor
                            ),
                        ),

                        create_metric(
                            "ISR Retenido",
                            format_money(
                                rf.isr_retenido
                            ),
                        ),
                    ]
                )
            )

            auditoria_view.controls.append(

                ft.ExpansionTile(

                    title=ft.Text(
                        "Ver más detalles "
                        "del resumen financiero"
                    ),

                    controls=[

                        ft.Container(

                            content=ft.Column(

                                controls=[

                                    ft.Row(

                                        controls=[

                                            create_metric(
                                                "Saldo Promedio Gravable",
                                                format_money(
                                                    rf.saldo_promedio_gravable
                                                ),
                                            ),

                                            create_metric(
                                                "Saldo Promedio Mínimo Mensual",
                                                format_money(
                                                    rf.saldo_promedio_minimo_mensual
                                                ),
                                            ),

                                            create_metric(
                                                "Saldo Global",
                                                format_money(
                                                    rf.saldo_global
                                                ),
                                            ),
                                        ]
                                    ),

                                    ft.Row(

                                        controls=[

                                            create_metric(
                                                "Cheques Pagados",
                                                safe_value(
                                                    rf.cheques_pagados
                                                ),
                                            ),

                                            create_metric(
                                                "Manejo de Cuenta",
                                                format_money(
                                                    rf.manejo_cuenta
                                                ),
                                            ),

                                            create_metric(
                                                "Cargos Objetados",
                                                format_money(
                                                    rf.cargos_objetados
                                                ),
                                            ),

                                            create_metric(
                                                "Abonos Objetados",
                                                format_money(
                                                    rf.abonos_objetados
                                                ),
                                            ),
                                        ]
                                    ),
                                ],
                                spacing=15,
                            ),

                            padding=10,
                        )
                    ],
                )
            )

        else:

            auditoria_view.controls.append(

                ft.Container(
                    content=ft.Text(
                        "⚠️ No se encontró "
                        "el resumen financiero."
                    ),
                    bgcolor=(
                        ft.Colors
                        .ERROR_CONTAINER
                    ),
                    padding=15,
                    border_radius=8,
                )
            )

        # ====================================================
        # 3. OTROS PRODUCTOS
        # ====================================================

        auditoria_view.controls.append(

            create_section_title(
                "3. Otros Productos y Comisiones",
                "💰",
            )
        )

        op = (
            estado.otros_productos
        )

        if op:

            otros_productos = ft.Container(

                content=ft.Column(

                    controls=[

                        ft.Text(

                            f"Producto de Inversión: "
                            f"{safe_value(
                                op.producto
                            )} "
                            f"(Contrato: "
                            f"{safe_value(
                                op.contrato
                            )})",

                            weight=(
                                ft.FontWeight.BOLD
                            ),
                        ),

                        ft.Row(

                            controls=[

                                create_metric(
                                    "Tasa Interés Anual",
                                    format_optional_float(
                                        op.tasa_interes_anual,
                                        suffix="%",
                                    ),
                                ),

                                create_metric(
                                    "GAT Nominal",
                                    format_optional_float(
                                        op.gat_nominal_anual,
                                        suffix="%",
                                    ),
                                ),

                                create_metric(
                                    "GAT Real",
                                    format_optional_float(
                                        op.gat_real_anual,
                                        suffix="%",
                                    ),
                                ),

                                create_metric(
                                    "Total Comisiones",
                                    format_optional_float(
                                        op.total_comisiones,
                                        prefix="$",
                                    ),
                                ),
                            ]
                        ),
                    ],
                    spacing=15,
                ),

                padding=15,

                border=ft.Border.all(
                    1,
                    ft.Colors.OUTLINE_VARIANT,
                ),

                border_radius=8,
            )

            auditoria_view.controls.append(
                otros_productos
            )

        else:

            auditoria_view.controls.append(

                ft.Container(
                    content=ft.Text(
                        "No se encontraron "
                        "otros productos o "
                        "comisiones en este "
                        "estado de cuenta."
                    ),
                    bgcolor=(
                        ft.Colors
                        .SURFACE_CONTAINER_LOW
                    ),
                    padding=15,
                    border_radius=8,
                )
            )

        # ====================================================
        # 4. VALIDACIONES FINANCIERAS
        # ====================================================

        if result.validaciones:

            correctas = sum(

                1

                for validacion
                in result.validaciones

                if validacion.correcto
            )

            total = len(
                result.validaciones
            )

            validaciones_controls = [

                ft.Text(

                    f"Integridad financiera: "
                    f"{correctas}/{total} "
                    f"validaciones correctas",

                    size=16,

                    weight=(
                        ft.FontWeight.BOLD
                    ),
                )
            ]

            for validacion in (
                result.validaciones
            ):

                if validacion.correcto:

                    icono = "✅"
                    color = (
                        ft.Colors.GREEN
                    )

                else:

                    icono = "❌"
                    color = (
                        ft.Colors.RED
                    )

                esperado = format_money(
                    validacion.esperado
                )

                obtenido = format_money(
                    validacion.obtenido
                )

                diferencia = format_money(
                    validacion.diferencia
                )

                validaciones_controls.append(

                    ft.ExpansionTile(

                        title=ft.Text(

                            f"{icono} "
                            f"{validacion.nombre}",

                            color=color,
                        ),

                        controls=[

                            ft.Container(

                                content=ft.Column(

                                    controls=[

                                        ft.Text(
                                            f"Esperado: "
                                            f"{esperado}"
                                        ),

                                        ft.Text(
                                            f"Obtenido: "
                                            f"{obtenido}"
                                        ),

                                        ft.Text(
                                            f"Diferencia: "
                                            f"{diferencia}"
                                        ),

                                        ft.Text(

                                            safe_value(
                                                validacion.mensaje
                                            ),

                                            italic=True,

                                            color=(
                                                ft.Colors
                                                .ON_SURFACE_VARIANT
                                            ),
                                        ),
                                    ]
                                ),

                                padding=ft.Padding.only(
                                    left=30,
                                    bottom=10,
                                ),
                            )
                        ],
                    )
                )

            auditoria_view.controls.append(

                ft.ExpansionTile(

                    title=ft.Text(

                        "✓ Validaciones Financieras",

                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    ),

                    expanded=False,

                    controls=(
                        validaciones_controls
                    ),
                )
            )

        # ====================================================
        # 5. MOVIMIENTOS
        # ====================================================

        movimientos = (
            estado.movimientos
            or []
        )

        auditoria_view.controls.append(

            create_section_title(

                f"5. Movimientos "
                f"({len(movimientos)})",

                "📑",
            )
        )

        if movimientos:

            auditoria_view.controls.append(

                create_movements_table(

                    movimientos,

                    fecha_corte_documento=(
                        dc.fecha_corte
                        if dc
                        else None
                    ),

                    numero_cuenta_documento=(
                        dc.numero_cuenta
                        if dc
                        else None
                    ),
                )
            )

        else:

            auditoria_view.controls.append(

                ft.Container(

                    content=ft.Text(
                        "⚠️ No se encontraron "
                        "movimientos en este "
                        "documento."
                    ),

                    bgcolor=(
                        ft.Colors
                        .ERROR_CONTAINER
                    ),

                    padding=15,

                    border_radius=8,
                )
            )

        page.update()

        reset_page_scroll()


    # ========================================================
    # WORKER DE PROCESAMIENTO
    # ========================================================
    #
    # MUY IMPORTANTE:
    #
    # Esta función NO toca ningún control de Flet.
    #
    # Solamente ejecuta el pipeline y coloca eventos en la
    # Queue.
    #
    # ========================================================

    def processing_worker(
        paths: list[str],
        names: list[str],
        batch_id: int,
        ocr_primary_engine: str,
    ):

        try:

            for event in (
                process_bank_statements_incremental(
                    paths,
                    names,
                    ocr_primary_engine=ocr_primary_engine,
                )
            ):

                processing_event_queue.put(
                    (
                        "event",
                        batch_id,
                        event,
                    )
                )

        except Exception as ex:

            processing_event_queue.put(

                (
                    "worker_error",
                    batch_id,
                    ex,
                    traceback.format_exc(),
                )
            )

        finally:

            processing_event_queue.put(

                (
                    "finished",
                    batch_id,
                )
            )


    # ========================================================
    # MANEJO DE EVENTOS DEL PIPELINE
    # ========================================================

    def handle_processing_event(
        event,
    ) -> bool:

        if event is None:
            return False

        # ----------------------------------------------------
        # VALIDACIÓN DEL ÍNDICE
        # ----------------------------------------------------

        index = getattr(
            event,
            "index",
            None,
        )

        if not isinstance(
            index,
            int,
        ):

            return False

        if not (
            0 <= index
            < len(processing_items)
        ):

            return False

        item = (
            processing_items[index]
        )

        # ----------------------------------------------------
        # STARTED
        # ----------------------------------------------------

        if event.kind == "started":

            item["processing_method"] = (
                event.processing_method
            )

            item["status"] = (
                "processing"
            )

            item["error"] = None

            return True

        # ----------------------------------------------------
        # COMPLETED
        # ----------------------------------------------------

        if event.kind == "completed":

            item["processing_method"] = (
                event.processing_method
            )

            item["status"] = (
                "completed"
            )

            item["result"] = (
                event.result
            )

            item["error"] = None

            result = event.result

            # -----------------------------------------------
            # SOLO RESULTADOS TERMINADOS
            # -----------------------------------------------

            if result is not None:

                was_empty = (
                    not results
                )

                results.append(
                    result
                )

                update_dropdown()

                # -------------------------------------------
                # MOSTRAR AUTOMÁTICAMENTE SOLO EL PRIMERO
                # -------------------------------------------

                if was_empty:

                    dropdown_files.value = (
                        "0"
                    )

                    render_result(
                        result
                    )

            return True

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if event.kind == "error":

            item["processing_method"] = (
                event.processing_method
            )

            item["status"] = (
                "error"
            )

            item["result"] = None

            item["error"] = (

                str(event.error)

                if event.error

                else
                "Error desconocido."
            )

            return True

        return False


    # ========================================================
    # FINALIZACIÓN POR ERROR DEL WORKER
    # ========================================================

    def handle_worker_error(
        ex,
        error_traceback: str,
    ):

        error_text = str(
            ex
        )

        # Los resultados que ya terminaron correctamente
        # permanecen disponibles.
        #
        # Los elementos que quedaron a medias se marcan como
        # error individual para que la tabla no los deje
        # permanentemente en "procesando".

        for item in processing_items:

            if item.get(
                "status"
            ) not in {
                "completed",
                "error",
            }:

                item["status"] = (
                    "error"
                )

                item["error"] = (
                    error_text
                )

        status_text.value = (
            "❌ Error durante el "
            "procesamiento: "
            f"{error_text}"
        )

        status_text.color = (
            ft.Colors.RED
        )

        auditoria_view.controls.clear()

        auditoria_view.controls.append(

            ft.Container(

                content=ft.Column(

                    controls=[

                        ft.Text(
                            "Error durante "
                            "el procesamiento",
                            weight=(
                                ft.FontWeight.BOLD
                            ),
                            color=(
                                ft.Colors.ERROR
                            ),
                        ),

                        ft.Text(
                            error_text
                        ),

                        ft.Text(
                            error_traceback,
                            selectable=True,
                            size=12,
                        ),
                    ]
                ),

                bgcolor=(
                    ft.Colors
                    .ERROR_CONTAINER
                ),

                padding=15,

                border_radius=8,
            )
        )


    # ========================================================
    # POLLER DE UI
    # ========================================================
    #
    # Este es el cambio fundamental.
    #
    # Flet revisa la Queue periódicamente.
    #
    # Todos los cambios de controles y page.update() suceden
    # aquí, no dentro del worker.
    #
    # ========================================================

    async def processing_ui_poller():

        while True:

            page_changed = False

            try:

                while True:

                    message = (
                        processing_event_queue
                        .get_nowait()
                    )

                    message_type = (
                        message[0]
                    )

                    batch_id = (
                        message[1]
                    )

                    # ---------------------------------------
                    # IGNORAR MENSAJES DE LOTES ANTERIORES
                    # ---------------------------------------

                    if (
                        batch_id
                        != processing_state[
                            "batch_id"
                        ]
                    ):

                        continue

                    # ---------------------------------------
                    # EVENTO NORMAL
                    # ---------------------------------------

                    if (
                        message_type
                        == "event"
                    ):

                        event = (
                            message[2]
                        )

                        changed = (
                            handle_processing_event(
                                event
                            )
                        )

                        if changed:

                            update_processing_summary()

                            update_processing_status()

                            page_changed = True

                    # ---------------------------------------
                    # ERROR GLOBAL
                    # ---------------------------------------

                    elif (
                        message_type
                        == "worker_error"
                    ):

                        ex = (
                            message[2]
                        )

                        error_traceback = (
                            message[3]
                        )

                        handle_worker_error(
                            ex,
                            error_traceback,
                        )

                        update_processing_summary()

                        processing_state[
                            "running"
                        ] = False

                        loading_ring.visible = (
                            False
                        )

                        upload_button.disabled = (
                            False
                        )

                        ocr_primary_selector.disabled = (
                            False
                        )

                        page_changed = True

                    # ---------------------------------------
                    # FIN DEL WORKER
                    # ---------------------------------------

                    elif (
                        message_type
                        == "finished"
                    ):

                        processing_state[
                            "running"
                        ] = False

                        loading_ring.visible = (
                            False
                        )

                        upload_button.disabled = (
                            False
                        )

                        ocr_primary_selector.disabled = (
                            False
                        )

                        update_processing_summary()

                        update_processing_status()

                        page_changed = True

            except Empty:

                pass

            except Exception as ex:

                print(
                    "Error en poller de UI:"
                )

                traceback.print_exc()

                status_text.value = (
                    "❌ Error actualizando "
                    "la interfaz: "
                    f"{ex}"
                )

                status_text.color = (
                    ft.Colors.RED
                )

                page_changed = True

            if page_changed:

                try:

                    page.update()

                except Exception:

                    # Si la página ya fue cerrada, no intentamos
                    # seguir pintándola.
                    return

            await asyncio.sleep(
                PROCESSING_UI_POLL_INTERVAL
            )


    # ========================================================
    # INICIALIZAR LOTE
    # ========================================================

    def initialize_processing_batch(
        paths: list[str],
        names: list[str],
    ):

        # ----------------------------------------------------
        # NUEVO BATCH
        # ----------------------------------------------------

        processing_state[
            "batch_id"
        ] += 1

        processing_state[
            "running"
        ] = True

        # ----------------------------------------------------
        # LIMPIAR ESTADO DEL BATCH ANTERIOR
        # ----------------------------------------------------

        results.clear()

        processing_items.clear()

        # ----------------------------------------------------
        # LIMPIAR EVENTOS RESIDUALES
        # ----------------------------------------------------

        try:

            while True:

                processing_event_queue.get_nowait()

        except Empty:

            pass

        # ----------------------------------------------------
        # CREAR ESTADO INICIAL
        # ----------------------------------------------------

        for file_name in names:

            processing_items.append(

                {

                    "file_name":
                        file_name,

                    "processing_method":
                        None,

                    "status":
                        "classifying",

                    "result":
                        None,

                    "error":
                        None,
                }
            )

        # ----------------------------------------------------
        # UI INICIAL
        # ----------------------------------------------------

        loading_ring.visible = (
            True
        )

        upload_button.disabled = (
            True
        )

        ocr_primary_selector.disabled = (
            True
        )

        export_button.disabled = (
            True
        )

        dropdown_files.visible = (
            False
        )

        dropdown_files.value = (
            None
        )

        auditoria_view.controls.clear()

        status_text.value = (
            "Preparando estados "
            "de cuenta..."
        )

        status_text.color = (
            ft.Colors.ON_SURFACE
        )

        update_processing_summary()

        update_processing_status()

        page.update()


    # ========================================================
    # INICIAR WORKER
    # ========================================================

    def start_processing_worker(
        paths: list[str],
        names: list[str],
        ocr_primary_engine: str,
    ):

        batch_id = (
            processing_state[
                "batch_id"
            ]
        )

        page.run_thread(
            processing_worker,
            paths,
            names,
            batch_id,
            ocr_primary_engine,
        )


    # ========================================================
    # SELECCIÓN DE ARCHIVOS
    # ========================================================

    async def pick_files(e):

        try:

            files = await (
                ft.FilePicker()
                .pick_files(
                    dialog_title=(
                        "Selecciona estados "
                        "de cuenta PDF"
                    ),
                    allow_multiple=True,
                    file_type=(
                        ft.FilePickerFileType.CUSTOM
                    ),
                    allowed_extensions=[
                        "pdf"
                    ],
                )
            )

            if not files:
                return

            paths = [

                file.path

                for file in files

                if file.path
            ]

            names = [

                file.name

                for file in files

                if file.path
            ]

            if not paths:

                status_text.value = (
                    "❌ No fue posible "
                    "obtener las rutas "
                    "de los archivos "
                    "seleccionados."
                )

                status_text.color = (
                    ft.Colors.RED
                )

                page.update()

                return

            # =================================================
            # MOSTRAR SECCIONES
            # =================================================

            auditoria_section.visible = (
                True
            )

            export_section.visible = (
                True
            )

            ocr_primary_engine = str(
                ocr_primary_selector.value or "tesseract"
            ).strip().lower()

            # =================================================
            # PREPARAR BATCH
            # =================================================

            initialize_processing_batch(
                paths,
                names,
            )

            # =================================================
            # ARRANCAR WORKER
            # =================================================

            start_processing_worker(
                paths,
                names,
                ocr_primary_engine,
            )

        except Exception as ex:

            status_text.value = (
                f"❌ Error al "
                f"seleccionar archivos: "
                f"{ex}"
            )

            status_text.color = (
                ft.Colors.RED
            )

            page.update()


    # ========================================================
    # CAMBIO DE ESTADO DE CUENTA
    # ========================================================

    def on_dropdown_change(e):

        try:

            index = int(
                e.control.value
            )

            if (
                0 <= index
                < len(results)
            ):

                render_result(
                    results[index]
                )

        except (
            TypeError,
            ValueError,
        ):

            return

        page.update()

        reset_page_scroll()


    # ========================================================
    # EXPORTACIÓN
    # ========================================================

    async def export_excel(e):

        if not results:
            return

        try:

            path = await (
                ft.FilePicker()
                .save_file(
                    dialog_title=(
                        "Guardar reporte Excel"
                    ),

                    file_name=(
                        "reporte_estados_de_"
                        "cuenta.xlsx"
                    ),

                    file_type=(
                        ft.FilePickerFileType.CUSTOM
                    ),

                    allowed_extensions=[
                        "xlsx"
                    ],
                )
            )

            if not path:
                return

            if not path.lower().endswith(
                ".xlsx"
            ):

                path += ".xlsx"

            # =================================================
            # SNAPSHOT
            # =================================================
            #
            # El snapshot contiene exclusivamente los
            # resultados que ya terminaron.
            #
            # Los OCR que todavía no hayan terminado no forman
            # parte del Excel en ese momento.
            #
            # =================================================

            results_snapshot = snapshot_results_for_export(
                results
            )

            export_button.disabled = (
                True
            )

            status_text.value = (
                "Generando archivo Excel..."
            )

            status_text.color = (
                ft.Colors.ON_SURFACE
            )

            page.update()

            def export_worker():

                try:

                    export_batch_excel(
                        results_snapshot,
                        path,
                    )

                    status_text.value = (
                        "✅ Archivo Excel "
                        "exportado correctamente."
                    )

                    status_text.color = (
                        ft.Colors.GREEN
                    )

                    try:

                        if sys.platform == "win32":

                            subprocess.run(

                                [
                                    "explorer",
                                    "/select,",
                                    path,
                                ]

                            )

                        elif (
                            sys.platform
                            == "darwin"
                        ):

                            subprocess.run(

                                [
                                    "open",
                                    "-R",
                                    path,
                                ]

                            )

                        else:

                            directory = (
                                os.path.dirname(
                                    path
                                )
                            )

                            subprocess.run(

                                [
                                    "xdg-open",
                                    directory,
                                ]

                            )

                    except Exception as folder_ex:

                        print(
                            "No se pudo "
                            "abrir la carpeta: "
                            f"{folder_ex}"
                        )

                except Exception as ex:

                    status_text.value = (
                        "❌ Error al "
                        "exportar Excel: "
                        f"{ex}"
                    )

                    status_text.color = (
                        ft.Colors.RED
                    )

                finally:

                    export_button.disabled = (
                        False
                    )

                    page.update()

            page.run_thread(
                export_worker
            )

        except Exception as ex:

            status_text.value = (
                "❌ Error al guardar "
                "el archivo: "
                f"{ex}"
            )

            status_text.color = (
                ft.Colors.RED
            )

            export_button.disabled = (
                False
            )

            page.update()


    # ========================================================
    # CONTROLES ESTÁTICOS
    # ========================================================

    upload_button = ft.FilledButton(
        content=(
            "Seleccionar estados "
            "de cuenta PDF"
        ),
        icon=ft.Icons.UPLOAD_FILE,
        on_click=pick_files,
        bgcolor=GOB_GREEN,
        color=BUTTON_TEXT,
    )

    feedback_button = ft.FilledButton(
        content="Ayuda",
        icon=ft.Icons.HELP_OUTLINE,
        on_click=show_feedback,
        bgcolor=GOB_GOLD,
        color=BUTTON_TEXT,
    )

    export_button.on_click = (
        export_excel
    )

    dropdown_files.on_select = (
        on_dropdown_change
    )


    # ========================================================
    # LOGO
    # ========================================================

    header_controls = []

    if LOGO_PATH.exists():

        header_controls.append(

            ft.Container(

                content=ft.Image(
                    src=str(
                        LOGO_PATH
                    ),
                    width=180,
                    height=120,
                    fit=ft.BoxFit.CONTAIN,
                ),

                width=185,
                height=125,

                alignment=(
                    ft.Alignment.CENTER
                ),
            )
        )

    header_controls.append(

        ft.Column(

            controls=[

                ft.Text(
                    "Secretaría "
                    "Anticorrupción "
                    "y Buen Gobierno",
                    size=13,
                    weight=(
                        ft.FontWeight.W_500
                    ),
                ),

                ft.Text(
                    "Dirección General "
                    "de Evaluación "
                    "de Confianza",
                    size=11,
                    weight=(
                        ft.FontWeight.W_500
                    ),
                ),

                ft.Text(
                    "Departamento de "
                    "Investigación de "
                    "Antecedentes",
                    size=10,
                    weight=(
                        ft.FontWeight.W_500
                    ),
                ),
            ],

            spacing=2,

            expand=True,
        )
    )


    # ========================================================
    # SECCIÓN AUDITORÍA
    # ========================================================

    auditoria_section = ft.Column(

        controls=[

            ft.Text(
                "🔍 Auditoría "
                "de Resultados",
                size=24,
                weight=(
                    ft.FontWeight.BOLD
                ),
            ),

            ft.Row(

                controls=[

                    processing_summary_view,

                    ft.Container(

                        content=dropdown_files,

                        width=390,

                        padding=10,
                    ),
                ],

                vertical_alignment=(
                    ft.CrossAxisAlignment.START
                ),

                spacing=15,
            ),

            auditoria_view,
        ],

        spacing=0,

        visible=False,
    )


    # ========================================================
    # SECCIÓN EXPORTACIÓN
    # ========================================================

    export_section = ft.Column(

        controls=[

            ft.Divider(),

            ft.Text(
                "📤 Exportar Todos "
                "los Resultados "
                "a Excel",
                size=24,
                weight=(
                    ft.FontWeight.BOLD
                ),
            ),

            ft.Container(

                content=ft.Text(

                    "Haz clic en el botón "
                    "para generar un único "
                    "archivo Excel con los "
                    "datos de todos los "
                    "estados de cuenta "
                    "procesados."
                ),

                padding=ft.Padding.only(
                    bottom=10
                ),
            ),

            export_button,

            ft.Container(
                height=50
            ),
        ],

        spacing=0,

        visible=False,
    )


    # ========================================================
    # CONTENIDO PRINCIPAL
    # ========================================================

    app_content = ft.Column(

        controls=[

            # ------------------------------------------------
            # ENCABEZADO
            # ------------------------------------------------

            ft.Row(

                controls=header_controls,

                vertical_alignment=(
                    ft.CrossAxisAlignment.CENTER
                ),
            ),

            ft.Divider(
                height=10
            ),

            # ------------------------------------------------
            # TÍTULO
            # ------------------------------------------------

            ft.Row(

                controls=[

                    ft.Text(
                        "📄 Extractor "
                        "de Movimientos "
                        "Financieros",
                        size=32,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                    ),

                    ft.Row(

                        controls=[

                            ft.Text(
                                "Versión 2.0",
                                weight=(
                                    ft.FontWeight.BOLD
                                ),
                            ),

                            feedback_button,
                        ],

                        vertical_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),

                        spacing=10,
                    ),
                ],

                alignment=(
                    ft.MainAxisAlignment
                    .SPACE_BETWEEN
                ),
            ),

            ft.Divider(),

            # ------------------------------------------------
            # CONTROLES
            # ------------------------------------------------

            ft.Row(

                controls=[

                    ocr_primary_selector,

                    upload_button,

                    loading_ring,

                    status_text,
                ],

                vertical_alignment=(
                    ft.CrossAxisAlignment.CENTER
                ),

                spacing=10,
            ),

            # ------------------------------------------------
            # AUDITORÍA
            # ------------------------------------------------

            auditoria_section,

            # ------------------------------------------------
            # EXPORTACIÓN
            # ------------------------------------------------

            export_section,
        ],

        spacing=0,
    )


    # ========================================================
    # ESCALA GLOBAL
    # ========================================================

    UI_SCALE = 0.85

    app_content.scale = ft.Scale(
        scale=UI_SCALE,
        alignment=ft.Alignment.TOP_LEFT,
    )


    # ========================================================
    # ARRANCAR POLLER DE UI
    # ========================================================
    #
    # Este task permanece escuchando la Queue durante toda
    # la vida de la aplicación.
    #
    # ========================================================

    page.run_task(
        processing_ui_poller
    )


    # ========================================================
    # AGREGAR APP
    # ========================================================

    page.add(
        app_content
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    # ft.app(target=main)

    ft.run(main)