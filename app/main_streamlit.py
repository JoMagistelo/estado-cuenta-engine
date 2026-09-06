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

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from engine.ocr_fallback_policy import normalize_ocr_engine, secondary_ocr_engine
from engine.pipeline import process_bank_statements_incremental
from exporters.excel import export_batch_excel

APP_VERSION = "2.2"
PROCESSING_UI_POLL_INTERVAL = 0.5
GOB_GREEN = "#1F4D3A"
GOB_GREEN_LIGHT = "#E8F0EC"
GOB_GOLD = "#B08D57"
GOB_CREAM = "#F7F4EE"
PRIMARY_VALIDATIONS = (
    "Total depósitos / abonos",
    "Total retiros / cargos",
)
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
MONEY_FIELDS = {"cargo", "abono", "saldo_operacion", "saldo_liquidacion"}


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
        return f"{prefix}{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def engine_label(engine: str | None) -> str:
    normalized = normalize_ocr_engine(engine, default="")
    return {"tesseract": "Tesseract", "paddleocr": "PaddleOCR"}.get(normalized, "OCR")


def initialize_session_state() -> None:
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
        "selected_index": None,
        "ocr_primary_engine": normalize_ocr_engine(os.getenv("OCR_PRIMARY_ENGINE", "tesseract")),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def create_batch_signature(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> tuple:
    return tuple(
        (name, len(data), hashlib.sha256(data).hexdigest())
        for name, data in uploaded_files_data
    )


def cleanup_temp_paths(paths: list[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except (FileNotFoundError, OSError):
            pass


def materialize_uploaded_files(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> list[str]:
    temp_paths: list[str] = []
    try:
        for file_name, file_bytes in uploaded_files_data:
            suffix = Path(file_name).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                temp_paths.append(tmp.name)
        return temp_paths
    except Exception:
        cleanup_temp_paths(temp_paths)
        raise


def traceback_string() -> str:
    import traceback

    return traceback.format_exc()


def processing_worker(
    temp_paths: list[str],
    names: list[str],
    processing_queue: Queue,
    primary_engine: str,
) -> None:
    try:
        for event in process_bank_statements_incremental(
            temp_paths,
            names,
            ocr_primary_engine=primary_engine,
        ):
            processing_queue.put(("event", event))
    except Exception as ex:
        processing_queue.put(("worker_error", ex, traceback_string()))
    finally:
        processing_queue.put(("finished",))
        cleanup_temp_paths(temp_paths)


def start_processing(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> None:
    temp_paths = materialize_uploaded_files(uploaded_files_data)
    processing_items = [
        {
            "file_name": file_name,
            "processing_method": None,
            "status": "classifying",
            "result": None,
            "error": None,
        }
        for file_name, _ in uploaded_files_data
    ]
    processing_queue = Queue()
    primary_engine = normalize_ocr_engine(st.session_state.ocr_primary_engine)
    worker = threading.Thread(
        target=processing_worker,
        args=(
            temp_paths,
            [name for name, _ in uploaded_files_data],
            processing_queue,
            primary_engine,
        ),
        daemon=True,
    )

    st.session_state.processing_queue = processing_queue
    st.session_state.processing_items = processing_items
    st.session_state.results = []
    st.session_state.worker_thread = worker
    st.session_state.worker_running = True
    st.session_state.worker_finished = False
    st.session_state.worker_error = None
    st.session_state.worker_traceback = None
    st.session_state.batch_signature = create_batch_signature(uploaded_files_data)
    st.session_state.batch_temp_paths = temp_paths
    st.session_state.selected_index = None
    worker.start()


def consume_processing_events() -> tuple[bool, bool, bool]:
    changed = False
    completed_added = False
    finished = False
    queue = st.session_state.processing_queue
    items = st.session_state.processing_items
    results = st.session_state.results

    while True:
        try:
            message = queue.get_nowait()
        except Empty:
            break

        message_type = message[0]
        if message_type == "event":
            event = message[1]
            index = getattr(event, "index", None)
            if not isinstance(index, int) or not (0 <= index < len(items)):
                continue
            item = items[index]
            if event.kind == "started":
                item.update(
                    processing_method=event.processing_method,
                    status="processing",
                    error=None,
                )
                changed = True
            elif event.kind == "completed":
                item.update(
                    processing_method=event.processing_method,
                    status="completed",
                    result=event.result,
                    error=None,
                )
                if event.result is not None:
                    results.append(event.result)
                    if st.session_state.selected_index is None:
                        st.session_state.selected_index = index
                    completed_added = True
                changed = True
            elif event.kind == "error":
                item.update(
                    processing_method=event.processing_method,
                    status="error",
                    result=None,
                    error=str(event.error or "Error desconocido"),
                )
                changed = True

        elif message_type == "worker_error":
            ex, tb = message[1], message[2]
            st.session_state.worker_error = str(ex)
            st.session_state.worker_traceback = tb
            for item in items:
                if item.get("status") not in {"completed", "error"}:
                    item.update(status="error", error=str(ex))
            changed = True

        elif message_type == "finished":
            st.session_state.worker_running = False
            st.session_state.worker_finished = True
            changed = True
            finished = True

    return changed, completed_added, finished


def processing_counts() -> tuple[int, int, int, int, int]:
    items = st.session_state.processing_items
    total = len(items)
    completed = sum(1 for item in items if item.get("status") == "completed")
    errors = sum(1 for item in items if item.get("status") == "error")
    pending = total - completed - errors
    scanned_pending = sum(
        1
        for item in items
        if item.get("status") == "processing" and item.get("processing_method") == "OCR"
    )
    return total, completed, errors, pending, scanned_pending


def render_processing_status() -> None:
    total, completed, errors, pending, scanned_pending = processing_counts()
    if not total:
        return
    if pending > 0:
        message = f"Procesando {completed} de {total} archivos"
        if scanned_pending:
            message += f" · {scanned_pending} PDF(s) escaneado(s) en OCR"
        if errors:
            message += f" · {errors} con error"
        st.info(message)
    elif errors == 0:
        st.success(f"✅ {completed} archivos procesados correctamente")
    elif completed:
        st.warning(f"✅ {completed} correctos · ⚠️ {errors} con error")
    else:
        st.error(f"❌ No fue posible procesar {errors} archivos")


@st.fragment(run_every=PROCESSING_UI_POLL_INTERVAL)
def processing_status_fragment() -> None:
    _changed, completed_added, finished = consume_processing_events()
    render_processing_status()
    # El resto de la página sólo se reconstruye cuando aparece un resultado nuevo
    # o termina el lote. Así los botones del selector no se mueven cada 0.5 s.
    if completed_added or finished:
        st.rerun()


def validation(result, name: str):
    for item in getattr(result, "validaciones", []) or []:
        if item.nombre == name:
            return item
    return None


def validation_symbol(item) -> str:
    return "—" if item is None else ("✅" if item.correcto else "❌")


def process_label(item: dict[str, Any]) -> str:
    method = item.get("processing_method")
    result = item.get("result")
    if method == "Digital":
        return "Digital"
    if method == "OCR":
        if result is None:
            return engine_label(st.session_state.ocr_primary_engine)
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


def completed_items() -> list[tuple[int, dict[str, Any]]]:
    return [
        (index, item)
        for index, item in enumerate(st.session_state.processing_items)
        if item.get("status") == "completed" and item.get("result") is not None
    ]


def render_selector_column(title: str, items: list[tuple[int, dict[str, Any]]]) -> None:
    st.markdown(f"#### {title}")
    if not items:
        st.caption("Sin resultados terminados")
        return

    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, item in items:
        grouped.setdefault(bank_key_for_item(item), []).append((index, item))

    for bank in sorted(grouped):
        st.markdown(f"**{bank}**")
        for index, item in grouped[bank]:
            result = item["result"]
            a = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))
            c = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))
            selected = st.session_state.selected_index == index
            label = f"{'●' if selected else '○'} {item['file_name']} · {process_label(item)} · A {a} · C {c}"
            if st.button(
                label,
                key=f"result_{index}_{item['file_name']}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state.selected_index = index
                st.rerun()


def render_result_selector() -> Any | None:
    completed = completed_items()
    if not completed:
        st.info("Aún no hay resultados terminados. Puedes esperar mientras los OCR continúan en segundo plano.")
        return None

    st.subheader("Resultados disponibles")
    st.caption(
        "Los resultados terminados permanecen estables y pueden revisarse mientras otros archivos siguen procesándose."
    )
    digital = [(i, item) for i, item in completed if item.get("processing_method") == "Digital"]
    scanned = [(i, item) for i, item in completed if item.get("processing_method") == "OCR"]
    col_digital, col_scanned = st.columns(2)
    with col_digital:
        render_selector_column("📄 PDFs digitales", digital)
    with col_scanned:
        render_selector_column("🖨️ PDFs escaneados (OCR)", scanned)

    selected_index = st.session_state.selected_index
    for index, item in completed:
        if index == selected_index:
            return item["result"]

    st.session_state.selected_index = completed[0][0]
    return completed[0][1]["result"]


def render_primary_validations(result) -> None:
    cols = st.columns(2)
    for col, name, short in zip(cols, PRIMARY_VALIDATIONS, ("Abonos", "Cargos")):
        item = validation(result, name)
        with col:
            with st.container(border=True):
                if item is None:
                    st.markdown(f"### — Validación {short}")
                    st.caption("No se pudo calcular")
                elif item.correcto:
                    st.markdown(f"### ✅ Validación {short}")
                    st.caption("Conciliación correcta")
                else:
                    st.markdown(f"### ❌ Validación {short}")
                    st.caption(
                        f"Esperado {format_money(item.esperado)} · "
                        f"Obtenido {format_money(item.obtenido)} · "
                        f"Diferencia {format_money(item.diferencia)}"
                    )


def render_other_validations(result) -> None:
    all_validations = list(getattr(result, "validaciones", []) or [])
    secondary = [item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS]
    correct = sum(1 for item in all_validations if item.correcto)
    st.caption(f"Integridad financiera: {correct}/{len(all_validations)} validaciones correctas")
    st.markdown(f"**Otras validaciones financieras ({len(secondary)})**")
    if not secondary:
        st.caption("No existen validaciones adicionales para este resultado.")
        return
    for item in secondary:
        icon = "✅" if item.correcto else "❌"
        with st.container(border=True):
            st.markdown(f"**{icon} {item.nombre}**")
            st.caption(
                f"Esperado: {format_money(item.esperado)} · "
                f"Obtenido: {format_money(item.obtenido)} · "
                f"Diferencia: {format_money(item.diferencia)}"
            )
            if getattr(item, "mensaje", None):
                st.caption(safe_value(item.mensaje))


def render_all_fields(estado) -> None:
    dc = getattr(estado, "datos_cuenta", None)
    rf = getattr(estado, "resumen_financiero", None)
    op = getattr(estado, "otros_productos", None)

    with st.expander("📌 Datos de la cuenta · todos los campos"):
        rows = {
            "Producto principal": safe_value(getattr(dc, "producto_principal", None)),
            "Periodo inicio": safe_value(getattr(dc, "periodo_inicio", None)),
            "Periodo fin": safe_value(getattr(dc, "periodo_fin", None)),
            "Fecha de corte": safe_value(getattr(dc, "fecha_corte", None)),
            "Número de cuenta": safe_value(getattr(dc, "numero_cuenta", None)),
            "Número de cliente": safe_value(getattr(dc, "numero_cliente", None)),
            "CLABE": safe_value(getattr(dc, "clabe", None)),
            "Nombre del cliente": safe_value(getattr(dc, "nombre_cliente", None)),
            "RFC": safe_value(getattr(dc, "rfc", None)),
        }
        st.dataframe(pd.DataFrame([rows]), use_container_width=True, hide_index=True)

    with st.expander("📈 Resumen financiero ampliado · todos los campos"):
        rows = {
            "Saldo promedio": format_money(getattr(rf, "saldo_promedio", None)),
            "Días del periodo": safe_value(getattr(rf, "dias_periodo", None)),
            "Tasa bruta anual": format_optional_float(getattr(rf, "tasa_bruta_anual", None), suffix="%"),
            "Saldo promedio gravable": format_money(getattr(rf, "saldo_promedio_gravable", None)),
            "Intereses a favor": format_money(getattr(rf, "intereses_a_favor", None)),
            "ISR retenido": format_money(getattr(rf, "isr_retenido", None)),
            "Cheques pagados": safe_value(getattr(rf, "cheques_pagados", None)),
            "Manejo de cuenta": format_money(getattr(rf, "manejo_cuenta", None)),
            "Cargos objetados": format_money(getattr(rf, "cargos_objetados", None)),
            "Abonos objetados": format_money(getattr(rf, "abonos_objetados", None)),
            "Saldo promedio mínimo mensual": format_money(getattr(rf, "saldo_promedio_minimo_mensual", None)),
            "Saldo global": format_money(getattr(rf, "saldo_global", None)),
        }
        st.dataframe(pd.DataFrame([rows]), use_container_width=True, hide_index=True)

    with st.expander("💰 Otros productos y comisiones · todos los campos"):
        rows = {
            "Contrato": safe_value(getattr(op, "contrato", None)),
            "Producto": safe_value(getattr(op, "producto", None)),
            "Tasa interés anual": format_optional_float(getattr(op, "tasa_interes_anual", None), suffix="%"),
            "GAT nominal anual": format_optional_float(getattr(op, "gat_nominal_anual", None), suffix="%"),
            "GAT real anual": format_optional_float(getattr(op, "gat_real_anual", None), suffix="%"),
            "Total comisiones": format_optional_float(getattr(op, "total_comisiones", None), prefix="$"),
        }
        st.dataframe(pd.DataFrame([rows]), use_container_width=True, hide_index=True)


def movement_dataframe(estado) -> pd.DataFrame:
    dc = getattr(estado, "datos_cuenta", None)
    movements = getattr(estado, "movimientos", None) or []
    rows: list[dict[str, Any]] = []
    for index, movement in enumerate(movements, 1):
        row: dict[str, Any] = {}
        for field_name, _label in MOVEMENT_COLUMNS:
            if field_name == "fecha_corte":
                value = getattr(dc, "fecha_corte", None)
            elif field_name == "numero_cuenta":
                value = getattr(dc, "numero_cuenta", None)
            elif field_name == "numero_movimiento":
                value = index
            else:
                value = getattr(movement, field_name, None)
            row[field_name] = value
        rows.append(row)
    return pd.DataFrame(rows, columns=[name for name, _ in MOVEMENT_COLUMNS])


def render_movements(estado) -> None:
    movements = getattr(estado, "movimientos", None) or []
    st.subheader(f"📑 Movimientos ({len(movements)})")
    if not movements:
        st.warning("No se encontraron movimientos en este documento.")
        return

    df = movement_dataframe(estado)
    for field in MONEY_FIELDS:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors="coerce")

    column_config: dict[str, Any] = {}
    for field_name, label in MOVEMENT_COLUMNS:
        if field_name in MONEY_FIELDS:
            column_config[field_name] = st.column_config.NumberColumn(label, format="$%.2f", width="small")
        elif field_name in {"concepto", "concepto_original", "beneficiario", "clave_rastreo"}:
            column_config[field_name] = st.column_config.TextColumn(label, width="medium")
        else:
            column_config[field_name] = st.column_config.TextColumn(label, width="small")

    st.caption("Encabezado fijo, filas compactas y desplazamiento horizontal/vertical.")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=430,
        row_height=30,
        column_config=column_config,
    )


def render_result(result) -> None:
    estado = getattr(result, "estado_cuenta", None)
    if estado is None:
        st.warning("Resultado sin estado de cuenta.")
        return

    dc = getattr(estado, "datos_cuenta", None)
    rf = getattr(estado, "resumen_financiero", None)
    method = getattr(result, "processing_method", "Digital")
    process_text = "Digital" if method == "Digital" else engine_label(getattr(result, "ocr_engine", None))

    st.markdown(f"### 🔍 {result.file_name}")
    st.caption(f"{str(result.bank_key).upper()} · {process_text}")

    info = st.columns(4)
    info[0].metric(
        "Periodo",
        f"{safe_value(getattr(dc, 'periodo_inicio', None))} al {safe_value(getattr(dc, 'periodo_fin', None))}",
    )
    info[1].metric("Cliente", safe_value(getattr(dc, "nombre_cliente", None)))
    info[2].metric("Cuenta", safe_value(getattr(dc, "numero_cuenta", None)))
    info[3].metric("CLABE", safe_value(getattr(dc, "clabe", None)))

    if method == "OCR":
        primary = engine_label(getattr(result, "ocr_primary_engine", None))
        secondary = (
            engine_label(getattr(result, "ocr_secondary_engine", None))
            if getattr(result, "ocr_secondary_engine", None)
            else ""
        )
        if getattr(result, "fallback_attempted", False):
            text = f"Primario: {primary} · Secundario: {secondary} · " + (
                "se usó el secundario" if getattr(result, "fallback_used", False) else "se conservó el primario"
            )
        else:
            text = f"Primario: {primary} · sin fallback: ambas validaciones principales pasaron"
        st.info(f"⚙️ {text}")

    render_all_fields(estado)
    st.subheader("📊 Resumen financiero")
    summary = st.columns(4)
    summary[0].metric("Saldo anterior", format_money(getattr(rf, "saldo_anterior", None)))
    summary[1].metric("Depósitos / Abonos", format_money(getattr(rf, "depositos_abonos", None)))
    summary[2].metric("Retiros / Cargos", format_money(getattr(rf, "retiros_cargos", None)))
    summary[3].metric("Saldo final", format_money(getattr(rf, "saldo_final", None)))
    render_primary_validations(result)
    render_other_validations(result)
    render_movements(estado)


def render_help() -> None:
    with st.expander("❓ Ayuda y formatos habilitados"):
        st.markdown("**PDFs digitales y escaneados**")
        st.write(
            "Los PDFs digitales contienen texto utilizable. Los PDFs escaneados (OCR) son imágenes o documentos "
            "sin texto digital útil y requieren un motor OCR."
        )
        st.markdown("**Validaciones financieras**")
        st.write(
            "A y C representan las conciliaciones de depósitos/abonos y retiros/cargos. El motor OCR secundario "
            "sólo se ejecuta si alguna de esas dos validaciones falla o no puede calcularse."
        )
        st.markdown("**Bancos y estados de cuenta habilitados**")
        st.markdown(
            "- **BBVA Digital:** Libretón Básico, Libretón Nómina, Libretón Premium\n"
            "- **Banorte Digital y Escaneado:** Nómina Banorte, Nómina Banorte sin chequera, Enlace Negocios\n"
            "- **Banamex Digital:** Mi Cuenta, Cuenta Base, Cuenta Prioriti\n"
            "- **HSBC Digital y Escaneado:** Ahorro y Debito\n"
            "- **Scotiabank Digital:** Nomina Clasic\n"
            "- **Banca Mifel:** Cuenta Alavista\n"
            "- **CETESDIRECTO Digital:** cetesdirecto\n"
            "- **MercadoPago Digital**"
        )


def render_settings() -> None:
    with st.sidebar:
        st.markdown(f"### ⚙️ Configuración · v{APP_VERSION}")
        st.info(
            "Recomendación: mantenga Tesseract como motor principal salvo indicación del área técnica. "
            "PaddleOCR puede tardar más en CPU."
        )
        options = ["tesseract", "paddleocr"]
        current = normalize_ocr_engine(st.session_state.ocr_primary_engine)
        selected = st.selectbox(
            "Motor OCR principal",
            options=options,
            index=options.index(current),
            format_func=engine_label,
            disabled=st.session_state.worker_running,
        )
        if not st.session_state.worker_running:
            st.session_state.ocr_primary_engine = normalize_ocr_engine(selected)
        primary = normalize_ocr_engine(st.session_state.ocr_primary_engine)
        st.caption(
            f"Orden: {engine_label(primary)} → {engine_label(secondary_ocr_engine(primary))} sólo si falla Abonos o Cargos."
        )
        st.caption("Los PDFs digitales nunca se envían a OCR.")


def render_export_section() -> None:
    results = st.session_state.results
    if not results:
        return
    st.divider()
    st.subheader("📤 Exportación")
    st.caption("El Excel usa el resultado elegido automáticamente por la política principal/fallback de cada PDF.")
    if st.button("Generar reporte Excel", type="primary", use_container_width=True):
        excel_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                excel_path = tmp_excel.name
            with st.spinner("Generando archivo Excel..."):
                export_batch_excel(list(results), excel_path)
            with open(excel_path, "rb") as file:
                data = file.read()
            st.download_button(
                "✅ Descargar reporte",
                data=data,
                file_name="reporte_estados_de_cuenta.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as ex:
            st.error(f"❌ Error al exportar Excel: {ex}")
        finally:
            if excel_path:
                try:
                    os.remove(excel_path)
                except (FileNotFoundError, OSError):
                    pass


def main() -> None:
    st.set_page_config(
        page_title="Extractor de Movimientos Financieros",
        layout="wide",
    )
    initialize_session_state()

    st.markdown(
        f"<div style='display:flex;align-items:center;gap:.7rem;'>"
        f"<h1 style='margin:0'>📄 Extractor de Movimientos Financieros</h1>"
        f"<span style='background:#F4EEE5;padding:.2rem .6rem;border-radius:1rem;font-size:.8rem;'>Versión {APP_VERSION}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption("PDFs digitales se leen directamente. PDFs escaneados (OCR) usan el motor configurado.")

    render_settings()
    render_help()

    uploaded_files = st.file_uploader(
        "Selecciona estados de cuenta PDF",
        type="pdf",
        accept_multiple_files=True,
        disabled=st.session_state.worker_running,
    )

    if uploaded_files:
        uploaded_files_data = tuple(
            (uploaded_file.name, uploaded_file.getvalue())
            for uploaded_file in uploaded_files
        )
        current_signature = create_batch_signature(uploaded_files_data)
        if current_signature != st.session_state.batch_signature and not st.session_state.worker_running:
            try:
                start_processing(uploaded_files_data)
                st.rerun()
            except Exception as ex:
                st.error(f"❌ No fue posible iniciar el procesamiento: {ex}")

    changed, completed_added, finished = consume_processing_events()
    if completed_added or finished:
        changed = True

    if st.session_state.worker_error:
        st.error(f"❌ Error durante el procesamiento: {st.session_state.worker_error}")
        if st.session_state.worker_traceback:
            with st.expander("Ver detalle técnico"):
                st.code(st.session_state.worker_traceback)

    if st.session_state.processing_items:
        if st.session_state.worker_running:
            processing_status_fragment()
        else:
            render_processing_status()

        st.divider()
        result = render_result_selector()
        if result is not None:
            st.divider()
            render_result(result)

    render_export_section()


if __name__ == "__main__":
    main()
