from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

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

from engine.pipeline import process_bank_statements
from exporters.excel import export_batch_excel


# ============================================================
# FUNCIONES CON CACHÉ
# ============================================================

#@st.cache_data
def cached_process_statements(uploaded_files_data: tuple[tuple[str, bytes], ...]):
    """
    Procesa los archivos subidos y cachea el resultado.

    Recibe una tupla hashable con:
    (
        (nombre_archivo, bytes_del_pdf),
        ...
    )

    Esto evita problemas de hash con UploadedFile de Streamlit.
    """

    temp_paths: list[str] = []

    try:
        for file_name, file_bytes in uploaded_files_data:
            suffix = Path(file_name).suffix or ".pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                temp_paths.append(tmp.name)

        results = process_bank_statements(temp_paths)
        return results

    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError:
                pass


# ============================================================
# APP
# ============================================================

def main():
    st.set_page_config(
        page_title="Motor de Estados de Cuenta",
        layout="wide",
    )

    st.title("📄 Motor de Estados de Cuenta")

    st.write(
        """
        Sube uno o varios estados de cuenta en formato PDF.

        El motor detectará el banco, extraerá la información y la presentará
        de forma estructurada para su auditoría y exportación.
        """
    )

    uploaded_files = st.file_uploader(
        "Selecciona estados de cuenta PDF",
        type="pdf",
        accept_multiple_files=True,
    )

    if not uploaded_files:
        return

    try:
        # ====================================================
        # PROCESAMIENTO
        # ====================================================
        uploaded_files_data = tuple(
            (uploaded_file.name, uploaded_file.getvalue())
            for uploaded_file in uploaded_files
        )

        with st.spinner("Procesando estados de cuenta..."):
            results = cached_process_statements(uploaded_files_data)

        st.success(f"✅ {len(results)} estados de cuenta procesados correctamente.")

        st.divider()

        # ====================================================
        # SELECTOR DE ESTADO DE CUENTA
        # ============================================================
        st.header("🔍 Auditoría de Resultados")

        file_options = {res.file_name: res for res in results}

        selected_file = st.selectbox(
            "Selecciona el estado de cuenta que deseas revisar:",
            options=list(file_options.keys()),
        )

        if selected_file:
            result = file_options[selected_file]
            estado = result.estado_cuenta

            st.markdown(f"#### Banco Detectado: `{result.bank_key.upper()}`")

            cols_info = st.columns(4)

            cols_info[0].metric(
                "Periodo",
                f"{estado.datos_cuenta.periodo_inicio} al {estado.datos_cuenta.periodo_fin}"
                if estado and estado.datos_cuenta
                else "N/A",
            )

            cols_info[1].metric(
                "Cliente",
                estado.datos_cuenta.nombre_cliente or "N/A"
                if estado and estado.datos_cuenta
                else "N/A",
            )

            cols_info[2].metric(
                "Cuenta",
                estado.datos_cuenta.numero_cuenta or "N/A"
                if estado and estado.datos_cuenta
                else "N/A",
            )

            cols_info[3].metric(
                "CLABE",
                estado.datos_cuenta.clabe or "N/A"
                if estado and estado.datos_cuenta
                else "N/A",
            )

            # ------------------------------------------------
            # DATOS CUENTA
            # ------------------------------------------------
            st.subheader("1. 📌 Datos de la Cuenta")

            dc = estado.datos_cuenta

            if dc:
                with st.container(border=True):
                    col1, col2, col3 = st.columns(3)

                    col1.markdown(f"**Producto:** {dc.producto_principal or 'N/A'}")
                    col1.markdown(f"**No. Cliente:** {dc.numero_cliente or 'N/A'}")

                    col2.markdown(f"**RFC:** {dc.rfc or 'N/A'}")
                    col2.markdown(f"**Fecha de Corte:** {dc.fecha_corte or 'N/A'}")

                    if estado.resumen_financiero:
                        col3.markdown(
                            f"**Días del Periodo:** {estado.resumen_financiero.dias_periodo or 'N/A'}"
                        )
                        col3.markdown(
                            f"**Tasa Bruta Anual:** {estado.resumen_financiero.tasa_bruta_anual or 'N/A'}%"
                        )
                    else:
                        col3.markdown("**Días del Periodo:** N/A")
                        col3.markdown("**Tasa Bruta Anual:** N/A")

            else:
                st.warning("No se encontraron datos de la cuenta.")

            # ------------------------------------------------
            # RESUMEN FINANCIERO
            # ------------------------------------------------
            st.subheader("2. 📊 Resumen Financiero")

            rf = estado.resumen_financiero

            if rf:
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns(4)

                    col1.metric("Saldo Anterior", f"${rf.saldo_anterior:,.2f}")
                    col2.metric("Depósitos / Abonos", f"${rf.depositos_abonos:,.2f}")
                    col3.metric("Retiros / Cargos", f"${rf.retiros_cargos:,.2f}")
                    col4.metric(
                        "Saldo Final",
                        f"${rf.saldo_final:,.2f}",
                        delta=f"{(rf.saldo_final - rf.saldo_anterior):,.2f}",
                    )

                    st.divider()

                    col_b1, col_b2, col_b3 = st.columns(3)

                    col_b1.metric(
                        "Saldo Promedio",
                        f"${rf.saldo_promedio:,.2f}" if rf.saldo_promedio is not None else "N/A",
                    )
                    col_b2.metric(
                        "Intereses a Favor",
                        f"${rf.intereses_a_favor:,.2f}" if rf.intereses_a_favor is not None else "N/A",
                    )
                    col_b3.metric(
                        "ISR Retenido",
                        f"${rf.isr_retenido:,.2f}" if rf.isr_retenido is not None else "N/A",
                    )
            else:
                st.warning("No se encontró el resumen financiero.")


            # ------------------------------------------------
            # RESUMEN FINANCIERO - DETALLES ADICIONALES
            # ------------------------------------------------
            with st.expander("Ver más detalles del resumen financiero"):
                if rf:
                    col_c1, col_c2, col_c3 = st.columns(3)
                    col_c1.metric("Saldo Promedio Gravable", f"${rf.saldo_promedio_gravable:,.2f}" if rf.saldo_promedio_gravable is not None else "N/A")
                    col_c2.metric("Saldo Promedio Mínimo Mensual", f"${rf.saldo_promedio_minimo_mensual:,.2f}" if rf.saldo_promedio_minimo_mensual is not None else "N/A")
                    col_c3.metric("Saldo Global", f"${rf.saldo_global:,.2f}" if rf.saldo_global is not None else "N/A")

                    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
                    col_d1.metric("Cheques Pagados", f"{rf.cheques_pagados}" if rf.cheques_pagados is not None else "N/A")
                    col_d2.metric("Manejo de Cuenta", f"${rf.manejo_cuenta:,.2f}" if rf.manejo_cuenta is not None else "N/A")
                    col_d3.metric("Cargos Objetados", f"${rf.cargos_objetados:,.2f}" if rf.cargos_objetados is not None else "N/A")
                    col_d4.metric("Abonos Objetados", f"${rf.abonos_objetados:,.2f}" if rf.abonos_objetados is not None else "N/A")


            # ------------------------------------------------
            # OTROS PRODUCTOS
            # ------------------------------------------------
            st.subheader("3. 💰 Otros Productos y Comisiones")

            op = estado.otros_productos

            if op:
                with st.container(border=True):
                    st.markdown(
                        f"**Producto de Inversión:** {op.producto or 'N/A'} "
                        f"(Contrato: {op.contrato or 'N/A'})"
                    )

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Tasa Interés Anual", f"{op.tasa_interes_anual or 0:.2f}%")
                    col2.metric("GAT Nominal", f"{op.gat_nominal_anual or 0:.2f}%" if op.gat_nominal_anual is not None else "N/A")
                    col3.metric("GAT Real", f"{op.gat_real_anual or 0:.2f}%" if op.gat_real_anual is not None else "N/A")

                    st.metric("Total Comisiones Cobradas", f"${op.total_comisiones:,.2f}" if op.total_comisiones is not None else "N/A")
            else:
                st.info(
                    "No se encontraron otros productos o comisiones en este estado de cuenta."
                )


            # ------------------------------------------------
            # VALIDACIONES FINANCIERAS
            # ------------------------------------------------
            with st.expander("✓ Validaciones Financieras"):

                if result.validaciones:
                    with st.container(border=True):
                        correctas = sum(1 for v in result.validaciones if v.correcto)
                        total = len(result.validaciones)

                        st.metric(
                            "Integridad financiera",
                            f"{correctas}/{total} validaciones correctas",
                        )

                        for validacion in result.validaciones:
                            if validacion.correcto:
                                st.success(f"✅ {validacion.nombre}")
                            else:
                                st.error(f"❌ {validacion.nombre}")

                            with st.expander("Detalle"):
                                esperado_str = (
                                    f"${validacion.esperado:,.2f}"
                                    if validacion.esperado is not None
                                    else "N/A"
                                )
                                obtenido_str = (
                                    f"${validacion.obtenido:,.2f}"
                                    if validacion.obtenido is not None
                                    else "N/A"
                                )
                                diferencia_str = (
                                    f"${validacion.diferencia:,.2f}"
                                    if validacion.diferencia is not None
                                    else "N/A"
                                )

                                st.write(f"Esperado: {esperado_str}")
                                st.write(f"Obtenido: {obtenido_str}")
                                st.write(f"Diferencia: {diferencia_str}")
                                st.caption(validacion.mensaje)

                else:
                    st.info("No existen validaciones disponibles.")

            # ------------------------------------------------
            # MOVIMIENTOS
            # ------------------------------------------------
            st.subheader(f"5. 📑 Movimientos ({len(estado.movimientos)})")

            df = pd.DataFrame([mov.__dict__ for mov in estado.movimientos])

            if not df.empty:
                for col in [
                    "cargo",
                    "abono",
                    "saldo_operacion",
                    "saldo_liquidacion",
                ]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                columnas_mostrar = [
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
                    col for col in columnas_mostrar if col in df.columns
                ]

                df_display = df[columnas_existentes].copy()

                st.dataframe(
                    df_display,
                    use_container_width=True,
                    height=500,
                    column_config={
                        "fecha_operacion": "Fecha Operación",
                        "fecha_liquidacion": "Fecha Liquidación",
                        "concepto": "Concepto",
                        "cargo": st.column_config.NumberColumn(
                            "Cargo",
                            format="$%.2f",
                        ),
                        "abono": st.column_config.NumberColumn(
                            "Abono",
                            format="$%.2f",
                        ),
                        "saldo_operacion": st.column_config.NumberColumn(
                            "Saldo Operación",
                            format="$%.2f",
                        ),
                        "saldo_liquidacion": st.column_config.NumberColumn(
                            "Saldo Liquidación",
                            format="$%.2f",
                        ),
                        "tipo_operacion": "Tipo",
                        "beneficiario": "Beneficiario",
                        "cuenta_beneficiario": "Cuenta Benef.",
                        "clabe_beneficiario": "CLABE",
                        "rfc": "RFC",
                        "referencia": "Referencia",
                        "autorizacion": "Autorización",
                        "hora_operacion": "Hora",
                    },
                )

            else:
                st.warning("No se encontraron movimientos en este documento.")


            # ------------------------------------------------
            # TEXTO CRUDO (PARA DEBUG)
            # ------------------------------------------------
            with st.expander("🛠️ Opciones de Depuración"):
                st.info(
                    "Esta sección contiene herramientas para desarrolladores. "
                    "Aquí puedes descargar el texto extraído del PDF para probar y mejorar los parsers."
                )

                raw_text = getattr(result, "raw_text", "")

                st.download_button(
                    label="Descargar texto crudo (.txt)",
                    data=raw_text.encode("utf-8"),
                    file_name=f"crudo_{selected_file.replace('.pdf', '.txt')}",
                    mime="text/plain",
                )

                # --- NUEVO: DESCARGA DE TABLAS ---
                import json
                tables_data = getattr(result, "tables", [])
                # Formateamos a JSON con indentación para que sea legible
                tables_json = json.dumps(tables_data, indent=4, ensure_ascii=False)
                
                st.download_button(
                    label="Descargar tablas crudas (.json)",
                    data=tables_json.encode("utf-8"),
                    file_name=f"tablas_{selected_file.replace('.pdf', '.json')}",
                    mime="application/json",
                )



            # ------------------------------------------------
            # COMPARACIÓN TEXTO VS TABLAS
            # ------------------------------------------------

            with st.expander("🔬 Comparación Texto vs Tablas"):
                debug = getattr(
                    estado,
                    "debug",
                    None
                )


                if debug:

                    def crear_comparacion(obj_text, obj_table, obj_final):

                        rows = []

                        for campo in obj_final.__dict__.keys():

                            rows.append(
                                {
                                    "Campo": campo,
                                    "Texto": getattr(
                                        obj_text,
                                        campo,
                                        None
                                    ),

                                    "Tabla": getattr(
                                        obj_table,
                                        campo,
                                        None
                                    ),

                                    "Resultado Final": getattr(
                                        obj_final,
                                        campo,
                                        None
                                    )
                                }
                            )

                        return pd.DataFrame(rows)



                    # ==========================
                    # DATOS CUENTA
                    # ==========================

                    st.markdown("### 📌 Datos Cuenta")

                    df_datos = crear_comparacion(
                        debug.datos_text,
                        debug.datos_table,
                        estado.datos_cuenta
                    )


                    st.dataframe(
                        df_datos,
                        use_container_width=True,
                        height=400
                    )


                    # ==========================
                    # RESUMEN FINANCIERO
                    # ==========================

                    st.markdown("### 📊 Resumen Financiero")


                    df_resumen = crear_comparacion(
                        debug.resumen_text,
                        debug.resumen_table,
                        estado.resumen_financiero
                    )


                    st.dataframe(
                        df_resumen,
                        use_container_width=True,
                        height=500
                    )



                    # ==========================
                    # OTROS PRODUCTOS
                    # ==========================

                    st.markdown("### 💰 Otros Productos")


                    df_otros = crear_comparacion(
                        debug.otros_text,
                        debug.otros_table,
                        estado.otros_productos
                    )


                    st.dataframe(
                        df_otros,
                        use_container_width=True,
                        height=300
                    )


                else:

                    st.info(
                        "No existe información debug del parser."
                    )

        st.divider()

        # ====================================================
        # EXPORTAR
        # ====================================================
        st.header("📤 Exportar Todos los Resultados a Excel")

        with st.container(border=True):
            st.markdown(
                "Haz clic en el botón para generar un único archivo Excel con los datos de todos los estados de cuenta procesados."
            )

            if st.button(
                "🚀 Generar y Descargar Reporte Excel",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Generando archivo Excel... por favor espera."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                        excel_path = tmp_excel.name

                    export_batch_excel(results, excel_path)

                    with open(excel_path, "rb") as file:
                        data = file.read()

                    st.download_button(
                        label="✅ ¡Listo! Haz clic aquí para descargar",
                        data=data,
                        file_name="reporte_estados_de_cuenta.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

                    os.remove(excel_path)

    except Exception as e:
        import traceback

        st.error(f"Ocurrió un error durante el procesamiento: {e}")
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()