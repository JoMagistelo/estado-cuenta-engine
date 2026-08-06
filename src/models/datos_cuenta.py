from dataclasses import dataclass
from typing import Optional


@dataclass
class DatosCuenta:
    """
    Información general del titular y la cuenta
    extraída del estado de cuenta.
    """

    # Nombre del producto principal

    producto_principal: Optional[str]

    # Periodo del estado de cuenta

    periodo_inicio: Optional[str]
    periodo_fin: Optional[str]
    fecha_corte: Optional[str]


    # Identificación de cuenta

    numero_cuenta: Optional[str]
    numero_cliente: Optional[str]
    clabe: Optional[str]


    # Datos del titular

    nombre_cliente: Optional[str]
    rfc: Optional[str]