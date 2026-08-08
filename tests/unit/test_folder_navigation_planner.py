from __future__ import annotations

import pytest

from pixelscope.core.folder_navigation import plan_folder_navigation


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
