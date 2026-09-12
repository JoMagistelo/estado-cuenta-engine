from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfplumber.utils import extract_text


@dataclass(slots=True)
class PDFTextStageData:
    """Resultado interno de ``PDFTextReader.read_stage()``."""

    raw_text: str
    initial_empty_pages: int
    has_extractable_text: bool


class PDFTextReader:
    """Extrae texto digital de un PDF.

    La ruta de clasificación usa el texto completo de la página como siempre.
    ``layer_tag`` existe exclusivamente para los artefactos OCR generados por el
    engine: permite reconstruir ``raw_text`` sólo desde la capa OCR verificada y
    evita mezclar texto previo, incompleto o defectuoso del PDF escaneado.
    """

    MAX_PAGES = 5

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
        *,
        layer_tag: str | None = None,
    ) -> str:
        file_path = Path(file_path)
        pages: list[str] = []

        with pdfplumber.open(file_path) as pdf:
            selected_pages = pdf.pages[
                start_page : start_page + PDFTextReader.MAX_PAGES
            ]
            for page in selected_pages:
                if layer_tag is None:
                    text = page.extract_text()
                else:
                    layer_chars = [
                        char
                        for char in page.chars
                        if str(char.get("tag") or "") == layer_tag
                    ]
                    text = extract_text(layer_chars) if layer_chars else ""
                if text:
                    pages.append(text)

        return "\n".join(pages)

    @staticmethod
    def read_stage(
        file_path: str | Path,
        start_page: int = 0,
    ) -> PDFTextStageData:
        """Primera etapa optimizada de clasificación Digital/OCR.

        Obtiene en una sola apertura el texto de las primeras ``MAX_PAGES``, el
        número de páginas iniciales vacías y si existe texto extraíble. Esta ruta
        deliberadamente no acepta ``layer_tag`` porque opera sobre el PDF de
        entrada antes de que exista cualquier artefacto OCR.
        """
        file_path = Path(file_path)
        pages: list[str] = []
        initial_empty_pages = 0
        found_extractable_text = False
        raw_text_end_page = start_page + PDFTextReader.MAX_PAGES

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            if start_page >= total_pages:
                return PDFTextStageData(
                    raw_text="",
                    initial_empty_pages=0,
                    has_extractable_text=False,
                )

            for physical_index in range(start_page, total_pages):
                page = pdf.pages[physical_index]
                text = page.extract_text()
                has_text = bool(text and text.strip())

                if not found_extractable_text:
                    if has_text:
                        found_extractable_text = True
                    else:
                        initial_empty_pages += 1

                if physical_index < raw_text_end_page and text:
                    pages.append(text)

                if (
                    found_extractable_text
                    and physical_index >= raw_text_end_page - 1
                ):
                    break

        return PDFTextStageData(
            raw_text="\n".join(pages),
            initial_empty_pages=initial_empty_pages,
            has_extractable_text=found_extractable_text,
        )
