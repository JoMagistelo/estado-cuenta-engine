from dataclasses import dataclass
from typing import Optional


@dataclass
class OtrosProductos:
    """
    Información de otros productos incluidos en el estado de cuenta (Inversiones)
    """

    contrato: Optional[str]
    producto: Optional[str]

    # Rendimientos

    tasa_interes_anual: Optional[float]
    gat_nominal_anual: Optional[float]
    gat_real_anual: Optional[float]

    # Costos asociados al producto

    total_comisiones: Optional[float]