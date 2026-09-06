from __future__ import annotations

import os
import re
from pathlib import Path
from threading import Lock
from typing import Any, Sequence

import pypdfium2 as pdfium
from PIL import Image

from readers.models import DocumentData


class PaddleOCRConfigurationError(RuntimeError):
    """Configuración local incompleta para ejecutar PaddleOCR."""


class PaddleOCRPDFReader:
    """Convierte PDF a ``DocumentData`` mediante PaddleOCR local.

    El reader está diseñado como fallback controlado de Tesseract. No descarga
    modelos en runtime y no utiliza la API alojada de PaddleOCR. Los modelos de
    detección y reconocimiento deben estar previamente instalados en rutas
    locales autorizadas.

    En Windows/CPU se prioriza estabilidad: oneDNN/MKL-DNN queda deshabilitado
    por defecto porque esta misma combinación PaddlePaddle 3.x + PP-OCRv5 ya
    produjo ``NotImplementedError`` durante inferencia. La aceleración sigue
    disponible como opt-in mediante ``PADDLEOCR_ENABLE_MKLDNN=1`` para pruebas
    controladas. La detección limita además el lado mayor de la página para
    evitar inferencia innecesaria a resolución completa.
    """

    MAX_TEXT_PAGES = 5
    RENDER_DPI = 300
    DEFAULT_LANGUAGE = "es"
    DEFAULT_DEVICE = "cpu"
    DEFAULT_DETECTION_MODEL_NAME = "PP-OCRv5_mobile_det"
    DEFAULT_RECOGNITION_MODEL_NAME = "latin_PP-OCRv5_mobile_rec"
    DEFAULT_TEXT_DET_LIMIT_SIDE_LEN = 1600
    DEFAULT_ENABLE_MKLDNN = False
    DEFAULT_CPU_THREADS = 10

    _engine: Any | None = None
    _engine_signature: tuple[Any, ...] | None = None
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
            raise FileNotFoundError(f"No existe el PDF: {file_path}")

        config = cls._load_config()
        engine = cls._get_engine(**config)
        dpi = cls._configured_dpi()
        text_det_limit_side_len = cls._configured_detection_side_len()

        pdf = pdfium.PdfDocument(str(file_path))
        all_words: list[dict[str, Any]] = []
        text_pages: list[str] = []
        doctop_offset = 0.0

        for physical_index in range(start_page, len(pdf)):
            page = pdf[physical_index]
            page_width, page_height = page.get_size()

            bitmap = page.render(scale=dpi / 72.0)
            image = bitmap.to_pil().convert("RGB")

            logical_page = physical_index - start_page + 1
            words, page_text = cls._read_page(
                engine=engine,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
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
                "source_path": str(file_path.resolve()),
                "reader": "paddleocr",
                "ocr": True,
                "dpi": dpi,
                "language": config["language"],
                "device": config["device"],
                "detection_model": config["detection_model_name"],
                "recognition_model": config["recognition_model_name"],
                "coordinate_space": "pdf_points",
                "network_model_downloads": False,
                "mkldnn_enabled": config["enable_mkldnn"],
                "cpu_threads": config["cpu_threads"],
                "text_det_limit_side_len": text_det_limit_side_len,
                "text_det_limit_type": "max",
            },
        )

    @classmethod
    def _load_config(cls) -> dict[str, Any]:
        detection_dir = cls._required_model_dir(
            "PADDLEOCR_TEXT_DETECTION_MODEL_DIR"
        )
        recognition_dir = cls._required_model_dir(
            "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR"
        )

        language = os.getenv(
            "PADDLEOCR_LANG",
            cls.DEFAULT_LANGUAGE,
        ).strip() or cls.DEFAULT_LANGUAGE
        if language.lower() != cls.DEFAULT_LANGUAGE:
            raise PaddleOCRConfigurationError(
                "Estado Cuenta Engine admite PaddleOCR únicamente en español "
                "para documentos bancarios de México. Configura "
                "PADDLEOCR_LANG=es."
            )

        return {
            "language": cls.DEFAULT_LANGUAGE,
            "device": os.getenv(
                "PADDLEOCR_DEVICE",
                cls.DEFAULT_DEVICE,
            ).strip()
            or cls.DEFAULT_DEVICE,
            "detection_model_name": os.getenv(
                "PADDLEOCR_TEXT_DETECTION_MODEL_NAME",
                cls.DEFAULT_DETECTION_MODEL_NAME,
            ).strip()
            or cls.DEFAULT_DETECTION_MODEL_NAME,
            "recognition_model_name": os.getenv(
                "PADDLEOCR_TEXT_RECOGNITION_MODEL_NAME",
                cls.DEFAULT_RECOGNITION_MODEL_NAME,
            ).strip()
            or cls.DEFAULT_RECOGNITION_MODEL_NAME,
            "detection_model_dir": str(detection_dir),
            "recognition_model_dir": str(recognition_dir),
            "enable_mkldnn": cls._configured_bool(
                "PADDLEOCR_ENABLE_MKLDNN",
                cls.DEFAULT_ENABLE_MKLDNN,
            ),
            "cpu_threads": cls._configured_cpu_threads(),
        }

    @staticmethod
    def _required_model_dir(variable_name: str) -> Path:
        configured = os.getenv(variable_name, "").strip()
        if not configured:
            raise PaddleOCRConfigurationError(
                f"Falta configurar {variable_name}. "
                "PaddleOCR no descargará modelos automáticamente."
            )

        path = Path(configured).expanduser().resolve()
        if not path.is_dir():
            raise PaddleOCRConfigurationError(
                f"La ruta configurada en {variable_name} no existe "
                "o no es un directorio válido."
            )

        return path

    @staticmethod
    def _configured_bool(variable_name: str, default: bool) -> bool:
        configured = os.getenv(variable_name, "").strip().lower()
        if not configured:
            return default
        if configured in {"1", "true", "yes", "on", "si", "sí"}:
            return True
        if configured in {"0", "false", "no", "off"}:
            return False
        return default

    @classmethod
    def _configured_cpu_threads(cls) -> int:
        configured = os.getenv("PADDLEOCR_CPU_THREADS", "").strip()
        if not configured:
            return cls.DEFAULT_CPU_THREADS

        try:
            threads = int(configured)
        except ValueError:
            return cls.DEFAULT_CPU_THREADS

        return max(1, min(threads, 32))

    @classmethod
    def _configured_dpi(cls) -> int:
        configured = os.getenv("PADDLEOCR_DPI", "").strip()
        if not configured:
            return cls.RENDER_DPI

        try:
            dpi = int(configured)
        except ValueError:
            return cls.RENDER_DPI

        return max(150, min(dpi, 600))

    @classmethod
    def _configured_detection_side_len(cls) -> int:
        configured = os.getenv(
            "PADDLEOCR_TEXT_DET_LIMIT_SIDE_LEN",
            "",
        ).strip()
        if not configured:
            return cls.DEFAULT_TEXT_DET_LIMIT_SIDE_LEN

        try:
            side_len = int(configured)
        except ValueError:
            return cls.DEFAULT_TEXT_DET_LIMIT_SIDE_LEN

        return max(960, min(side_len, 2400))

    @classmethod
    def _get_engine(
        cls,
        language: str,
        device: str,
        detection_model_name: str,
        recognition_model_name: str,
        detection_model_dir: str,
        recognition_model_dir: str,
        enable_mkldnn: bool,
        cpu_threads: int,
    ):
        signature = (
            language,
            device,
            detection_model_name,
            recognition_model_name,
            detection_model_dir,
            recognition_model_dir,
            enable_mkldnn,
            cpu_threads,
        )

        with cls._engine_lock:
            if cls._engine is not None and cls._engine_signature == signature:
                return cls._engine

            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"
            os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = (
                "1" if enable_mkldnn else "0"
            )

            try:
                from paddleocr import PaddleOCR
            except ModuleNotFoundError as exc:
                raise PaddleOCRConfigurationError(
                    "PaddleOCR no está instalado. Instala el extra opcional "
                    "del proyecto: .[paddleocr]."
                ) from exc

            try:
                cls._engine = PaddleOCR(
                    device=device,
                    text_detection_model_name=detection_model_name,
                    text_detection_model_dir=detection_model_dir,
                    text_recognition_model_name=recognition_model_name,
                    text_recognition_model_dir=recognition_model_dir,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    enable_mkldnn=enable_mkldnn,
                    cpu_threads=cpu_threads,
                )
            except Exception as exc:
                raise PaddleOCRConfigurationError(
                    "No se pudo inicializar PaddleOCR con los modelos locales "
                    "configurados."
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
        text_det_limit_side_len: int,
    ) -> tuple[list[dict[str, Any]], str]:
        try:
            import numpy as np
        except ModuleNotFoundError as exc:
            raise PaddleOCRConfigurationError(
                "La instalación de PaddleOCR no incluye NumPy."
            ) from exc

        image_array = np.asarray(image)

        with cls._predict_lock:
            result = engine.predict(
                image_array,
                text_det_limit_side_len=text_det_limit_side_len,
                text_det_limit_type="max",
            )

        image_width = max(float(image.width), 1.0)
        pixel_to_pdf = page_width / image_width

        line_items: list[
            tuple[float, float, float, float, str, float]
        ] = []

        for page_result in result:
            texts = cls._result_field(page_result, "rec_texts", default=[])
            scores = cls._result_field(page_result, "rec_scores", default=[])
            boxes = cls._result_field(page_result, "rec_boxes", default=[])

            for index, raw_text in enumerate(texts):
                text = str(raw_text or "").strip()
                if not text or index >= len(boxes):
                    continue

                box = boxes[index]
                try:
                    x0_px = float(box[0])
                    top_px = float(box[1])
                    x1_px = float(box[2])
                    bottom_px = float(box[3])
                except (TypeError, ValueError, IndexError):
                    continue

                try:
                    score = float(scores[index])
                except (TypeError, ValueError, IndexError):
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

        line_items.sort(key=lambda item: (item[0], item[1]))

        words: list[dict[str, Any]] = []
        page_lines: list[str] = []

        for top_px, x0_px, x1_px, bottom_px, text, score in line_items:
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
    def _result_field(result: Any, name: str, default: Any) -> Any:
        payload = getattr(result, "json", None)
        if callable(payload):
            try:
                payload = payload()
            except TypeError:
                payload = None

        if isinstance(payload, dict):
            data = payload.get("res", payload)
            if isinstance(data, dict) and name in data:
                return data[name]

        if isinstance(result, dict):
            data = result.get("res", result)
            if isinstance(data, dict) and name in data:
                return data[name]

        try:
            value = result[name]
        except (KeyError, TypeError, IndexError):
            value = None

        if value is not None:
            return value

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
        """Divide una caja de línea PaddleOCR en tokens espaciales."""
        if len(pdf_box) < 4:
            return []

        x0, top, x1, bottom = map(float, pdf_box[:4])
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
        words: list[dict[str, Any]] = []

        for match in re.finditer(r"\S+", normalized):
            token = match.group(0)
            token_x0 = x0 + width * (match.start() / char_count)
            token_x1 = x0 + width * (match.end() / char_count)

            words.append(
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

        return words
