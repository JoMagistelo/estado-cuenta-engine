from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import pandas as pd
import streamlit as st


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


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROCESSING_UI_POLL_INTERVAL = 0.5


# ============================================================
# ESTADO DE SESIÓN
# ============================================================

def initialize_session_state() -> None:
    """
    Inicializa todo el estado necesario para administrar un lote
    de procesamiento en segundo plano.

    El Queue y el worker pertenecen exclusivamente a la sesión
    actual del usuario.
    """

    defaults = {
        "processing_queue": Queue(),
        "processing_items": [],
        "results": [],
        "worker_thread": None,
        "worker_running": False,
        "worker_finished": False,
        "worker_error": None,
        "worker_traceback": None,
        "batch_signature": None,
        "batch_temp_paths": [],
        "selected_file": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


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
        - string como N/A
    """

    if value is None:
        return na_value

    if isinstance(value, str):
        try:
            numeric_value = float(
                value.replace(",", "")
            )
        except (
            ValueError,
            TypeError,
        ):
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


def safe_value(
    value: Any,
) -> str:

    if value is None or value == "":
        return "N/A"

    return str(value)


# ============================================================
# IDENTIFICACIÓN DE LOTE
# ============================================================

def create_batch_signature(
    uploaded_files_data: tuple[
        tuple[str, bytes],
        ...
    ],
) -> tuple[
    tuple[str, int, str],
    ...
]:
    """
    Crea una identidad estable para el conjunto de archivos.

    El hash SHA-256 evita que dos archivos con el mismo nombre y
    tamaño se consideren necesariamente el mismo contenido.
    """

    signature = []

    for file_name, file_bytes in uploaded_files_data:

        digest = hashlib.sha256(
            file_bytes
        ).hexdigest()

        signature.append(
            (
                file_name,
                len(file_bytes),
                digest,
            )
        )

    return tuple(signature)


# ============================================================
# LIMPIEZA DE ARCHIVOS TEMPORALES
# ============================================================

def cleanup_temp_paths(
    paths: list[str],
) -> None:

    for path in paths:

        try:
            os.remove(path)

        except FileNotFoundError:
            pass

        except OSError:
            pass


# ============================================================
# PREPARAR ARCHIVOS
# ============================================================

def materialize_uploaded_files(
    uploaded_files_data: tuple[
        tuple[str, bytes],
        ...
    ],
) -> list[str]:
    """
    Copia los PDFs subidos a archivos temporales.

    El worker trabaja exclusivamente con esas rutas.
    """

    temp_paths: list[str] = []

    try:

        for file_name, file_bytes in (
            uploaded_files_data
        ):

            suffix = (
                Path(file_name).suffix
                or ".pdf"
            )

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as tmp:

                tmp.write(
                    file_bytes
                )

                temp_paths.append(
                    tmp.name
                )

        return temp_paths

    except Exception:

        cleanup_temp_paths(
            temp_paths
        )

        raise


# ============================================================
# WORKER
# ============================================================

def processing_worker(
    temp_paths: list[str],
    names: list[str],
    processing_queue: Queue,
) -> None:
    """
    Ejecuta el pipeline en segundo plano.

    IMPORTANTE:

    Este hilo NO utiliza Streamlit.
    No llama st.*.
    No modifica st.session_state.

    Únicamente publica eventos en Queue.
    """

    try:

        for event in (
            process_bank_statements_incremental(
                temp_paths,
                names,
            )
        ):

            processing_queue.put(
                (
                    "event",
                    event,
                )
            )

    except Exception as ex:

        processing_queue.put(
            (
                "worker_error",
                ex,
                traceback_string(
                    ex
                ),
            )
        )

    finally:

        processing_queue.put(
            (
                "finished",
            )
        )

        cleanup_temp_paths(
            temp_paths
        )


def traceback_string(
    ex: Exception,
) -> str:
    """
    Construye el traceback del worker sin importar
    traceback globalmente en todo el módulo.
    """

    import traceback

    return traceback.format_exc()


# ============================================================
# INICIAR PROCESAMIENTO
# ============================================================

def start_processing(
    uploaded_files_data: tuple[
        tuple[str, bytes],
        ...
    ],
) -> None:

    temp_paths = materialize_uploaded_files(
        uploaded_files_data
    )

    processing_items = []

    for file_name, _ in uploaded_files_data:

        processing_items.append(
            {
                "file_name": file_name,
                "processing_method": None,
                "status": "classifying",
                "result": None,
                "error": None,
            }
        )

    processing_queue = Queue()

    batch_signature = create_batch_signature(
        uploaded_files_data
    )

    worker = threading.Thread(
        target=processing_worker,
        args=(
            temp_paths,
            [
                file_name
                for file_name, _
                in uploaded_files_data
            ],
            processing_queue,
        ),
        daemon=True,
    )

    # --------------------------------------------------------
    # ESTADO DE SESIÓN
    # --------------------------------------------------------

    st.session_state.processing_queue = (
        processing_queue
    )

    st.session_state.processing_items = (
        processing_items
    )

    st.session_state.results = []

    st.session_state.worker_thread = (
        worker
    )

    st.session_state.worker_running = (
        True
    )

    st.session_state.worker_finished = (
        False
    )

    st.session_state.worker_error = (
        None
    )

    st.session_state.worker_traceback = (
        None
    )

    st.session_state.batch_signature = (
        batch_signature
    )

    st.session_state.batch_temp_paths = (
        temp_paths
    )

    st.session_state.selected_file = (
        None
    )

    worker.start()


# ============================================================
# PROCESAR EVENTOS
# ============================================================

def consume_processing_events() -> bool:
    """
    Consume todos los eventos disponibles de la Queue.

    Devuelve True si la interfaz sufrió algún cambio.
    """

    changed = False

    queue = (
        st.session_state.processing_queue
    )

    items = (
        st.session_state.processing_items
    )

    results = (
        st.session_state.results
    )

    while True:

        try:

            message = (
                queue.get_nowait()
            )

        except Empty:

            break

        message_type = message[0]

        # ====================================================
        # EVENTO NORMAL
        # ====================================================

        if message_type == "event":

            event = message[1]

            index = getattr(
                event,
                "index",
                None,
            )

            if not isinstance(
                index,
                int,
            ):

                continue

            if not (
                0
                <= index
                < len(items)
            ):

                continue

            item = items[index]

            # ------------------------------------------------
            # STARTED
            # ------------------------------------------------

            if event.kind == "started":

                item["processing_method"] = (
                    event.processing_method
                )

                item["status"] = (
                    "processing"
                )

                item["error"] = None

                changed = True

            # ------------------------------------------------
            # COMPLETED
            # ------------------------------------------------

            elif event.kind == "completed":

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

                if result is not None:

                    results.append(
                        result
                    )

                changed = True

            # ------------------------------------------------
            # ERROR INDIVIDUAL
            # ------------------------------------------------

            elif event.kind == "error":

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
                    else "Error desconocido."
                )

                changed = True

        # ====================================================
        # ERROR GLOBAL
        # ====================================================

        elif message_type == "worker_error":

            ex = message[1]
            error_traceback = message[2]

            st.session_state.worker_error = (
                str(ex)
            )

            st.session_state.worker_traceback = (
                error_traceback
            )

            for item in items:

                if item.get("status") not in {
                    "completed",
                    "error",
                }:

                    item["status"] = (
                        "error"
                    )

                    item["error"] = (
                        str(ex)
                    )

            changed = True

        # ====================================================
        # FINISHED
        # ====================================================

        elif message_type == "finished":

            st.session_state.worker_running = (
                False
            )

            st.session_state.worker_finished = (
                True
            )

            changed = True

    return changed


# ============================================================
# ESTADO DEL LOTE
# ============================================================

def get_processing_counts() -> tuple[
    int,
    int,
    int,
    int,
]:
    """
    Devuelve:

        total
        completados
        errores
        pendientes
    """

    items = (
        st.session_state.processing_items
    )

    total = len(items)

    completed = sum(
        1
        for item in items
        if item.get("status")
        == "completed"
    )

    errors = sum(
        1
        for item in items
        if item.get("status")
        == "error"
    )

    pending = (
        total
        - completed
        - errors
    )

    return (
        total,
        completed,
        errors,
        pending,
    )


def get_ocr_pending_count() -> int:

    return sum(
        1
        for item
        in st.session_state.processing_items

        if (
            item.get("status")
            == "processing"

            and item.get(
                "processing_method"
            )
            == "OCR"
        )
    )


def render_processing_status() -> None:

    total, completed, errors, pending = (
        get_processing_counts()
    )

    ocr_pending = (
        get_ocr_pending_count()
    )

    if pending > 0:

        message = (
            f"Procesando "
            f"{completed} de "
            f"{total} archivos"
        )

        if ocr_pending:

            message += (
                f" · {ocr_pending} "
                f"OCR en segundo plano"
            )

        if errors:

            message += (
                f" · {errors} con error"
            )

        st.info(
            message
        )

        return

    if errors == 0:

        st.success(
            f"✅ {completed} estados "
            f"de cuenta procesados "
            f"correctamente."
        )

    elif completed > 0:

        st.warning(
            f"✅ {completed} estados "
            f"de cuenta procesados "
            f"correctamente. "
            f"⚠️ {errors} con error."
        )

    else:

        st.error(
            f"❌ No fue posible "
            f"procesar los "
            f"{errors} archivos "
            f"seleccionados."
        )


# ============================================================
# TABLA RESUMEN
# ============================================================

def render_processing_summary() -> None:
    """
    Muestra todos los archivos seleccionados.

    No importa si todavía no terminaron.
    """

    items = (
        st.session_state.processing_items
    )

    if not items:

        return

    st.subheader(
        "📋 Estado del procesamiento"
    )

    rows = []

    for item in items:

        method = (
            item.get(
                "processing_method"
            )
        )

        status = (
            item.get(
                "status"
            )
        )

        file_name = (
            item.get(
                "file_name",
                "",
            )
        )

        if method:

            process_display = (
                method
            )

        else:

            process_display = (
                "Detectando..."
            )

        if status == "completed":

            status_display = "✅ Terminado"

        elif status == "error":

            status_display = "❌ Error"

        elif status == "processing":

            status_display = "⏳ Procesando"

        else:

            status_display = "⏳ Clasificando"

        rows.append(
            {
                "Archivo": file_name,
                "Proceso": process_display,
                "Estado": status_display,
            }
        )

    df = pd.DataFrame(
        rows
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# SELECTOR
# ============================================================

def get_completed_results() -> list[Any]:

    return list(
        st.session_state.results
    )


def render_result_selector():

    results = get_completed_results()

    if not results:

        st.info(
            "Aún no hay estados de cuenta "
            "terminados para revisar."
        )

        return None

    file_options = [
        result.file_name
        for result in results
    ]

    # --------------------------------------------------------
    # MANTENER SELECCIÓN
    # --------------------------------------------------------

    current_selected = (
        st.session_state.selected_file
    )

    if (
        current_selected
        not in file_options
    ):

        current_selected = (
            file_options[0]
        )

        st.session_state.selected_file = (
            current_selected
        )

    selected_file = st.selectbox(

        "Selecciona el estado de cuenta "
        "que deseas revisar:",

        options=file_options,

        index=file_options.index(
            current_selected
        ),

        key="selected_file_key",
    )

    st.session_state.selected_file = (
        selected_file
    )

    for result in results:

        if (
            result.file_name
            == selected_file
        ):

            return result

    return None


# ============================================================
# RENDER DOCUMENTO IMAGEN
# ============================================================

def render_image_document(
    result,
) -> None:

    st.warning(
        "🖼️ Se detectó que este documento "
        "es una imagen o un PDF escaneado."
    )

    st.info(
        "🚧 El motor detectó correctamente "
        "que el archivo es un PDF basado "
        "en imagen. La extracción de datos "
        "mediante OCR está pendiente de "
        "implementación."
    )

    st.markdown(
        """
        **Estado del procesamiento**

        - 📄 Tipo: PDF basado en imagen
        - 🖼️ Detección: correcta
        - 🔎 OCR: pendiente de implementación
        - 🏦 Detección de banco: pendiente de OCR
        - 📊 Extracción financiera: pendiente de OCR
        """
    )


# ============================================================
# RENDER DIGITAL
# ============================================================

def render_digital_result(
    result,
) -> None:

    estado = (
        result.estado_cuenta
    )

    if estado is None:

        st.warning(
            "No existe información de "
            "estado de cuenta para este "
            "resultado."
        )

        return

    st.markdown(
        f"#### Banco Detectado: "
        f"`{result.bank_key.upper()}`"
    )

    dc = (
        estado.datos_cuenta
    )

    # ========================================================
    # MÉTRICAS PRINCIPALES
    # ========================================================

    cols_info = st.columns(4)

    cols_info[0].metric(

        "Periodo",

        (
            f"{dc.periodo_inicio} al "
            f"{dc.periodo_fin}"
        )

        if dc

        else "N/A",
    )

    cols_info[1].metric(

        "Cliente",

        (
            dc.nombre_cliente
            or "N/A"
        )

        if dc

        else "N/A",
    )

    cols_info[2].metric(

        "Cuenta",

        (
            dc.numero_cuenta
            or "N/A"
        )

        if dc

        else "N/A",
    )

    cols_info[3].metric(

        "CLABE",

        (
            dc.clabe
            or "N/A"
        )

        if dc

        else "N/A",
    )

    # ========================================================
    # DATOS CUENTA
    # ========================================================

    st.subheader(
        "1. 📌 Datos de la Cuenta"
    )

    if dc:

        with st.container(
            border=True
        ):

            col1, col2, col3 = (
                st.columns(3)
            )

            col1.markdown(
                f"**Producto:** "
                f"{dc.producto_principal or 'N/A'}"
            )

            col1.markdown(
                f"**No. Cliente:** "
                f"{dc.numero_cliente or 'N/A'}"
            )

            col2.markdown(
                f"**RFC:** "
                f"{dc.rfc or 'N/A'}"
            )

            col2.markdown(
                f"**Fecha de Corte:** "
                f"{dc.fecha_corte or 'N/A'}"
            )

            rf = (
                estado.resumen_financiero
            )

            if rf:

                col3.markdown(
                    f"**Días del Periodo:** "
                    f"{rf.dias_periodo or 'N/A'}"
                )

                col3.markdown(
                    f"**Tasa Bruta Anual:** "
                    f"{rf.tasa_bruta_anual or 'N/A'}%"
                )

            else:

                col3.markdown(
                    "**Días del Periodo:** N/A"
                )

                col3.markdown(
                    "**Tasa Bruta Anual:** N/A"
                )

    else:

        st.warning(
            "No se encontraron datos "
            "de la cuenta."
        )

    # ========================================================
    # RESUMEN FINANCIERO
    # ========================================================

    st.subheader(
        "2. 📊 Resumen Financiero"
    )

    rf = (
        estado.resumen_financiero
    )

    if rf:

        with st.container(
            border=True
        ):

            col1, col2, col3, col4 = (
                st.columns(4)
            )

            col1.metric(
                "Saldo Anterior",
                format_money(
                    rf.saldo_anterior
                ),
            )

            col2.metric(
                "Depósitos / Abonos",
                format_money(
                    rf.depositos_abonos
                ),
            )

            col3.metric(
                "Retiros / Cargos",
                format_money(
                    rf.retiros_cargos
                ),
            )

            delta = 0.0

            try:

                delta = (
                    rf.saldo_final
                    - rf.saldo_anterior
                )

            except (
                TypeError,
                ValueError,
            ):

                delta = 0.0

            col4.metric(
                "Saldo Final",
                format_money(
                    rf.saldo_final
                ),
                delta=f"{delta:,.2f}",
            )

            st.divider()

            col_b1, col_b2, col_b3 = (
                st.columns(3)
            )

            col_b1.metric(
                "Saldo Promedio",
                format_money(
                    rf.saldo_promedio
                ),
            )

            col_b2.metric(
                "Intereses a Favor",
                format_money(
                    rf.intereses_a_favor
                ),
            )

            col_b3.metric(
                "ISR Retenido",
                format_money(
                    rf.isr_retenido
                ),
            )

    else:

        st.warning(
            "No se encontró el resumen "
            "financiero."
        )

    # ========================================================
    # DETALLES ADICIONALES
    # ========================================================

    with st.expander(
        "Ver más detalles del resumen financiero"
    ):

        if rf:

            col_c1, col_c2, col_c3 = (
                st.columns(3)
            )

            col_c1.metric(
                "Saldo Promedio Gravable",
                format_money(
                    rf.saldo_promedio_gravable
                ),
            )

            col_c2.metric(
                "Saldo Promedio "
                "Mínimo Mensual",
                format_money(
                    rf.saldo_promedio_minimo_mensual
                ),
            )

            col_c3.metric(
                "Saldo Global",
                format_money(
                    rf.saldo_global
                ),
            )

            col_d1, col_d2, col_d3, col_d4 = (
                st.columns(4)
            )

            col_d1.metric(
                "Cheques Pagados",
                safe_value(
                    rf.cheques_pagados
                ),
            )

            col_d2.metric(
                "Manejo de Cuenta",
                format_money(
                    rf.manejo_cuenta
                ),
            )

            col_d3.metric(
                "Cargos Objetados",
                format_money(
                    rf.cargos_objetados
                ),
            )

            col_d4.metric(
                "Abonos Objetados",
                format_money(
                    rf.abonos_objetados
                ),
            )

    # ========================================================
    # OTROS PRODUCTOS
    # ========================================================

    st.subheader(
        "3. 💰 Otros Productos y Comisiones"
    )

    op = (
        estado.otros_productos
    )

    if op:

        with st.container(
            border=True
        ):

            st.markdown(

                f"**Producto de Inversión:** "
                f"{op.producto or 'N/A'} "
                f"(Contrato: "
                f"{op.contrato or 'N/A'})"
            )

            col1, col2, col3 = (
                st.columns(3)
            )

            col1.metric(

                "Tasa Interés Anual",

                format_optional_float(
                    op.tasa_interes_anual,
                    format_str="{:.2f}",
                    suffix="%",
                ),
            )

            col2.metric(

                "GAT Nominal",

                format_optional_float(
                    op.gat_nominal_anual,
                    format_str="{:.2f}",
                    suffix="%",
                ),
            )

            col3.metric(

                "GAT Real",

                format_optional_float(
                    op.gat_real_anual,
                    format_str="{:.2f}",
                    suffix="%",
                ),
            )

            st.metric(

                "Total Comisiones Cobradas",

                format_optional_float(
                    op.total_comisiones,
                    prefix="$",
                ),
            )

    else:

        st.info(
            "No se encontraron otros "
            "productos o comisiones en "
            "este estado de cuenta."
        )

    # ========================================================
    # VALIDACIONES
    # ========================================================

    with st.expander(
        "✓ Validaciones Financieras"
    ):

        if result.validaciones:

            with st.container(
                border=True
            ):

                correctas = sum(

                    1

                    for v
                    in result.validaciones

                    if v.correcto
                )

                total = len(
                    result.validaciones
                )

                st.metric(

                    "Integridad financiera",

                    f"{correctas}/"
                    f"{total} "
                    f"validaciones correctas",
                )

                for validacion in (
                    result.validaciones
                ):

                    if validacion.correcto:

                        st.success(
                            f"✅ "
                            f"{validacion.nombre}"
                        )

                    else:

                        st.error(
                            f"❌ "
                            f"{validacion.nombre}"
                        )

                    with st.expander(
                        "Detalle"
                    ):

                        st.write(
                            "Esperado: "
                            +
                            format_money(
                                validacion.esperado
                            )
                        )

                        st.write(
                            "Obtenido: "
                            +
                            format_money(
                                validacion.obtenido
                            )
                        )

                        st.write(
                            "Diferencia: "
                            +
                            format_money(
                                validacion.diferencia
                            )
                        )

                        st.caption(
                            safe_value(
                                validacion.mensaje
                            )
                        )

        else:

            st.info(
                "No existen validaciones "
                "disponibles."
            )

    # ========================================================
    # MOVIMIENTOS
    # ========================================================

    movimientos = (
        estado.movimientos
        or []
    )

    st.subheader(
        f"5. 📑 Movimientos "
        f"({len(movimientos)})"
    )

    if not movimientos:

        st.warning(
            "No se encontraron movimientos "
            "en este documento."
        )

        return

    df = pd.DataFrame(
        [
            movimiento.__dict__
            for movimiento
            in movimientos
        ]
    )

    if df.empty:

        st.warning(
            "No se encontraron movimientos "
            "en este documento."
        )

        return

    for col in [

        "cargo",
        "abono",
        "saldo_operacion",
        "saldo_liquidacion",

    ]:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    # --------------------------------------------------------
    # COLUMNAS
    # --------------------------------------------------------

    columnas_mostrar = [

        "fecha_corte",

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

    columnas_existentes = [

        col

        for col
        in columnas_mostrar

        if col in df.columns
    ]

    df_display = (
        df[
            columnas_existentes
        ]
        .copy()
    )

    # --------------------------------------------------------
    # CONFIGURACIÓN
    # --------------------------------------------------------

    column_config = {

        "fecha_corte":
            "Fecha Corte",

        "fecha_operacion":
            "Fecha Operación",

        "fecha_liquidacion":
            "Fecha Liquidación",

        "concepto":
            "Concepto",

        "cargo":
            st.column_config.NumberColumn(
                "Cargo",
                format="$%.2f",
            ),

        "abono":
            st.column_config.NumberColumn(
                "Abono",
                format="$%.2f",
            ),

        "saldo_operacion":
            st.column_config.NumberColumn(
                "Saldo Operación",
                format="$%.2f",
            ),

        "saldo_liquidacion":
            st.column_config.NumberColumn(
                "Saldo Liquidación",
                format="$%.2f",
            ),

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

        "autorizacion":
            "Autorización",

        "hora_operacion":
            "Hora",
    }

    st.dataframe(

        df_display,

        use_container_width=True,

        height=500,

        hide_index=True,

        column_config=column_config,
    )


# ============================================================
# RENDER AUDITORÍA
# ============================================================

def render_audit_view() -> None:
    """
    Renderiza el área dinámica de auditoría.

    Esta función se ejecuta dentro de un fragmento para que
    pueda actualizarse automáticamente mientras el worker
    sigue procesando archivos.
    """

    # ========================================================
    # CONSUMIR EVENTOS
    # ========================================================

    consume_processing_events()

    # ========================================================
    # ESTADO DEL PROCESAMIENTO
    # ========================================================

    render_processing_status()

    st.divider()

    # ========================================================
    # TABLA GENERAL
    # ========================================================

    render_processing_summary()

    st.divider()

    # ========================================================
    # RESULTADOS TERMINADOS
    # ========================================================

    st.header(
        "🔍 Auditoría de Resultados"
    )

    result = render_result_selector()

    if result is None:

        return

    # ========================================================
    # RESULTADO
    # ========================================================

    if (
        result.bank_key
        == "imagen_no_procesada"
    ):

        render_image_document(
            result
        )

    else:

        render_digital_result(
            result
        )


# ============================================================
# FRAGMENTO DE ACTUALIZACIÓN
# ============================================================
#
# Streamlit ejecuta este fragmento periódicamente.
#
# Esto permite que:
#
#   - la tabla cambie conforme llegan eventos
#   - aparezcan resultados terminados
#   - el selector reciba nuevos archivos
#   - no sea necesario tocar ningún widget
#
# ============================================================

@st.fragment(
    run_every=PROCESSING_UI_POLL_INTERVAL
)
def processing_fragment():

    if not st.session_state.processing_items:

        return

    render_audit_view()


# ============================================================
# EXPORTACIÓN
# ============================================================

def render_export_section() -> None:

    results = (
        st.session_state.results
    )

    if not results:

        return

    st.divider()

    st.header(
        "📤 Exportar Todos los Resultados a Excel"
    )

    with st.container(
        border=True
    ):

        st.markdown(
            "Haz clic en el botón para generar "
            "un único archivo Excel con los "
            "datos de todos los estados de "
            "cuenta terminados."
        )

        if st.button(
            "🚀 Generar y Descargar "
            "Reporte Excel",
            type="primary",
            use_container_width=True,
        ):

            results_snapshot = list(
                results
            )

            excel_path = None

            try:

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".xlsx",
                ) as tmp_excel:

                    excel_path = (
                        tmp_excel.name
                    )

                with st.spinner(
                    "Generando archivo Excel..."
                ):

                    export_batch_excel(
                        results_snapshot,
                        excel_path,
                    )

                with open(
                    excel_path,
                    "rb",
                ) as file:

                    data = file.read()

                st.download_button(

                    label=(
                        "✅ ¡Listo! Haz clic "
                        "aquí para descargar"
                    ),

                    data=data,

                    file_name=(
                        "reporte_estados_de_"
                        "cuenta.xlsx"
                    ),

                    mime=(
                        "application/"
                        "vnd.openxmlformats-"
                        "officedocument."
                        "spreadsheetml.sheet"
                    ),

                    use_container_width=True,
                )

            except Exception as ex:

                st.error(
                    "❌ Error al exportar "
                    f"Excel: {ex}"
                )

            finally:

                if excel_path:

                    try:

                        os.remove(
                            excel_path
                        )

                    except (
                        FileNotFoundError,
                        OSError,
                    ):

                        pass


# ============================================================
# APP
# ============================================================

def main():

    st.set_page_config(

        page_title=(
            "Motor de Estados de Cuenta"
        ),

        layout="wide",
    )

    # ========================================================
    # ENCABEZADO
    # ========================================================

    st.title(
        "📄 Motor de Estados de Cuenta"
    )

    st.write(
        """
        Sube uno o varios estados de cuenta
        en formato PDF.

        El motor detectará el banco,
        extraerá la información y la
        presentará de forma estructurada
        para su auditoría y exportación.
        """
    )

    # ========================================================
    # ESTADO DEL WORKER
    # ========================================================

    worker_running = (
        st.session_state.worker_running
    )

    # ========================================================
    # UPLOADER
    # ========================================================
    #
    # Mientras existe un lote procesándose,
    # evitamos iniciar otro lote simultáneamente
    # en la misma sesión.
    #
    # ========================================================

    uploaded_files = st.file_uploader(

        "Selecciona estados de cuenta PDF",

        type="pdf",

        accept_multiple_files=True,

        disabled=worker_running,
    )

    # ========================================================
    # CREAR NUEVO LOTE
    # ========================================================

    if uploaded_files:

        uploaded_files_data = tuple(

            (
                uploaded_file.name,
                uploaded_file.getvalue(),
            )

            for uploaded_file
            in uploaded_files
        )

        current_signature = (
            create_batch_signature(
                uploaded_files_data
            )
        )

        previous_signature = (
            st.session_state.batch_signature
        )

        # ----------------------------------------------------
        # SOLAMENTE INICIAR SI ES UN LOTE NUEVO
        # ----------------------------------------------------

        if (
            current_signature
            != previous_signature
        ):

            if not worker_running:

                try:

                    start_processing(
                        uploaded_files_data
                    )

                    st.rerun()

                except Exception as ex:

                    st.error(
                        "❌ No fue posible "
                        "iniciar el procesamiento: "
                        f"{ex}"
                    )

    # ========================================================
    # ERROR GLOBAL
    # ========================================================

    if (
        st.session_state.worker_error
        is not None
    ):

        st.error(

            "❌ Error durante el "
            "procesamiento:\n\n"
            f"{st.session_state.worker_error}"
        )

        if (
            st.session_state.worker_traceback
        ):

            with st.expander(
                "Ver detalle técnico"
            ):

                st.code(
                    st.session_state.worker_traceback
                )

    # ========================================================
    # AUDITORÍA DINÁMICA
    # ========================================================

    processing_fragment()

    # ========================================================
    # EXPORTACIÓN
    # ========================================================

    render_export_section()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()