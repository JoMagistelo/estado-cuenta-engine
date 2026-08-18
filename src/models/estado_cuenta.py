from dataclasses import dataclass, field
from typing import List

from models.datos_cuenta import DatosCuenta
from models.otros_productos import OtrosProductos
from models.resumen_financiero import ResumenFinanciero
from models.movimiento import Movimiento

@dataclass
class EstadoCuenta:
    """
    Modelo principal que representa un estado de cuenta completo.
    """

    datos_cuenta: DatosCuenta
    otros_productos: OtrosProductos
    resumen_financiero: ResumenFinanciero
    movimientos: List[Movimiento] = field(default_factory=list)