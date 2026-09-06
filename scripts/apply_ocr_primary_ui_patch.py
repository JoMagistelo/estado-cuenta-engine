from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Parche '{label}' esperaba 1 coincidencia y encontró {count}."
        )
    return text.replace(old, new, 1)


def replace_count(
    text: str,
    old: str,
    new: str,
    expected_count: int,
    label: str,
) -> str:
    count = text.count(old)
    if count != expected_count:
        raise RuntimeError(
            f"Parche '{label}' esperaba {expected_count} coincidencias "
            f"y encontró {count}."
        )
    return text.replace(old, new)


def patch_pipeline() -> None:
    path = ROOT / "src" / "engine" / "pipeline.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from engine.statement_processor import process_single_statement_with_ocr_review\n",
        "from engine.ocr_execution import normalize_ocr_engine\n"
        "from engine.statement_processor import process_single_statement_with_ocr_review\n",
        "pipeline import",
    )

    text = replace_once(
        text,
        "def _process_prepared_statement(\n"
        "    prepared: PreparedStatement,\n"
        ") -> ProcessingResult:\n",
        "def _process_prepared_statement(\n"
        "    prepared: PreparedStatement,\n"
        "    ocr_primary_engine: str = \"tesseract\",\n"
        ") -> ProcessingResult:\n",
        "pipeline prepared signature",
    )

    text = replace_once(
        text,
        "    document = prepared.document\n\n"
        "    # ========================================================\n"
        "    # OCR\n"
        "    # ========================================================\n\n"
        "    if prepared.processing_method == \"OCR\":\n\n"
        "        document = ReaderManager.read_ocr(\n"
        "            prepared.pdf_path,\n"
        "            start_page=0,\n"
        "        )\n",
        "    document = prepared.document\n"
        "    ocr_primary_engine = normalize_ocr_engine(ocr_primary_engine)\n"
        "    allow_secondary_review = True\n\n"
        "    # ========================================================\n"
        "    # OCR\n"
        "    # ========================================================\n\n"
        "    if prepared.processing_method == \"OCR\":\n\n"
        "        if ocr_primary_engine == \"paddleocr\":\n"
        "            try:\n"
        "                document = ReaderManager.read_paddle_ocr(\n"
        "                    prepared.pdf_path,\n"
        "                    start_page=0,\n"
        "                )\n"
        "            except Exception as primary_exc:\n"
        "                # Una preferencia de usuario no debe provocar la\n"
        "                # pérdida del documento si PaddleOCR falla.\n"
        "                document = ReaderManager.read_ocr(\n"
        "                    prepared.pdf_path,\n"
        "                    start_page=0,\n"
        "                )\n"
        "                allow_secondary_review = False\n"
        "                document.metadata.update(\n"
        "                    {\n"
        "                        \"ocr_primary_requested\": \"paddleocr\",\n"
        "                        \"ocr_primary_error_type\": type(primary_exc).__name__,\n"
        "                        \"ocr_primary_fallback_engine\": \"tesseract\",\n"
        "                    }\n"
        "                )\n"
        "        else:\n"
        "            document = ReaderManager.read_ocr(\n"
        "                prepared.pdf_path,\n"
        "                start_page=0,\n"
        "            )\n\n"
        "        document.metadata[\"ocr_primary_requested\"] = ocr_primary_engine\n",
        "pipeline OCR reader selection",
    )

    text = replace_once(
        text,
        "        process_single_statement_with_ocr_review(\n"
        "            document=document,\n"
        "            bank_key=bank_key,\n"
        "        )\n",
        "        process_single_statement_with_ocr_review(\n"
        "            document=document,\n"
        "            bank_key=bank_key,\n"
        "            allow_secondary=allow_secondary_review,\n"
        "        )\n",
        "pipeline review args",
    )

    text = replace_once(
        text,
        "def process_bank_statements(\n"
        "    pdf_paths: list[str],\n"
        "    file_names: list[str] | None = None,\n"
        ") -> list[ProcessingResult]:\n",
        "def process_bank_statements(\n"
        "    pdf_paths: list[str],\n"
        "    file_names: list[str] | None = None,\n"
        "    ocr_primary_engine: str = \"tesseract\",\n"
        ") -> list[ProcessingResult]:\n",
        "pipeline sequential signature",
    )

    text = replace_once(
        text,
        "        result = _process_prepared_statement(\n"
        "            prepared\n"
        "        )\n",
        "        result = _process_prepared_statement(\n"
        "            prepared,\n"
        "            ocr_primary_engine=ocr_primary_engine,\n"
        "        )\n",
        "pipeline sequential call",
    )

    text = replace_once(
        text,
        "def process_bank_statements_incremental(\n"
        "    pdf_paths: list[str],\n"
        "    file_names: list[str] | None = None,\n"
        "    classification_workers: int = 2,\n"
        "    digital_workers: int = 4,\n"
        "    ocr_workers: int = 1,\n"
        "):\n",
        "def process_bank_statements_incremental(\n"
        "    pdf_paths: list[str],\n"
        "    file_names: list[str] | None = None,\n"
        "    classification_workers: int = 2,\n"
        "    digital_workers: int = 4,\n"
        "    ocr_workers: int = 1,\n"
        "    ocr_primary_engine: str = \"tesseract\",\n"
        "):\n",
        "pipeline incremental signature",
    )

    text = replace_once(
        text,
        "    total = len(pdf_paths)\n\n"
        "    if total == 0:\n",
        "    total = len(pdf_paths)\n"
        "    ocr_primary_engine = normalize_ocr_engine(ocr_primary_engine)\n\n"
        "    if total == 0:\n",
        "pipeline normalize batch preference",
    )

    text = replace_count(
        text,
        "                            _process_prepared_statement,\n"
        "                            prepared,\n",
        "                            _process_prepared_statement,\n"
        "                            prepared,\n"
        "                            ocr_primary_engine,\n",
        2,
        "pipeline executor calls",
    )

    path.write_text(text, encoding="utf-8")


def patch_flet() -> None:
    path = ROOT / "app" / "main_flet.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from exporters.excel import export_batch_excel\n",
        "from exporters.excel import export_batch_excel\n"
        "from exporters.export_snapshot import snapshot_results_for_export\n",
        "flet export snapshot import",
    )

    text = replace_once(
        text,
        "    loading_ring = ft.ProgressRing(\n"
        "        width=20,\n"
        "        height=20,\n"
        "        visible=False,\n"
        "    )\n\n"
        "    dropdown_files = ft.Dropdown(\n",
        "    loading_ring = ft.ProgressRing(\n"
        "        width=20,\n"
        "        height=20,\n"
        "        visible=False,\n"
        "    )\n\n"
        "    ocr_primary_selector = ft.Dropdown(\n"
        "        label=\"Motor OCR principal\",\n"
        "        value=\"tesseract\",\n"
        "        width=260,\n"
        "        options=[\n"
        "            ft.DropdownOption(\n"
        "                key=\"tesseract\",\n"
        "                text=\"Tesseract primero\",\n"
        "            ),\n"
        "            ft.DropdownOption(\n"
        "                key=\"paddleocr\",\n"
        "                text=\"PaddleOCR primero\",\n"
        "            ),\n"
        "        ],\n"
        "    )\n\n"
        "    dropdown_files = ft.Dropdown(\n",
        "flet OCR primary selector",
    )

    text = replace_once(
        text,
        "    def processing_worker(\n"
        "        paths: list[str],\n"
        "        names: list[str],\n"
        "        batch_id: int,\n"
        "    ):\n",
        "    def processing_worker(\n"
        "        paths: list[str],\n"
        "        names: list[str],\n"
        "        batch_id: int,\n"
        "        ocr_primary_engine: str,\n"
        "    ):\n",
        "flet worker signature",
    )

    text = replace_once(
        text,
        "                process_bank_statements_incremental(\n"
        "                    paths,\n"
        "                    names,\n"
        "                )\n",
        "                process_bank_statements_incremental(\n"
        "                    paths,\n"
        "                    names,\n"
        "                    ocr_primary_engine=ocr_primary_engine,\n"
        "                )\n",
        "flet pipeline preference",
    )

    text = replace_count(
        text,
        "                        upload_button.disabled = (\n"
        "                            False\n"
        "                        )\n\n"
        "                        page_changed = True\n",
        "                        upload_button.disabled = (\n"
        "                            False\n"
        "                        )\n\n"
        "                        ocr_primary_selector.disabled = (\n"
        "                            False\n"
        "                        )\n\n"
        "                        page_changed = True\n",
        2,
        "flet re-enable selector",
    )

    text = replace_once(
        text,
        "        upload_button.disabled = (\n"
        "            True\n"
        "        )\n\n"
        "        export_button.disabled = (\n",
        "        upload_button.disabled = (\n"
        "            True\n"
        "        )\n\n"
        "        ocr_primary_selector.disabled = (\n"
        "            True\n"
        "        )\n\n"
        "        export_button.disabled = (\n",
        "flet disable selector",
    )

    text = replace_once(
        text,
        "    def start_processing_worker(\n"
        "        paths: list[str],\n"
        "        names: list[str],\n"
        "    ):\n",
        "    def start_processing_worker(\n"
        "        paths: list[str],\n"
        "        names: list[str],\n"
        "        ocr_primary_engine: str,\n"
        "    ):\n",
        "flet start worker signature",
    )

    text = replace_once(
        text,
        "            processing_worker,\n"
        "            paths,\n"
        "            names,\n"
        "            batch_id,\n"
        "        )\n",
        "            processing_worker,\n"
        "            paths,\n"
        "            names,\n"
        "            batch_id,\n"
        "            ocr_primary_engine,\n"
        "        )\n",
        "flet run_thread args",
    )

    text = replace_once(
        text,
        "            # =================================================\n"
        "            # PREPARAR BATCH\n"
        "            # =================================================\n\n"
        "            initialize_processing_batch(\n"
        "                paths,\n"
        "                names,\n"
        "            )\n",
        "            ocr_primary_engine = str(\n"
        "                ocr_primary_selector.value or \"tesseract\"\n"
        "            ).strip().lower()\n\n"
        "            # =================================================\n"
        "            # PREPARAR BATCH\n"
        "            # =================================================\n\n"
        "            initialize_processing_batch(\n"
        "                paths,\n"
        "                names,\n"
        "            )\n",
        "flet capture preference",
    )

    text = replace_once(
        text,
        "            start_processing_worker(\n"
        "                paths,\n"
        "                names,\n"
        "            )\n",
        "            start_processing_worker(\n"
        "                paths,\n"
        "                names,\n"
        "                ocr_primary_engine,\n"
        "            )\n",
        "flet start worker call",
    )

    text = replace_once(
        text,
        "            results_snapshot = list(\n"
        "                results\n"
        "            )\n",
        "            results_snapshot = snapshot_results_for_export(\n"
        "                results\n"
        "            )\n",
        "flet safe export snapshot",
    )

    text = replace_once(
        text,
        "                controls=[\n\n"
        "                    upload_button,\n\n"
        "                    loading_ring,\n\n"
        "                    status_text,\n"
        "                ],\n",
        "                controls=[\n\n"
        "                    ocr_primary_selector,\n\n"
        "                    upload_button,\n\n"
        "                    loading_ring,\n\n"
        "                    status_text,\n"
        "                ],\n",
        "flet top controls",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_pipeline()
    patch_flet()
    print("Parche OCR principal aplicado correctamente.")


if __name__ == "__main__":
    main()
