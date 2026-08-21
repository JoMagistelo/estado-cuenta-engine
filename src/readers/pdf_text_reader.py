from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


# ============================================================
# RESULTADO DE LA ETAPA DE TEXTO
# ============================================================


@dataclass(slots=True)
class PDFTextStageData:
    """
    Resultado interno de PDFTextReader.read_stage().

    raw_text:
        Texto extraído de las primeras MAX_PAGES páginas
        a partir de start_page.

    initial_empty_pages:
        Número de páginas iniciales sin texto extraíble.

    has_extractable_text:
        True si existe al menos una página con texto
        extraíble desde start_page.
    """

    raw_text: str
    initial_empty_pages: int
    has_extractable_text: bool


# ============================================================
# READER
# ============================================================


class PDFTextReader:
    """
    Extrae texto digital de un PDF.

    MAX_PAGES determina cuántas páginas se conservan en
    raw_text.

    Adicionalmente read_stage() permite al pipeline conocer:

        - cuántas páginas iniciales están vacías
        - si existe texto extraíble en el PDF

    sin ejecutar PDFWordReader.
    """

    MAX_PAGES = 5

    # ========================================================
    # LECTURA ORIGINAL
    # ========================================================

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
    ) -> str:
        """
        Extrae texto de las primeras MAX_PAGES páginas,
        comenzando desde start_page.

        Conserva el comportamiento original.
        """

        file_path = Path(file_path)

        pages: list[str] = []

        with pdfplumber.open(file_path) as pdf:

            selected_pages = pdf.pages[
                start_page:
                start_page + PDFTextReader.MAX_PAGES
            ]

            for page in selected_pages:

                text = page.extract_text()

                if text:
                    pages.append(text)

        return "\n".join(pages)

    # ========================================================
    # LECTURA OPTIMIZADA
    # ========================================================

    @staticmethod
    def read_stage(
        file_path: str | Path,
        start_page: int = 0,
    ) -> PDFTextStageData:
        """
        Primera etapa optimizada del pipeline.

        Obtiene en una sola apertura del PDF:

            1. raw_text de las primeras MAX_PAGES páginas.
            2. páginas iniciales vacías.
            3. existencia de texto extraíble.

        NO extrae palabras espaciales.
        """

        file_path = Path(file_path)

        pages: list[str] = []

        initial_empty_pages = 0
        found_extractable_text = False

        raw_text_end_page = (
            start_page + PDFTextReader.MAX_PAGES
        )

        with pdfplumber.open(file_path) as pdf:

            total_pages = len(pdf.pages)

            # =================================================
            # PDF SIN PÁGINAS DISPONIBLES DESDE start_page
            # =================================================

            if start_page >= total_pages:

                return PDFTextStageData(
                    raw_text="",
                    initial_empty_pages=0,
                    has_extractable_text=False,
                )

            # =================================================
            # PRIMER RECORRIDO
            # =================================================

            for physical_index in range(
                start_page,
                total_pages,
            ):

                page = pdf.pages[physical_index]

                text = page.extract_text()

                has_text = bool(
                    text and text.strip()
                )

                # ---------------------------------------------
                # PÁGINAS INICIALES VACÍAS
                # ---------------------------------------------

                if not found_extractable_text:

                    if has_text:

                        found_extractable_text = True

                    else:

                        initial_empty_pages += 1

                # ---------------------------------------------
                # RAW TEXT
                #
                # Exactamente las primeras MAX_PAGES páginas
                # desde start_page.
                # ---------------------------------------------

                if physical_index < raw_text_end_page:

                    if text:

                        pages.append(text)

                # ---------------------------------------------
                # Una vez que:
                #
                #   - encontramos texto
                #   - ya terminamos las primeras MAX_PAGES
                #
                # no necesitamos seguir recorriendo.
                # ---------------------------------------------

                if (
                    found_extractable_text
                    and physical_index >= raw_text_end_page - 1
                ):

                    break

            # =================================================
            # SI LAS PRIMERAS MAX_PAGES FUERON VACÍAS
            # =================================================
            #
            # Debemos continuar buscando texto más adelante.
            #
            # Esto permite distinguir:
            #
            #   PDF imagen
            #
            # de:
            #
            #   PDF digital cuyo contenido comienza
            #   después de MAX_PAGES páginas vacías.
            #
            # =================================================

            if not found_extractable_text:

                for physical_index in range(
                    start_page + PDFTextReader.MAX_PAGES,
                    total_pages,
                ):

                    page = pdf.pages[physical_index]

                    text = page.extract_text()

                    if text and text.strip():

                        found_extractable_text = True

                        break

        return PDFTextStageData(
            raw_text="\n".join(pages),
            initial_empty_pages=initial_empty_pages,
            has_extractable_text=found_extractable_text,
        )