from __future__ import annotations

import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return updated


def patch_flet() -> None:
    path = Path("app/main_flet.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(text, "APP_VERSION = '2.3'", "APP_VERSION = '2.4'", "Flet version")
    text = replace_once(
        text,
        """    selector_filter = ft.TextField(\n        hint_text='Filtrar PDF, banco o estado',\n        width=250,\n        height=38,\n        text_size=11,\n        prefix_icon=ft.Icons.SEARCH,\n    )\n    result_dropdown = ft.Dropdown(\n        label='Ir a resultado',\n        width=285,\n        height=38,\n        text_size=10,\n        options=[],\n        disabled=True,\n    )\n""",
        """    selector_filter = ft.TextField(\n        hint_text='Filtrar PDF, banco o estado',\n        width=420,\n        height=38,\n        text_size=11,\n        prefix_icon=ft.Icons.SEARCH,\n    )\n""",
        "remove redundant result dropdown",
    )

    text = sub_once(
        text,
        r"\n    def refresh_result_dropdown\(\) -> None:\n.*?(?=\n    def rebuild_selector\()",
        "\n",
        "remove dropdown refresh",
    )
    text = text.replace("        refresh_result_dropdown()\n", "")
    text = text.replace("                result_dropdown,\n", "")
    text = text.replace("                    result_dropdown,\n", "")
    text = text.replace("        result_dropdown.value = None\n", "")

    text = sub_once(
        text,
        r"\n    def on_result_dropdown_change\(e\) -> None:\n.*?\n    result_dropdown\.on_change = on_result_dropdown_change\n",
        "\n",
        "remove dropdown handler",
    )

    old_beneficiary = """    def beneficiary_analytics(movements) -> list[tuple[str, float, float]]:\n        grouped: dict[str, list[float]] = {}\n        for movement in movements:\n            name = getattr(movement, 'beneficiario', None) or 'Sin beneficiario'\n            values = grouped.setdefault(str(name), [0.0, 0.0])\n            values[0] += numeric(getattr(movement, 'cargo', 0.0))\n            values[1] += numeric(getattr(movement, 'abono', 0.0))\n        rows = [(name, values[0], values[1]) for name, values in grouped.items()]\n        rows.sort(key=lambda item: item[1] + item[2], reverse=True)\n        return rows[:8]\n"""
    new_beneficiary = """    def beneficiary_analytics(\n        movements,\n    ) -> list[tuple[str, float, float, int, int]]:\n        grouped: dict[str, list[float]] = {}\n        for movement in movements:\n            name = getattr(movement, 'beneficiario', None) or 'Sin beneficiario'\n            values = grouped.setdefault(str(name), [0.0, 0.0, 0.0, 0.0])\n            cargo = numeric(getattr(movement, 'cargo', 0.0))\n            abono = numeric(getattr(movement, 'abono', 0.0))\n            values[0] += cargo\n            values[1] += abono\n            if cargo > 0:\n                values[2] += 1\n            if abono > 0:\n                values[3] += 1\n        rows = [\n            (name, values[0], values[1], int(values[2]), int(values[3]))\n            for name, values in grouped.items()\n        ]\n        rows.sort(key=lambda item: item[1] + item[2], reverse=True)\n        return rows[:8]\n"""
    text = replace_once(text, old_beneficiary, new_beneficiary, "beneficiary counts")

    text = replace_once(
        text,
        "    def analytics_bar_card(title: str, rows: list[tuple[str, float, float]]) -> ft.Container:\n",
        """    def analytics_bar_card(\n        title: str,\n        rows: list[tuple],\n        *,\n        show_counts: bool = False,\n    ) -> ft.Container:\n""",
        "analytics card signature",
    )
    text = replace_once(
        text,
        "        maximum = max(max(cargo, abono) for _label, cargo, abono in rows) or 1.0\n",
        "        maximum = max(max(float(row[1]), float(row[2])) for row in rows) or 1.0\n",
        "analytics maximum",
    )
    text = replace_once(
        text,
        """        for label, cargo, abono in rows:\n            cargo_width = max(2, int(180 * cargo / maximum))\n            abono_width = max(2, int(180 * abono / maximum))\n            controls.append(\n                ft.Column(\n                    [\n                        ft.Text(label, size=8, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),\n""",
        """        for row in rows:\n            label, cargo, abono = row[:3]\n            cargo_count = int(row[3]) if len(row) > 3 else 0\n            abono_count = int(row[4]) if len(row) > 4 else 0\n            cargo_width = max(2, int(180 * cargo / maximum))\n            abono_width = max(2, int(180 * abono / maximum))\n            label_controls: list[ft.Control] = []\n            if show_counts:\n                label_controls.append(\n                    ft.Container(\n                        ft.Text(\n                            f'C {cargo_count} · A {abono_count}',\n                            size=7,\n                            color=ft.Colors.ON_SURFACE_VARIANT,\n                        ),\n                        width=58,\n                    )\n                )\n            label_controls.append(\n                ft.Text(\n                    str(label),\n                    size=8,\n                    max_lines=1,\n                    overflow=ft.TextOverflow.ELLIPSIS,\n                    expand=True,\n                )\n            )\n            controls.append(\n                ft.Column(\n                    [\n                        ft.Row(label_controls, spacing=4),\n""",
        "analytics beneficiary count prefix",
    )
    text = replace_once(
        text,
        """        beneficiary = analytics_bar_card(\n            'Cargos y abonos por beneficiario · Top 8',\n            beneficiary_analytics(movements),\n        )\n""",
        """        beneficiary = analytics_bar_card(\n            'Cargos y abonos por beneficiario · Top 8',\n            beneficiary_analytics(movements),\n            show_counts=True,\n        )\n""",
        "enable beneficiary counts",
    )

    old_error = """            else:\n                error_type = getattr(review, 'paddle_error_type', None) if review is not None else None\n                suffix = f' · error {error_type}' if error_type else ''\n                lines.append(\n                    ft.Text(\n                        f'Fallback intentado: {engine_label(secondary)} · no produjo candidato{suffix}.',\n                        size=8,\n                        color=DANGER,\n                        weight=ft.FontWeight.BOLD,\n                    )\n                )\n"""
    new_error = """            else:\n                error_type = getattr(review, 'paddle_error_type', None) if review is not None else None\n                suffix = f' · error {error_type}' if error_type else ''\n                error_message = ''\n                if review is not None and primary in available:\n                    try:\n                        primary_candidate = review.get_candidate(primary)\n                        error_message = str(\n                            (primary_candidate.document.metadata or {}).get(\n                                'ocr_fallback_error_message',\n                                '',\n                            )\n                            or ''\n                        ).strip()\n                    except Exception:\n                        error_message = ''\n                detail = f' · {error_message}' if error_message else ''\n                lines.append(\n                    ft.Text(\n                        f'Fallback intentado: {engine_label(secondary)} · no produjo candidato{suffix}{detail}.',\n                        size=8,\n                        color=DANGER,\n                        weight=ft.FontWeight.BOLD,\n                    )\n                )\n"""
    text = replace_once(text, old_error, new_error, "surface fallback error detail")

    if "result_dropdown" in text or "Ir a resultado" in text:
        raise RuntimeError("result dropdown references remain after cleanup")

    path.write_text(text, encoding="utf-8")


def patch_reader() -> None:
    path = Path("src/readers/paddleocr_pdf_reader.py")
    text = path.read_text(encoding="utf-8")

    old_config_start = """    def _load_config(cls) -> dict[str, Any]:\n        detection_dir = cls._required_model_dir(\n            \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\"\n        )\n        recognition_dir = cls._required_model_dir(\n            \"PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR\"\n        )\n\n        language = os.getenv(\n"""
    new_config_start = """    def _load_config(cls) -> dict[str, Any]:\n        detection_model_name = os.getenv(\n            \"PADDLEOCR_TEXT_DETECTION_MODEL_NAME\",\n            cls.DEFAULT_DETECTION_MODEL_NAME,\n        ).strip() or cls.DEFAULT_DETECTION_MODEL_NAME\n        recognition_model_name = os.getenv(\n            \"PADDLEOCR_TEXT_RECOGNITION_MODEL_NAME\",\n            cls.DEFAULT_RECOGNITION_MODEL_NAME,\n        ).strip() or cls.DEFAULT_RECOGNITION_MODEL_NAME\n        detection_dir = cls._resolve_model_dir(\n            \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\",\n            detection_model_name,\n        )\n        recognition_dir = cls._resolve_model_dir(\n            \"PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR\",\n            recognition_model_name,\n        )\n\n        language = os.getenv(\n"""
    text = replace_once(text, old_config_start, new_config_start, "reader model resolution start")

    text = replace_once(
        text,
        """            \"detection_model_name\": os.getenv(\n                \"PADDLEOCR_TEXT_DETECTION_MODEL_NAME\",\n                cls.DEFAULT_DETECTION_MODEL_NAME,\n            ).strip()\n            or cls.DEFAULT_DETECTION_MODEL_NAME,\n            \"recognition_model_name\": os.getenv(\n                \"PADDLEOCR_TEXT_RECOGNITION_MODEL_NAME\",\n                cls.DEFAULT_RECOGNITION_MODEL_NAME,\n            ).strip()\n            or cls.DEFAULT_RECOGNITION_MODEL_NAME,\n""",
        """            \"detection_model_name\": detection_model_name,\n            \"recognition_model_name\": recognition_model_name,\n""",
        "reader model names",
    )

    text = sub_once(
        text,
        r"    @staticmethod\n    def _required_model_dir\(variable_name: str\) -> Path:\n.*?\n        return path\n",
        """    @classmethod\n    def _resolve_model_dir(\n        cls,\n        variable_name: str,\n        model_name: str,\n    ) -> Path:\n        configured = os.getenv(variable_name, \"\").strip()\n        if configured:\n            path = Path(configured).expanduser().resolve()\n            if not path.is_dir():\n                raise PaddleOCRConfigurationError(\n                    f\"La ruta configurada en {variable_name} no existe o no es \"\n                    \"un directorio válido.\"\n                )\n            return path\n\n        candidates = cls._model_dir_candidates(model_name)\n        for candidate in candidates:\n            if candidate.is_dir():\n                return candidate.resolve()\n\n        searched = \", \".join(cls._display_path(item) for item in candidates)\n        raise PaddleOCRConfigurationError(\n            f\"No se encontró el modelo local {model_name}. Configura \"\n            f\"{variable_name} o PADDLEOCR_MODEL_ROOT. Rutas locales revisadas: \"\n            f\"{searched or 'ninguna'}. PaddleOCR no descargará modelos \"\n            \"automáticamente.\"\n        )\n\n    @classmethod\n    def _model_dir_candidates(cls, model_name: str) -> list[Path]:\n        candidates: list[Path] = []\n\n        model_root = os.getenv(\"PADDLEOCR_MODEL_ROOT\", \"\").strip()\n        if model_root:\n            candidates.append(Path(model_root).expanduser() / model_name)\n\n        program_data = os.getenv(\"PROGRAMDATA\", \"\").strip()\n        if program_data:\n            candidates.append(\n                Path(program_data)\n                / \"EstadoCuentaEngine\"\n                / \"PaddleOCR\"\n                / model_name\n            )\n\n        local_app_data = os.getenv(\"LOCALAPPDATA\", \"\").strip()\n        if local_app_data:\n            candidates.append(\n                Path(local_app_data)\n                / \"EstadoCuentaEngine\"\n                / \"PaddleOCR\"\n                / model_name\n            )\n\n        candidates.append(\n            Path.home() / \".paddlex\" / \"official_models\" / model_name\n        )\n\n        unique: list[Path] = []\n        seen: set[str] = set()\n        for candidate in candidates:\n            key = str(candidate.expanduser()).casefold()\n            if key in seen:\n                continue\n            seen.add(key)\n            unique.append(candidate.expanduser())\n        return unique\n\n    @staticmethod\n    def _display_path(path: Path) -> str:\n        try:\n            home = Path.home().resolve()\n            resolved = path.expanduser().resolve()\n            try:\n                relative = resolved.relative_to(home)\n            except ValueError:\n                return str(resolved)\n            return str(Path(\"~\") / relative)\n        except Exception:\n            return str(path)\n""",
        "reader local model resolver",
    )

    text = replace_once(
        text,
        """    El reader está diseñado como fallback controlado de Tesseract. No descarga\n    modelos en runtime y no utiliza la API alojada de PaddleOCR. Los modelos de\n    detección y reconocimiento deben estar previamente instalados en rutas\n    locales autorizadas.\n""",
        """    El reader está diseñado como fallback controlado de Tesseract. No descarga\n    modelos en runtime y no utiliza la API alojada de PaddleOCR. Los modelos de\n    detección y reconocimiento deben estar previamente instalados. Las rutas\n    explícitas tienen prioridad y, si no existen variables de entorno, se\n    resuelven ubicaciones locales controladas (ProgramData/LocalAppData y la\n    caché local oficial de PaddleX) sin habilitar descargas.\n""",
        "reader docstring model resolution",
    )

    path.write_text(text, encoding="utf-8")


def patch_reader_tests() -> None:
    path = Path("tests/readers/test_paddleocr_pdf_reader.py")
    text = path.read_text(encoding="utf-8")

    old_required = """def test_model_directories_are_required(monkeypatch):\n    monkeypatch.delenv(\n        \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\",\n        raising=False,\n    )\n    monkeypatch.delenv(\n        \"PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR\",\n        raising=False,\n    )\n\n    with pytest.raises(PaddleOCRConfigurationError):\n        PaddleOCRPDFReader._load_config()\n\n\n"""
    new_required = """def test_model_directories_raise_when_no_local_model_is_resolvable(monkeypatch):\n    monkeypatch.delenv(\n        \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\",\n        raising=False,\n    )\n    monkeypatch.delenv(\n        \"PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR\",\n        raising=False,\n    )\n    monkeypatch.delenv(\"PADDLEOCR_MODEL_ROOT\", raising=False)\n    monkeypatch.setattr(\n        PaddleOCRPDFReader,\n        \"_model_dir_candidates\",\n        classmethod(lambda cls, model_name: []),\n    )\n\n    with pytest.raises(PaddleOCRConfigurationError, match=\"No se encontró el modelo local\"):\n        PaddleOCRPDFReader._load_config()\n\n\ndef test_cached_paddlex_models_are_resolved_without_session_env(tmp_path, monkeypatch):\n    detection = tmp_path / \"PP-OCRv5_mobile_det\"\n    recognition = tmp_path / \"latin_PP-OCRv5_mobile_rec\"\n    detection.mkdir()\n    recognition.mkdir()\n\n    monkeypatch.delenv(\"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\", raising=False)\n    monkeypatch.delenv(\"PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR\", raising=False)\n    monkeypatch.delenv(\"PADDLEOCR_MODEL_ROOT\", raising=False)\n    monkeypatch.setattr(\n        PaddleOCRPDFReader,\n        \"_model_dir_candidates\",\n        classmethod(lambda cls, model_name: [tmp_path / model_name]),\n    )\n\n    config = PaddleOCRPDFReader._load_config()\n\n    assert config[\"detection_model_dir\"] == str(detection.resolve())\n    assert config[\"recognition_model_dir\"] == str(recognition.resolve())\n\n\ndef test_explicit_invalid_model_path_does_not_silently_fallback(tmp_path, monkeypatch):\n    cached = tmp_path / \"PP-OCRv5_mobile_det\"\n    cached.mkdir()\n    monkeypatch.setenv(\n        \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\",\n        str(tmp_path / \"missing\"),\n    )\n    monkeypatch.setattr(\n        PaddleOCRPDFReader,\n        \"_model_dir_candidates\",\n        classmethod(lambda cls, model_name: [cached]),\n    )\n\n    with pytest.raises(PaddleOCRConfigurationError, match=\"ruta configurada\"):\n        PaddleOCRPDFReader._resolve_model_dir(\n            \"PADDLEOCR_TEXT_DETECTION_MODEL_DIR\",\n            \"PP-OCRv5_mobile_det\",\n        )\n\n\n"""
    text = replace_once(text, old_required, new_required, "reader model tests")
    path.write_text(text, encoding="utf-8")


def patch_diagnostic() -> None:
    path = Path("scripts/diagnostico_paddleocr.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from engine.statement_processor import process_single_statement_with_ocr_review\n",
        """from engine.statement_processor import (\n    _build_candidate,\n    _process_once,\n    process_single_statement_with_ocr_review,\n)\n""",
        "diagnostic imports",
    )

    marker = "\ndef main() -> int:\n"
    helper = """\ndef _run_forced_comparison(pdf_path: Path, visible_name: str) -> int:\n    \"\"\"Fuerza ambos motores para demostrar que PaddleOCR realmente infiere.\"\"\"\n    try:\n        tesseract_document = ReaderManager.read_ocr(pdf_path, start_page=0)\n        bank_key = identify_bank_key(\n            raw_text=tesseract_document.raw_text,\n            file_name=visible_name,\n        )\n        if not bank_key:\n            print(\"ERROR: no se pudo identificar el banco.\", file=sys.stderr)\n            return 3\n\n        paddle_document = ReaderManager.read_paddle_ocr(pdf_path, start_page=0)\n        tesseract_estado, tesseract_document = _process_once(\n            tesseract_document,\n            bank_key,\n        )\n        paddle_estado, paddle_document = _process_once(\n            paddle_document,\n            bank_key,\n        )\n        tesseract_candidate = _build_candidate(\n            \"tesseract\",\n            tesseract_estado,\n            tesseract_document,\n        )\n        paddle_candidate = _build_candidate(\n            \"paddleocr\",\n            paddle_estado,\n            paddle_document,\n        )\n    except Exception as exc:\n        print(\n            f\"ERROR PaddleOCR/Tesseract: {type(exc).__name__}: {exc}\",\n            file=sys.stderr,\n        )\n        return 6\n\n    print(\"=== Comparación OCR forzada ===\")\n    print(f\"Banco detectado: {bank_key}\")\n    _print_candidate(tesseract_candidate)\n    _print_candidate(paddle_candidate)\n    print(\n        \"PaddleOCR inference: OK · reader=paddleocr · \"\n        f\"tokens espaciales={len(paddle_document.spatial_words)}\"\n    )\n    print(\"No se imprimieron datos personales ni valores financieros.\")\n    return 0\n\n\n"""
    text = replace_once(text, marker, helper + "def main() -> int:\n", "forced comparison helper")

    text = replace_once(
        text,
        """    parser.add_argument(\n        \"--motor\",\n        choices=(\"recomendado\", \"tesseract\", \"paddleocr\"),\n        default=\"recomendado\",\n        help=(\n            \"Motor cuya salida se considera seleccionada para el diagnóstico. \"\n            \"Por defecto se utiliza la recomendación automática.\"\n        ),\n    )\n""",
        """    parser.add_argument(\n        \"--motor\",\n        choices=(\"recomendado\", \"tesseract\", \"paddleocr\"),\n        default=\"recomendado\",\n        help=(\n            \"Motor cuya salida se considera seleccionada para el diagnóstico. \"\n            \"Por defecto se utiliza la recomendación automática.\"\n        ),\n    )\n    parser.add_argument(\n        \"--comparar-motores\",\n        action=\"store_true\",\n        help=(\n            \"Fuerza Tesseract y PaddleOCR sobre el mismo PDF, aunque la política \"\n            \"de fallback no lo requiera, y reporta sólo conteos técnicos.\"\n        ),\n    )\n""",
        "diagnostic compare flag",
    )

    text = replace_once(
        text,
        """    visible_name = args.nombre or pdf_path.name\n\n    try:\n""",
        """    visible_name = args.nombre or pdf_path.name\n\n    if args.comparar_motores:\n        return _run_forced_comparison(pdf_path, visible_name)\n\n    try:\n""",
        "diagnostic compare dispatch",
    )
    path.write_text(text, encoding="utf-8")


def patch_versions() -> None:
    path = Path("pyproject.toml")
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'version = "2.3.0"', 'version = "2.4.0"', "package version")
    path.write_text(text, encoding="utf-8")

    path = Path("app/main_streamlit.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "APP_VERSION = '2.3'", "APP_VERSION = '2.4'", "Streamlit version")
    path.write_text(text, encoding="utf-8")

    path = Path("EstadoCuentaEngine.spec")
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "APP_VERSION = (2, 3, 0, 0)", "APP_VERSION = (2, 4, 0, 0)", "EXE version")
    path.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    path = Path("docs/14_paddleocr_fallback.md")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "- exige rutas locales explícitas para los modelos;",
        "- resuelve únicamente modelos locales: variables explícitas, raíz administrada, ProgramData/LocalAppData o caché oficial local de PaddleX;",
    )
    text = text.replace(
        "- oneDNN/MKL-DNN habilitado por defecto para conservar rendimiento práctico en CPU;",
        "- oneDNN/MKL-DNN deshabilitado por defecto para priorizar estabilidad en Windows/CPU; puede habilitarse de forma explícita después de UAT;",
    )
    text = text.replace(
        "`PADDLEOCR_ENABLE_MKLDNN=1` es la configuración operativa normal para CPU. Puede establecerse en `0` únicamente para diagnóstico de compatibilidad; esa configuración puede reducir de forma importante el rendimiento.",
        "`PADDLEOCR_ENABLE_MKLDNN=0` es la configuración estable predeterminada. `PADDLEOCR_ENABLE_MKLDNN=1` queda como opt-in de rendimiento y debe probarse con el runtime aprobado antes de adoptarse.",
    )
    insert_after = """$env:PADDLEOCR_CPU_THREADS = \"10\"\n```\n"""
    addition = """$env:PADDLEOCR_CPU_THREADS = \"10\"\n```\n\nDesde la versión 2.4 las dos variables de directorio siguen teniendo prioridad, pero dejan de depender de la sesión actual de PowerShell cuando los modelos ya están instalados en una ubicación local reconocida. El reader busca, en este orden:\n\n1. `PADDLEOCR_TEXT_DETECTION_MODEL_DIR` / `PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR`;\n2. `PADDLEOCR_MODEL_ROOT\\<modelo>`;\n3. `%PROGRAMDATA%\\EstadoCuentaEngine\\PaddleOCR\\<modelo>`;\n4. `%LOCALAPPDATA%\\EstadoCuentaEngine\\PaddleOCR\\<modelo>`;\n5. `~\\.paddlex\\official_models\\<modelo>`.\n\nEn todos los casos se pasa un directorio local explícito al runtime; esta resolución **no habilita descargas**. Si una variable individual está configurada con una ruta inválida, se rechaza en lugar de ocultar el error usando otra ubicación.\n"""
    text = replace_once(text, insert_after, addition, "docs model resolution")
    path.write_text(text, encoding="utf-8")


def create_new_tests() -> None:
    integration = Path("tests/readers/test_paddleocr_live_integration.py")
    integration.write_text(
        """from __future__ import annotations\n\nimport os\nfrom pathlib import Path\n\nimport pytest\n\nfrom readers.reader_manager import ReaderManager\n\n\n@pytest.mark.integration\ndef test_live_tesseract_and_paddleocr_both_produce_spatial_output():\n    configured = os.getenv(\"ESTADO_CUENTA_TEST_PDF\", \"\").strip()\n    if not configured:\n        pytest.skip(\"Define ESTADO_CUENTA_TEST_PDF para ejecutar UAT OCR local.\")\n\n    pdf_path = Path(configured).expanduser().resolve()\n    if not pdf_path.is_file():\n        pytest.skip(\"ESTADO_CUENTA_TEST_PDF no apunta a un PDF disponible.\")\n\n    tesseract = ReaderManager.read_ocr(pdf_path, start_page=0)\n    paddle = ReaderManager.read_paddle_ocr(pdf_path, start_page=0)\n\n    assert tesseract.metadata[\"reader\"] == \"tesseract\"\n    assert paddle.metadata[\"reader\"] == \"paddleocr\"\n    assert tesseract.spatial_words\n    assert paddle.spatial_words\n""",
        encoding="utf-8",
    )

    ui_contract = Path("tests/test_ui_contract_v24.py")
    ui_contract.write_text(
        """from pathlib import Path\n\n\ndef test_flet_uses_clickable_result_rows_without_redundant_dropdown():\n    source = Path(\"app/main_flet.py\").read_text(encoding=\"utf-8\")\n\n    assert \"Ir a resultado\" not in source\n    assert \"result_dropdown\" not in source\n    assert \"on_click=(lambda e, i=index: select_item(i))\" in source\n\n\ndef test_beneficiary_visual_includes_subtle_movement_counts():\n    source = Path(\"app/main_flet.py\").read_text(encoding=\"utf-8\")\n\n    assert \"show_counts=True\" in source\n    assert \"f'C {cargo_count} · A {abono_count}'\" in source\n""",
        encoding="utf-8",
    )


def main() -> None:
    patch_flet()
    patch_reader()
    patch_reader_tests()
    patch_diagnostic()
    patch_versions()
    patch_docs()
    create_new_tests()


if __name__ == "__main__":
    main()
