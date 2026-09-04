from __future__ import annotations

import re

from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import pypdfium2 as pdfium

from readers.models import DocumentData
from readers.tesseract_pdf_reader import TesseractPDFReader


class AdaptiveTesseractPDFReader:
    """
    Mantiene Tesseract 300 DPI / PSM 3 como lectura principal.

    Sólo en páginas que ya muestran estructura de tabla financiera se
    ejecuta una segunda lectura a mayor resolución. La recuperación se
    adopta únicamente si agrega filas contables estructuradas y conserva
    una cantidad razonable de palabras con confianza alta.

    Esto evita convertir 450 DPI en un cambio global de comportamiento.
    """

    RECOVERY_DPI = 450
    MIN_PRIMARY_STRUCTURED_ROWS = 2
    MIN_STRUCTURED_ROW_GAIN = 1
    MIN_HIGH_CONFIDENCE_RATIO = 0.85
    LINE_Y_TOLERANCE = 5.0

    MONEY_PATTERN = re.compile(
        r"^\$?\s*[\d,]+(?:\.\d{1,2})$"
    )
    DAY_PATTERN = re.compile(
        r"^[\s.,;:|_]*(?:0?[1-9]|[12]\d|3[01])"
        r"[\s.,;:|_]*$"
    )

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_page(word: Dict[str, Any]) -> int:
        try:
            return int(word.get("page", 1))
        except (TypeError, ValueError):
            return 1

    @classmethod
    def _center_y(cls, word: Dict[str, Any]) -> float:
        top = cls._safe_float(word.get("top", 0.0))
        bottom = cls._safe_float(word.get("bottom", top))
        return (top + bottom) / 2.0

    @classmethod
    def _group_lines(
        cls,
        words: Sequence[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        ordered = sorted(
            (
                word
                for word in words
                if str(word.get("text", "")).strip()
            ),
            key=lambda word: (
                cls._center_y(word),
                cls._safe_float(word.get("x0", 0.0)),
            ),
        )
        lines: List[List[Dict[str, Any]]] = []

        for word in ordered:
            center_y = cls._center_y(word)
            target = None

            for line in reversed(lines):
                line_y = sum(cls._center_y(item) for item in line) / len(line)
                if abs(line_y - center_y) <= cls.LINE_Y_TOLERANCE:
                    target = line
                    break
                if center_y - line_y > cls.LINE_Y_TOLERANCE:
                    break

            if target is None:
                lines.append([word])
            else:
                target.append(word)

        for line in lines:
            line.sort(key=lambda item: cls._safe_float(item.get("x0", 0.0)))

        return lines

    @classmethod
    def page_quality(
        cls,
        words: Sequence[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        """
        Devuelve:
            filas contables estructuradas,
            palabras con confianza >= 60,
            caracteres con confianza >= 40.

        La primera métrica decide la recuperación; las otras dos evitan
        aceptar una lectura que gane una fila a costa de degradar toda
        la página.
        """

        structured_rows = 0

        for line in cls._group_lines(words):
            has_day = any(
                cls._safe_float(word.get("x0", 0.0)) < 75.0
                and cls.DAY_PATTERN.fullmatch(
                    str(word.get("text", "")).strip()
                )
                for word in line
            )
            money_words = [
                word
                for word in line
                if cls.MONEY_PATTERN.fullmatch(
                    str(word.get("text", "")).strip()
                )
                and re.search(r"\d", str(word.get("text", "")))
            ]

            if has_day and len(money_words) >= 2:
                structured_rows += 1

        high_confidence = 0
        confident_characters = 0

        for word in words:
            confidence = cls._safe_float(word.get("confidence", -1.0), -1.0)
            text = str(word.get("text", "")).strip()

            if confidence >= 60.0:
                high_confidence += 1
            if confidence >= 40.0:
                confident_characters += len(text)

        return structured_rows, high_confidence, confident_characters

    @classmethod
    def should_use_recovery_page(
        cls,
        primary_words: Sequence[Dict[str, Any]],
        recovery_words: Sequence[Dict[str, Any]],
    ) -> bool:
        primary_rows, primary_high, primary_chars = cls.page_quality(primary_words)
        recovery_rows, recovery_high, recovery_chars = cls.page_quality(recovery_words)

        if primary_rows < cls.MIN_PRIMARY_STRUCTURED_ROWS:
            return False

        if recovery_rows < primary_rows + cls.MIN_STRUCTURED_ROW_GAIN:
            return False

        minimum_high = int(primary_high * cls.MIN_HIGH_CONFIDENCE_RATIO)
        if recovery_high < minimum_high:
            return False

        # La cantidad de caracteres es una segunda barrera suave. Se
        # tolera una reducción moderada porque una lectura más limpia
        # puede unir tokens, pero no una pérdida masiva de contenido.
        minimum_chars = int(primary_chars * 0.80)
        if recovery_chars < minimum_chars:
            return False

        return True

    @classmethod
    def read(
        cls,
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        file_path = Path(file_path)

        primary = TesseractPDFReader.read(
            file_path,
            start_page=start_page,
        )

        if not primary.spatial_words:
            return primary

        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for word in primary.spatial_words:
            by_page.setdefault(cls._safe_page(word), []).append(word)

        candidate_pages = [
            page
            for page, page_words in by_page.items()
            if cls.page_quality(page_words)[0] >= cls.MIN_PRIMARY_STRUCTURED_ROWS
        ]

        if not candidate_pages:
            return primary

        _, tessdata_dir = TesseractPDFReader._configure_tesseract()
        pdf = pdfium.PdfDocument(str(file_path))

        page_heights: List[float] = []
        for physical_index in range(len(pdf)):
            _, page_height = pdf[physical_index].get_size()
            page_heights.append(page_height)

        replacement_pages: Dict[int, List[Dict[str, Any]]] = {}
        recovery_pages: List[int] = []

        for logical_page in sorted(candidate_pages):
            physical_index = start_page + logical_page - 1
            if physical_index < 0 or physical_index >= len(pdf):
                continue

            page = pdf[physical_index]
            page_width, _ = page.get_size()
            bitmap = page.render(
                scale=cls.RECOVERY_DPI / 72
            )
            image = TesseractPDFReader._preprocess(
                bitmap.to_pil()
            )

            doctop_offset = sum(page_heights[start_page:physical_index])

            recovery_words, _ = TesseractPDFReader._read_page(
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                tessdata_dir=tessdata_dir,
            )

            primary_page_words = by_page.get(logical_page, [])

            if cls.should_use_recovery_page(
                primary_page_words,
                recovery_words,
            ):
                replacement_pages[logical_page] = recovery_words
                recovery_pages.append(logical_page)

        if not replacement_pages:
            metadata = dict(primary.metadata or {})
            metadata.update(
                {
                    "adaptive_ocr": True,
                    "recovery_dpi": cls.RECOVERY_DPI,
                    "recovery_pages": [],
                }
            )
            return DocumentData(
                raw_text=primary.raw_text,
                normalized_text=primary.normalized_text,
                spatial_words=primary.spatial_words,
                metadata=metadata,
            )

        combined: List[Dict[str, Any]] = []
        all_pages = set(by_page) | set(replacement_pages)

        for page in sorted(all_pages):
            combined.extend(
                replacement_pages.get(page, by_page.get(page, []))
            )

        combined.sort(
            key=lambda word: (
                cls._safe_page(word),
                cls._safe_float(word.get("top", 0.0)),
                cls._safe_float(word.get("x0", 0.0)),
            )
        )

        metadata = dict(primary.metadata or {})
        metadata.update(
            {
                "adaptive_ocr": True,
                "primary_dpi": TesseractPDFReader.RENDER_DPI,
                "recovery_dpi": cls.RECOVERY_DPI,
                "recovery_pages": recovery_pages,
            }
        )

        return DocumentData(
            raw_text=primary.raw_text,
            normalized_text=primary.normalized_text,
            spatial_words=combined,
            metadata=metadata,
        )
