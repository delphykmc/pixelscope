from pixelscope.core.review_selection import (
    ReviewSelectionState,
    difference_sources_survive_selection,
)


def test_review_state_enter_pick_unpick_clear_and_exit() -> None:
    state = ReviewSelectionState()

    state.enter(["A", "B", "C"])
    assert state.active
    assert state.baseline_selected_ids == ("A", "B", "C")
    assert state.picked_count == 0

    assert state.set_picked("B", True)
    assert not state.set_picked("B", True)
    assert state.picked_ids == {"B"}
    assert state.set_picked("B", False)
    assert not state.set_picked("B", False)
    assert state.picked_ids == set()

    state.set_picked("A", True)
    state.set_picked("C", True)
    assert state.clear_picks()
    assert not state.clear_picks()
    assert state.picked_ids == set()

    state.exit()
    assert not state.active
    assert state.baseline_selected_ids == ()
    assert state.picked_ids == set()


def test_review_state_ignores_nonbaseline_ids_and_preserves_baseline_order() -> None:
    state = ReviewSelectionState()
    state.enter(["A", "B", "C", "D", "E", "F", "G"])

    assert not state.set_picked("derived", True)
    state.set_picked("G", True)
    state.set_picked("B", True)
    state.set_picked("E", True)

    assert state.picked_ids == {"B", "E", "G"}
    assert state.kept_selected_ids() == ("B", "E", "G")


def test_review_state_reenter_replaces_temporary_baseline_and_picks() -> None:
    state = ReviewSelectionState()
    state.enter(["A", "B"])
    state.set_picked("B", True)

    state.enter(["C", "D"])

    assert state.active
    assert state.baseline_selected_ids == ("C", "D")
    assert state.picked_ids == set()
    assert state.matches_selected_ids(["C", "D"])
    assert not state.matches_selected_ids(["D", "C"])


def test_difference_sources_survive_only_when_both_provenance_sources_are_kept() -> None:
    assert difference_sources_survive_selection(("A", "B"), ("A", "B"))
    assert difference_sources_survive_selection(("A", "B"), ("C", "A", "B"))
    assert not difference_sources_survive_selection(("A", "B"), ("A", "C"))
    assert not difference_sources_survive_selection(("A", "B"), ("B", "C"))
    assert not difference_sources_survive_selection(("A", "B"), ("C", "D", "E"))
    assert not difference_sources_survive_selection((), ("A", "B"))
    assert not difference_sources_survive_selection(("A",), ("A", "B"))
