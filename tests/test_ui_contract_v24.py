from pathlib import Path


def test_flet_uses_clickable_result_rows_without_redundant_dropdown():
    source = Path("app/main_flet.py").read_text(encoding="utf-8")

    assert "Ir a resultado" not in source
    assert "result_dropdown" not in source
    assert "on_click=(lambda e, i=index: select_item(i))" in source


def test_beneficiary_visual_includes_subtle_movement_counts():
    source = Path("app/main_flet.py").read_text(encoding="utf-8")

    assert "show_counts=True" in source
    assert "f'C {cargo_count} · A {abono_count}'" in source
