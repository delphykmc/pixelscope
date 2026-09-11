from __future__ import annotations

import pytest

from pixelscope.core.folder_navigation import (
    FolderComparisonBootstrapPlan,
    plan_folder_comparison_direction,
    plan_folder_comparison_targets,
    plan_folder_navigation,
)

COMPARISON_ORDER = ("a", "b", "c", "d", "e", "f", "g")
COMPARISON_DOCUMENTS = {
    folder: tuple(f"{folder}-{index}" for index in range(4)) for folder in COMPARISON_ORDER
}


def test_plans_one_registered_position_for_one_to_six_folders() -> None:
    for count in range(1, 7):
        selection = tuple((f"folder-{index}", f"{index}-1") for index in range(count))
        sequences = {
            f"folder-{index}": (f"{index}-0", f"{index}-1", f"{index}-2") for index in range(count)
        }

        next_plan = plan_folder_navigation(selection, sequences, 1)
        previous_plan = plan_folder_navigation(selection, sequences, -1)

        assert next_plan is not None
        assert next_plan.document_ids == tuple(f"{index}-2" for index in range(count))
        assert next_plan.folder_keys == tuple(f"folder-{index}" for index in range(count))
        assert next_plan.indices == (2,) * count
        assert previous_plan is not None
        assert previous_plan.document_ids == tuple(f"{index}-0" for index in range(count))
        assert previous_plan.indices == (0,) * count


@pytest.mark.parametrize(
    ("selection", "sequences"),
    (
        ((), {}),
        (
            tuple((f"folder-{index}", f"{index}-0") for index in range(7)),
            {f"folder-{index}": (f"{index}-0", f"{index}-1") for index in range(7)},
        ),
        (
            (("same", "a"), ("same", "b")),
            {"same": ("a", "b", "c")},
        ),
        (
            (("missing", "a"),),
            {},
        ),
        (
            (("folder", "unregistered"),),
            {"folder": ("a", "b")},
        ),
    ),
)
def test_rejects_invalid_navigation_groups(
    selection: tuple[tuple[str, str], ...],
    sequences: dict[str, tuple[str, ...]],
) -> None:
    assert plan_folder_navigation(selection, sequences, 1) is None


def test_any_folder_endpoint_makes_the_entire_plan_invalid() -> None:
    selection = (("a", "a-0"), ("b", "b-1"))
    sequences = {"a": ("a-0", "a-1"), "b": ("b-0", "b-1")}

    assert plan_folder_navigation(selection, sequences, 1) is None


def test_plan_is_read_only_and_deterministic() -> None:
    selection = [("a", "a-0"), ("b", "b-0")]
    sequences = {"a": ["a-0", "a-1"], "b": ["b-0", "b-1"]}

    first = plan_folder_navigation(selection, sequences, 1)
    second = plan_folder_navigation(selection, sequences, 1)

    assert first == second
    assert selection == [("a", "a-0"), ("b", "b-0")]
    assert sequences == {"a": ["a-0", "a-1"], "b": ["b-0", "b-1"]}


@pytest.mark.parametrize("step", (-2, 0, 2))
def test_rejects_unsupported_step(step: int) -> None:
    with pytest.raises(ValueError, match="-1 or 1"):
        plan_folder_navigation((("folder", "a"),), {"folder": ("a", "b")}, step)


def test_comparison_targets_use_anchor_ordinal_and_registered_order() -> None:
    selection = (("c", "c-1"), ("a", "a-1"))

    assert plan_folder_comparison_targets(
        selection, COMPARISON_DOCUMENTS, COMPARISON_ORDER, "c-1"
    ) == (
        FolderComparisonBootstrapPlan("c", "b", "b-1", 1),
        FolderComparisonBootstrapPlan("c", "d", "d-1", 1),
        FolderComparisonBootstrapPlan("c", "e", "e-1", 1),
        FolderComparisonBootstrapPlan("c", "f", "f-1", 1),
        FolderComparisonBootstrapPlan("c", "g", "g-1", 1),
    )


def test_comparison_direction_selects_nearest_without_wrapping() -> None:
    selection = (("c", "c-2"),)

    assert plan_folder_comparison_direction(
        selection, COMPARISON_DOCUMENTS, COMPARISON_ORDER, "c-2", -1
    ) == FolderComparisonBootstrapPlan("c", "b", "b-2", 2)
    assert plan_folder_comparison_direction(
        selection, COMPARISON_DOCUMENTS, COMPARISON_ORDER, "c-2", 1
    ) == FolderComparisonBootstrapPlan("c", "d", "d-2", 2)
    assert (
        plan_folder_comparison_direction(
            (("a", "a-0"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "a-0", -1
        )
        is None
    )
    assert (
        plan_folder_comparison_direction(
            (("g", "g-0"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "g-0", 1
        )
        is None
    )


def test_comparison_skips_selected_and_short_folders_without_fallback() -> None:
    documents = {**COMPARISON_DOCUMENTS, "b": ("b-0",), "d": ("d-0",)}
    selection = (("a", "a-1"), ("c", "c-1"), ("e", "e-1"))

    assert plan_folder_comparison_targets(selection, documents, COMPARISON_ORDER, "c-1") == (
        FolderComparisonBootstrapPlan("c", "f", "f-1", 1),
        FolderComparisonBootstrapPlan("c", "g", "g-1", 1),
    )


@pytest.mark.parametrize(
    ("selection", "documents", "order", "anchor"),
    (
        ((), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "a-0"),
        ((("a", "a-0"),) * 6, COMPARISON_DOCUMENTS, COMPARISON_ORDER, "a-0"),
        ((("a", "a-0"),), {"a": ("a-0",)}, ("a", "a"), "a-0"),
        ((("missing", "x"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "x"),
        ((("a", "a-0"),), COMPARISON_DOCUMENTS, ("b", "c"), "a-0"),
        ((("a", "not-present"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "not-present"),
        ((("a", "a-0"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "not-selected"),
    ),
)
def test_comparison_targets_reject_invalid_context(
    selection: tuple[tuple[str, str], ...],
    documents: dict[str, tuple[str, ...]],
    order: tuple[str, ...],
    anchor: str,
) -> None:
    assert plan_folder_comparison_targets(selection, documents, order, anchor) == ()
    assert plan_folder_comparison_direction(selection, documents, order, anchor, 1) is None


@pytest.mark.parametrize("step", (-2, 0, 2))
def test_comparison_direction_rejects_invalid_step(step: int) -> None:
    with pytest.raises(ValueError, match="-1 or 1"):
        plan_folder_comparison_direction(
            (("a", "a-0"),), COMPARISON_DOCUMENTS, COMPARISON_ORDER, "a-0", step
        )


def test_comparison_planner_is_read_only_and_deterministic() -> None:
    selection = [("c", "c-1")]
    documents = {key: list(value) for key, value in COMPARISON_DOCUMENTS.items()}
    first = plan_folder_comparison_targets(selection, documents, COMPARISON_ORDER, "c-1")
    second = plan_folder_comparison_targets(selection, documents, COMPARISON_ORDER, "c-1")

    assert first == second
    assert selection == [("c", "c-1")]
    assert documents == {key: list(value) for key, value in COMPARISON_DOCUMENTS.items()}
