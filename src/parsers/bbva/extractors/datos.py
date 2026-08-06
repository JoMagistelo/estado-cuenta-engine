from __future__ import annotations

import re

from extractors.clabe_extractor import extract_clabes

from models.datos_cuenta import DatosCuenta


def extract_datos_cuenta(
    normalized_text: str
) -> DatosCuenta:

    """
    Extrae información principal
    de la cuenta BBVA.
    """


    prod_principal_match = re.search(
        r"Estado\s+de\s+Cuenta\s+(.*?)\s+P[ÁA]GINA",
        normalized_text,
        re.IGNORECASE | re.DOTALL
    )


    producto_principal = (
        prod_principal_match.group(1)
        .strip()
        .upper()
        if prod_principal_match
        else "CUENTA BBVA"
    )


    periodo_inicio = (
        m.group(1) if (m := re.search(
        r"PERIODO\s+DEL\s+(\d{2}/\d{2}/\d{4})\s+AL\s+(\d{2}/\d{2}/\d{4})",
        normalized_text,
    )) else None
    )


    periodo_fin = (
        m.group(2) if m else None
    )


    fecha_corte = (
        m.group(1) if (m := re.search(
        r"FECHA\s+DE\s+CORTE\s+([\d/]+)",
        normalized_text,
    )) else None
    )


    numero_cuenta = (
        m.group(1) if (m := re.search(
        r"NO\.\s+DE\s+CUENTA\s+(\S+)",
        normalized_text,
    )) else None
    )


    numero_cliente = (
        m.group(1) if (m := re.search(
        r"NO\.\s+DE\s+CLIENTE\s+(\S+)",
        normalized_text,
    )) else None
    )


    clabes = extract_clabes(
        normalized_text
    )


    clabe = (
        clabes[0]
        if clabes
        else None
    )


    titular_match = re.search(
        r"NO\.\s+DE\s+CLIENTE\s+\S+\s+([A-Z\s]+?)\s+R\.?F\.?C\.?\s*([A-Z0-9\-]{10,15})",
        normalized_text,
    )


    if titular_match:

        nombre_cliente = titular_match.group(1).strip()
        rfc = titular_match.group(2).strip()

    else:

        nombre_cliente = None
        rfc = None



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