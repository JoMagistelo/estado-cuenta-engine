from __future__ import annotations

from typing import Any
from readers.models.document_data import DocumentData

from models.estado_cuenta import EstadoCuenta
from models.parser_bbva_debug import ParserDebug

from .extractors.datos import extract_datos_cuenta
from .extractors.resumen import extract_resumen_financiero
from .extractors.otros_productos import extract_otros_productos

from .extractors.tables_parser import extract_datos_tables
from .extractors.tables_parser import extract_resumen_tables
from .extractors.tables_parser import extract_otros_tables

from .extractors.movimientos_words import extract_movimientos_words



def choose_value(
    table_value,
    text_value,
    field_name=None
):

    """
    Tabla primero cuando es confiable.
    Texto gana cuando tabla perdió información.
    """


    if table_value is None:
        return text_value


    zero_sensitive = {

        "saldo_promedio",
        "dias_periodo",
        "saldo_anterior",
        "depositos_abonos",
        "retiros_cargos",
        "saldo_final",
        "saldo_global",

    }


    if field_name in zero_sensitive:

        if (
            table_value == 0
            and text_value not in (None,0,"")
        ):
            return text_value



    return table_value



def merge_datos(
    datos_table,
    datos_text
):

    return type(datos_text)(

        producto_principal=
            choose_value(
                datos_table.producto_principal,
                datos_text.producto_principal,
                "producto_principal"
            ),

        periodo_inicio=
            choose_value(
                datos_table.periodo_inicio,
                datos_text.periodo_inicio,
                "periodo_inicio"

                
            ),

        periodo_fin=
            choose_value(
                datos_table.periodo_fin,
                datos_text.periodo_fin,
                "periodo_fin"
            ),

        fecha_corte=
            choose_value(
                datos_table.fecha_corte,
                datos_text.fecha_corte,
                "fecha_corte"
            ),

        numero_cuenta=
            choose_value(
                datos_table.numero_cuenta,
                datos_text.numero_cuenta,
                "numero_cuenta"
            ),

        numero_cliente=
            choose_value(
                datos_table.numero_cliente,
                datos_text.numero_cliente,
                "numero_cliente"
            ),

        clabe=
            choose_value(
                datos_table.clabe,
                datos_text.clabe,
                "clabe"
            ),

        nombre_cliente=
            choose_value(
                datos_table.nombre_cliente,
                datos_text.nombre_cliente,
                "nombre_cliente"
            ),

        rfc=
            choose_value(
                datos_table.rfc,
                datos_text.rfc,
                "rfc"
            )

    )



def merge_resumen(
    resumen_table,
    resumen_text
):


    return type(resumen_text)(

        saldo_promedio=
            choose_value(
                resumen_table.saldo_promedio,
                resumen_text.saldo_promedio,
                "saldo_promedio"
            ),


        dias_periodo=
            choose_value(
                resumen_table.dias_periodo,
                resumen_text.dias_periodo,
                "dias_periodo"
            ),


        tasa_bruta_anual=
            choose_value(
                resumen_table.tasa_bruta_anual,
                resumen_text.tasa_bruta_anual,
                "tasa_bruta_anual"
            ),


        saldo_promedio_gravable=
            choose_value(
                resumen_table.saldo_promedio_gravable,
                resumen_text.saldo_promedio_gravable,
                "saldo_promedio_gravable"
            ),


        intereses_a_favor=
            choose_value(
                resumen_table.intereses_a_favor,
                resumen_text.intereses_a_favor,
                "intereses_a_favor"
            ),


        isr_retenido=
            choose_value(
                resumen_table.isr_retenido,
                resumen_text.isr_retenido,
                "isr_retenido"
            ),


        cheques_pagados=
            choose_value(
                resumen_table.cheques_pagados,
                resumen_text.cheques_pagados,
                "cheques_pagados"
            ),


        manejo_cuenta=
            choose_value(
                resumen_table.manejo_cuenta,
                resumen_text.manejo_cuenta,
                "manejo_cuenta"
            ),


        cargos_objetados=
            choose_value(
                resumen_table.cargos_objetados,
                resumen_text.cargos_objetados,
                "cargos_objetados"
            ),


        abonos_objetados=
            choose_value(
                resumen_table.abonos_objetados,
                resumen_text.abonos_objetados,
                "abonos_objetados"
            ),


        saldo_anterior=
            choose_value(
                resumen_table.saldo_anterior,
                resumen_text.saldo_anterior,
                "saldo_anterior"
            ),


        depositos_abonos=
            choose_value(
                resumen_table.depositos_abonos,
                resumen_text.depositos_abonos,
                "depositos_abonos"
            ),


        retiros_cargos=
            choose_value(
                resumen_table.retiros_cargos,
                resumen_text.retiros_cargos,
                "retiros_cargos"
            ),


        saldo_final=
            choose_value(
                resumen_table.saldo_final,
                resumen_text.saldo_final,
                "saldo_final"
            ),


        saldo_promedio_minimo_mensual=
            choose_value(
                resumen_table.saldo_promedio_minimo_mensual,
                resumen_text.saldo_promedio_minimo_mensual,
                "saldo_promedio_minimo_mensual"
            ),


        saldo_global=
            choose_value(
                resumen_table.saldo_global,
                resumen_text.saldo_global,
                "saldo_global"
            )
    )



def parse_bbva(
    document: DocumentData
):

    text = document.normalized_text
    tables = document.tables
    # ==========================
    # TEXTO (Parser Antiguo)
    # ==========================
    datos_text = extract_datos_cuenta(text)
    resumen_text = extract_resumen_financiero(text)
    otros_text = extract_otros_productos(text)

    # ==========================
    # TABLAS (Parser Nuevo)
    # ==========================
    try:
        # AÑADIMOS text=text
        datos_table = extract_datos_tables(tables, text=text)
    except Exception:
        datos_table = datos_text

    try:
        # Resumen_tables fue diseñado para solo recibir tables
        resumen_table = extract_resumen_tables(tables)
    except Exception as e:
        print("ERROR TABLE RESUMEN:", e)
        resumen_table = resumen_text

    try:
        # AÑADIMOS text=text
        otros_table = extract_otros_tables(tables, text=text)
    except Exception:
        otros_table = otros_text

    # ==========================
    # MERGE (Tabla gana si no es None)
    # ==========================
    datos = merge_datos(datos_table, datos_text)
    resumen = merge_resumen(resumen_table, resumen_text)

    # ==========================
    # MOVIMIENTOS
    # ==========================
    movimientos = extract_movimientos_words(document.spatial_words)

    estado = EstadoCuenta(
        datos_cuenta=datos,
        resumen_financiero=resumen,
        otros_productos=otros_table,
        movimientos=movimientos
    )

    estado.debug = ParserDebug(
        datos_text=datos_text,
        datos_table=datos_table,
        resumen_text=resumen_text,
        resumen_table=resumen_table,
        otros_text=otros_text,
        otros_table=otros_table
    )

    return estado