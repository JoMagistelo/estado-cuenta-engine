from pathlib import Path


path = Path("app/main_flet.py")
text = path.read_text(encoding="utf-8")

helper_marker = "    def create_ocr_review_controls(\n"
helper_anchor = "\n\n    # ========================================================\n    # RENDER RESULTADO\n    # ========================================================\n"

helper_block = r'''

    # ========================================================
    # COMPARACIÓN Y SELECCIÓN OCR
    # ========================================================

    def ocr_engine_label(
        engine: str | None,
    ) -> str:

        labels = {
            "tesseract": "Tesseract",
            "paddleocr": "PaddleOCR",
        }

        normalized = (
            str(engine or "")
            .strip()
            .lower()
        )

        return labels.get(
            normalized,
            normalized or "OCR",
        )


    def create_ocr_review_controls(
        result,
    ) -> ft.Container | None:

        review = getattr(
            result,
            "ocr_review",
            None,
        )

        if review is None:
            return None

        engines = list(
            result.available_ocr_engines()
        )

        if len(engines) < 2:
            return None

        selected_engine = (
            result.selected_ocr_engine
            or engines[0]
        )

        recommended_engine = (
            result.recommended_ocr_engine
            or "tesseract"
        )

        def on_ocr_engine_change(e):

            engine = str(
                e.control.value or ""
            ).strip().lower()

            if engine not in engines:
                return

            result.select_ocr_engine(
                engine
            )

            update_processing_summary()

            render_result(
                result
            )

        selector = ft.Dropdown(
            label=(
                "Resultado OCR mostrado y "
                "usado para exportación"
            ),
            value=selected_engine,
            width=330,
            options=[
                ft.DropdownOption(
                    key=engine,
                    text=ocr_engine_label(
                        engine
                    ),
                )
                for engine in engines
            ],
        )

        selector.on_select = (
            on_ocr_engine_change
        )

        candidate_cards = []

        for engine in engines:

            candidate = (
                review.get_candidate(
                    engine
                )
            )

            badges = []

            if engine == recommended_engine:

                badges.append(
                    ft.Text(
                        "Recomendado",
                        size=10,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                        color=GOB_GREEN,
                    )
                )

            if engine == selected_engine:

                badges.append(
                    ft.Text(
                        "Mostrando / se exportará",
                        size=10,
                        weight=(
                            ft.FontWeight.BOLD
                        ),
                        color=GOB_GOLD,
                    )
                )

            candidate_cards.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                ocr_engine_label(
                                    engine
                                ),
                                size=15,
                                weight=(
                                    ft.FontWeight.BOLD
                                ),
                            ),
                            *badges,
                            ft.Text(
                                "Movimientos: "
                                f"{candidate.movement_count}",
                                size=12,
                            ),
                            ft.Text(
                                "Validaciones: "
                                f"{candidate.validation_total}",
                                size=12,
                            ),
                            ft.Text(
                                "Taches: "
                                f"{candidate.validation_failed}",
                                size=12,
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=12,
                    border=ft.Border.all(
                        1,
                        ft.Colors.OUTLINE_VARIANT,
                    ),
                    border_radius=8,
                    expand=True,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "🔎 Comparación OCR",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Cuando ambos motores están disponibles puedes "
                        "alternar el resultado que deseas revisar. La "
                        "selección actual es también la que se utilizará "
                        "al generar el Excel.",
                        size=12,
                        color=(
                            ft.Colors
                            .ON_SURFACE_VARIANT
                        ),
                    ),
                    selector,
                    ft.Row(
                        controls=candidate_cards,
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            padding=15,
            bgcolor=GOB_GREEN_LIGHT,
            border=ft.Border.all(
                1,
                ft.Colors.OUTLINE_VARIANT,
            ),
            border_radius=10,
        )
'''

if helper_marker not in text:
    if helper_anchor not in text:
        raise RuntimeError("No se encontró el ancla para insertar comparación OCR en Flet.")
    text = text.replace(
        helper_anchor,
        helper_block + helper_anchor,
        1,
    )

call_anchor = '''        if result is None:\n\n            page.update()\n            reset_page_scroll()\n\n            return\n\n        estado = (\n            result.estado_cuenta\n        )\n'''

call_replacement = '''        if result is None:\n\n            page.update()\n            reset_page_scroll()\n\n            return\n\n        ocr_review_controls = (\n            create_ocr_review_controls(\n                result\n            )\n        )\n\n        if ocr_review_controls is not None:\n\n            auditoria_view.controls.append(\n                ocr_review_controls\n            )\n\n        estado = (\n            result.estado_cuenta\n        )\n'''

if "        ocr_review_controls = (\n" not in text:
    if call_anchor not in text:
        raise RuntimeError("No se encontró el ancla para activar comparación OCR en render_result().")
    text = text.replace(
        call_anchor,
        call_replacement,
        1,
    )

path.write_text(
    text,
    encoding="utf-8",
)
