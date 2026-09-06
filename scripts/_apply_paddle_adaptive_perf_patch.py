from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


# Restore the fast PaddlePaddle 3.2 path that was validated in PR #20 while
# keeping a one-shot compatibility recovery for machines that still raise
# NotImplementedError in oneDNN.
reader = Path("src/readers/paddleocr_pdf_reader.py")
text = reader.read_text(encoding="utf-8")
text = replace_once(
    text,
    """    En Windows/CPU se prioriza estabilidad: oneDNN/MKL-DNN queda deshabilitado
    por defecto porque esta misma combinación PaddlePaddle 3.x + PP-OCRv5 ya
    produjo ``NotImplementedError`` durante inferencia. La aceleración sigue
    disponible como opt-in mediante ``PADDLEOCR_ENABLE_MKLDNN=1`` para pruebas
    controladas. La detección limita además el lado mayor de la página para
    evitar inferencia innecesaria a resolución completa.
""",
    """    En Windows/CPU con PaddlePaddle 3.2.0 se usa oneDNN/MKL-DNN por defecto,
    recuperando el perfil de rendimiento validado en la UAT del PR #20. Si una
    máquina concreta vuelve a producir ``NotImplementedError`` en esa ruta, el
    reader reinicializa el engine una sola vez con MKL-DNN deshabilitado y
    reintenta la misma página. La detección mantiene además un límite del lado
    mayor para evitar inferencia innecesaria a resolución completa.
""",
    "reader docstring",
)
text = replace_once(
    text,
    "    DEFAULT_ENABLE_MKLDNN = False\n",
    "    DEFAULT_ENABLE_MKLDNN = True\n",
    "restore Paddle 3.2 accelerated default",
)

old_read = """            words, page_text = cls._read_page(
                engine=engine,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
            )

            all_words.extend(words)
"""
new_read = """            engine, words, page_text, recovered_backend = (
                cls._read_page_with_backend_recovery(
                    engine=engine,
                    config=config,
                    image=image,
                    logical_page=logical_page,
                    page_width=page_width,
                    doctop_offset=doctop_offset,
                    text_det_limit_side_len=text_det_limit_side_len,
                )
            )
            if recovered_backend:
                config = {**config, \"enable_mkldnn\": False}

            all_words.extend(words)
"""
text = replace_once(text, old_read, new_read, "reader page recovery call")

text = replace_once(
    text,
    '                "mkldnn_enabled": config["enable_mkldnn"],\n',
    '                "mkldnn_enabled": config["enable_mkldnn"],\n                "mkldnn_backend_recovered": not config["enable_mkldnn"] and cls.DEFAULT_ENABLE_MKLDNN,\n',
    "reader backend metadata",
)

marker = """    @classmethod
    def _read_page(
"""
helper = """    @staticmethod
    def _is_mkldnn_compatibility_error(exc: Exception) -> bool:
        if isinstance(exc, NotImplementedError):
            return True
        detail = f\"{type(exc).__name__}: {exc}\".lower()
        return \"notimplemented\" in detail or \"not implemented\" in detail

    @classmethod
    def _read_page_with_backend_recovery(
        cls,
        *,
        engine: Any,
        config: dict[str, Any],
        image: Image.Image,
        logical_page: int,
        page_width: float,
        doctop_offset: float,
        text_det_limit_side_len: int,
    ) -> tuple[Any, list[dict[str, Any]], str, bool]:
        \"\"\"Usa oneDNN rápido y degrada una sola vez ante incompatibilidad real.\"\"\"
        try:
            words, page_text = cls._read_page(
                engine=engine,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
            )
            return engine, words, page_text, False
        except Exception as exc:
            if not config.get(\"enable_mkldnn\") or not cls._is_mkldnn_compatibility_error(exc):
                raise

            safe_config = {**config, \"enable_mkldnn\": False}
            safe_engine = cls._get_engine(**safe_config)
            words, page_text = cls._read_page(
                engine=safe_engine,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
            )
            return safe_engine, words, page_text, True

"""
text = replace_once(text, marker, helper + marker, "adaptive backend helper")
reader.write_text(text, encoding="utf-8")


cancelable = Path("src/readers/cancelable_ocr_reader.py")
text = cancelable.read_text(encoding="utf-8")
old_cancel = """        words, page_text = PaddleOCRPDFReader._read_page(
            engine=engine,
            image=image,
            logical_page=logical_page,
            page_width=page_width,
            doctop_offset=doctop_offset,
            text_det_limit_side_len=text_det_limit_side_len,
        )
        _raise_if_cancelled(cancel_event)
"""
new_cancel = """        engine, words, page_text, recovered_backend = (
            PaddleOCRPDFReader._read_page_with_backend_recovery(
                engine=engine,
                config=config,
                image=image,
                logical_page=logical_page,
                page_width=page_width,
                doctop_offset=doctop_offset,
                text_det_limit_side_len=text_det_limit_side_len,
            )
        )
        if recovered_backend:
            config = {**config, \"enable_mkldnn\": False}
        _raise_if_cancelled(cancel_event)
"""
text = replace_once(text, old_cancel, new_cancel, "cancelable page recovery call")
text = replace_once(
    text,
    '            "mkldnn_enabled": config["enable_mkldnn"],\n',
    '            "mkldnn_enabled": config["enable_mkldnn"],\n            "mkldnn_backend_recovered": not config["enable_mkldnn"] and PaddleOCRPDFReader.DEFAULT_ENABLE_MKLDNN,\n',
    "cancelable backend metadata",
)
cancelable.write_text(text, encoding="utf-8")


tests = Path("tests/readers/test_paddleocr_pdf_reader.py")
text = tests.read_text(encoding="utf-8")
text = replace_once(
    text,
    "def test_cpu_engine_disables_mkldnn_by_default(monkeypatch):\n",
    "def test_cpu_engine_uses_mkldnn_by_default(monkeypatch):\n",
    "test name",
)
text = replace_once(
    text,
    '            enable_mkldnn=False,\n            cpu_threads=10,\n        )\n\n        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "0"\n        assert captured_kwargs["enable_mkldnn"] is False\n',
    '            enable_mkldnn=True,\n            cpu_threads=10,\n        )\n\n        assert os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "1"\n        assert captured_kwargs["enable_mkldnn"] is True\n',
    "default backend assertions",
)
text = replace_once(
    text,
    '    assert config["enable_mkldnn"] is False\n',
    '    assert config["enable_mkldnn"] is True\n',
    "config default accelerated",
)

anchor = """def test_cpu_threads_are_bounded_and_configurable(monkeypatch):
"""
new_tests = """def test_backend_recovery_retries_notimplemented_without_mkldnn(monkeypatch):
    class FastEngine:
        def predict(self, image, **kwargs):
            raise NotImplementedError(\"oneDNN kernel unavailable\")

    class SafeEngine:
        def predict(self, image, **kwargs):
            return []

    safe_engine = SafeEngine()
    requested_configs = []

    def fake_get_engine(**config):
        requested_configs.append(config)
        assert config[\"enable_mkldnn\"] is False
        return safe_engine

    monkeypatch.setattr(PaddleOCRPDFReader, \"_get_engine\", fake_get_engine)

    config = {
        \"language\": \"es\",
        \"device\": \"cpu\",
        \"detection_model_name\": \"PP-OCRv5_mobile_det\",
        \"recognition_model_name\": \"latin_PP-OCRv5_mobile_rec\",
        \"detection_model_dir\": \"C:/modelos/det\",
        \"recognition_model_dir\": \"C:/modelos/rec\",
        \"enable_mkldnn\": True,
        \"cpu_threads\": 10,
    }

    engine, words, page_text, recovered = PaddleOCRPDFReader._read_page_with_backend_recovery(
        engine=FastEngine(),
        config=config,
        image=Image.new(\"RGB\", (100, 200)),
        logical_page=1,
        page_width=612.0,
        doctop_offset=0.0,
        text_det_limit_side_len=1200,
    )

    assert engine is safe_engine
    assert words == []
    assert page_text == \"\"
    assert recovered is True
    assert len(requested_configs) == 1


def test_backend_recovery_does_not_hide_unrelated_errors():
    class BrokenEngine:
        def predict(self, image, **kwargs):
            raise ValueError(\"bad input\")

    config = {
        \"enable_mkldnn\": True,
    }

    with pytest.raises(ValueError, match=\"bad input\"):
        PaddleOCRPDFReader._read_page_with_backend_recovery(
            engine=BrokenEngine(),
            config=config,
            image=Image.new(\"RGB\", (100, 200)),
            logical_page=1,
            page_width=612.0,
            doctop_offset=0.0,
            text_det_limit_side_len=1200,
        )


"""
text = replace_once(text, anchor, new_tests + anchor, "backend recovery tests")
tests.write_text(text, encoding="utf-8")


# The real-inference bootstrap previously forced the slow backend, so CI could
# not detect the regression that the user saw. Let it exercise the application's
# actual default now; adaptive recovery still protects incompatible machines.
bootstrap = Path("scripts/preparar_modelos_paddleocr.py")
text = bootstrap.read_text(encoding="utf-8")
text = replace_once(
    text,
    '        "PADDLEOCR_ENABLE_MKLDNN": "0",\n',
    '        "PADDLEOCR_ENABLE_MKLDNN": None,\n',
    "bootstrap default backend",
)
old_inference = """        engine = PaddleOCRPDFReader._get_engine(**config)

        from PIL import Image, ImageDraw

        image = Image.new("RGB", (720, 220), "white")
        draw = ImageDraw.Draw(image)
        draw.text((24, 80), "PRUEBA OCR 1234567890", fill="black")
        PaddleOCRPDFReader._read_page(
            engine=engine,
            image=image,
            logical_page=1,
            page_width=612.0,
            doctop_offset=0.0,
            text_det_limit_side_len=1200,
        )
"""
new_inference = """        engine = PaddleOCRPDFReader._get_engine(**config)

        from PIL import Image, ImageDraw

        image = Image.new("RGB", (720, 220), "white")
        draw = ImageDraw.Draw(image)
        draw.text((24, 80), "PRUEBA OCR 1234567890", fill="black")
        _, _, _, recovered_backend = PaddleOCRPDFReader._read_page_with_backend_recovery(
            engine=engine,
            config=config,
            image=image,
            logical_page=1,
            page_width=612.0,
            doctop_offset=0.0,
            text_det_limit_side_len=1200,
        )
        if recovered_backend:
            print("Aviso: oneDNN no fue compatible; la inferencia se recuperó sin MKL-DNN.")
"""
text = replace_once(text, old_inference, new_inference, "bootstrap adaptive inference")
bootstrap.write_text(text, encoding="utf-8")
