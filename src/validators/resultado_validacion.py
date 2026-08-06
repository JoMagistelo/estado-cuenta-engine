from dataclasses import dataclass


@dataclass
class ResultadoValidacion:

    nombre: str

    esperado: float | int | None

    obtenido: float | int | None

    diferencia: float | None

    correcto: bool

    mensaje: str