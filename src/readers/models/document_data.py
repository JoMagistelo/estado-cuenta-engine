from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentData:
    """
    Representa los datos obtenidos de un documento PDF
    durante la etapa de lectura.

    El texto digital se obtiene únicamente de las primeras
    2 páginas.

    Las palabras con coordenadas espaciales constituyen
    la fuente principal de información estructural para
    el procesamiento posterior.
    """

    # ========================================================
    # TEXTO DIGITAL
    # ========================================================
    #
    # Contiene únicamente el texto de las primeras 2 páginas.
    #

    raw_text: str = ""
    normalized_text: str = ""

    # ========================================================
    # PALABRAS CON INFORMACIÓN ESPACIAL
    # ========================================================
    #
    # Cada elemento contiene, como mínimo:
    #
    # {
    #     "text": "...",
    #     "x0": ...,
    #     "x1": ...,
    #     "top": ...,
    #     "doctop": ...,
    #     "bottom": ...,
    #     "upright": ...,
    #     "height": ...,
    #     "width": ...,
    #     "direction": ...,
    #     "page": ...
    # }
    #

    spatial_words: list[dict[str, Any]] = field(default_factory=list)

    # ========================================================
    # METADATA
    # ========================================================

    metadata: dict[str, Any] = field(default_factory=dict)