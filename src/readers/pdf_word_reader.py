from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
from pdfplumber.utils import extract_words


class PDFWordReader:
    """Extrae palabras del PDF con coordenadas en puntos PDF.

    ``layer_tag`` permite limitar la extracción a una capa de contenido marcado.
    La ruta digital lo omite y conserva exactamente el comportamiento histórico;
    los PDFs OCR generados por el engine lo utilizan para leer únicamente la capa
    de texto verificada e ignorar cualquier texto previo o defectuoso del escaneo.

    El número de página entregado al resto del sistema representa la página
    lógica del documento.

    Ejemplo::

        start_page=0
        física 1 -> página 1
        física 2 -> página 2

        start_page=2
        física 3 -> página 1
        física 4 -> página 2
    """

    @staticmethod
    def read(
        file_path: str | Path,
        start_page: int = 0,
        *,
        layer_tag: str | None = None,
    ) -> list[dict[str, Any]]:
        file_path = Path(file_path)
        all_words: list[dict[str, Any]] = []

        with pdfplumber.open(file_path) as pdf:
            for physical_page_index, page in enumerate(
                pdf.pages[start_page:],
                start=start_page,
            ):
                if layer_tag is None:
                    words = page.extract_words(
                        keep_blank_chars=False,
                        use_text_flow=True,
                    )
                else:
                    layer_chars = [
                        char
                        for char in page.chars
                        if str(char.get("tag") or "") == layer_tag
                    ]
                    words = extract_words(
                        layer_chars,
                        keep_blank_chars=False,
                        use_text_flow=True,
                    )

                logical_page = physical_page_index - start_page + 1
                for word in words:
                    word["page"] = logical_page
                    all_words.append(word)

        return all_words
