from __future__ import annotations

import re
from typing import Any

from models.datos_cuenta import DatosCuenta
from models.otros_productos import OtrosProductos
from models.resumen_financiero import ResumenFinanciero

from parsers.bbva.utils.table_utils import (
    extract_clabe_from_table,
    extract_value_after_label_from_text,
    find_row_value,
    find_table,
    normalize_fragmented_text,
    parse_amount,
    parse_int,
    row_text,
    table_text,
)


# ==========================================================
# HELPERS INTERNOS
# ==========================================================

def _extract_producto_principal(source_text: str) -> str:
    match = re.search(
        r"Estado\s+de\s+Cuenta\s+(.*?)\s+P[ÁA]GINA",
        source_text,
        re.IGNORECASE | re.DOTALL,
    )

    if match:
        return match.group(1).strip().upper()

    return "CUENTA BBVA"


def _extract_nombre_y_rfc(source_text: str, tables: list[list[list[Any]]]) -> tuple[str | None, str | None]:
    nombre = None
    rfc = None

    # Buscamos primero estructuralmente en las tablas, ya que BBVA pone el nombre
    # debajo de "No. de Cliente" pero partido en varias celdas.
    for table in tables:
        for i, row in enumerate(table):
            r_text = row_text(row).upper()
            
            # Nombre del cliente
            if not nombre and ("NO. DE CLIENTE" in r_text or "NO DE CLIENTE" in r_text):
                if i + 1 < len(table):
                    n_text = row_text(table[i+1]).upper()
                    # Corrección de letras aisladas del OCR (ej. "NAV A" -> "NAVA")
                    n_text = re.sub(r"\b([A-Z]+)\s+([A-Z])\b", r"\1\2", n_text)
                    nombre = " ".join(n_text.split())
            
            # RFC
            if not rfc and ("R.F.C" in r_text or "RFC" in r_text):
                idx = r_text.find("R.F.C") if "R.F.C" in r_text else r_text.find("RFC")
                if idx != -1:
                    rfc_part = r_text[idx:].replace("R.F.C", "").replace("RFC", "").replace(".", "").replace(" ", "")
                    match = re.search(r"([A-Z0-9]{10,15})", rfc_part)
                    if match:
                        rfc = match.group(1)

    # Fallback suave por regex sobre el texto unificado
    if not nombre or not rfc:
        match = re.search(
            r"NO\.\s+DE\s+CLIENTE\s+[A-Z0-9]+\s+([A-Z\s]+?)\s+R\.?F\.?C\.?\s*([A-Z0-9\-]{10,15})",
            source_text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            if not nombre:
                nombre = normalize_fragmented_text(match.group(1)).upper()
            if not rfc:
                rfc = match.group(2).strip().upper()

    return nombre, rfc


def _extract_periodo(source_text: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"DEL\s+(\d{2}/\d{2}/\d{4})\s+AL\s+(\d{2}/\d{2}/\d{4})",
        source_text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1), match.group(2)

    return None, None


def _find_first_reasonable_table(
    tables: list[list[list[Any]]],
    keywords: list[str],
) -> list[list[str]] | None:
    table = find_table(tables, keywords, all_keywords=False)
    return table


# ==========================================================
# DATOS CUENTA
# ==========================================================

def extract_datos_tables(
    tables: list[list[list[Any]]],
    text: str | None = None,
) -> DatosCuenta:
    """
    Extrae datos de cuenta desde tablas BBVA.
    """
    table = _find_first_reasonable_table(
        tables,
        ["Periodo", "Fecha de Corte", "No. de Cuenta", "No. de Cliente"],
    )

    if not table and tables:
        table = tables[0]

    if not table:
        raise ValueError("No se encontró tabla de datos de cuenta.")

    source_text = normalize_fragmented_text(text or table_text(table))

    producto_principal = _extract_producto_principal(source_text)
    periodo_inicio, periodo_fin = _extract_periodo(source_text)

    # Usamos regex sobre el texto de la tabla para ser resilientes a la fragmentación de celdas.
    # `find_row_value` puede fallar si el número está en múltiples celdas.
    fecha_corte = extract_value_after_label_from_text(
        source_text, r"Fecha\s+de\s+Corte", r"(\d{2}/\d{2}/\d{4})"
    )
    numero_cuenta = extract_value_after_label_from_text(
        source_text, r"No\.\s+de\s+Cuenta", r"(\d+)"
    )
    numero_cliente = extract_value_after_label_from_text(
        source_text, r"No\.\s+de\s+Cliente", r"(\d+)"
    )

    nombre_cliente, rfc_candidate = _extract_nombre_y_rfc(source_text, tables)

    # El RFC puede estar en la misma línea que el nombre o en una separada.
    rfc_table = find_row_value(table, "R.F.C")
    rfc = rfc_candidate or rfc_table

    clabe = extract_clabe_from_table(table)

    if not clabe:
        clabe_match = re.search(
            r"CLABE\s+([0-9\s]{18,})",
            source_text,
            re.IGNORECASE,
        )
        if clabe_match:
            clabe = "".join(re.findall(r"\d", clabe_match.group(1)))[:18] or None

    return DatosCuenta(
        producto_principal=producto_principal,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        fecha_corte=fecha_corte,
        numero_cuenta=numero_cuenta,
        numero_cliente=numero_cliente,
        clabe=clabe,
        nombre_cliente=nombre_cliente,
        rfc=rfc,
    )


# ==========================================================
# RESUMEN FINANCIERO
# ==========================================================

def extract_resumen_tables(
    tables: list[list[list[Any]]],
) -> ResumenFinanciero:
    """
    Extractor financiero super-resiliente contra artefactos OCR de BBVA.
    Convierte todas las tablas a texto y utiliza regex focalizadas corrigiendo la fragmentación.
    """
    lines = []
    for table in tables:
        for row in table:
            lines.append(row_text(row))

    full_text = "\n".join(lines)

    # 1. Corrección específica para montos con coma separada por espacios del OCR (ej. "6, 341.00" -> "6,341.00")
    full_text = re.sub(r"(\d+,)\s+(\d{3}(?:\.\d{2})?)", r"\1\2", full_text)

    # 2. Corrección de etiquetas fragmentadas para que los match funcionen siempre
    replacements = [
        (r"Saldo\s*P\s*romedio\s*Grava\s*ble", "Saldo Promedio Gravable"),
        (r"Saldo\s*P\s*romedio", "Saldo Promedio"),
        (r"Sa\s*ldo\s*Anterior", "Saldo Anterior"),
        (r"Sa\s*ldo\s*Final", "Saldo Final"),
        (r"Sa\s*ldo\s*Promedio\s*M[íi]nimo", "Saldo Promedio Minimo"),
        (r"D[íi]as\s*de\s*l\s*Periodo", "Dias del Periodo"),
        (r"De\s*p[óo]sitos", "Depositos"),
        (r"Re\s*tiros", "Retiros"),
        (r"Interes\s*es\s*a\s*Favor", "Intereses a Favor"),
        (r"ISR\s*Ret\s*enido", "ISR Retenido"),
        (r"Tasa\s*Br\s*uta", "Tasa Bruta"),
        (r"Chequ\s*es\s*pagados", "Cheques Pagados"),
    ]
    for pat, repl in replacements:
        full_text = re.sub(pat, repl, full_text, flags=re.IGNORECASE)

    # Funciones extractoras (Rendimiento se saca del 1er monto de la línea, Comportamiento del último)
    def get_first_amount(pattern: str) -> float | None:
        match = re.search(pattern + r"[^\d\n]*((?:-)?\d{1,3}(?:,\d{3})*(?:\.\d+)?)", full_text, re.IGNORECASE)
        return parse_amount(match.group(1)) if match else None

    def get_last_amount(pattern: str) -> float | None:
        match = re.search(pattern + r"([^\n]*)", full_text, re.IGNORECASE)
        if match:
            numbers = re.findall(r"((?:-)?\d{1,3}(?:,\d{3})*(?:\.\d+)?)", match.group(1))
            if numbers:
                return parse_amount(numbers[-1])
        return None

    def get_first_int(pattern: str) -> int | None:
        match = re.search(pattern + r"[^\d\n]*(\d+)", full_text, re.IGNORECASE)
        return parse_int(match.group(1)) if match else None

    # Columna Izquierda (Rendimiento)
    saldo_promedio = get_first_amount(r"Saldo Promedio(?!\s*Gravable|\s*Minimo)")
    dias_periodo = get_first_int(r"Dias del Periodo")
    tasa_bruta_anual = get_first_amount(r"Tasa Bruta")
    saldo_promedio_gravable = get_first_amount(r"Saldo Promedio Gravable")
    intereses_a_favor = get_first_amount(r"Intereses a Favor")
    isr_retenido = get_first_amount(r"ISR Retenido")

    # Columna Derecha (Comportamiento)
    saldo_anterior = get_last_amount(r"Saldo Anterior")
    depositos_abonos = get_last_amount(r"Depositos")
    retiros_cargos = get_last_amount(r"Retiros")
    saldo_final = get_last_amount(r"Saldo Final")
    saldo_promedio_minimo_mensual = get_last_amount(r"Saldo Promedio Minimo")



    # =========================================================
    # EXTRACCIÓN RESILIENTE A ARTEFACTOS VERTICALES (OCR BBVA)
    # =========================================================
    
    # 1. Cheques Pagados y Manejo de Cuenta
    cheques_pagados = None
    manejo_cuenta = None
    
    # Atrapa: "Chequ\nManejo... es pagados\nde Cuenta..."
    cheques_match = re.search(
        r"Chequ[\s\S]{1,35}es\s*pagados[\s\S]{1,35}Cuenta[^\d]*(\d+)[^\d]*([\d\.,]+)", 
        full_text, 
        re.IGNORECASE
    )
    if cheques_match:
        cheques_pagados = parse_int(cheques_match.group(1))
        manejo_cuenta = parse_amount(cheques_match.group(2))
    else:
        # Fallback por si en otros formatos sí sale limpio
        cheques_pagados = get_first_int(r"Cheques Pagados")
        manejo_cuenta = get_first_amount(r"Manejo\s*de\s*Cuenta")

    # 2. Cargos y Abonos Objetados
    cargos_objetados = None
    abonos_objetados = None
    
    # Atrapa: "Cargos\nAbono... Objetados\ns Objetados... 0\n0... 0.00\n0.00"
    objetados_match = re.search(
        r"Cargos[\s\S]{1,35}Abono[\s\S]{1,35}Objetados[\s\S]{1,35}Objetados[^\d]*\d+[^\d]*\d+[^\d]*([\d\.,]+)[^\d]*([\d\.,]+)",
        full_text,
        re.IGNORECASE
    )
    if objetados_match:
        # Los grupos 1 y 2 atrapan los dos montos flotantes (0.00 y 0.00) e ignoran el conteo de eventos (0 y 0)
        cargos_objetados = parse_amount(objetados_match.group(1))
        abonos_objetados = parse_amount(objetados_match.group(2))
    else:
        # Fallback original
        cargos_objetados = get_first_amount(r"Cargos\s*Objetados")
        abonos_objetados = get_first_amount(r"Abonos\s*Objetados")


    # Saldo Global (usualmente al final)
    saldo_global = get_last_amount(r"Saldo\s*Global")

    return ResumenFinanciero(
        saldo_promedio=saldo_promedio,
        dias_periodo=dias_periodo,
        tasa_bruta_anual=tasa_bruta_anual,
        saldo_promedio_gravable=saldo_promedio_gravable,
        intereses_a_favor=intereses_a_favor,
        isr_retenido=isr_retenido,
        cheques_pagados=cheques_pagados,
        manejo_cuenta=manejo_cuenta,
        cargos_objetados=cargos_objetados,
        abonos_objetados=abonos_objetados,
        saldo_anterior=saldo_anterior,
        depositos_abonos=depositos_abonos,
        retiros_cargos=retiros_cargos,
        saldo_final=saldo_final,
        saldo_promedio_minimo_mensual=saldo_promedio_minimo_mensual,
        saldo_global=saldo_global,
    )


# ==========================================================
# OTROS PRODUCTOS
# ==========================================================

def extract_otros_tables(
    tables: list[list[list[Any]]],
    text: str | None = None,
) -> OtrosProductos:
    table = _find_first_reasonable_table(
        tables,
        ["Otros productos incluidos en el estado de cuenta"],
    )

    if not table and tables:
        table = tables[0]

    if not table:
        return OtrosProductos(
            contrato=None,
            producto=None,
            tasa_interes_anual=0.0,
            gat_nominal_anual=None,
            gat_real_anual=None,
            total_comisiones=0.0,
        )
        
    return OtrosProductos(
        contrato=None,
        producto=None,
        tasa_interes_anual=0.0,
        gat_nominal_anual=None,
        gat_real_anual=None,
        total_comisiones=0.0,
    )

def extract_bbva_tables(
    tables: list[list[list[Any]]],
    text: str | None = None,
) -> dict[str, Any]:
    """
    Función principal que coordina la extracción de todas las secciones del estado de cuenta.
    """
    return {
        "datos_cuenta": extract_datos_tables(tables, text),
        "resumen_financiero": extract_resumen_tables(tables),
        "otros_productos": extract_otros_tables(tables, text),
    }