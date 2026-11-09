"""Browser UI using the same Excel/CEP services as the Windows application."""

from __future__ import annotations

import hashlib
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

import streamlit as st

from cep.evidence import CepEvidence, match_evidence
from cep.package import append_cep, export_cep_zip
from cep.queries import BANXICO_BATCH_URL, batch_texts, queries_from_workbook
from exporters.excel.workbook_bundle import WorkbookBundle, original_from_results


def set_cep_bundle(bundle):
    for key in ('cep_txt_files', 'cep_final_zip', 'cep_enriched_pair', 'cep_txt_adjacent'):
        st.session_state.pop(key, None)
    queries = queries_from_workbook(bundle.improved)
    st.session_state.cep_bundle = bundle
    st.session_state.cep_queries = queries
    st.session_state.cep_normalized = True
    st.session_state.cep_evidence = CepEvidence()


def set_cep_source(source, name="movimientos.xlsx"):
    bundle = WorkbookBundle.from_uploaded(source, source_name=name)
    queries = queries_from_workbook(bundle.improved)
    for key in ('cep_bundle', 'cep_queries', 'cep_txt_files', 'cep_final_zip',
                'cep_enriched_pair', 'cep_txt_adjacent'):
        st.session_state.pop(key, None)
    st.session_state.cep_source = bundle.original
    st.session_state.cep_source_name = name
    st.session_state.cep_bundle = bundle
    st.session_state.cep_queries = queries
    st.session_state.cep_normalized = False
    st.session_state.cep_evidence = CepEvidence()


def render_cep_workspace(results, busy=False):
    st.subheader("CEP Banxico")
    st.caption(
        "Carga cualquier Excel de Estado Cuenta Engine (antiguo, original, mejorado o cruzado). "
        "Puedes generar TXT inmediatamente desde las correcciones de Movimientos; "
        "normalizar es opcional. El Excel original del motor se descarga en Extracción."
    )
    uploaded = st.file_uploader("Excel de movimientos", type=["xlsx"], key="cep_excel_upload")
    if uploaded:
        data = uploaded.getvalue()
        token = hashlib.sha256(data).hexdigest()
        if st.session_state.get("cep_excel_token") != token:
            try:
                set_cep_source(data, uploaded.name)
                st.session_state.cep_excel_token = token
            except Exception as error:
                st.error(str(error))
    if st.button("Usar extracción actual", key="cep_use_current", disabled=busy or not results):
        try:
            with st.spinner("Cargando los movimientos…"):
                set_cep_source(original_from_results(list(results)))
        except Exception as error:
            st.error(str(error))
    source = st.session_state.get("cep_source")
    if source is None:
        return
    st.write(st.session_state.cep_source_name)
    if st.button("Normalizar Excel", type="primary", key="cep_normalize"):
        try:
            with st.spinner("Homologando fechas y recuperando datos SPEI…"):
                set_cep_bundle(WorkbookBundle.from_excel(source, source_name=st.session_state.cep_source_name))
        except Exception as error:
            st.error(str(error))
    bundle = st.session_state.get("cep_bundle")
    if bundle is None:
        return
    queries = st.session_state.cep_queries
    evidence = st.session_state.cep_evidence
    candidates = [q for q in queries if q.candidate]
    state = "Excel normalizado" if st.session_state.get("cep_normalized") else "Excel cargado sin modificaciones"
    st.write(
        f"{state} · {bundle.report.movements} movimientos · "
        f"{sum(q.ready for q in candidates)} candidatos con datos para TXT"
        + (f" · {bundle.report.dates_review} fechas para revisión" if st.session_state.get("cep_normalized") else "")
    )
    st.subheader("Preparar TXT")
    adjacent = st.checkbox("Fecha homologada y reintentos ±1 día", value=True, key="cep_adjacent_dates")
    if st.button("Preparar TXT Banxico", key="cep_make_txt"):
        try:
            st.session_state.cep_txt_files = batch_texts(queries, adjacent_days=adjacent)
            st.session_state.cep_txt_adjacent = adjacent
        except Exception as error:
            st.error(str(error))
    if st.session_state.get("cep_txt_files") and st.session_state.get('cep_txt_adjacent') == adjacent:
        files = st.session_state.cep_txt_files
        for name, content in files.items():
            st.download_button("Descargar TXT Banxico" if len(files) == 1 else f"Descargar {name}", content,
                               "consultas_banxico.txt" if len(files) == 1 else name, "text/plain; charset=utf-8", key="cep_txt_" + name)
    st.link_button("Abrir consulta por lotes en Banxico", BANXICO_BATCH_URL)
    st.caption("Carga los TXT en Banxico y solicita PDF y XML. Después importa aquí los ZIP descargados.")
    st.subheader("Cruzar resultados Banxico")
    zips = st.file_uploader("ZIP Banxico (puedes seleccionar varios)", type=["zip"], accept_multiple_files=True, key="cep_zip_upload")
    if zips and st.button("Importar ZIP y cruzar", key="cep_import_zips"):
        try:
            with st.spinner("Cruzando comprobantes con los movimientos…"):
                combined = deepcopy(evidence)
                for file in zips:
                    combined.add_zip(file.getvalue(), name=file.name)
                st.session_state.cep_evidence = evidence = combined
                st.session_state.pop('cep_final_zip', None)
                combined_matches = match_evidence(queries, evidence)
                st.session_state.cep_enriched_pair = (
                    append_cep(bundle.original, combined_matches, queries, evidence),
                    append_cep(bundle.improved, combined_matches, queries, evidence))
        except Exception as error:
            st.error(str(error))
    matches = match_evidence(queries, evidence) if evidence.preserved else {}
    if matches:
        counts = Counter(v["CEP Estado"] for v in matches.values())
        st.write(" · ".join(f"{name}: {count}" for name, count in counts.items()))
    raw, clean = st.session_state.get('cep_enriched_pair', (bundle.original, bundle.improved))
    normalized = st.session_state.get("cep_normalized")
    label = "Descargar Excel normalizado" if normalized else "Descargar Excel cargado"
    filename = ("excel_normalizado" if normalized else "excel_cargado")
    st.download_button(label, clean, filename + ("_con_CEP" if matches else "") + ".xlsx")
    if evidence.preserved and st.button("Preparar ZIP final", key="cep_make_final"):
        try:
            with tempfile.TemporaryDirectory(prefix="engine_cep_web_") as folder:
                path = Path(folder) / "Movimientos_y_CEP.zip"
                export_cep_zip(bundle, queries, evidence, path)
                st.session_state.cep_final_zip = path.read_bytes()
        except Exception as error:
            st.error(str(error))
    if st.session_state.get("cep_final_zip"):
        st.download_button("Descargar ZIP final", st.session_state.cep_final_zip, "Movimientos_y_CEP.zip", "application/zip")
    if candidates:
        st.dataframe([q.audit() | matches.get(q.row, {}) for q in candidates], hide_index=True, use_container_width=True)
    st.caption(
        "Los encabezados verdes de Movimientos en el Excel normalizado o cruzado "
        "señalan los datos usados para preparar el TXT. "
        "Control CEP muestra los 6 campos que se consultan y el motivo de cada resultado. "
        "Corrige las columnas originales de Movimientos, vuelve a cargar el Excel y prepara "
        "un TXT nuevo sin normalizar. El ZIP conserva ambos Excel cruzados y los PDF/XML."
    )
