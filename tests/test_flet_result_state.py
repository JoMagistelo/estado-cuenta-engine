from types import SimpleNamespace

from utils.result_state import (
    movement_matches_kind,
    remove_result_reference,
    replace_result_reference,
)


def test_result_references_follow_reprocess_and_delete_by_identity() -> None:
    original = object()
    equal_but_distinct = object()
    updated = object()
    results = [original, equal_but_distinct]

    replace_result_reference(results, original, updated)

    assert results == [updated, equal_but_distinct]
    assert remove_result_reference(results, updated) is True
    assert results == [equal_but_distinct]
    assert remove_result_reference(results, original) is False


def test_movement_kind_filter_accepts_only_positive_selected_amount() -> None:
    cargo = SimpleNamespace(cargo=15.0, abono=0.0)
    abono = SimpleNamespace(cargo=0.0, abono=20.0)
    neutral = SimpleNamespace(cargo=0.0, abono=0.0)

    assert movement_matches_kind(cargo, None)
    assert movement_matches_kind(cargo, 'cargo')
    assert not movement_matches_kind(cargo, 'abono')
    assert movement_matches_kind(abono, 'abono')
    assert not movement_matches_kind(abono, 'cargo')
    assert not movement_matches_kind(neutral, 'cargo')
    assert not movement_matches_kind(neutral, 'abono')
