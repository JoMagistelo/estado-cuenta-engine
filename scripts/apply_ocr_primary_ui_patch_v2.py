from __future__ import annotations

import re

import apply_ocr_primary_ui_patch as patch

# Runner temporal y determinista para aplicar el parche sobre la rama vigente.
_original_replace_count = patch.replace_count


def _flexible_replace_count(
    text: str,
    old: str,
    new: str,
    expected_count: int,
    label: str,
) -> str:
    if label == "pipeline executor calls":
        pattern = re.compile(
            r"(?m)(?P<first>^[ \t]+_process_prepared_statement,\n)"
            r"(?P<indent>^[ \t]+)prepared,\n"
        )

        def repl_executor(match: re.Match[str]) -> str:
            indent = match.group("indent")
            return (
                match.group("first")
                + f"{indent}prepared,\n"
                + f"{indent}ocr_primary_engine,\n"
            )

        replaced, count = pattern.subn(repl_executor, text)
        if count != expected_count:
            raise RuntimeError(
                f"Parche '{label}' esperaba {expected_count} coincidencias "
                f"y encontró {count}."
            )
        return replaced

    if label == "flet re-enable selector":
        pattern = re.compile(
            r"(?m)(?P<indent>^[ \t]+)upload_button\.disabled = \(\n"
            r"(?P=indent)    False\n"
            r"(?P=indent)\)\n"
            r"(?!\n(?P=indent)ocr_primary_selector\.disabled)"
        )

        def repl_selector(match: re.Match[str]) -> str:
            indent = match.group("indent")
            original = match.group(0)
            return (
                original
                + "\n"
                + f"{indent}ocr_primary_selector.disabled = (\n"
                + f"{indent}    False\n"
                + f"{indent})\n"
            )

        replaced, count = pattern.subn(repl_selector, text)
        if count < 1:
            raise RuntimeError(
                "No se encontró ningún punto seguro para reactivar "
                "el selector OCR."
            )
        return replaced

    return _original_replace_count(
        text,
        old,
        new,
        expected_count,
        label,
    )


patch.replace_count = _flexible_replace_count
patch.main()
