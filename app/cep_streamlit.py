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
from cep.queries import BANXICO_BATCH_URL, queries_from_workbook, txt_zip
from exporters.excel.workbook_bundle import WorkbookBundle


def set_cep_bundle(bundle):
    for key in ('cep_txt_zip', 'cep_final_zip', 'cep_enriched_pair', 'cep_txt_adjacent'):
        st.session_state.pop(key, None)
    st.session_state.cep_bundle = bundle
    st.session_state.cep_queries = queries_from_workbook(bundle.improved)
    st.session_state.cep_evidence = CepEvidence()


def render_cep_workspace(results, busy=False):
    st.subheader("CEP Banxico")
    st.caption("Carga un Excel original o mejorado. El TXT siempre usa la copia mejorada con fechas homologadas.")
    uploaded = st.file_uploader("Excel de movimientos", type=["xlsx"], key="cep_excel_upload")
    if uploaded:
        data = uploaded.getvalue()
        token = hashlib.sha256(data).hexdigest()
        if st.session_state.get("cep_excel_token") != token:
            try:
                with st.spinner("Homologando y comprobando el Excel…"):
                    set_cep_bundle(WorkbookBundle.from_excel(data, source_name=uploaded.name))
                st.session_state.cep_excel_token = token
            except Exception as error:
                st.error(str(error))
    if st.button("Usar extracción actual", key="cep_use_current", disabled=busy or not results):
        try:
            with st.spinner("Preparando ambos Excel…"):
                set_cep_bundle(WorkbookBundle.from_results(list(results)))
        except Exception as error:
            st.error(str(error))
    bundle = st.session_state.get("cep_bundle")
    if bundle is None:
        return
    queries = st.session_state.cep_queries
    evidence = st.session_state.cep_evidence
    candidates = [q for q in queries if q.candidate]
    st.write(f"{bundle.report.movements} movimientos · {sum(q.ready for q in candidates)} candidatos con datos para TXT · {bundle.report.dates_review} fechas para revisión")
    st.subheader("Preparar TXT")
    adjacent = st.checkbox("Fecha original y reintentos ±1 día", value=True, key="cep_adjacent_dates")
    if st.button("Generar TXT Banxico", key="cep_make_txt"):
        try:
            st.session_state.cep_txt_zip = txt_zip(queries, adjacent_days=adjacent)
            st.session_state.cep_txt_adjacent = adjacent
        except Exception as error:
            st.error(str(error))
    if st.session_state.get("cep_txt_zip") and st.session_state.get('cep_txt_adjacent') == adjacent:
        st.download_button("Descargar TXT (ZIP)", st.session_state.cep_txt_zip,
                           "TXT_Banxico.zip", "application/zip")
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
    a, b = st.columns(2)
    a.download_button("Excel original", raw, "excel_original_con_CEP.xlsx" if matches else "excel_original.xlsx")
    b.download_button("Excel mejorado", clean, "excel_mejorado_con_CEP.xlsx" if matches else "excel_mejorado.xlsx")
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
    st.caption("Las columnas CEP se añaden al final de Movimientos en ambos Excel. Los cruces ambiguos quedan para revisión. Un fallo de búsqueda no significa que la transferencia falló.")
