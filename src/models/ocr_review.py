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
    """Comparación en memoria de resultados Tesseract/PaddleOCR.

    ``selected_engine`` representa la vista activa que se está mostrando en la
    interfaz. Cuando existen dos motores, esa vista puede venir de la sugerencia
    automática y NO equivale a una decisión de exportación. ``confirmed_engine``
    sólo se establece por una elección explícita del usuario.
    """

    candidates: dict[str, OCRCandidate] = field(default_factory=dict)
    recommended_engine: str = "tesseract"
    selected_engine: str = "tesseract"
    trigger_reasons: tuple[str, ...] = ()
    paddle_error_type: str | None = None
    confirmed_engine: str | None = None

    def available_engines(self) -> tuple[str, ...]:
        ordered = []
        for engine in ("tesseract", "paddleocr"):
            if engine in self.candidates:
                ordered.append(engine)

        for engine in self.candidates:
            if engine not in ordered:
                ordered.append(engine)

        return tuple(ordered)

    @property
    def requires_user_selection(self) -> bool:
        """Indica si hay alternativas reales que el usuario debe resolver."""
        return len(self.available_engines()) > 1

    @property
    def selection_confirmed(self) -> bool:
        """True cuando no hay elección que hacer o ya se confirmó una."""
        return not self.requires_user_selection or self.confirmed_engine is not None

    def get_candidate(self, engine: str) -> OCRCandidate:
        normalized = engine.strip().lower()
        try:
            return self.candidates[normalized]
        except KeyError as exc:
            raise ValueError(
                f"No existe candidato OCR disponible para '{engine}'."
            ) from exc

    def preview(self, engine: str) -> OCRCandidate:
        """Cambia únicamente la vista activa sin confirmar la exportación."""
        candidate = self.get_candidate(engine)
        self.selected_engine = candidate.engine
        return candidate

    def select(self, engine: str, *, confirm: bool = True) -> OCRCandidate:
        """Activa un candidato y, por defecto, confirma la elección manual."""
        candidate = self.preview(engine)
        if confirm:
            self.confirmed_engine = candidate.engine
        return candidate
