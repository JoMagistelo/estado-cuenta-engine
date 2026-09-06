from __future__ import annotations

import re

import apply_ocr_primary_ui_patch as patch


_original_replace_count = patch.replace_count


def _flexible_replace_count(
    text: str,
    old: str,
    new: str,
    expected_count: int,
    label: str,
) -> str:
    if label != "pipeline executor calls":
        return _original_replace_count(
            text,
            old,
            new,
            expected_count,
            label,
        )

    pattern = re.compile(
        r"(?m)(?P<first>^[ \t]+_process_prepared_statement,\n)"
        r"(?P<indent>^[ \t]+)prepared,\n"
    )

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            match.group("first")
            + f"{indent}prepared,\n"
            + f"{indent}ocr_primary_engine,\n"
        )

    replaced, count = pattern.subn(repl, text)
    if count != expected_count:
        raise RuntimeError(
            f"Parche '{label}' esperaba {expected_count} coincidencias "
            f"y encontró {count}."
        )
    return replaced


patch.replace_count = _flexible_replace_count
patch.main()
