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
from exporters.excel.batch_exporter import pending_ocr_selection_files

APP_VERSION = '2.4'
PROCESSING_UI_POLL_INTERVAL = 0.75

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
FINAL_STATUSES = {'completed', 'error', 'cancelled'}
MOVEMENT_COLUMNS = [
    ('fecha_corte', 'Fecha Corte'),
    ('numero_cuenta', 'Número de Cuenta'),
    ('numero_movimiento', 'No. Movimiento'),
    ('fecha_operacion', 'Fecha Operación'),
    ('fecha_liquidacion', 'Fecha Liquidación'),
    ('concepto', 'Concepto'),
    ('cargo', 'Cargo'),
    ('abono', 'Abono'),
    ('saldo_operacion', 'Saldo Operación'),
    ('saldo_liquidacion', 'Saldo Liquidación'),
    ('tipo_operacion', 'Tipo'),
    ('beneficiario', 'Beneficiario'),
    ('cuenta_beneficiario', 'Cuenta Benef.'),
    ('clabe_beneficiario', 'CLABE Benef.'),
    ('rfc', 'RFC'),
    ('referencia', 'Referencia'),
    ('clave_rastreo', 'Clave Rastreo'),
    ('autorizacion', 'Autorización'),
    ('hora_operacion', 'Hora'),
    ('__bank__', 'Banco'),
    ('caja', 'Caja'),
    ('concepto_original', 'Concepto Original'),
]


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
    defaults = {
        'processing_queue': Queue(),
        'processing_items': [],
        'results': [],
        'worker_thread': None,
        'worker_running': False,
        'worker_finished': False,
        'worker_error': None,
        'worker_traceback': None,
        'batch_signature': None,
        'batch_temp_paths': [],
        'selected_index': None,
        'ocr_primary_engine': normalize_ocr_engine(
            os.getenv('OCR_PRIMARY_ENGINE', 'tesseract')
        ),
        'stop_event': threading.Event(),
        'stop_requested': False,
        'started_at': None,
        'initial_dialog_pending': False,
        'result_filter': '',
        'uploader_nonce': 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def inject_css() -> None:
    st.markdown(
        f'''
        <style>
        .stApp {{
            background: #FBFBFC;
        }}
        [data-testid="stHeader"] {{
            background: rgba(251,251,252,0.94);
        }}
        .app-title {{
            font-size: 1.75rem;
            font-weight: 750;
            color: #202124;
            line-height: 1.15;
        }}
        .version-pill {{
            display: inline-block;
            background: {GOB_GOLD_LIGHT};
            border-radius: 999px;
            padding: 4px 10px;
            font-size: .76rem;
            font-weight: 700;
        }}
        .bank-label {{
            background: {GOB_CREAM};
            color: {GOB_GREEN_DARK};
            border-radius: 7px;
            padding: 5px 8px;
            font-size: .82rem;
            font-weight: 700;
            margin: 4px 0;
        }}
        .processing-card {{
            background: white;
            border: 1px solid #DADDE1;
            border-left: 5px solid {GOB_GREEN};
            border-radius: 12px;
            padding: 10px 14px;
            margin: 6px 0 12px 0;
        }}
        .processing-card.stop {{
            border-left-color: {DANGER};
        }}
        .tiny-note {{
            color: #6B7075;
            font-size: .78rem;
        }}
        .live-note {{
            color: #6B7075;
            font-size: .78rem;
            margin-top: -8px;
            margin-bottom: 6px;
        }}
        .selector-columns {{
            color: #6B7075;
            font-size: .72rem;
            font-weight: 700;
            margin: 0 0 3px 0;
        }}
        .movement-total {{
            background: {GOB_CREAM};
            border: 1px solid #E0DDD7;
            border-radius: 8px;
            padding: 6px 10px;
            min-height: 2.25rem;
            line-height: 1.05;
        }}
        .movement-total .label {{
            color: #6B7075;
            font-size: .70rem;
        }}
        .movement-total .value {{
            color: #202124;
            font-size: .93rem;
            font-weight: 750;
        }}
        div[data-testid="stMetric"] {{
            background: white;
            border: 1px solid #E0E3E7;
            border-radius: 10px;
            padding: 8px 10px;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid #DADDE1;
            border-radius: 10px;
            overflow: hidden;
        }}
        div[data-testid="stTextInput"] input {{
            min-height: 2.25rem;
            height: 2.25rem;
            font-size: .88rem;
        }}
        div[data-baseweb="select"] > div {{
            min-height: 2.25rem;
            font-size: .88rem;
        }}
        </style>
        ''',
        unsafe_allow_html=True,
    )


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


def processing_worker(
    temp_paths: list[str],
    names: list[str],
    processing_queue: Queue,
    primary_engine: str,
    stop_event: threading.Event,
) -> None:
    try:
        for event in process_bank_statements_incremental(
            temp_paths,
            names,
            ocr_primary_engine=primary_engine,
            cancel_event=stop_event,
        ):
            processing_queue.put(('event', event))
    except Exception as ex:
        processing_queue.put(('worker_error', ex, traceback_string()))
    finally:
        processing_queue.put(('finished',))
        cleanup_temp_paths(temp_paths)


def start_processing(uploaded_files_data: tuple[tuple[str, bytes], ...]) -> None:
    temp_paths = materialize_uploaded_files(uploaded_files_data)
    processing_items = [
        {
            'file_name': file_name,
            'processing_method': None,
            'status': 'classifying',
            'result': None,
            'error': None,
        }
        for file_name, _ in uploaded_files_data
    ]
    processing_queue = Queue()
    stop_event = threading.Event()
    primary_engine = normalize_ocr_engine(st.session_state.ocr_primary_engine)
    worker = threading.Thread(
        target=processing_worker,
        args=(
            temp_paths,
            [name for name, _ in uploaded_files_data],
            processing_queue,
            primary_engine,
            stop_event,
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
    st.session_state.stop_event = stop_event
    st.session_state.stop_requested = False
    st.session_state.started_at = time.perf_counter()
    st.session_state.initial_dialog_pending = True
    st.session_state.result_filter = ''
    worker.start()


def reset_batch() -> None:
    if st.session_state.worker_running:
        return
    st.session_state.processing_queue = Queue()
    st.session_state.processing_items = []
    st.session_state.results = []
    st.session_state.worker_thread = None
    st.session_state.worker_finished = False
    st.session_state.worker_error = None
    st.session_state.worker_traceback = None
    st.session_state.batch_signature = None
    st.session_state.batch_temp_paths = []
    st.session_state.selected_index = None
    st.session_state.stop_event = threading.Event()
    st.session_state.stop_requested = False
    st.session_state.started_at = None
    st.session_state.initial_dialog_pending = False
    st.session_state.result_filter = ''
    st.session_state.uploader_nonce += 1


def consume_processing_events() -> tuple[bool, bool, bool, bool]:
    changed = False
    completed_added = False
    first_selection_added = False
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
                item.update(
                    processing_method=event.processing_method,
                    status='processing',
                    error=None,
                )
                changed = True
            elif event.kind == 'completed':
                item.update(
                    processing_method=event.processing_method,
                    status='completed',
                    result=event.result,
                    error=None,
                )
                if event.result is not None:
                    results.append(event.result)
                    completed_added = True
                    if st.session_state.selected_index is None:
                        st.session_state.selected_index = index
                        first_selection_added = True
                changed = True
            elif event.kind == 'cancelled':
                item.update(
                    processing_method=(
                        event.processing_method or item.get('processing_method')
                    ),
                    status='cancelled',
                    result=None,
                    error=None,
                )
                changed = True
            elif event.kind == 'error':
                item.update(
                    processing_method=(
                        event.processing_method or item.get('processing_method')
                    ),
                    status='error',
                    result=None,
                    error=str(event.error or 'Error desconocido'),
                )
                changed = True
        elif message_type == 'worker_error':
            ex, tb = message[1], message[2]
            st.session_state.worker_error = str(ex)
            st.session_state.worker_traceback = tb
            for item in items:
                if item.get('status') not in FINAL_STATUSES:
                    item.update(status='error', error=str(ex))
            changed = True
        elif message_type == 'finished':
            if st.session_state.stop_requested:
                for item in items:
                    if item.get('status') not in FINAL_STATUSES:
                        item.update(status='cancelled', result=None, error=None)
            st.session_state.worker_running = False
            st.session_state.worker_finished = True
            changed = True
            finished = True
    return changed, completed_added, first_selection_added, finished


def processing_counts() -> tuple[int, int, int, int, int]:
    items = st.session_state.processing_items
    total = len(items)
    completed = sum(item.get('status') == 'completed' for item in items)
    errors = sum(item.get('status') == 'error' for item in items)
    cancelled = sum(item.get('status') == 'cancelled' for item in items)
    scanned_active = sum(
        item.get('status') == 'processing' and item.get('processing_method') == 'OCR'
        for item in items
    )
    return total, completed, errors, cancelled, scanned_active


def validation(result, name: str):
    if result is None:
        return None
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
        review = getattr(result, 'ocr_review', None)
        if review is not None and review.requires_user_selection:
            return f'{label} · {"elegido" if result.ocr_selection_confirmed else "elegir"}'
        if getattr(result, 'fallback_attempted', False):
            return f'{label} · revisado'
        return label
    return 'Detectando'


def bank_key_for_item(item: dict[str, Any]) -> str:
    result = item.get('result')
    if result is not None:
        return str(getattr(result, 'bank_key', 'desconocido') or 'desconocido').upper()
    status = item.get('status')
    if status == 'processing':
        return 'PROCESANDO'
    if status == 'error':
        return 'ERROR'
    if status == 'cancelled':
        return 'CANCELADO'
    return 'PENDIENTE'


def status_label(item: dict[str, Any]) -> str:
    return {
        'classifying': '⏳ Detectando tipo',
        'processing': '⏳ Procesando',
        'completed': '✅ Terminado',
        'error': '❌ Error',
        'cancelled': '⏹ Cancelado',
    }.get(str(item.get('status')), '○ Pendiente')


def item_matches_filter(item: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = ' '.join(
        [
            str(item.get('file_name') or ''),
            process_label(item),
            bank_key_for_item(item),
            status_label(item),
            str(item.get('error') or ''),
        ]
    ).lower()
    return query.lower() in haystack


def completed_items() -> list[tuple[int, dict[str, Any]]]:
    return [
        (index, item)
        for index, item in enumerate(st.session_state.processing_items)
        if item.get('status') == 'completed' and item.get('result') is not None
    ]


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
            css_class = 'processing-card stop'
        else:
            title = f'Procesando {completed} de {total} archivos'
            css_class = 'processing-card'
        st.markdown(
            f'''
            <div class="{css_class}">
              <strong>{title}</strong><br>
              <span class="tiny-note">
                Tiempo {elapsed // 60:02d}:{elapsed % 60:02d}
                {(' · OCR activo' if scanned_active else '')}
                {(' · ' + str(errors) + ' con error' if errors else '')}
              </span>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        if st.button(
            '⏹ Detener procesamiento',
            type='secondary',
            disabled=st.session_state.stop_requested,
            key='stop_processing',
        ):
            st.session_state.stop_requested = True
            st.session_state.stop_event.set()
            st.rerun(scope='fragment')
    elif st.session_state.stop_requested:
        st.warning(
            f'⏹ Procesamiento detenido. Se conservaron {completed} resultado(s); '
            f'{cancelled} archivo(s) se omitieron.'
        )
    elif errors:
        st.warning(f'✅ {completed} correctos · ⚠️ {errors} con error')
    else:
        st.success(f'✅ {completed} archivos procesados correctamente')


def render_unclassified(items: list[tuple[int, dict[str, Any]]]) -> None:
    if not items:
        return
    with st.container(border=True):
        st.markdown('**Detectando tipo de PDF**')
        for _index, item in items:
            detail = item.get('error') or status_label(item)
            st.caption(f"{status_label(item)} · {item.get('file_name', '')} · {detail}")


def select_result(index: int) -> None:
    if st.session_state.selected_index == index:
        return
    st.session_state.selected_index = index
    st.rerun()


def render_selector_column(
    title: str,
    items: list[tuple[int, dict[str, Any]]],
) -> None:
    st.markdown(f'#### {title}')
    st.markdown(
        '<div class="selector-columns">Archivo / estado · Motor · Abonos · Cargos</div>',
        unsafe_allow_html=True,
    )
    if not items:
        st.caption('Sin archivos en este filtro.')
        return
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, item in items:
        grouped.setdefault(bank_key_for_item(item), []).append((index, item))
    for bank in sorted(grouped):
        st.markdown(
            f'<div class="bank-label">{bank} · {len(grouped[bank])} archivo(s)</div>',
            unsafe_allow_html=True,
        )
        for index, item in grouped[bank]:
            result = item.get('result')
            abonos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))
            cargos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))
            selected = st.session_state.selected_index == index
            label = (
                f"{status_label(item)} · {item['file_name']} · {process_label(item)} · "
                f'Abonos {abonos} · Cargos {cargos}'
            )
            completed = item.get('status') == 'completed' and result is not None
            if st.button(
                label,
                key=f'result_{index}',
                use_container_width=True,
                type='primary' if selected and completed else 'secondary',
                disabled=not completed,
            ):
                select_result(index)


def render_result_selector() -> None:
    items = list(enumerate(st.session_state.processing_items))
    if not items:
        return

    completed = completed_items()
    filter_col, dropdown_col, _spacer = st.columns([1, 1.15, 1.85])
    with filter_col:
        query = st.text_input(
            'Filtrar resultados',
            value=st.session_state.result_filter,
            placeholder='Filtrar PDF, banco o estado',
            label_visibility='collapsed',
            key='result_filter_widget',
        )
        st.session_state.result_filter = query
    with dropdown_col:
        if completed:
            indices = [index for index, _item in completed]
            selected_index = st.session_state.selected_index
            selected_position = (
                indices.index(selected_index) if selected_index in indices else 0
            )
            chosen = st.selectbox(
                'Ir a resultado',
                options=indices,
                index=selected_position,
                format_func=lambda idx: (
                    f"{st.session_state.processing_items[idx]['file_name']} · "
                    f"{bank_key_for_item(st.session_state.processing_items[idx])} · "
                    f"{process_label(st.session_state.processing_items[idx])}"
                ),
                label_visibility='collapsed',
                key='result_jump',
            )
            if chosen != st.session_state.selected_index:
                st.session_state.selected_index = chosen
                st.rerun()
        else:
            st.selectbox(
                'Ir a resultado',
                options=['Sin resultados terminados'],
                disabled=True,
                label_visibility='collapsed',
                key='result_jump_empty',
            )

    st.markdown(
        '<div class="live-note">Los archivos aparecen aquí mientras se procesan.</div>',
        unsafe_allow_html=True,
    )
    visible = [
        (index, item)
        for index, item in items
        if item_matches_filter(item, query.strip())
    ]
    unclassified = [
        (index, item)
        for index, item in visible
        if item.get('processing_method') not in {'Digital', 'OCR'}
    ]
    render_unclassified(unclassified)

    digital = [
        (index, item)
        for index, item in visible
        if item.get('processing_method') == 'Digital'
    ]
    scanned = [
        (index, item)
        for index, item in visible
        if item.get('processing_method') == 'OCR'
    ]
    col_digital, col_scanned = st.columns(2)
    with col_digital:
        render_selector_column('📄 PDFs digitales', digital)
    with col_scanned:
        render_selector_column('🖨️ PDFs escaneados (OCR)', scanned)


@st.fragment(run_every=PROCESSING_UI_POLL_INTERVAL)
def live_processing_fragment() -> None:
    _changed, _completed_added, first_selection_added, finished = consume_processing_events()
    render_processing_card()
    st.markdown('### Resultados disponibles')
    render_result_selector()
    if first_selection_added or finished:
        st.rerun()


def render_static_processing_workspace() -> None:
    consume_processing_events()
    render_processing_card()
    if st.session_state.processing_items:
        st.markdown('### Resultados disponibles')
        render_result_selector()


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
    active = result.selected_ocr_engine
    confirmed = result.confirmed_ocr_engine
    recommended = result.recommended_ocr_engine
    st.caption(
        f'Sugerencia automática: {engine_label(recommended)}. '
        'Puedes revisar ambos resultados; la sugerencia no se conserva para el Excel por defecto.'
    )
    if confirmed is None:
        st.warning('Debes elegir explícitamente uno de los dos motores antes de exportar este archivo.')
    else:
        st.success(f'Para el Excel se conservará: {engine_label(confirmed)}.')

    cols = st.columns(len(engines))
    for col, engine in zip(cols, engines):
        candidate = review.get_candidate(engine)
        is_active = engine == active
        is_confirmed = engine == confirmed
        with col:
            with st.container(border=True):
                title_suffix = []
                if is_active:
                    title_suffix.append('vista actual')
                if is_confirmed:
                    title_suffix.append('elegido para Excel')
                suffix = f" · {' · '.join(title_suffix)}" if title_suffix else ''
                st.markdown(f'**{engine_label(engine)}{suffix}**')
                st.caption(
                    f'{candidate.movement_count} mov. · '
                    f'{candidate.validation_failed}/{candidate.validation_total} validaciones con falla'
                )
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button(
                        'Ver resultado',
                        key=f'ocr_preview_{result.file_name}_{engine}',
                        disabled=is_active,
                        use_container_width=True,
                    ):
                        result.preview_ocr_engine(engine)
                        st.rerun()
                with action_cols[1]:
                    if st.button(
                        'Elegir para Excel' if not is_confirmed else 'Elegido ✓',
                        key=f'ocr_confirm_{result.file_name}_{engine}',
                        disabled=is_confirmed,
                        type='primary' if not is_confirmed else 'secondary',
                        use_container_width=True,
                    ):
                        result.select_ocr_engine(engine)
                        st.rerun()


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
                    st.caption(
                        f'Esperado {format_money(item.esperado)} · '
                        f'Obtenido {format_money(item.obtenido)} · '
                        f'Diferencia {format_money(item.diferencia)}'
                    )


def render_other_validations(result) -> None:
    all_validations = list(getattr(result, 'validaciones', []) or [])
    secondary = [item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS]
    correct = sum(item.correcto for item in all_validations)
    st.caption(
        f'Integridad financiera: {correct}/{len(all_validations)} validaciones correctas'
    )
    st.markdown(f'**Otras validaciones financieras ({len(secondary)})**')
    if not secondary:
        st.caption('No existen validaciones adicionales para este resultado.')
        return
    for item in secondary:
        with st.container(border=True):
            icon = '✅' if item.correcto else '❌'
            st.markdown(f'**{icon} {item.nombre}**')
            st.caption(
                f'Esperado {format_money(item.esperado)} · '
                f'Obtenido {format_money(item.obtenido)} · '
                f'Diferencia {format_money(item.diferencia)}'
            )
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


def filter_movement_dataframe(df: pd.DataFrame, query: str) -> pd.DataFrame:
    query = query.strip()
    if not query or df.empty:
        return df
    searchable = df.fillna('').astype(str).agg(' '.join, axis=1)
    return df[searchable.str.contains(query, case=False, regex=False, na=False)]


def beneficiary_analytics(result) -> pd.DataFrame:
    grouped: dict[str, list[float]] = {}
    for movement in result.estado_cuenta.movimientos or []:
        name = getattr(movement, 'beneficiario', None) or 'Sin beneficiario'
        values = grouped.setdefault(str(name), [0.0, 0.0])
        values[0] += numeric(getattr(movement, 'cargo', 0.0))
        values[1] += numeric(getattr(movement, 'abono', 0.0))
    rows = [
        {'Beneficiario': name, 'Cargos': values[0], 'Abonos': values[1]}
        for name, values in grouped.items()
    ]
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
    rows = [
        {'Banco': bank, 'Cargos': values[0], 'Abonos': values[1]}
        for bank, values in grouped.items()
    ]
    if not rows:
        return pd.DataFrame(columns=['Cargos', 'Abonos'])
    return pd.DataFrame(rows).set_index('Banco')


def flow_frequency(result) -> pd.DataFrame:
    movements = result.estado_cuenta.movimientos or []
    cargos = sum(numeric(getattr(movement, 'cargo', 0.0)) > 0 for movement in movements)
    abonos = sum(numeric(getattr(movement, 'abono', 0.0)) > 0 for movement in movements)
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


def render_movement_total(label: str, value: float) -> None:
    st.markdown(
        f'''
        <div class="movement-total">
          <div class="label">{label}</div>
          <div class="value">{format_money(value)}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


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
    process_text = (
        'Digital' if method == 'Digital' else engine_label(getattr(result, 'ocr_engine', None))
    )

    st.markdown(f'## 🔍 {result.file_name}')
    st.caption(f'{str(result.bank_key).upper()} · {process_text}')
    cols = st.columns(4)
    cols[0].metric(
        'Periodo',
        f"{safe_value(getattr(dc, 'periodo_inicio', None))} al "
        f"{safe_value(getattr(dc, 'periodo_fin', None))}",
    )
    cols[1].metric('Cliente', safe_value(getattr(dc, 'nombre_cliente', None)))
    cols[2].metric('Cuenta', safe_value(getattr(dc, 'numero_cuenta', None)))
    cols[3].metric('CLABE', safe_value(getattr(dc, 'clabe', None)))

    if method == 'OCR':
        render_ocr_candidate_selector(result)

    with st.expander('📌 Datos de la cuenta · todos los campos'):
        entries = [
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
        entries = [
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
        cols = st.columns(4)
        for i, (label, value) in enumerate(entries):
            cols[i % 4].metric(label, value)

    with st.expander('💰 Otros productos y comisiones · todos los campos'):
        entries = [
            ('Contrato', safe_value(getattr(op, 'contrato', None))),
            ('Producto', safe_value(getattr(op, 'producto', None))),
            ('Tasa interés anual', format_optional_float(getattr(op, 'tasa_interes_anual', None), suffix='%')),
            ('GAT nominal anual', format_optional_float(getattr(op, 'gat_nominal_anual', None), suffix='%')),
            ('GAT real anual', format_optional_float(getattr(op, 'gat_real_anual', None), suffix='%')),
            ('Total comisiones', format_optional_float(getattr(op, 'total_comisiones', None), prefix='$')),
        ]
        cols = st.columns(3)
        for i, (label, value) in enumerate(entries):
            cols[i % 3].metric(label, value)

    st.markdown(f'### 📑 Movimientos ({len(movements)})')
    if not movements:
        st.warning('No se encontraron movimientos.')
        return

    df = movement_dataframe(result)
    filter_col, cargo_col, abono_col, _space = st.columns([2.2, 1, 1, 2.2])
    with filter_col:
        movement_query = st.text_input(
            'Filtrar movimientos',
            placeholder='Buscar fecha, concepto, beneficiario, referencia, importe…',
            label_visibility='collapsed',
            key=f'movement_filter_{result.file_name}',
        )
    filtered_df = filter_movement_dataframe(df, movement_query)
    cargo_total = (
        pd.to_numeric(filtered_df['Cargo'], errors='coerce').fillna(0).sum()
        if 'Cargo' in filtered_df.columns
        else 0.0
    )
    abono_total = (
        pd.to_numeric(filtered_df['Abono'], errors='coerce').fillna(0).sum()
        if 'Abono' in filtered_df.columns
        else 0.0
    )
    with cargo_col:
        render_movement_total('Cargos', float(cargo_total))
    with abono_col:
        render_movement_total('Abonos', float(abono_total))

    st.caption(
        f'Mostrando {len(filtered_df)} de {len(df)} movimiento(s). '
        'Los totales corresponden al filtro actual.'
    )
    column_config = {
        'Cargo': st.column_config.NumberColumn('Cargo', format='$%.2f', width='small'),
        'Abono': st.column_config.NumberColumn('Abono', format='$%.2f', width='small'),
        'Saldo Operación': st.column_config.NumberColumn(
            'Saldo Operación', format='$%.2f', width='small'
        ),
        'Saldo Liquidación': st.column_config.NumberColumn(
            'Saldo Liquidación', format='$%.2f', width='small'
        ),
        'Concepto': st.column_config.TextColumn('Concepto', width='large'),
        'Concepto Original': st.column_config.TextColumn('Concepto Original', width='large'),
    }
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=430,
        hide_index=True,
        column_config=column_config,
    )
    if st.toggle(
        'Mostrar análisis visual',
        value=False,
        key=f'analytics_toggle_{result.file_name}',
    ):
        render_analytics(result)


def render_export_section() -> None:
    if not st.session_state.results:
        return
    st.divider()
    pending = pending_ocr_selection_files(list(st.session_state.results))
    col_text, col_button = st.columns([3, 1])
    with col_text:
        st.markdown('### 📤 Exportación')
        st.caption(
            'El archivo incluye únicamente resultados terminados. En PDFs con dos motores OCR, la elección para Excel debe ser explícita.'
        )
        if pending:
            st.warning(
                f'Falta elegir el motor OCR para {len(pending)} archivo(s): '
                + ', '.join(pending[:3])
                + ('…' if len(pending) > 3 else '')
            )
    with col_button:
        if st.button(
            'Preparar Excel',
            type='primary',
            use_container_width=True,
            disabled=bool(pending),
        ):
            excel_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    excel_path = tmp.name
                export_batch_excel(list(st.session_state.results), excel_path)
                with open(excel_path, 'rb') as file:
                    data = file.read()
                st.download_button(
                    'Descargar Excel',
                    data=data,
                    file_name='reporte_estados_de_cuenta.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True,
                )
            except Exception as ex:
                st.error(f'Error al generar Excel: {ex}')
            finally:
                if excel_path:
                    try:
                        os.remove(excel_path)
                    except (FileNotFoundError, OSError):
                        pass


@st.dialog(
    'Procesando estados de cuenta',
    width='small',
    dismissible=True,
    icon='spinner',
    on_dismiss='ignore',
)
def processing_dialog() -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=150)
    st.write(
        'Los PDFs aparecerán en Resultados disponibles en cuanto se clasifique su tipo. '
        'Puedes cerrar esta ventana y revisar los resultados mientras continúa el lote.'
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button('Ver procesamiento', use_container_width=True, key='dialog_background'):
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
            st.markdown(
                '<div class="app-title">Extractor de Movimientos Financieros</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                'Secretaría Anticorrupción y Buen Gobierno · Dirección General de Evaluación de Confianza'
            )
        with col_actions:
            st.markdown(
                f'<span class="version-pill">Versión {APP_VERSION}</span>',
                unsafe_allow_html=True,
            )
            with st.popover(
                '⚙️',
                help='Configuración',
                disabled=st.session_state.worker_running,
            ):
                engine = st.selectbox(
                    'Motor OCR principal',
                    options=['tesseract', 'paddleocr'],
                    index=(
                        0 if st.session_state.ocr_primary_engine == 'tesseract' else 1
                    ),
                    format_func=engine_label,
                )
                st.caption(
                    'El motor principal sólo define el orden de procesamiento. Cuando se ejecutan ambos motores, tú eliges cuál resultado conservar para el Excel.'
                )
                if st.button('Guardar configuración', key='save_config'):
                    st.session_state.ocr_primary_engine = normalize_ocr_engine(engine)
                    st.success('Guardado')
            with st.popover('❔', help='Ayuda'):
                st.markdown(
                    '**Validaciones**  \nLas columnas Abonos y Cargos muestran las conciliaciones principales sin abreviaturas.'
                )
                st.markdown(
                    '**OCR dual**  \nSi existen resultados de Tesseract y PaddleOCR puedes revisar ambos y debes elegir explícitamente cuál conservar para Excel.'
                )
                st.markdown(
                    '**Estados vivos**  \nLos PDFs se muestran mientras se clasifican y procesan. Los terminados pueden revisarse sin esperar al lote completo.'
                )
                st.markdown(
                    '**Formatos habilitados**  \nBBVA Digital · Banorte Digital/Escaneado · Banamex Digital · HSBC Digital/Escaneado · Scotiabank Digital · Mifel · CETESDIRECTO · MercadoPago'
                )


def render_upload_area() -> None:
    uploader_key = f'statement_uploader_{st.session_state.uploader_nonce}'
    uploaded_files = st.file_uploader(
        'Seleccionar estados de cuenta PDF',
        type='pdf',
        accept_multiple_files=True,
        disabled=st.session_state.worker_running,
        key=uploader_key,
    )

    if (
        not st.session_state.worker_running
        and st.session_state.processing_items
        and st.button('Nuevo lote', type='secondary', key='new_batch')
    ):
        reset_batch()
        st.rerun()

    if uploaded_files:
        uploaded_files_data = tuple(
            (uploaded_file.name, uploaded_file.getvalue())
            for uploaded_file in uploaded_files
        )
        current_signature = create_batch_signature(uploaded_files_data)
        if (
            current_signature != st.session_state.batch_signature
            and not st.session_state.worker_running
        ):
            try:
                start_processing(uploaded_files_data)
                st.toast('Procesamiento iniciado', icon='⏳')
                st.rerun()
            except Exception as ex:
                st.error(f'No fue posible iniciar el procesamiento: {ex}')


def main() -> None:
    st.set_page_config(page_title='Extractor de Movimientos Financieros', layout='wide')
    initialize_session_state()
    inject_css()
    render_header()

    if st.session_state.worker_running and st.session_state.initial_dialog_pending:
        st.session_state.initial_dialog_pending = False
        processing_dialog()

    render_upload_area()

    if st.session_state.worker_error:
        st.error(f'Error durante el procesamiento: {st.session_state.worker_error}')
        if st.session_state.worker_traceback:
            with st.expander('Detalle técnico'):
                st.code(st.session_state.worker_traceback)

    if st.session_state.worker_running:
        live_processing_fragment()
    else:
        render_static_processing_workspace()

    result = selected_result()
    if result is not None:
        st.divider()
        render_result(result)

    render_export_section()


if __name__ == '__main__':
    main()
