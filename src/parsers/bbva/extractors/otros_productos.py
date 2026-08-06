from __future__ import annotations

import re

from models.otros_productos import OtrosProductos

from utils.parsers import (
    parse_monto,
    parse_str_o_none,
    parse_val_o_none,
)



def extract_otros_productos(
    normalized_text: str
) -> OtrosProductos:

    """
    Extrae productos adicionales
    incluidos en el estado de cuenta BBVA.
    """


    inversion_match = re.search(
        r"OTROS\s+PRODUCTOS\s+INCLUIDOS.*?CONTRATO.*?COMISIONES.*?\n\s*([A-Z0-9/N/A\.\- ]+)\s+([A-Z0-9/N/A\.\- ]+)\s+([A-Z0-9/N/A\.\- ]+)\s+([A-Z0-9/N/A\.\- ]+)\s+([A-Z0-9/N/A\.\- ]+)\s+([A-Z0-9/N/A\.\- ]+)",
        normalized_text,
        re.DOTALL,
    )


    if inversion_match:


        contrato = parse_str_o_none(
            inversion_match.group(1)
        )


        producto_inversion = parse_str_o_none(
            inversion_match.group(2)
        )


        tasa_interes = (
            parse_val_o_none(
                inversion_match.group(3)
            )
            or 0.0
        )


        gat_nominal = parse_val_o_none(
            inversion_match.group(4)
        )


        gat_real = parse_val_o_none(
            inversion_match.group(5)
        )


        comision_inversion = (
            parse_val_o_none(
                inversion_match.group(6)
            )
            or 0.0
        )


    else:


        contrato = None

        producto_inversion = None

        tasa_interes = 0.0

        gat_nominal = None

        gat_real = None

        comision_inversion = 0.0



    total_comisiones = parse_monto(
        r"TOTAL\s+COMISIONES\s+([\d.]+)",
        normalized_text,
        default=comision_inversion,
    )



    return OtrosProductos(

        contrato=contrato,

        producto=producto_inversion,

        tasa_interes_anual=tasa_interes,

        gat_nominal_anual=gat_nominal,

        gat_real_anual=gat_real,

        total_comisiones=total_comisiones,

    )