from __future__ import annotations

import os
import re
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Sequence

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from readers.models import DocumentData


class PaddleOCRPDFReader:
    """
    Convierte un PDF a ``DocumentData`` mediante PaddleOCR 3.x.

    Objetivo de compatibilidad:

        PaddleOCR
            -> detección/reconocimiento por línea
            -> división proporcional en tokens
            -> mismo esquema ``spatial_words`` usado por Tesseract

    PaddleOCR devuelve cajas por línea de texto. Los parsers del engine
    trabajan principalmente con palabras/tokens, por lo que cada línea
    reconocida se divide por espacios y su caja se reparte de forma
    proporcional. No se modifican las coordenadas verticales.

    El import de PaddleOCR es deliberadamente lazy: el engine puede seguir
    usando Tesseract sin instalar PaddleOCR hasta que realmente necesite el
    fallback.
    """

    MAX_TEXT_PAGES = 5
    RENDER_DPI = 300
    DEFAULT_LANGUAGE = "es"
    DEFAULT_DEVICE = "cpu"

    _engine: Any | None = None
    _engine_signature: tuple[str, str] | None = None
    _engine_lock = Lock()
    _predict_lock = Lock()

    @classmethod
    def read(
        cls,
        file_path: str | Path,
        start_page: int = 0,
    ) -> DocumentData:
        file_path = Path(file_path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"No existe el PDF: {file_path}"
            )

        language = os.getenv(
            "PADDLEOCR_LANG",
            cls.DEFAULT_LANGUAGE,
        ).strip() or cls.DEFAULT_LANGUAGE

        device = os.getenv(
            "PADDLEOCR_DEVICE",
            cls.DEFAULT_DEVICE,
        ).strip() or cls.DEFAULT_DEVICE

        dpi = cls._configured_dpi()
        engine = cls._get_engine(
            language=language,
            device=device,
        )

        pdf = pdfium.PdfDocument(str(file_path))

        all_words: list[dict[str, Any]] = []
        text_pages: list[str] = []
        doctop_offset = 0.0

        for physical_index in range(start_page, len(pdf)):
            page = pdf[physical_index]
            page_width, page_height = page.get_size()

            bitmap = page.render(
                scale=dpi / 72.0
            )
            image = bitmap.to_pil().convert("RGB")

            logical_page = (
                physical_index
                - start_page
                + 1
            )

            words, page_text = cls._read_page(
                engine=engine,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
            )

            all_words.extend(words)

            if logical_page <= cls.MAX_TEXT_PAGES:
                text_pages.append(page_text)

            doctop_offset += page_height

        return DocumentData(
            raw_text="\n".join(text_pages),
            normalized_text="",
            spatial_words=all_words,
            metadata={
                "start_page": start_page,
                "reader": "paddleocr",
                "ocr": True,
                "dpi": dpi,
                "language": language,
                "device": device,
                "coordinate_space": "pdf_points",
            },
        )

    @classmethod
    def _configured_dpi(cls) -> int:
        configured = os.getenv("PADDLEOCR_DPI")
        if not configured:
            return cls.RENDER_DPI

        try:
            dpi = int(configured)
        except ValueError:
            return cls.RENDER_DPI

        # Evita configuraciones accidentales demasiado pequeñas/grandes.
        return max(150, min(dpi, 600))

    @classmethod
    def _get_engine(
        cls,
        language: str,
        device: str,
    ):
        signature = (language, device)

        with cls._engine_lock:
            if (
                cls._engine is not None
                and cls._engine_signature == signature
            ):
                return cls._engine

            try:
                from paddleocr import PaddleOCR
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "PaddleOCR no está instalado. Instala primero "
                    "PaddlePaddle y después paddleocr>=3.7.0. "
                    "Consulta docs/paddleocr_fallback.md."
                ) from exc

            try:
                cls._engine = PaddleOCR(
                    lang=language,
                    device=device,
                    engine="paddle",
                    # No usamos unwarping/orientación global porque pueden
                    # alterar la geometría base respecto al PDF. La orientación
                    # de línea sí mejora reconocimiento sin cambiar el sistema
                    # global de coordenadas que consumen los parsers.
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=True,
                )
            except Exception as exc:
                raise RuntimeError(
                    "No se pudo inicializar PaddleOCR. Revisa la instalación "
                    "de PaddlePaddle/PaddleOCR y PADDLEOCR_DEVICE."
                ) from exc

            cls._engine_signature = signature
            return cls._engine

    @classmethod
    def _read_page(
        cls,
        engine: Any,
        image: Image.Image,
        logical_page: int,
        page_width: float,
        doctop_offset: float,
    ) -> tuple[list[dict[str, Any]], str]:
        image_array = np.asarray(image)

        # PaddleOCR mantiene modelos pesados en memoria. Serializamos la
        # inferencia para evitar carreras si alguien sube ocr_workers > 1.
        with cls._predict_lock:
            result = engine.predict(image_array)

        image_width = max(float(image.width), 1.0)
        pixel_to_pdf = page_width / image_width

        line_items: list[
            tuple[float, float, float, float, str, float]
        ] = []

        for page_result in result:
            texts = cls._result_field(
                page_result,
                "rec_texts",
                default=[],
            )
            scores = cls._result_field(
                page_result,
                "rec_scores",
                default=[],
            )
            boxes = cls._result_field(
                page_result,
                "rec_boxes",
                default=[],
            )

            for index, raw_text in enumerate(texts):
                text = str(raw_text or "").strip()
                if not text:
                    continue
                if index >= len(boxes):
                    continue

                box = boxes[index]
                try:
                    x0_px, top_px, x1_px, bottom_px = (
                        float(box[0]),
                        float(box[1]),
                        float(box[2]),
                        float(box[3]),
                    )
                except (
                    TypeError,
                    ValueError,
                    IndexError,
                ):
                    continue

                try:
                    score = float(scores[index])
                except (
                    TypeError,
                    ValueError,
                    IndexError,
                ):
                    score = 0.0

                line_items.append(
                    (
                        top_px,
                        x0_px,
                        x1_px,
                        bottom_px,
                        text,
                        score,
                    )
                )

        line_items.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        words: list[dict[str, Any]] = []
        page_lines: list[str] = []

        for (
            top_px,
            x0_px,
            x1_px,
            bottom_px,
            text,
            score,
        ) in line_items:
            page_lines.append(text)

            pdf_box = (
                x0_px * pixel_to_pdf,
                top_px * pixel_to_pdf,
                x1_px * pixel_to_pdf,
                bottom_px * pixel_to_pdf,
            )

            words.extend(
                cls._split_recognition_into_words(
                    text=text,
                    pdf_box=pdf_box,
                    logical_page=logical_page,
                    doctop_offset=doctop_offset,
                    confidence=score * 100.0,
                )
            )

        words.sort(
            key=lambda word: (
                int(word.get("page", 1)),
                float(word.get("top", 0.0)),
                float(word.get("x0", 0.0)),
            )
        )

        return words, "\n".join(page_lines)

    @staticmethod
    def _result_field(
        result: Any,
        name: str,
        default: Any,
    ) -> Any:
        """
        PaddleOCR 3.x expone Result como mapping. Este helper tolera
        adicionalmente wrappers con ``res`` o atributos para reducir el
        acoplamiento a una versión menor concreta.
        """
        try:
            value = result[name]
        except (
            KeyError,
            TypeError,
            IndexError,
        ):
            value = None

        if value is not None:
            return value

        nested = getattr(result, "res", None)
        if isinstance(nested, dict) and name in nested:
            return nested[name]

        value = getattr(result, name, None)
        return default if value is None else value

    @staticmethod
    def _split_recognition_into_words(
        text: str,
        pdf_box: Sequence[float],
        logical_page: int,
        doctop_offset: float,
        confidence: float,
    ) -> list[dict[str, Any]]:
        """
        Convierte una caja de línea PaddleOCR en tokens compatibles con
        ``PDFWordReader``/``TesseractPDFReader``.

        La posición X se reparte según la posición de cada token dentro de
        la cadena reconocida. Esto es aproximado, pero conserva mucho mejor
        las columnas que tratar toda la línea como una única ``word``.
        """
        if len(pdf_box) < 4:
            return []

        x0, top, x1, bottom = (
            float(pdf_box[0]),
            float(pdf_box[1]),
            float(pdf_box[2]),
            float(pdf_box[3]),
        )

        if x1 < x0:
            x0, x1 = x1, x0
        if bottom < top:
            top, bottom = bottom, top

        normalized = re.sub(r"\s+", " ", text.strip())
        if not normalized:
            return []

        width = max(x1 - x0, 0.001)
        height = max(bottom - top, 0.001)
        char_count = max(len(normalized), 1)

        result: list[dict[str, Any]] = []

        for match in re.finditer(r"\S+", normalized):
            token = match.group(0)

            token_x0 = (
                x0
                + width * (match.start() / char_count)
            )
            token_x1 = (
                x0
                + width * (match.end() / char_count)
            )

            result.append(
                {
                    "text": token,
                    "x0": token_x0,
                    "x1": token_x1,
                    "top": top,
                    "bottom": bottom,
                    "doctop": doctop_offset + top,
                    "width": max(token_x1 - token_x0, 0.001),
                    "height": height,
                    "upright": True,
                    "direction": "ltr",
                    "page": logical_page,
                    "confidence": confidence,
                }
            )

        return result
