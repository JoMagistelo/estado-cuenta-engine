from __future__ import annotations

from dataclasses import dataclass, field

from models.estado_cuenta import EstadoCuenta
from readers.models import DocumentData
from validators.resultado_validacion import ResultadoValidacion


@dataclass(slots=True)
class OCRCandidate:
    """Resultado completo de un motor OCR para el mismo documento."""

    engine: str
    estado_cuenta: EstadoCuenta
    document: DocumentData
    validaciones: list[ResultadoValidacion] = field(default_factory=list)

    @property
    def movement_count(self) -> int:
        movimientos = getattr(self.estado_cuenta, "movimientos", None) or []
        return len(movimientos)

    @property
    def validation_total(self) -> int:
        return len(self.validaciones)

    @property
    def validation_failed(self) -> int:
        return sum(1 for item in self.validaciones if not item.correcto)


@dataclass(slots=True)
class OCRReview:
    """Comparación en memoria de resultados Tesseract/PaddleOCR."""

    candidates: dict[str, OCRCandidate] = field(default_factory=dict)
    recommended_engine: str = "tesseract"
    selected_engine: str = "tesseract"
    trigger_reasons: tuple[str, ...] = ()
    paddle_error_type: str | None = None

    def available_engines(self) -> tuple[str, ...]:
        ordered = []
        for engine in ("tesseract", "paddleocr"):
            if engine in self.candidates:
                ordered.append(engine)

        for engine in self.candidates:
            if engine not in ordered:
                ordered.append(engine)

        return tuple(ordered)

    def get_candidate(self, engine: str) -> OCRCandidate:
        normalized = engine.strip().lower()
        try:
            return self.candidates[normalized]
        except KeyError as exc:
            raise ValueError(
                f"No existe candidato OCR disponible para '{engine}'."
            ) from exc

    def select(self, engine: str) -> OCRCandidate:
        candidate = self.get_candidate(engine)
        self.selected_engine = candidate.engine
        return candidate
