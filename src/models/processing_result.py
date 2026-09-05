from __future__ import annotations

from dataclasses import dataclass, field

from models.estado_cuenta import EstadoCuenta
from models.ocr_review import OCRReview
from validators.resultado_validacion import ResultadoValidacion


@dataclass
class ProcessingResult:
    """Resultado completo del procesamiento de un estado de cuenta.

    Para documentos OCR, ``ocr_review`` puede conservar temporalmente los
    candidatos Tesseract y PaddleOCR. El candidato seleccionado se refleja en
    los campos públicos existentes para mantener compatibilidad con mappers,
    exportadores e interfaces actuales.
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

    def available_ocr_engines(self) -> tuple[str, ...]:
        if self.ocr_review is None:
            return ()
        return self.ocr_review.available_engines()

    @property
    def selected_ocr_engine(self) -> str | None:
        if self.ocr_review is None:
            return None
        return self.ocr_review.selected_engine

    @property
    def recommended_ocr_engine(self) -> str | None:
        if self.ocr_review is None:
            return None
        return self.ocr_review.recommended_engine

    def select_ocr_engine(self, engine: str) -> None:
        """Aplica en memoria el candidato OCR elegido por el usuario."""
        if self.ocr_review is None:
            raise ValueError("Este resultado no contiene alternativas OCR.")

        candidate = self.ocr_review.select(engine)
        self.estado_cuenta = candidate.estado_cuenta
        self.raw_text = candidate.document.raw_text
        self.normalized_text = candidate.document.normalized_text
        self.validaciones = list(candidate.validaciones)
