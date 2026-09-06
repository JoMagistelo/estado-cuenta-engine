from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_flet() -> None:
    path = Path("app/main_flet.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "SELECTOR_ENGINE_WIDTH = 105\nSELECTOR_STATUS_WIDTH = 54\nSELECTOR_VALIDATION_WIDTH = 58",
        "SELECTOR_ENGINE_WIDTH = 150\nSELECTOR_STATUS_WIDTH = 54\nSELECTOR_TIME_WIDTH = 64\nSELECTOR_VALIDATION_WIDTH = 58",
        "selector widths",
    )

    text = replace_once(
        text,
        "def format_elapsed(seconds: float) -> str:\n    seconds = max(int(seconds or 0), 0)\n    return f'{seconds // 60:02d}:{seconds % 60:02d}'\n\n\ndef numeric(value: Any) -> float:",
        "def format_elapsed(seconds: float) -> str:\n    seconds = max(int(seconds or 0), 0)\n    return f'{seconds // 60:02d}:{seconds % 60:02d}'\n\n\ndef format_seconds(seconds: Any) -> str:\n    if seconds is None:\n        return '—'\n    try:\n        value = max(float(seconds), 0.0)\n    except (TypeError, ValueError):\n        return '—'\n    return f'{value:.1f} s'\n\n\ndef numeric(value: Any) -> float:",
        "format seconds",
    )

    old_process_label = """    def process_label(item: dict[str, Any]) -> str:\n        method = item.get('processing_method')\n        result = item.get('result')\n        if method == 'Digital':\n            return 'Digital'\n        if method == 'OCR':\n            if result is None:\n                return engine_label(settings['ocr_primary_engine'])\n            label = engine_label(getattr(result, 'ocr_engine', None))\n            review = getattr(result, 'ocr_review', None)\n            if review is not None and review.requires_user_selection:\n                if not getattr(result, 'ocr_selection_confirmed', False):\n                    return f'{label} · elegir'\n                return f'{label} · elegido'\n            if getattr(result, 'fallback_attempted', False):\n                return f'{label} · revisado'\n            return label\n        return 'Detectando'\n"""
    new_process_label = """    def process_label(item: dict[str, Any]) -> str:\n        method = item.get('processing_method')\n        result = item.get('result')\n        if method == 'Digital':\n            return 'Digital'\n        if method == 'OCR':\n            if result is None:\n                requested = item.get('requested_ocr_engine') or settings['ocr_primary_engine']\n                return engine_label(requested)\n\n            requested = getattr(result, 'ocr_requested_primary_engine', None)\n            primary = getattr(result, 'ocr_primary_engine', None)\n            secondary = getattr(result, 'ocr_secondary_engine', None)\n            if requested and primary and requested != primary:\n                return f'{engine_label(requested)} ↯ {engine_label(primary)}'\n\n            if getattr(result, 'fallback_attempted', False) and secondary:\n                available = set(result.available_ocr_engines())\n                marker = '✓' if secondary in available else '⚠'\n                return f'{engine_label(primary)} → {engine_label(secondary)} {marker}'\n\n            return engine_label(getattr(result, 'ocr_engine', None) or primary)\n        return 'Detectando'\n"""
    text = replace_once(text, old_process_label, new_process_label, "process label")

    text = replace_once(
        text,
        """    def selector_row_content(index: int, item: dict[str, Any]) -> ft.Row:\n        result = item.get('result')\n        abonos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))\n        cargos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))\n        return ft.Row(\n""",
        """    def selector_row_content(index: int, item: dict[str, Any]) -> ft.Row:\n        result = item.get('result')\n        abonos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[0]))\n        cargos = validation_symbol(validation(result, PRIMARY_VALIDATIONS[1]))\n        elapsed = format_seconds(item.get('elapsed_seconds'))\n        return ft.Row(\n""",
        "selector elapsed variable",
    )

    text = replace_once(
        text,
        """                ft.Container(\n                    status_control(item),\n                    width=SELECTOR_STATUS_WIDTH,\n                    alignment=ft.Alignment.CENTER,\n                ),\n                ft.Container(\n                    ft.Text(abonos, size=10),\n""",
        """                ft.Container(\n                    status_control(item),\n                    width=SELECTOR_STATUS_WIDTH,\n                    alignment=ft.Alignment.CENTER,\n                ),\n                ft.Container(\n                    ft.Text(elapsed, size=8, color=ft.Colors.ON_SURFACE_VARIANT),\n                    width=SELECTOR_TIME_WIDTH,\n                    alignment=ft.Alignment.CENTER,\n                ),\n                ft.Container(\n                    ft.Text(abonos, size=10),\n""",
        "selector elapsed cell",
    )

    text = replace_once(
        text,
        """                    heading('Motor', SELECTOR_ENGINE_WIDTH),\n                    heading('Estado', SELECTOR_STATUS_WIDTH),\n                    heading('Abonos', SELECTOR_VALIDATION_WIDTH),\n""",
        """                    heading('Motor', SELECTOR_ENGINE_WIDTH),\n                    heading('Estado', SELECTOR_STATUS_WIDTH),\n                    heading('Tiempo', SELECTOR_TIME_WIDTH),\n                    heading('Abonos', SELECTOR_VALIDATION_WIDTH),\n""",
        "selector time heading",
    )

    marker = """    def beneficiary_analytics(movements) -> list[tuple[str, float, float]]:\n"""
    execution_card = """    def ocr_execution_card(result) -> ft.Container:\n        requested = getattr(result, 'ocr_requested_primary_engine', None)\n        primary = getattr(result, 'ocr_primary_engine', None)\n        secondary = getattr(result, 'ocr_secondary_engine', None)\n        review = getattr(result, 'ocr_review', None)\n        available = set(result.available_ocr_engines()) if review is not None else set()\n\n        lines: list[ft.Control] = [\n            ft.Text(\n                f'Motor solicitado en Configuración: {engine_label(requested or primary)}',\n                size=8,\n                weight=ft.FontWeight.BOLD,\n            )\n        ]\n\n        if requested and primary and requested != primary:\n            lines.append(\n                ft.Text(\n                    f'{engine_label(requested)} no pudo iniciar; el PDF fue recuperado con {engine_label(primary)}.',\n                    size=8,\n                    color=DANGER,\n                )\n            )\n        elif primary:\n            lines.append(\n                ft.Text(\n                    f'Motor primario ejecutado: {engine_label(primary)}',\n                    size=8,\n                    color=GOB_GREEN,\n                )\n            )\n\n        if getattr(result, 'fallback_attempted', False) and secondary:\n            if secondary in available:\n                lines.append(\n                    ft.Text(\n                        f'Fallback ejecutado: {engine_label(secondary)} · candidato disponible para revisión.',\n                        size=8,\n                        color=GOB_GREEN,\n                        weight=ft.FontWeight.BOLD,\n                    )\n                )\n            else:\n                error_type = getattr(review, 'paddle_error_type', None) if review is not None else None\n                suffix = f' · error {error_type}' if error_type else ''\n                lines.append(\n                    ft.Text(\n                        f'Fallback intentado: {engine_label(secondary)} · no produjo candidato{suffix}.',\n                        size=8,\n                        color=DANGER,\n                        weight=ft.FontWeight.BOLD,\n                    )\n                )\n        else:\n            lines.append(\n                ft.Text(\n                    'Fallback: no requerido por las validaciones del motor principal.',\n                    size=8,\n                    color=ft.Colors.ON_SURFACE_VARIANT,\n                )\n            )\n\n        if len(available) > 1:\n            lines.append(\n                ft.Text(\n                    'Hay dos resultados reales en memoria. Puedes alternarlos y elegir cuál se exportará.',\n                    size=8,\n                    color=GOB_GREEN_DARK,\n                )\n            )\n\n        return ft.Container(\n            ft.Column(lines, spacing=3, tight=True),\n            padding=7,\n            bgcolor=GOB_GREEN_LIGHT,\n            border_radius=6,\n            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),\n        )\n\n\n"""
    text = replace_once(text, marker, execution_card + marker, "OCR execution card")

    old_ocr_block = """        if method == 'OCR':\n            review = getattr(result, 'ocr_review', None)\n            engines = list(result.available_ocr_engines()) if review is not None else []\n            if len(engines) > 1:\n                confirmed = result.confirmed_ocr_engine\n                info_text = (\n                    f'Comparación OCR disponible · vista actual: {engine_label(result.selected_ocr_engine)} · '\n                    f'sugerencia automática: {engine_label(result.recommended_ocr_engine)}'\n                )\n                if confirmed:\n                    info_text += f' · elegido para Excel: {engine_label(confirmed)}'\n                else:\n                    info_text += ' · pendiente de elección para Excel'\n            else:\n                info_text = f'Motor utilizado: {engine_label(getattr(result, \"ocr_engine\", None))}'\n            audit_view.controls.append(\n                ft.Container(\n                    ft.Text(f'⚙️ {info_text}', size=8, color=GOB_GREEN),\n                    padding=6,\n                    bgcolor=GOB_GREEN_LIGHT,\n                    border_radius=6,\n                )\n            )\n            candidate_selector = ocr_candidate_selector(result)\n            if candidate_selector is not None:\n                audit_view.controls.append(candidate_selector)\n\n"""
    new_ocr_block = """        if method == 'OCR':\n            audit_view.controls.append(ocr_execution_card(result))\n            candidate_selector = ocr_candidate_selector(result)\n            if candidate_selector is not None:\n                audit_view.controls.append(candidate_selector)\n\n"""
    text = replace_once(text, old_ocr_block, new_ocr_block, "render OCR block")

    start = text.index("        account_entries = [")
    end = text.index("        summary_entries = [", start)
    old_layout = text[start:end]
    new_layout = """        audit_view.controls.extend(\n            [\n                ft.Row(\n                    [\n                        metric('Saldo anterior', format_money(getattr(rf, 'saldo_anterior', None))),\n                        metric('Depósitos / Abonos', format_money(getattr(rf, 'depositos_abonos', None))),\n                        metric('Retiros / Cargos', format_money(getattr(rf, 'retiros_cargos', None))),\n                        metric('Saldo final', format_money(getattr(rf, 'saldo_final', None))),\n                    ],\n                    spacing=6,\n                ),\n                ft.Row(\n                    [\n                        validation_card(result, PRIMARY_VALIDATIONS[0], 'Validación abonos'),\n                        validation_card(result, PRIMARY_VALIDATIONS[1], 'Validación cargos'),\n                    ],\n                    spacing=6,\n                ),\n            ]\n        )\n\n        all_validations = list(getattr(result, 'validaciones', []) or [])\n        secondary_validations = [\n            item for item in all_validations if item.nombre not in PRIMARY_VALIDATIONS\n        ]\n        correct_count = sum(item.correcto for item in all_validations)\n        audit_view.controls.append(\n            ft.Text(\n                f'Integridad financiera: {correct_count}/{len(all_validations)} validaciones correctas',\n                size=8,\n                weight=ft.FontWeight.BOLD,\n                color=ft.Colors.ON_SURFACE_VARIANT,\n            )\n        )\n\n        secondary_controls = (\n            [secondary_validation_row(item) for item in secondary_validations]\n            if secondary_validations\n            else [ft.Text('No existen validaciones adicionales para este resultado.', size=8)]\n        )\n        audit_view.controls.append(\n            ft.ExpansionTile(\n                title=ft.Text(\n                    f'🔎 Otras validaciones financieras ({len(secondary_validations)})',\n                    size=9,\n                    weight=ft.FontWeight.BOLD,\n                ),\n                controls=[\n                    ft.Container(\n                        ft.Column(secondary_controls, spacing=5),\n                        padding=6,\n                    )\n                ],\n            )\n        )\n\n        account_entries = [\n            ('Producto principal', safe_value(getattr(dc, 'producto_principal', None))),\n            ('Periodo inicio', safe_value(getattr(dc, 'periodo_inicio', None))),\n            ('Periodo fin', safe_value(getattr(dc, 'periodo_fin', None))),\n            ('Fecha de corte', safe_value(getattr(dc, 'fecha_corte', None))),\n            ('Número de cuenta', safe_value(getattr(dc, 'numero_cuenta', None))),\n            ('Número de cliente', safe_value(getattr(dc, 'numero_cliente', None))),\n            ('CLABE', safe_value(getattr(dc, 'clabe', None))),\n            ('Nombre del cliente', safe_value(getattr(dc, 'nombre_cliente', None))),\n            ('RFC', safe_value(getattr(dc, 'rfc', None))),\n        ]\n        audit_view.controls.append(\n            ft.ExpansionTile(\n                title=ft.Text(\n                    '📌 Datos de la cuenta · todos los campos',\n                    size=9,\n                    weight=ft.FontWeight.BOLD,\n                ),\n                controls=[ft.Container(ft.Column(metrics_rows(account_entries, 3), spacing=6), padding=6)],\n            )\n        )\n\n"""
    text = text[:start] + new_layout + text[end:]
    if old_layout == new_layout:
        raise RuntimeError("layout block was not changed")

    text = replace_once(
        text,
        "'📈 Resumen financiero ampliado · todos los campos'",
        "'📈 Detalle financiero · todos los campos'",
        "expanded financial title",
    )

    text = replace_once(
        text,
        """                    ft.Text(\n                        'El segundo motor se ejecuta cuando las validaciones principales requieren revisión.',\n                        size=8,\n                        color=ft.Colors.ON_SURFACE_VARIANT,\n                    ),\n""",
        """                    ft.Text(\n                        'El segundo motor se ejecuta si el resultado principal tiene cualquier validación con tache, faltan validaciones clave o no se detectan movimientos.',\n                        size=8,\n                        color=ft.Colors.ON_SURFACE_VARIANT,\n                    ),\n""",
        "settings fallback help",
    )

    text = replace_once(
        text,
        """    def handle_event(event):\n        index = getattr(event, 'index', None)\n""",
        """    def finalize_item_duration(item: dict[str, Any]) -> None:\n        started_at = item.get('processing_started_at')\n        if isinstance(started_at, (int, float)):\n            item['elapsed_seconds'] = max(time.perf_counter() - started_at, 0.0)\n\n    def handle_event(event):\n        index = getattr(event, 'index', None)\n""",
        "duration helper",
    )

    text = replace_once(
        text,
        """        if event.kind == 'started':\n            item.update(\n                status='processing',\n                processing_method=event.processing_method,\n                error=None,\n            )\n""",
        """        if event.kind == 'started':\n            item.update(\n                status='processing',\n                processing_method=event.processing_method,\n                processing_started_at=time.perf_counter(),\n                elapsed_seconds=None,\n                error=None,\n            )\n""",
        "duration start",
    )

    text = replace_once(
        text,
        """        if event.kind == 'cancelled':\n            item.update(\n""",
        """        if event.kind == 'cancelled':\n            finalize_item_duration(item)\n            item.update(\n""",
        "duration cancel",
    )
    text = replace_once(
        text,
        """        if event.kind == 'completed':\n            item.update(\n""",
        """        if event.kind == 'completed':\n            finalize_item_duration(item)\n            item.update(\n""",
        "duration completed",
    )
    text = replace_once(
        text,
        """        if event.kind == 'error':\n            item.update(\n""",
        """        if event.kind == 'error':\n            finalize_item_duration(item)\n            item.update(\n""",
        "duration error",
    )

    text = replace_once(
        text,
        """                    'status': 'classifying',\n                    'result': None,\n                    'error': None,\n""",
        """                    'status': 'classifying',\n                    'result': None,\n                    'error': None,\n                    'requested_ocr_engine': settings['ocr_primary_engine'],\n                    'processing_started_at': None,\n                    'elapsed_seconds': None,\n""",
        "initial item timing",
    )

    path.write_text(text, encoding="utf-8")


def patch_policy() -> None:
    path = Path("src/engine/ocr_fallback_policy.py")
    text = path.read_text(encoding="utf-8")

    old = """def fallback_trigger_reasons(\n    validaciones: list[ResultadoValidacion],\n    *,\n    has_movements: bool,\n) -> tuple[str, ...]:\n    \"\"\"Razones de fallback limitadas a las dos validaciones financieras clave.\n\n    No se activa un segundo OCR por cantidad de movimientos, campos opcionales,\n    score heurístico ni por simple disponibilidad. Si no hay movimientos, las\n    validaciones principales no podrán existir y eso se representa como\n    ``validacion_principal_ausente``.\n    \"\"\"\n    status = _primary_validation_map(validaciones)\n    reasons: list[str] = []\n\n    missing = [name for name in PRIMARY_VALIDATION_NAMES if name not in status]\n    failed = [name for name, ok in status.items() if not ok]\n\n    # Se conservan estas etiquetas diagnósticas por compatibilidad, pero la\n    # decisión de fallback se toma únicamente por validaciones principales.\n    if not has_movements:\n        reasons.append(\"sin_movimientos\")\n    if not validaciones:\n        reasons.append(\"sin_validaciones\")\n    if missing:\n        reasons.append(\"validacion_principal_ausente\")\n    if failed:\n        reasons.append(\"validacion_principal_fallida\")\n\n    return tuple(reasons)\n\n\ndef should_attempt_secondary_fallback(\n    validaciones: list[ResultadoValidacion],\n    *,\n    has_movements: bool = True,\n) -> bool:\n    reasons = fallback_trigger_reasons(\n        validaciones,\n        has_movements=has_movements,\n    )\n    return any(\n        reason in {\n            \"validacion_principal_ausente\",\n            \"validacion_principal_fallida\",\n        }\n        for reason in reasons\n    )\n"""
    new = """def fallback_trigger_reasons(\n    validaciones: list[ResultadoValidacion],\n    *,\n    has_movements: bool,\n) -> tuple[str, ...]:\n    \"\"\"Describe señales objetivas que justifican ejecutar el segundo OCR.\n\n    Se recupera el comportamiento de revisión dual: cualquier validación con\n    tache puede indicar un problema de lectura OCR y debe permitir comparar el\n    mismo PDF con el motor secundario. También se intenta cuando faltan las\n    conciliaciones clave o no se obtuvieron movimientos/validaciones.\n    \"\"\"\n    status = _primary_validation_map(validaciones)\n    profile = validation_profile(validaciones)\n    reasons: list[str] = []\n\n    missing = [name for name in PRIMARY_VALIDATION_NAMES if name not in status]\n    primary_failed = [name for name, ok in status.items() if not ok]\n\n    if not has_movements:\n        reasons.append(\"sin_movimientos\")\n    if not validaciones:\n        reasons.append(\"sin_validaciones\")\n    if profile.failed > 0:\n        reasons.append(\"validacion_fallida\")\n    if missing:\n        reasons.append(\"validacion_principal_ausente\")\n    if primary_failed:\n        reasons.append(\"validacion_principal_fallida\")\n\n    return tuple(dict.fromkeys(reasons))\n\n\ndef should_attempt_secondary_fallback(\n    validaciones: list[ResultadoValidacion],\n    *,\n    has_movements: bool = True,\n) -> bool:\n    return bool(\n        fallback_trigger_reasons(\n            validaciones,\n            has_movements=has_movements,\n        )\n    )\n"""
    text = replace_once(text, old, new, "fallback policy")
    text = text.replace(
        "Tesseract como primario, PaddleOCR es el secundario y sólo se ejecuta si\n    falla una validación financiera principal.",
        "Tesseract como primario, PaddleOCR es el secundario y se ejecuta cuando\n    el resultado presenta una señal objetiva de revisión financiera.",
    )
    text = text.replace(
        '"""API histórica: respeta la bandera vieja y el nuevo criterio estricto."""',
        '"""API histórica: respeta la bandera vieja y el criterio de revisión dual."""',
    )
    path.write_text(text, encoding="utf-8")


def patch_processing_result() -> None:
    path = Path("src/models/processing_result.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    ocr_engine: str | None = None\n    ocr_primary_engine: str | None = None",
        "    ocr_engine: str | None = None\n    ocr_requested_primary_engine: str | None = None\n    ocr_primary_engine: str | None = None",
        "requested primary field",
    )
    path.write_text(text, encoding="utf-8")


def patch_pipeline() -> None:
    path = Path("src/engine/pipeline.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """    document = prepared.document\n    primary_engine = normalize_ocr_engine(ocr_primary_engine)\n    if prepared.processing_method == 'OCR':\n""",
        """    document = prepared.document\n    requested_primary_engine = normalize_ocr_engine(ocr_primary_engine)\n    primary_engine = requested_primary_engine\n    if prepared.processing_method == 'OCR':\n""",
        "pipeline requested primary snapshot",
    )
    text = replace_once(
        text,
        """        ocr_review=ocr_review,\n        ocr_engine=selected_engine,\n        ocr_primary_engine=primary_used,\n""",
        """        ocr_review=ocr_review,\n        ocr_engine=selected_engine,\n        ocr_requested_primary_engine=(\n            requested_primary_engine if prepared.processing_method == 'OCR' else None\n        ),\n        ocr_primary_engine=primary_used,\n""",
        "pipeline result requested primary",
    )
    text = text.replace(
        "validaciones principales de abonos/cargos lo requieren.",
        "validaciones del resultado indican que conviene comparar el segundo OCR.",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_flet()
    patch_policy()
    patch_processing_result()
    patch_pipeline()


if __name__ == "__main__":
    main()
