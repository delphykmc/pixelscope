"""Contracts for the deliberately small durable pytest registry."""

from __future__ import annotations

from scripts.ci_test_groups import DURABLE_TEST_GROUPS, nodes


def test_registry_contains_only_named_durable_groups_with_rationales() -> None:
    assert set(DURABLE_TEST_GROUPS) == {"help", "release", "raw", "yuv"}
    for tests in DURABLE_TEST_GROUPS.values():
        assert tests
        assert all(test.rationale.strip() for test in tests)
        assert len({test.node for test in tests}) == len(tests)


def test_historical_phase_modules_are_selected_by_authoritative_node() -> None:
    raw = nodes("raw")

    assert (
        "tests/unit/test_wp_b_raw_profile_compatibility.py"
        "::test_minimum_stride_uses_storage_specific_row_layout"
    ) in raw
    assert "tests/unit/test_wp_b_raw_profile_compatibility.py" not in raw


def test_raw_and_yuv_groups_stay_focused_on_core_contracts() -> None:
    assert len(nodes("raw")) <= 6
    assert len(nodes("yuv")) <= 10


def test_group_nodes_are_unique_across_durable_groups() -> None:
    all_nodes = [test.node for tests in DURABLE_TEST_GROUPS.values() for test in tests]
    assert len(all_nodes) == len(set(all_nodes))
