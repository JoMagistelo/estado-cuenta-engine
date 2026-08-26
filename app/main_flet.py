#flet pack app\main_flet.py --name EstadoCuentaEngine
#pyinstaller EstadoCuentaEngine.spec
from __future__ import annotations

import os
import sys
import subprocess
import traceback
from pathlib import Path
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

from engine.pipeline import process_bank_statements
from exporters.excel import export_batch_excel


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
    """
    Formatea un valor que puede ser:
    - float/int
    - None
    - string numérico
    - string como 'N/A'
    """
    if value is None:
        return na_value

    if isinstance(value, str):
        try:
            numeric_value = float(value.replace(",", ""))
        except (ValueError, TypeError):
            return value
    else:
        numeric_value = value

    formatted_value = format_str.format(numeric_value)

    return f"{prefix}{formatted_value}{suffix}"


def create_metric(
    title: str,
    value: str,
    delta: str | None = None,
) -> ft.Container:
    """
    Equivalente visual aproximado a st.metric().
    """

    controls = [
        ft.Text(
            title,
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500,
        ),
        ft.Text(
            value,
            size=20,
            weight=ft.FontWeight.BOLD,
        ),
    ]

    if delta is not None:
        if delta.startswith("-"):
            delta_color = ft.Colors.ERROR
        elif delta.startswith("0.00"):
            delta_color = ft.Colors.ON_SURFACE_VARIANT
        else:
            delta_color = ft.Colors.GREEN

        controls.append(
            ft.Text(
                delta,
                size=13,
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


def safe_value(value: Any) -> str:
    """
    Convierte None en N/A y deja los demás valores como texto.
    """
    if value is None or value == "":
        return "N/A"

    return str(value)


def format_money(value: Any) -> str:
    if value is None:
        return "N/A"

    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


# ============================================================
# APP
# ============================================================

def main(page: ft.Page):

    # ========================================================
    # CONFIGURACIÓN
    # ========================================================

    page.title = "Motor de Estados de Cuenta"
    page.window.width = 1100
    page.window.height = 800
    page.padding = 18
    page.theme_mode = ft.ThemeMode.LIGHT

    # Scroll global de la aplicación
    page.scroll = ft.ScrollMode.AUTO

    # ========================================================
    # ESTADO
    # ========================================================

    results = []

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

    dropdown_files = ft.Dropdown(
        label="Selecciona el estado de cuenta que deseas revisar",
        width=390,
        visible=False,
    )

    # ========================================================
    # RESUMEN DE ARCHIVOS PROCESADOS
    # ========================================================

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
    )

    # ========================================================
    # FUNCIONES: RESUMEN DE PROCESAMIENTO
    # ========================================================

    def get_validation_result(
        result,
        validation_name: str,
    ):
        """
        Busca una validación concreta por nombre.

        No depende de la posición de la validación dentro de
        result.validaciones.
        """

        for validacion in result.validaciones:

            if validacion.nombre == validation_name:
                return validacion

        return None


    def create_validation_status(
        validacion,
    ) -> ft.Container:
        """
        Construye visualmente el resultado de una validación.

        Estados:

            ✅ correcta -> verde
            ❌ incorrecta -> rojo
            — no disponible -> neutro
        """

        if validacion is None:

            return ft.Container(
                content=ft.Text(
                    "—",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                padding=8,
                border_radius=6,
                alignment=ft.Alignment.CENTER,
            )

        if validacion.correcto:

            return ft.Container(
                content=ft.Text(
                    "✅",
                    size=16,
                    text_align=ft.TextAlign.CENTER,
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


    def create_processing_method_status(
        processing_method: str,
    ) -> ft.Container:
        """
        Representa visualmente el método de procesamiento.
        """

        if processing_method.upper() == "OCR":

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


    def create_processing_summary(
        processed_results,
    ) -> ft.Container:
        """
        Construye la tabla resumen de archivos procesados.

        Columnas:

            Archivo
            Proceso
            Abonos
            Cargos

        Las validaciones mostradas son exclusivamente:

            Total depósitos / abonos
            Total retiros / cargos
        """

        rows = []

        for result in processed_results:

            validacion_abonos = get_validation_result(
                result,
                "Total depósitos / abonos",
            )

            validacion_cargos = get_validation_result(
                result,
                "Total retiros / cargos",
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            content=ft.Text(
                                result.file_name,
                                size=12,
                            )
                        ),
                        ft.DataCell(
                            content=create_processing_method_status(
                                result.processing_method
                            )
                        ),
                        ft.DataCell(
                            content=create_validation_status(
                                validacion_abonos
                            )
                        ),
                        ft.DataCell(
                            content=create_validation_status(
                                validacion_cargos
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(
                    label=ft.Text(
                        "Archivo",
                        weight=ft.FontWeight.BOLD,
                    )
                ),
                ft.DataColumn(
                    label=ft.Text(
                        "Proceso",
                        weight=ft.FontWeight.BOLD,
                    )
                ),
                ft.DataColumn(
                    label=ft.Text(
                        "Abonos",
                        weight=ft.FontWeight.BOLD,
                    )
                ),
                ft.DataColumn(
                    label=ft.Text(
                        "Cargos",
                        weight=ft.FontWeight.BOLD,
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
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Row(
                        controls=[
                            table
                        ],
                        scroll=ft.ScrollMode.AUTO,
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
        """
        Actualiza la tabla resumen utilizando el estado actual
        de results.
        """

        if not results:

            processing_summary_view.content = None
            processing_summary_view.visible = False

            return

        processing_summary_view.content = (
            create_processing_summary(
                results
            )
        )

        processing_summary_view.visible = True


    # ========================================================
    # FUNCIÓN: RENDER IMAGEN
    # ========================================================

    def render_image_document(result):

        auditoria_view.controls.clear()

        auditoria_view.controls.extend(
            [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "🖼️ Se detectó que este documento es una imagen o un PDF escaneado.",
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ON_ERROR_CONTAINER,
                            ),
                        ],
                    ),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    padding=15,
                    border_radius=8,
                ),

                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "🚧 El motor detectó correctamente que el archivo es un PDF basado en imagen.",
                                color=ft.Colors.ON_SECONDARY_CONTAINER,
                            ),
                            ft.Text(
                                "La extracción de datos mediante OCR está pendiente de implementación.",
                                color=ft.Colors.ON_SECONDARY_CONTAINER,
                            ),
                        ],
                    ),
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                    padding=15,
                    border_radius=8,
                ),

                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Estado del procesamiento",
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text("📄 Tipo: PDF basado en imagen"),
                            ft.Text("🖼️ Detección: correcta"),
                            ft.Text("🔎 OCR: pendiente de implementación"),
                            ft.Text("🏦 Detección de banco: pendiente de OCR"),
                            ft.Text("📊 Extracción financiera: pendiente de OCR"),
                        ],
                        spacing=5,
                    ),
                    padding=15,
                ),
            ]
        )


    # ========================================================
    # FUNCIÓN: TABLA DE MOVIMIENTOS
    # ========================================================

    def create_movements_table(
        movimientos,
        fecha_corte_documento: str | None = None,
        numero_cuenta_documento: str | None = None,
    ) -> ft.Column:
        """
        Crea una tabla de datos (DataTable) para mostrar los movimientos.

        Nota sobre el "No. de Movimiento":
        El modelo de datos `Movimiento` que viene del motor de procesamiento
        no incluye un número de movimiento secuencial (ej. 1, 2, 3...).
        Para poder mostrar un número de fila en la tabla, este se genera
        dinámicamente en esta función usando `enumerate()` al momento de
        crear las filas. Esto evita modificar el modelo de datos del backend
        solo por una necesidad de la interfaz de usuario.
        Lo mismo con la fecha de corte, se imprime en el fronted pero pertenece al modelo de datos de la cuenta.
        """

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
            "autorizacion",
            "hora_operacion",
        ]

        columnas_existentes: list[str] = []

        if movimientos:
            movimiento_prueba = movimientos[0]

            for columna in columnas_mostrar:

                if columna == "numero_movimiento":
                    columnas_existentes.append(columna)

                elif (
                    columna == "fecha_corte"
                    and fecha_corte_documento
                ):
                    columnas_existentes.append(columna)

                elif (
                    columna == "numero_cuenta"
                    and numero_cuenta_documento
                ):
                    columnas_existentes.append(columna)

                elif hasattr(
                    movimiento_prueba,
                    columna,
                ):
                    columnas_existentes.append(columna)

        columns = []

        for columna in columnas_existentes:

            nombres = {
                "fecha_corte": "Fecha Corte",
                "numero_cuenta": "Número de Cuenta",
                "fecha_operacion": "Fecha Operación",
                "fecha_liquidacion": "Fecha Liquidación",
                "concepto": "Concepto",
                "numero_movimiento": "No. Movimiento",
                "cargo": "Cargo",
                "abono": "Abono",
                "saldo_operacion": "Saldo Operación",
                "saldo_liquidacion": "Saldo Liquidación",
                "tipo_operacion": "Tipo",
                "beneficiario": "Beneficiario",
                "cuenta_beneficiario": "Cuenta Benef.",
                "clabe_beneficiario": "CLABE",
                "rfc": "RFC",
                "referencia": "Referencia",
                "autorizacion": "Autorización",
                "hora_operacion": "Hora",
            }

            columns.append(
                ft.DataColumn(
                    label=ft.Text(
                        nombres.get(
                            columna,
                            columna.replace(
                                "_",
                                " ",
                            ).title(),
                        ),
                        weight=ft.FontWeight.BOLD,
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

                if columna == "numero_movimiento":
                    value = index

                elif columna == "fecha_corte":
                    value = fecha_corte_documento

                elif columna == "numero_cuenta":
                    value = numero_cuenta_documento

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
                            size=13,
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
            column_spacing=20,
        )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[table],
                    scroll=ft.ScrollMode.ALWAYS,
                )
            ],
            scroll=ft.ScrollMode.ALWAYS,
            height=500,
        )


    # ========================================================
    # FUNCIÓN: RENDER RESULTADO
    # ========================================================

    def render_result(result):

        auditoria_view.controls.clear()

        if result is None:
            page.update()
            return

        estado = result.estado_cuenta

        # ====================================================
        # DOCUMENTO IMAGEN
        # ====================================================

        if result.bank_key == "imagen_no_procesada":

            render_image_document(result)

            page.update()

            return

        # ====================================================
        # DOCUMENTO DIGITAL
        # ====================================================

        auditoria_view.controls.append(
            ft.Text(
                f"Banco Detectado: {result.bank_key.upper()}",
                size=20,
                weight=ft.FontWeight.BOLD,
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
            f"{dc.periodo_inicio} al {dc.periodo_fin}"
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

            rf = estado.resumen_financiero

            dias_periodo = (
                safe_value(rf.dias_periodo)
                if rf
                else "N/A"
            )

            tasa_bruta = (
                f"{safe_value(rf.tasa_bruta_anual)}%"
                if rf
                else "N/A"
            )

            datos_cuenta = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    f"Producto: {safe_value(dc.producto_principal)}"
                                ),
                                ft.Text(
                                    f"No. Cliente: {safe_value(dc.numero_cliente)}"
                                ),
                            ],
                            expand=True,
                        ),

                        ft.Column(
                            controls=[
                                ft.Text(
                                    f"RFC: {safe_value(dc.rfc)}"
                                ),
                                ft.Text(
                                    f"Fecha de Corte: {safe_value(dc.fecha_corte)}"
                                ),
                            ],
                            expand=True,
                        ),

                        ft.Column(
                            controls=[
                                ft.Text(
                                    f"Días del Periodo: {dias_periodo}"
                                ),
                                ft.Text(
                                    f"Tasa Bruta Anual: {tasa_bruta}"
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
                        "⚠️ No se encontraron datos de la cuenta."
                    ),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
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

        rf = estado.resumen_financiero

        if rf:

            saldo_anterior = rf.saldo_anterior or 0
            saldo_final = rf.saldo_final or 0
            delta_val = saldo_final - saldo_anterior

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

            # -----------------------------------------------
            # DETALLES ADICIONALES
            # -----------------------------------------------

            auditoria_view.controls.append(
                ft.ExpansionTile(
                    title=ft.Text(
                        "Ver más detalles del resumen financiero"
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
                        "⚠️ No se encontró el resumen financiero."
                    ),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
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

        op = estado.otros_productos

        if op:

            otros_productos = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Producto de Inversión: "
                            f"{safe_value(op.producto)} "
                            f"(Contrato: {safe_value(op.contrato)})",
                            weight=ft.FontWeight.BOLD,
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
                        "No se encontraron otros productos "
                        "o comisiones en este estado de cuenta."
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
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
                for validacion in result.validaciones
                if validacion.correcto
            )

            total = len(
                result.validaciones
            )

            validaciones_controls = [
                ft.Text(
                    f"Integridad financiera: "
                    f"{correctas}/{total} validaciones correctas",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                )
            ]

            for validacion in result.validaciones:

                if validacion.correcto:
                    icono = "✅"
                    color = ft.Colors.GREEN
                else:
                    icono = "❌"
                    color = ft.Colors.RED

                esperado = (
                    format_money(
                        validacion.esperado
                    )
                )

                obtenido = (
                    format_money(
                        validacion.obtenido
                    )
                )

                diferencia = (
                    format_money(
                        validacion.diferencia
                    )
                )

                validaciones_controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(
                            f"{icono} {validacion.nombre}",
                            color=color,
                        ),
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            f"Esperado: {esperado}"
                                        ),
                                        ft.Text(
                                            f"Obtenido: {obtenido}"
                                        ),
                                        ft.Text(
                                            f"Diferencia: {diferencia}"
                                        ),
                                        ft.Text(
                                            safe_value(
                                                validacion.mensaje
                                            ),
                                            italic=True,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
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
                        weight=ft.FontWeight.BOLD,
                    ),
                    expanded=False,
                    controls=validaciones_controls,
                )
            )

        # ====================================================
        # 5. MOVIMIENTOS
        # ====================================================

        movimientos = estado.movimientos or []

        auditoria_view.controls.append(
            create_section_title(
                f"5. Movimientos ({len(movimientos)})",
                "📑",
            )
        )

        if movimientos:

            auditoria_view.controls.append(
                create_movements_table(
                    movimientos,
                    fecha_corte_documento=dc.fecha_corte if dc else None,
                    numero_cuenta_documento=dc.numero_cuenta if dc else None,
                )
            )

        else:

            auditoria_view.controls.append(
                ft.Container(
                    content=ft.Text(
                        "⚠️ No se encontraron movimientos "
                        "en este documento."
                    ),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    padding=15,
                    border_radius=8,
                )
            )


    # ========================================================
    # PROCESAMIENTO
    # ========================================================

    def process_selected_files(
        paths: list[str],
        names: list[str],
    ):

        loading_ring.visible = True
        status_text.value = "Procesando estados de cuenta..."
        status_text.color = ft.Colors.ON_SURFACE
        upload_button.disabled = True

        page.update()

        try:

            processed_results = process_bank_statements(
                paths,
                names,
            )

            results.clear()
            results.extend(
                processed_results
            )

            # =================================================
            # ACTUALIZAR RESUMEN DE ARCHIVOS
            # =================================================

            update_processing_summary()

            # =================================================
            # ACTUALIZAR SELECTOR
            # =================================================

            dropdown_files.options = [
                ft.DropdownOption(
                    key=str(index),
                    text=result.file_name,
                )
                for index, result in enumerate(results)
            ]

            if results:

                dropdown_files.value = "0"
                dropdown_files.visible = True

                export_button.disabled = False

                status_text.value = (
                    f"✅ {len(results)} estados de cuenta "
                    f"procesados correctamente."
                )

                status_text.color = ft.Colors.GREEN

                render_result(
                    results[0]
                )

            else:

                dropdown_files.visible = False
                export_button.disabled = True

                status_text.value = (
                    "⚠️ No se obtuvieron resultados."
                )

                auditoria_view.controls.clear()

                auditoria_view.controls.append(
                    ft.Text(
                        "No se encontraron estados de cuenta procesables."
                    )
                )

        except Exception as ex:

            status_text.value = (
                f"❌ Error durante el procesamiento: {ex}"
            )

            status_text.color = ft.Colors.RED

            auditoria_view.controls.clear()

            auditoria_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Error durante el procesamiento",
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ERROR,
                            ),
                            ft.Text(
                                str(ex)
                            ),
                            ft.Text(
                                traceback.format_exc(),
                                selectable=True,
                                size=12,
                            ),
                        ]
                    ),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    padding=15,
                    border_radius=8,
                )
            )

        finally:

            loading_ring.visible = False
            upload_button.disabled = False

            page.update()


    # ========================================================
    # SELECCIÓN DE ARCHIVOS
    # ========================================================

    async def pick_files(e):

        try:

            files = await ft.FilePicker().pick_files(
                dialog_title="Selecciona estados de cuenta PDF",
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
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
                    "❌ No fue posible obtener las rutas "
                    "de los archivos seleccionados."
                )

                status_text.color = ft.Colors.RED

                page.update()

                return

            loading_ring.visible = True
            status_text.value = "Procesando estados de cuenta..."
            status_text.color = ft.Colors.ON_SURFACE
            upload_button.disabled = True

            page.update()

            page.run_thread(
                process_selected_files,
                paths,
                names,
            )

        except Exception as ex:

            status_text.value = (
                f"❌ Error al seleccionar archivos: {ex}"
            )

            status_text.color = ft.Colors.RED

            page.update()


    # ========================================================
    # CAMBIO DE ESTADO DE CUENTA
    # ========================================================

    def on_dropdown_change(e):

        try:

            index = int(
                e.control.value
            )

            if 0 <= index < len(results):

                render_result(
                    results[index]
                )

        except (
            TypeError,
            ValueError,
        ):
            return

        page.update()


    # ========================================================
    # EXPORTACIÓN
    # ========================================================

    async def export_excel(e):

        if not results:
            return

        try:

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

            export_button.disabled = True

            status_text.value = (
                "Generando archivo Excel..."
            )

            status_text.color = ft.Colors.ON_SURFACE

            page.update()

            def export_worker():

                try:

                    export_batch_excel(
                        results,
                        path,
                    )

                    status_text.value = (
                        "✅ Archivo Excel exportado correctamente."
                    )

                    status_text.color = ft.Colors.GREEN

                    try:

                        if sys.platform == "win32":

                            subprocess.run(
                                [
                                    "explorer",
                                    "/select,",
                                    path,
                                ]
                            )

                        elif sys.platform == "darwin":

                            subprocess.run(
                                [
                                    "open",
                                    "-R",
                                    path,
                                ]
                            )

                        else:

                            directory = os.path.dirname(
                                path
                            )

                            subprocess.run(
                                [
                                    "xdg-open",
                                    directory,
                                ]
                            )

                    except Exception as folder_ex:

                        print(
                            f"No se pudo abrir la carpeta: {folder_ex}"
                        )

                except Exception as ex:

                    status_text.value = (
                        f"❌ Error al exportar Excel: {ex}"
                    )

                    status_text.color = ft.Colors.RED

                finally:

                    export_button.disabled = False

                    page.update()

            page.run_thread(
                export_worker
            )

        except Exception as ex:

            status_text.value = (
                f"❌ Error al guardar el archivo: {ex}"
            )

            status_text.color = ft.Colors.RED

            export_button.disabled = False

            page.update()


    # ========================================================
    # CONTROLES ESTÁTICOS
    # ========================================================

    upload_button = ft.FilledButton(
        content="Seleccionar estados de cuenta PDF",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=pick_files,
    )

    export_button.on_click = export_excel

    dropdown_files.on_select = on_dropdown_change


    # ========================================================
    # UI
    # ========================================================

    page.add(

        ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(
                            "Secretaría Anticorrupción y Buen Gobierno",
                            size=15,
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(
                            "Dirección General de Evaluación de Confianza",
                            size=13,
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(
                            "Departamento de Investigación de Antecedentes",
                            size=13,
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(
                            "Bancos habilitados (v1.0.3): BBVA, Banorte y Banamex Próximamente (v1.2.0): Estados de cuenta escaneados de: BBVA, Banamex, HSBC.",
                            size=10,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=2,
                ),
            ],
        ),

        ft.Divider(height=10),

        ft.Row(
            controls=[
                ft.Text(
                    "📄 Motor de Estados de Cuenta",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Versión 1.0.3"
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),

        ft.Divider(),

        ft.Row(
            controls=[
                upload_button,
                loading_ring,
                status_text,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),

        ft.Divider(),

        ft.Text(
            "🔍 Auditoría de Resultados",
            size=24,
            weight=ft.FontWeight.BOLD,
        ),

        # ====================================================
        # TABLA + SELECTOR
        # ====================================================

        ft.Row(
            controls=[
                processing_summary_view,

                ft.Container(
                    content=dropdown_files,
                    width=390,
                    padding=10,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=15,
        ),

        auditoria_view,

        ft.Divider(),

        ft.Text(
            "📤 Exportar Todos los Resultados a Excel",
            size=24,
            weight=ft.FontWeight.BOLD,
        ),

        ft.Container(
            content=ft.Text(
                "Haz clic en el botón para generar un único archivo "
                "Excel con los datos de todos los estados de cuenta "
                "procesados."
            ),
            padding=ft.Padding.only(
                bottom=10,
            ),
        ),

        export_button,

        ft.Container(
            height=50,
        ),
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    #ft.app(target=main)
    ft.run(main)