"""W05 runtime comparison plans cannot mutate page membership or authorize Calculate."""

from __future__ import annotations

import pytest

from pixelscope.core.comparison_presets import (
    ComparisonPair,
    ComparisonPreset,
    plan_comparison,
)


def test_four_presets_and_workspace_preserve_runtime_identity() -> None:
    ids = ("source-a", "source-b", "source-c", "source-d")
    pair = ComparisonPair(ids[0], ids[2])
    assert plan_comparison(ids, ComparisonPreset.WORKSPACE, pair).source_ids == ids
    assert plan_comparison(ids, ComparisonPreset.ORIGINAL_2, pair).source_ids == (
        ids[0],
        ids[2],
    )
    assert plan_comparison(ids, ComparisonPreset.ORIGINAL_4, pair).source_ids == ids
    result = plan_comparison(ids, ComparisonPreset.AB_DIFF, pair, cached_valid=True)
    assert result.source_ids == pair.source_ids
    assert result.show_difference
    focused = plan_comparison(ids, ComparisonPreset.DIFF_FOCUS, pair, cached_valid=True)
    assert focused.source_ids == ()
    assert focused.show_difference


@pytest.mark.parametrize("count", [2, 4, 6])
def test_page_sizes_remain_canonical(count: int) -> None:
    ids = tuple(f"source-{i}" for i in range(count))
    pair = ComparisonPair(ids[0], ids[1])
    originals = plan_comparison(ids, ComparisonPreset.ORIGINAL_2, pair)
    assert originals.available and originals.source_ids == ids[:2]
    four = plan_comparison(ids, ComparisonPreset.ORIGINAL_4, pair)
    assert four.available == (count >= 4)
    assert four.source_ids == (ids[:4] if count >= 4 else ())


def test_page_two_uses_actual_ids_not_slot_numbers() -> None:
    ids = tuple(f"source-{i}" for i in range(6, 12))
    pair = ComparisonPair(ids[0], ids[3])
    plan = plan_comparison(ids, ComparisonPreset.ORIGINAL_4, pair)
    assert plan.source_ids == ids[:4]
    assert plan.pair == pair


@pytest.mark.parametrize("state", ["not-calculated", "pending", "stale"])
def test_missing_difference_is_never_presented(state: str) -> None:
    pair = ComparisonPair("a", "b")
    plan = plan_comparison(
        ("a", "b"),
        ComparisonPreset.AB_DIFF,
        pair,
        pending=state == "pending",
        stale=state == "stale",
    )
    assert plan.available
    assert not plan.show_difference
    assert plan.source_ids == ("a", "b")
    assert plan.difference_state == state
    focus = plan_comparison(
        ("a", "b"),
        ComparisonPreset.DIFF_FOCUS,
        pair,
        pending=state == "pending",
        stale=state == "stale",
    )
    assert not focus.show_difference and focus.source_ids == ()


@pytest.mark.parametrize(
    "pair",
    [
        ComparisonPair("a", "a"),
        ComparisonPair("a", "missing"),
        ComparisonPair("missing", "b"),
        None,
    ],
)
def test_invalid_pair_fails_closed(pair: ComparisonPair | None) -> None:
    for preset in (
        ComparisonPreset.ORIGINAL_2,
        ComparisonPreset.ORIGINAL_4,
        ComparisonPreset.AB_DIFF,
        ComparisonPreset.DIFF_FOCUS,
    ):
        plan = plan_comparison(("a", "b", "c", "d"), preset, pair)
        assert not plan.available
        assert plan.source_ids == ()
        assert not plan.show_difference


def test_four_mode_does_not_silently_show_source_outside_first_four() -> None:
    ids = ("a", "b", "c", "d", "e", "f")
    plan = plan_comparison(
        ids,
        ComparisonPreset.ORIGINAL_4,
        ComparisonPair("a", "e"),
    )
    assert not plan.available
    assert not plan.source_ids


def test_generation_and_channel_gate_belongs_to_caller() -> None:
    pair = ComparisonPair("a", "b")
    stale = plan_comparison(
        ("a", "b"),
        ComparisonPreset.AB_DIFF,
        pair,
        cached_valid=False,
        stale=True,
    )
    valid = plan_comparison(
        ("a", "b"),
        ComparisonPreset.AB_DIFF,
        pair,
        cached_valid=True,
        stale=True,
    )
    assert stale.difference_state == "stale"
    assert not stale.show_difference
    assert valid.difference_state == "cached-valid"
    assert valid.show_difference


def test_reused_basenames_have_distinct_runtime_pair_roles() -> None:
    ids = ("id-from-parent-one", "id-from-parent-two", "id-from-parent-three", "id4")
    pair = ComparisonPair(ids[0], ids[2])
    result = plan_comparison(ids, ComparisonPreset.ORIGINAL_4, pair)
    assert result.pair == pair
    with pytest.raises(ValueError, match="duplicate source identities"):
        plan_comparison(("id", "id"), ComparisonPreset.WORKSPACE, pair)
