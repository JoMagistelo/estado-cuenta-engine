from __future__ import annotations
import hashlib
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any
import pandas as pd
import streamlit as st
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from engine.ocr_fallback_policy import normalize_ocr_engine
from engine.pipeline import process_bank_statements_incremental
from exporters.excel import export_batch_excel
APP_VERSION = '2.3'
PROCESSING_UI_POLL_INTERVAL = 1.25
GOB_GREEN = '#1F4D3A'
GOB_GREEN_DARK = '#163A2C'
GOB_GREEN_LIGHT = '#E8F0EC'
GOB_GOLD = '#B08D57'
GOB_GOLD_LIGHT = '#F4EEE5'
GOB_CREAM = '#F7F4EE'
DANGER = '#A63D40'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / 'assets' / 'logo_gobierno_mexico.png'
PRIMARY_VALIDATIONS = ('Total depósitos / abonos', 'Total retiros / cargos')
MOVEMENT_COLUMNS = [('fecha_corte', 'Fecha Corte'), ('numero_cuenta', 'Número de Cuenta'), ('numero_movimiento', 'No. Movimiento'), ('fecha_operacion', 'Fecha Operación'), ('fecha_liquidacion', 'Fecha Liquidación'), ('concepto', 'Concepto'), ('cargo', 'Cargo'), ('abono', 'Abono'), ('saldo_operacion', 'Saldo Operación'), ('saldo_liquidacion', 'Saldo Liquidación'), ('tipo_operacion', 'Tipo'), ('beneficiario', 'Beneficiario'), ('cuenta_beneficiario', 'Cuenta Benef.'), ('clabe_beneficiario', 'CLABE Benef.'), ('rfc', 'RFC'), ('referencia', 'Referencia'), ('clave_rastreo', 'Clave Rastreo'), ('autorizacion', 'Autorización'), ('hora_operacion', 'Hora'), ('__bank__', 'Banco'), ('caja', 'Caja'), ('concepto_original', 'Concepto Original')]
MONEY_FIELDS = {'cargo', 'abono', 'saldo_operacion', 'saldo_liquidacion'}

def safe_value(value: Any) -> str:
    return 'N/A' if value is None or value == '' else str(value)

def format_money(value: Any) -> str:
    if value is None:
        return 'N/A'
    try:
        return f'${float(value):,.2f}'
    except (TypeError, ValueError):
        return str(value)

def format_optional_float(value: Any, *, suffix: str='', prefix: str='', na_value: str='N/A') -> str:
    if value is None:
        return na_value
    try:
        return f'{prefix}{float(value):,.2f}{suffix}'
    except (TypeError, ValueError):
        return str(value)

def engine_label(engine: str | None) -> str:
    normalized = normalize_ocr_engine(engine, default='')
    return {'tesseract': 'Tesseract', 'paddleocr': 'PaddleOCR'}.get(normalized, 'OCR')

def numeric(value: Any) -> float:
    try:
        return max(float(value or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0

def initialize_session_state() -> None:
    defaults = {'processing_queue': Queue(), 'processing_items': [], 'results': [], 'worker_thread': None, 'worker_running': False, 'worker_finished': False, 'worker_error': None, 'worker_traceback': None, 'batch_signature': None, 'batch_temp_paths': [], 'selected_index': None, 'ocr_primary_engine': normalize_ocr_engine(os.getenv('OCR_PRIMARY_ENGINE', 'tesseract')), 'stop_event': threading.Event(), 'stop_requested': False, 'started_at': None, 'initial_dialog_pending': False}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def inject_css() -> None:
    st.markdown(f'\n        <style>\n        .stApp {{\n            background: #FBFBFC;\n        }}\n        [data-testid="stHeader"] {{\n            background: rgba(251,251,252,0.94);\n        }}\n        .institution-card {{\n            background: white;\n            border: 1px solid #E0E3E7;\n            border-radius: 14px;\n            padding: 14px 18px;\n            margin-bottom: 12px;\n        }}\n        .app-title {{\n            font-size: 1.75rem;\n            font-weight: 750;\n            color: #202124;\n            line-height: 1.15;\n        }}\n        .version-pill {{\n            display: inline-block;\n            background: {GOB_GOLD_LIGHT};\n            border-radius: 999px;\n            padding: 4px 10px;\n            font-size: .76rem;\n            font-weight: 700;\n        }}\n        .bank-label {{\n            background: {GOB_CREAM};\n            color: {GOB_GREEN_DARK};\n            border-radius: 7px;\n            padding: 5px 8px;\n            font-size: .82rem;\n            font-weight: 700;\n            margin: 4px 0;\n        }}\n        .processing-card {{\n            background: white;\n            border: 1px solid #DADDE1;\n            border-left: 5px solid {GOB_GREEN};\n            border-radius: 12px;\n            padding: 10px 14px;\n            margin: 6px 0 12px 0;\n        }}\n        .tiny-note {{\n            color: #6B7075;\n            font-size: .78rem;\n        }}\n        div[data-testid="stMetric"] {{\n            background: white;\n            border: 1px solid #E0E3E7;\n            border-radius: 10px;\n            padding: 8px 10px;\n        }}\n        div[data-testid="stDataFrame"] {{\n            border: 1px solid #DADDE1;\n            border-radius: 10px;\n            overflow: hidden;\n        }}\n        </style>\n        ', unsafe_allow_html=True)

def create_batch_signature(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> tuple:
    return tuple(((name, len(data), hashlib.sha256(data).hexdigest()) for name, data in uploaded_files_data))

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
            suffix = Path(file_name).suffix or '.pdf'
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

def processing_worker(temp_paths: list[str], names: list[str], processing_queue: Queue, primary_engine: str, stop_event: threading.Event) -> None:
    try:
        for event in process_bank_statements_incremental(temp_paths, names, ocr_primary_engine=primary_engine, cancel_event=stop_event):
            processing_queue.put(('event', event))
    except Exception as ex:
        processing_queue.put(('worker_error', ex, traceback_string()))
    finally:
        processing_queue.put(('finished',))
        cleanup_temp_paths(temp_paths)

def start_processing(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> None:
    temp_paths = materialize_uploaded_files(uploaded_files_data)
    processing_items = [{'file_name': file_name, 'processing_method': None, 'status': 'classifying', 'result': None, 'error': None} for file_name, _ in uploaded_files_data]
    processing_queue = Queue()
    stop_event = threading.Event()
    primary_engine = normalize_ocr_engine(st.session_state.ocr_primary_engine)
    worker = threading.Thread(target=processing_worker, args=(temp_paths, [name for name, _ in uploaded_files_data], processing_queue, primary_engine, stop_event), daemon=True)
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
    st.session_state.stop_event = stop_event
    st.session_state.stop_requested = False
    st.session_state.started_at = time.perf_counter()
    st.session_state.initial_dialog_pending = True
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
        if message_type == 'event':
            event = message[1]
            index = getattr(event, 'index', None)
            if not isinstance(index, int) or not 0 <= index < len(items):
                continue
            item = items[index]
            if event.kind == 'started':
                item.update(processing_method=event.processing_method, status='processing', error=None)
                changed = True
            elif event.kind == 'completed':
                item.update(processing_method=event.processing_method, status='completed', result=event.result, error=None)
                if event.result is not None:
                    results.append(event.result)
                    completed_added = True
                    if st.session_state.selected_index is None:
                        st.session_state.selected_index = index
                changed = True
            elif event.kind == 'cancelled':
                item.update(processing_method=event.processing_method or item.get('processing_method'), status='cancelled', result=None, error=None)
                changed = True
            elif event.kind == 'error':
                item.update(processing_method=event.processing_method, status='error', result=None, error=str(event.error or 'Error desconocido'))
                changed = True
        elif message_type == 'worker_error':
            ex, tb = (message[1], message[2])
            st.session_state.worker_error = str(ex)
            st.session_state.worker_traceback = tb
            for item in items:
                if item.get('status') not in {'completed', 'error', 'cancelled'}:
                    item.update(status='error', error=str(ex))
            changed = True
        elif message_type == 'finished':
            st.session_state.worker_running = False
            st.session_state.worker_finished = True
            changed = True
            finished = True
    return (changed, completed_added, finished)

def processing_counts() -> tuple[int, int, int, int, int]:
    items = st.session_state.processing_items
    total = len(items)
    completed = sum((1 for item in items if item.get('status') == 'completed'))
    errors = sum((1 for item in items if item.get('status') == 'error'))
    cancelled = sum((1 for item in items if item.get('status') == 'cancelled'))
    pending = total - completed - errors - cancelled
    scanned_active = sum((1 for item in items if item.get('status') == 'processing' and item.get('processing_method') == 'OCR'))
    return (total, completed, errors, cancelled, scanned_active)

def validation(result, name: str):
    for item in getattr(result, 'validaciones', []) or []:
        if item.nombre == name:
            return item
    return None

def validation_symbol(item) -> str:
    return '—' if item is None else '✅' if item.correcto else '❌'

def process_label(item: dict[str, Any]) -> str:
    method = item.get('processing_method')
    result = item.get('result')
    if method == 'Digital':
        return 'Digital'
    if method == 'OCR':
        if result is None:
            return engine_label(st.session_state.ocr_primary_engine)
        label = engine_label(getattr(result, 'ocr_engine', None))
        if getattr(result, 'fallback_used', False):
            return f'{label} · fallback'
        if getattr(result, 'fallback_attempted', False):
            return f'{label} · revisado'
        return label
    return 'Detectando'

def bank_key_for_item(item: dict[str, Any]) -> str:
    result = item.get('result')
    if result is None:
        return 'PENDIENTE'
    return str(getattr(result, 'bank_key', 'desconocido') or 'desconocido').upper()

def completed_items() -> list[tuple[int, dict[str, Any]]]:
    return [(index, item) for index, item in enumerate(st.session_state.processing_items) if item.get('status') == 'completed' and item.get('result') is not None]

def render_processing_card() -> None:
    total, completed, errors, cancelled, scanned_active = processing_counts()
    if not total:
        return
    elapsed = 0
    if st.session_state.started_at:
        elapsed = int(time.perf_counter() - st.session_state.started_at)
    if st.session_state.worker_running:
        if st.session_state.stop_requested:
            title = f'Deteniendo · {completed} resultado(s) conservado(s)'
        else:
            title = f'Procesando {completed} de {total} archivos'
        st.markdown(f"""\n            <div class="processing-card">\n              <strong>{title}</strong><br>\n              <span class="tiny-note">\n                Tiempo {elapsed // 60:02d}:{elapsed % 60:02d}\n                {(' · OCR activo' if scanned_active else '')}\n              </span>\n            </div>\n            """, unsafe_allow_html=True)
        if st.button('⏹ Detener procesamiento', type='secondary', disabled=st.session_state.stop_requested, key='stop_processing'):
            st.session_state.stop_requested = True
            st.session_state.stop_event.set()
            st.rerun(scope='fragment')
    elif st.session_state.stop_requested:
        st.warning(f'⏹ Procesamiento detenido. Se conservaron {completed} resultado(s); {cancelled} archivo(s) se omitieron.')
    elif errors:
        st.warning(f'✅ {completed} correctos · ⚠️ {errors} con error')
    else:
        st.success(f'✅ {completed} archivos procesados correctamente')

def render_selector_column(title: str, items: list[tuple[int, dict[str, Any]]]) -> None:
    st.markdown(f'#### {title}')
    if not items:
        st.caption('Sin resultados terminados')
        return
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, item in items:
        grouped.setdefault(bank_key_for_item(item), []).append((index, item))
    for bank in sorted(grouped):
        st.markdown(f'<div class="bank-label">{bank} · {len(grouped[bank])} archivo(s)</div>', unsafe_allow_html=True)
        for index, item in grouped[bank]:
            result = item['result']
            a = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))
            c = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))
            selected = st.session_state.selected_index == index
            label = f"{('●' if selected else '○')} {item['file_name']} · {process_label(item)} · A {a} · C {c}"
            if st.button(label, key=f'result_{index}', use_container_width=True, type='primary' if selected else 'secondary'):
                st.session_state.selected_index = index
                st.rerun()

def render_result_selector() -> None:
    completed = completed_items()
    if not completed:
        st.caption('Los resultados aparecerán aquí conforme terminen.')
        return
    digital = [(index, item) for index, item in completed if item.get('processing_method') == 'Digital']
    scanned = [(index, item) for index, item in completed if item.get('processing_method') == 'OCR']
    col_digital, col_scanned = st.columns(2)
    with col_digital:
        render_selector_column('📄 PDFs digitales', digital)
    with col_scanned:
        render_selector_column('🖨️ PDFs escaneados (OCR)', scanned)

@st.fragment(run_every=PROCESSING_UI_POLL_INTERVAL)
def processing_status_fragment():
    _changed, completed_added, finished = consume_processing_events()
    render_processing_card()
    if completed_added or finished:
        st.rerun()

def selected_result() -> Any | None:
    index = st.session_state.selected_index
    if not isinstance(index, int):
        return None
    items = st.session_state.processing_items
    if not 0 <= index < len(items):
        return None
    item = items[index]
    if item.get('status') != 'completed':
        return None
    return item.get('result')

def render_ocr_candidate_selector(result) -> None:
    review = getattr(result, 'ocr_review', None)
    if review is None:
        return
    engines = list(result.available_ocr_engines())
    if len(engines) < 2:
        return
    st.markdown('#### Comparación OCR')
    selected = result.selected_ocr_engine
    selected_engine = st.radio('Resultado que se conservará para la exportación', options=engines, index=engines.index(selected), format_func=engine_label, horizontal=True, key=f'ocr_candidate_{result.file_name}')
    if selected_engine != selected:
        result.select_ocr_engine(selected_engine)
        st.rerun()
    cols = st.columns(len(engines))
    for col, engine in zip(cols, engines):
        candidate = review.get_candidate(engine)
        with col:
            with st.container(border=True):
                st.markdown(f'**{engine_label(engine)}**')
                st.caption(f'{candidate.movement_count} mov. · {candidate.validation_failed}/{candidate.validation_total} validaciones con falla')
    st.caption(f'Recomendación automática: {engine_label(result.recommended_ocr_engine)}. La selección actual es la que se mostrará y exportará.')

def render_primary_validations(result) -> None:
    cols = st.columns(2)
    for col, name, short in zip(cols, PRIMARY_VALIDATIONS, ('Abonos', 'Cargos')):
        item = validation(result, name)
        with col:
            with st.container(border=True):
                if item is None:
                    st.markdown(f'### — Validación {short}')
                    st.caption('No se pudo calcular')
                elif item.correcto:
                    st.markdown(f'### ✅ Validación {short}')
                    st.caption('Conciliación correcta')
                else:
                    st.markdown(f'### ❌ Validación {short}')
                    st.caption(f'Esperado {format_money(item.esperado)} · Obtenido {format_money(item.obtenido)} · Diferencia {format_money(item.diferencia)}')

def render_other_validations(result) -> None:
    all_validations = list(getattr(result, 'validaciones', []) or [])
    secondary = [item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS]
    correct = sum((1 for item in all_validations if item.correcto))
    st.caption(f'Integridad financiera: {correct}/{len(all_validations)} validaciones correctas')
    st.markdown(f'**Otras validaciones financieras ({len(secondary)})**')
    if not secondary:
        st.caption('No existen validaciones adicionales para este resultado.')
        return
    for item in secondary:
        with st.container(border=True):
            icon = '✅' if item.correcto else '❌'
            st.markdown(f'**{icon} {item.nombre}**')
            st.caption(f'Esperado {format_money(item.esperado)} · Obtenido {format_money(item.obtenido)} · Diferencia {format_money(item.diferencia)}')
            if getattr(item, 'mensaje', None):
                st.caption(safe_value(item.mensaje))

def movement_dataframe(result) -> pd.DataFrame:
    estado = result.estado_cuenta
    dc = getattr(estado, 'datos_cuenta', None)
    movements = getattr(estado, 'movimientos', None) or []
    rows = []
    for index, movement in enumerate(movements, 1):
        row: dict[str, Any] = {}
        for field_name, label in MOVEMENT_COLUMNS:
            if field_name == 'fecha_corte':
                value = getattr(dc, 'fecha_corte', None)
            elif field_name == 'numero_cuenta':
                value = getattr(dc, 'numero_cuenta', None)
            elif field_name == 'numero_movimiento':
                value = index
            elif field_name == '__bank__':
                value = str(result.bank_key).upper()
            else:
                value = getattr(movement, field_name, None)
            row[label] = value
        rows.append(row)
    df = pd.DataFrame(rows)
    for label in ('Cargo', 'Abono', 'Saldo Operación', 'Saldo Liquidación'):
        if label in df.columns:
            df[label] = pd.to_numeric(df[label], errors='coerce')
    return df

def beneficiary_analytics(result) -> pd.DataFrame:
    grouped: dict[str, list[float]] = {}
    for movement in result.estado_cuenta.movimientos or []:
        name = getattr(movement, 'beneficiario', None) or 'Sin beneficiario'
        values = grouped.setdefault(str(name), [0.0, 0.0])
        values[0] += numeric(getattr(movement, 'cargo', 0.0))
        values[1] += numeric(getattr(movement, 'abono', 0.0))
    rows = [{'Beneficiario': name, 'Cargos': values[0], 'Abonos': values[1]} for name, values in grouped.items()]
    rows.sort(key=lambda row: row['Cargos'] + row['Abonos'], reverse=True)
    if not rows:
        return pd.DataFrame(columns=['Cargos', 'Abonos'])
    return pd.DataFrame(rows[:10]).set_index('Beneficiario')

def bank_analytics() -> pd.DataFrame:
    grouped: dict[str, list[float]] = {}
    for result in st.session_state.results:
        bank = str(getattr(result, 'bank_key', 'N/A') or 'N/A').upper()
        values = grouped.setdefault(bank, [0.0, 0.0])
        estado = getattr(result, 'estado_cuenta', None)
        for movement in getattr(estado, 'movimientos', None) or []:
            values[0] += numeric(getattr(movement, 'cargo', 0.0))
            values[1] += numeric(getattr(movement, 'abono', 0.0))
    rows = [{'Banco': bank, 'Cargos': values[0], 'Abonos': values[1]} for bank, values in grouped.items()]
    if not rows:
        return pd.DataFrame(columns=['Cargos', 'Abonos'])
    return pd.DataFrame(rows).set_index('Banco')

def flow_frequency(result) -> pd.DataFrame:
    movements = result.estado_cuenta.movimientos or []
    cargos = sum((1 for movement in movements if numeric(getattr(movement, 'cargo', 0.0)) > 0))
    abonos = sum((1 for movement in movements if numeric(getattr(movement, 'abono', 0.0)) > 0))
    return pd.DataFrame({'Movimientos': [cargos, abonos]}, index=['Cargos', 'Abonos'])

def render_analytics(result) -> None:
    st.markdown('### 📊 Análisis visual')
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**Cargos y abonos por beneficiario · Top 10**')
        beneficiary = beneficiary_analytics(result)
        if beneficiary.empty:
            st.caption('Sin beneficiarios suficientes.')
        else:
            st.bar_chart(beneficiary, height=300)
    with col2:
        st.markdown('**Cargos y abonos por banco · lote procesado**')
        banks = bank_analytics()
        if banks.empty:
            st.caption('Sin datos suficientes.')
        else:
            st.bar_chart(banks, height=300)
    st.markdown('**Frecuencia de cargos y abonos**')
    st.bar_chart(flow_frequency(result), height=220)

def render_result(result) -> None:
    estado = getattr(result, 'estado_cuenta', None)
    if estado is None:
        st.warning('Resultado sin estado de cuenta.')
        return
    dc = getattr(estado, 'datos_cuenta', None)
    rf = getattr(estado, 'resumen_financiero', None)
    op = getattr(estado, 'otros_productos', None)
    movements = getattr(estado, 'movimientos', None) or []
    method = getattr(result, 'processing_method', 'Digital')
    process_text = 'Digital' if method == 'Digital' else engine_label(getattr(result, 'ocr_engine', None))
    st.markdown(f'## 🔍 {result.file_name}')
    st.caption(f'{str(result.bank_key).upper()} · {process_text}')
    cols = st.columns(4)
    cols[0].metric('Periodo', f"{safe_value(getattr(dc, 'periodo_inicio', None))} al {safe_value(getattr(dc, 'periodo_fin', None))}")
    cols[1].metric('Cliente', safe_value(getattr(dc, 'nombre_cliente', None)))
    cols[2].metric('Cuenta', safe_value(getattr(dc, 'numero_cuenta', None)))
    cols[3].metric('CLABE', safe_value(getattr(dc, 'clabe', None)))
    if method == 'OCR':
        render_ocr_candidate_selector(result)
    with st.expander('📌 Datos de la cuenta · todos los campos'):
        entries = [('Producto principal', safe_value(getattr(dc, 'producto_principal', None))), ('Periodo inicio', safe_value(getattr(dc, 'periodo_inicio', None))), ('Periodo fin', safe_value(getattr(dc, 'periodo_fin', None))), ('Fecha de corte', safe_value(getattr(dc, 'fecha_corte', None))), ('Número de cuenta', safe_value(getattr(dc, 'numero_cuenta', None))), ('Número de cliente', safe_value(getattr(dc, 'numero_cliente', None))), ('CLABE', safe_value(getattr(dc, 'clabe', None))), ('Nombre del cliente', safe_value(getattr(dc, 'nombre_cliente', None))), ('RFC', safe_value(getattr(dc, 'rfc', None)))]
        cols = st.columns(3)
        for i, (label, value) in enumerate(entries):
            cols[i % 3].metric(label, value)
    st.markdown('### 📊 Resumen financiero')
    cols = st.columns(4)
    cols[0].metric('Saldo anterior', format_money(getattr(rf, 'saldo_anterior', None)))
    cols[1].metric('Depósitos / Abonos', format_money(getattr(rf, 'depositos_abonos', None)))
    cols[2].metric('Retiros / Cargos', format_money(getattr(rf, 'retiros_cargos', None)))
    cols[3].metric('Saldo final', format_money(getattr(rf, 'saldo_final', None)))
    render_primary_validations(result)
    render_other_validations(result)
    with st.expander('📈 Resumen financiero ampliado · todos los campos'):
        entries = [('Saldo promedio', format_money(getattr(rf, 'saldo_promedio', None))), ('Días del periodo', safe_value(getattr(rf, 'dias_periodo', None))), ('Tasa bruta anual', format_optional_float(getattr(rf, 'tasa_bruta_anual', None), suffix='%')), ('Saldo promedio gravable', format_money(getattr(rf, 'saldo_promedio_gravable', None))), ('Intereses a favor', format_money(getattr(rf, 'intereses_a_favor', None))), ('ISR retenido', format_money(getattr(rf, 'isr_retenido', None))), ('Cheques pagados', safe_value(getattr(rf, 'cheques_pagados', None))), ('Manejo de cuenta', format_money(getattr(rf, 'manejo_cuenta', None))), ('Cargos objetados', format_money(getattr(rf, 'cargos_objetados', None))), ('Abonos objetados', format_money(getattr(rf, 'abonos_objetados', None))), ('Saldo promedio mínimo mensual', format_money(getattr(rf, 'saldo_promedio_minimo_mensual', None))), ('Saldo global', format_money(getattr(rf, 'saldo_global', None)))]
        cols = st.columns(4)
        for i, (label, value) in enumerate(entries):
            cols[i % 4].metric(label, value)
    with st.expander('💰 Otros productos y comisiones · todos los campos'):
        entries = [('Contrato', safe_value(getattr(op, 'contrato', None))), ('Producto', safe_value(getattr(op, 'producto', None))), ('Tasa interés anual', format_optional_float(getattr(op, 'tasa_interes_anual', None), suffix='%')), ('GAT nominal anual', format_optional_float(getattr(op, 'gat_nominal_anual', None), suffix='%')), ('GAT real anual', format_optional_float(getattr(op, 'gat_real_anual', None), suffix='%')), ('Total comisiones', format_optional_float(getattr(op, 'total_comisiones', None), prefix='$'))]
        cols = st.columns(3)
        for i, (label, value) in enumerate(entries):
            cols[i % 3].metric(label, value)
    st.markdown(f'### 📑 Movimientos ({len(movements)})')
    if not movements:
        st.warning('No se encontraron movimientos.')
        return
    df = movement_dataframe(result)
    column_config = {'Cargo': st.column_config.NumberColumn('Cargo', format='$%.2f', width='small'), 'Abono': st.column_config.NumberColumn('Abono', format='$%.2f', width='small'), 'Saldo Operación': st.column_config.NumberColumn('Saldo Operación', format='$%.2f', width='small'), 'Saldo Liquidación': st.column_config.NumberColumn('Saldo Liquidación', format='$%.2f', width='small'), 'Concepto': st.column_config.TextColumn('Concepto', width='large'), 'Concepto Original': st.column_config.TextColumn('Concepto Original', width='large')}
    st.dataframe(df, use_container_width=True, height=430, hide_index=True, column_config=column_config)
    render_analytics(result)

def render_export_section() -> None:
    if not st.session_state.results:
        return
    st.divider()
    col_text, col_button = st.columns([3, 1])
    with col_text:
        st.markdown('### 📤 Exportación')
        st.caption('El archivo incluye únicamente los resultados terminados y usa la selección OCR activa de cada PDF.')
    with col_button:
        if st.button('Preparar Excel', type='primary', use_container_width=True):
            excel_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    excel_path = tmp.name
                export_batch_excel(list(st.session_state.results), excel_path)
                with open(excel_path, 'rb') as file:
                    data = file.read()
                st.download_button('Descargar Excel', data=data, file_name='reporte_estados_de_cuenta.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
            except Exception as ex:
                st.error(f'Error al generar Excel: {ex}')
            finally:
                if excel_path:
                    try:
                        os.remove(excel_path)
                    except (FileNotFoundError, OSError):
                        pass

@st.dialog('Procesando estados de cuenta', width='small', dismissible=True, icon='spinner', on_dismiss='ignore')
def processing_dialog() -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=150)
    st.write('Los resultados terminados se conservarán y podrán revisarse mientras el resto del lote continúa.')
    col1, col2 = st.columns(2)
    with col1:
        if st.button('Continuar en segundo plano', use_container_width=True, key='dialog_background'):
            st.rerun()
    with col2:
        if st.button('Detener', use_container_width=True, key='dialog_stop'):
            st.session_state.stop_requested = True
            st.session_state.stop_event.set()
            st.rerun()

def render_header() -> None:
    with st.container(border=True):
        col_logo, col_title, col_actions = st.columns([1.2, 5.5, 1.3])
        with col_logo:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=150)
        with col_title:
            st.markdown('<div class="app-title">Extractor de Movimientos Financieros</div>', unsafe_allow_html=True)
            st.caption('Secretaría Anticorrupción y Buen Gobierno · Dirección General de Evaluación de Confianza')
        with col_actions:
            st.markdown(f'<span class="version-pill">Versión {APP_VERSION}</span>', unsafe_allow_html=True)
            with st.popover('⚙️', help='Configuración', disabled=st.session_state.worker_running):
                engine = st.selectbox('Motor OCR principal', options=['tesseract', 'paddleocr'], index=0 if st.session_state.ocr_primary_engine == 'tesseract' else 1, format_func=engine_label)
                st.caption('Se recomienda Tesseract. Cambie a PaddleOCR sólo si observa diferencias importantes entre el PDF original y el resultado exportado; suele ser más lento.')
                if st.button('Guardar configuración', key='save_config'):
                    st.session_state.ocr_primary_engine = normalize_ocr_engine(engine)
                    st.success('Guardado')
            with st.popover('❔', help='Ayuda'):
                st.markdown('**Validaciones**  \nA y C representan las conciliaciones principales de Abonos y Cargos.')
                st.markdown('**Formatos habilitados**  \nBBVA Digital · Banorte Digital/Escaneado · Banamex Digital · HSBC Digital/Escaneado · Scotiabank Digital · Mifel · CETESDIRECTO · MercadoPago')

def main() -> None:
    st.set_page_config(page_title='Extractor de Movimientos Financieros', layout='wide')
    initialize_session_state()
    inject_css()
    render_header()
    if st.session_state.worker_running and st.session_state.initial_dialog_pending:
        st.session_state.initial_dialog_pending = False
        processing_dialog()
    uploaded_files = st.file_uploader('Seleccionar estados de cuenta PDF', type='pdf', accept_multiple_files=True, disabled=st.session_state.worker_running)
    if uploaded_files:
        uploaded_files_data = tuple(((uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in uploaded_files))
        current_signature = create_batch_signature(uploaded_files_data)
        if current_signature != st.session_state.batch_signature and (not st.session_state.worker_running):
            try:
                start_processing(uploaded_files_data)
                st.toast('Procesamiento iniciado', icon='⏳')
                st.rerun()
            except Exception as ex:
                st.error(f'No fue posible iniciar el procesamiento: {ex}')
    if st.session_state.worker_error:
        st.error(f'Error durante el procesamiento: {st.session_state.worker_error}')
        if st.session_state.worker_traceback:
            with st.expander('Detalle técnico'):
                st.code(st.session_state.worker_traceback)
    processing_status_fragment()
    if st.session_state.processing_items:
        st.markdown('### Resultados disponibles')
        render_result_selector()
    result = selected_result()
    if result is not None:
        st.divider()
        render_result(result)
    render_export_section()
if __name__ == '__main__':
    main()
