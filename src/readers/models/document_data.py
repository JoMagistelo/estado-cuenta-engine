from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentData:
    raw_text: str = ""
    normalized_text: str = ""
    tables: list[list[list[Any]]] = field(default_factory=list)
    
    # NUEVO: Lista de palabras con coordenadas espaciales
    spatial_words: list[dict[str, Any]] = field(default_factory=list) 
    
    metadata: dict[str, Any] = field(default_factory=dict)