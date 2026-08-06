import re
from typing import Optional


def parse_val_o_none(val: str) -> Optional[float]:
    """
    Convierte una cadena a float cuando representa un valor numérico.

    Si el valor está vacío, contiene indicadores como
    'N/A' o 'N\\A', devuelve None.

    Parameters
    ----------
    val : str
        Valor de entrada.

    Returns
    -------
    Optional[float]
        Número convertido o None si no es válido.

    Examples
    --------
    >>> parse_val_o_none("1,250.35")
    1250.35

    >>> parse_val_o_none("N/A")
    None
    """
    if not val or "N/A" in val.upper() or r"N\A" in val.upper():
        return None

    val_clean = val.replace(",", "")

    try:
        return float(val_clean)
    except ValueError:
        return None


def parse_str_o_none(val: str) -> Optional[str]:
    """
    Devuelve una cadena limpia o None si representa un valor ausente.

    Se utiliza para campos opcionales donde algunos bancos escriben
    'N/A' o dejan el campo vacío.

    Parameters
    ----------
    val : str
        Cadena de entrada.

    Returns
    -------
    Optional[str]
        Texto limpio o None.
    """
    if not val or "N/A" in val.upper() or r"N\A" in val.upper():
        return None

    return val.strip()


def parse_monto(pattern: str, text: str, default: float = 0.0) -> float:
    """
    Extrae un monto utilizando una expresión regular.

    Busca el primer grupo capturado del patrón, elimina separadores
    de miles y lo convierte a float.

    Parameters
    ----------
    pattern : str
        Expresión regular con un grupo capturado.

    text : str
        Texto donde se realizará la búsqueda.

    default : float, optional
        Valor devuelto cuando no se encuentra el patrón o
        la conversión falla.

    Returns
    -------
    float
        Monto convertido o el valor por defecto.

    Examples
    --------
    >>> parse_monto(r"Saldo:\\s*([\\d,.]+)", texto)
    1500.25
    """
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        val_str = match.group(1).replace(",", "")

        try:
            return float(val_str)
        except ValueError:
            return default

    return default


def parse_entero(pattern: str, text: str, default: int = 0) -> int:
    """
    Extrae un número entero mediante una expresión regular.

    Resulta útil para campos como:

    - Días del periodo
    - Número de cheques
    - Cantidad de movimientos
    - Número de transacciones

    Parameters
    ----------
    pattern : str
        Expresión regular con un grupo capturado.

    text : str
        Texto de entrada.

    default : int, optional
        Valor devuelto cuando el dato no puede convertirse.

    Returns
    -------
    int
        Entero extraído o el valor por defecto.
    """
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return default

    return default