from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from models.estado_cuenta import EstadoCuenta
from models.ocr_review import OCRReview
from validators.resultado_validacion import ResultadoValidacion


@dataclass
class ProcessingResult:
    """Resultado completo del procesamiento de un estado de cuenta.

    ``ocr_artifacts`` contiene exclusivamente PDFs con capa OCR ya verificada.
    El diccionario se indexa por motor para que un reproceso manual pueda
    conservar el artefacto primario y el secundario sin duplicar el documento
    digital ni mezclar rutas temporales con la lógica bancaria.
    """

    file_name: str
    bank_key: str
    estado_cuenta: EstadoCuenta
    raw_text: str
    normalized_text: str
    validaciones: list[ResultadoValidacion] = field(default_factory=list)
    processing_method: str = "Digital"
    debug: object | None = None
    ocr_review: OCRReview | None = None
    ocr_engine: str | None = None
    ocr_requested_primary_engine: str | None = None
    ocr_primary_engine: str | None = None
    ocr_secondary_engine: str | None = None
    fallback_attempted: bool = False
    fallback_used: bool = False
    source_pdf_path: str | None = None
    ocr_artifacts: dict[str, str] = field(default_factory=dict)
    ocr_reprocessed: bool = False

    def available_ocr_engines(self) -> tuple[str, ...]:
        if self.ocr_review is None:
            return ()
        return self.ocr_review.available_engines()

    @property
    def selected_ocr_engine(self) -> str | None:
        """Motor de la vista activa."""
        if self.ocr_review is not None:
            return self.ocr_review.selected_engine
        return self.ocr_engine

    @property
    def recommended_ocr_engine(self) -> str | None:
        if self.ocr_review is not None:
            return self.ocr_review.recommended_engine
        return self.ocr_engine

    @property
    def confirmed_ocr_engine(self) -> str | None:
        """Motor elegido explícitamente para exportación, si aplica."""
        if self.ocr_review is None:
            return self.ocr_engine
        if not self.ocr_review.requires_user_selection:
            engines = self.ocr_review.available_engines()
            return engines[0] if engines else self.ocr_engine
        return self.ocr_review.confirmed_engine

    @property
    def ocr_selection_confirmed(self) -> bool:
        if self.ocr_review is None:
            return True
        return self.ocr_review.selection_confirmed

    def register_ocr_artifact(self, engine: str, pdf_path: str | Path) -> None:
        normalized = str(engine or "").strip().lower()
        if normalized not in {"tesseract", "paddleocr"}:
            raise ValueError(f"Motor OCR no soportado para artefacto: {engine!r}.")
        self.ocr_artifacts[normalized] = str(Path(pdf_path).expanduser().resolve())

    def ocr_artifact_path(self, engine: str | None = None) -> str | None:
        normalized = str(engine or self.ocr_engine or "").strip().lower()
        if not normalized:
            return None
        return self.ocr_artifacts.get(normalized)

    def _activate_ocr_candidate(self, engine: str, *, confirm: bool) -> None:
        if self.ocr_review is None:
            raise ValueError("Este resultado no contiene alternativas OCR.")

        candidate = self.ocr_review.select(engine, confirm=confirm)
        self.estado_cuenta = candidate.estado_cuenta
        self.raw_text = candidate.document.raw_text
        self.normalized_text = candidate.document.normalized_text
        self.validaciones = list(candidate.validaciones)
        self.ocr_engine = candidate.engine
        # ``fallback_used`` se conserva sólo por compatibilidad histórica. Un
        # reproceso manual se identifica de forma independiente con
        # ``ocr_reprocessed`` y nunca se presenta como fallback automático.
        self.fallback_used = bool(
            not self.ocr_reprocessed
            and self.ocr_primary_engine
            and candidate.engine != self.ocr_primary_engine
        )

    def preview_ocr_engine(self, engine: str) -> None:
        """Muestra un candidato sin convertirlo en elección de exportación."""
        self._activate_ocr_candidate(engine, confirm=False)

    def select_ocr_engine(self, engine: str) -> None:
        """Confirma explícitamente el motor OCR que debe conservarse."""
        self._activate_ocr_candidate(engine, confirm=True)

    def restore_confirmed_ocr_engine(self) -> None:
        """Restaura la elección confirmada antes de serializar/exportar."""
        engine = self.confirmed_ocr_engine
        if engine is None:
            raise ValueError(
                f"El archivo '{self.file_name}' requiere elegir un resultado OCR antes de exportar."
            )
        if self.ocr_review is not None and self.ocr_review.requires_user_selection:
            self._activate_ocr_candidate(engine, confirm=False)
