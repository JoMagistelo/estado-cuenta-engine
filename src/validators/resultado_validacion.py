from dataclasses import dataclass


@dataclass
class ResultadoValidacion:

    nombre: str

    esperado: float | int | None

    obtenido: float | int | None

    diferencia: float | None

    correcto: bool

    mensaje: str

    # Conciliación condicionada que debe mostrarse con su explicación, no como
    # igualdad exacta. Los resultados existentes mantienen el valor False.
    advertencia: bool = False
