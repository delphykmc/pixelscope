from pathlib import Path

import pytest
from scripts.ci_test_groups import (
    CI_TEST_GROUPS,
    DURABLE_TEST_GROUPS,
    OWNER_LOCAL_UI_TEST_GROUPS,
    nodes,
)

ROOT = Path(__file__).resolve().parents[2]


def test_durable_groups_are_small_explicit_and_resolve_to_files() -> None:
    assert set(CI_TEST_GROUPS) == {"release", "raw-core", "yuv-core"}
    assert set(OWNER_LOCAL_UI_TEST_GROUPS) == {"help-ui", "raw-ui", "yuv-ui"}
    assert set(DURABLE_TEST_GROUPS) == set(CI_TEST_GROUPS) | set(OWNER_LOCAL_UI_TEST_GROUPS)

    all_nodes: list[str] = []
    for group, tests in DURABLE_TEST_GROUPS.items():
        assert tests, group
        assert len(tests) <= 8, group
        for test in tests:
            path = test.node.split("::", 1)[0]
            assert path.startswith("tests/"), test.node
            assert (ROOT / path).is_file(), test.node
            assert test.rationale.strip(), test.node
            all_nodes.append(test.node)

    assert len(all_nodes) == len(set(all_nodes))


def test_hosted_ci_groups_are_unit_only_and_ui_groups_are_owner_local() -> None:
    for group, tests in CI_TEST_GROUPS.items():
        assert all(test.node.startswith("tests/unit/") for test in tests), group

    for group, tests in OWNER_LOCAL_UI_TEST_GROUPS.items():
        assert all(test.node.startswith("tests/ui/") for test in tests), group


def test_release_group_covers_owned_candidate_distribution_and_publication_contracts() -> None:
    assert nodes("release") == [
        "tests/unit/test_release_packaging.py",
        "tests/unit/test_release_candidate.py",
        "tests/unit/test_release_candidate_provenance.py",
        "tests/unit/test_release_distribution.py",
        "tests/unit/test_release_target_descriptor.py",
        "tests/unit/test_release_publication.py",
    ]


def test_raw_and_yuv_executor_groups_preserve_core_and_ui_contracts() -> None:
    assert nodes("raw-core") == [
        "tests/unit/test_raw_reader.py",
        "tests/unit/test_packed_raw_stream.py",
        "tests/unit/test_wp_b_raw_profile_compatibility.py",
    ]
    assert nodes("raw-ui") == [
        "tests/ui/test_p1c_raw_dialog.py",
        "tests/ui/test_wp_b_raw_binary_compatibility.py",
    ]
    assert nodes("yuv-core") == [
        "tests/unit/test_yuv_runtime_contracts.py",
        "tests/unit/test_yuv_semantics.py",
    ]
    assert nodes("yuv-ui") == [
        "tests/ui/test_wp_c1_yuv_semantics.py",
        "tests/ui/test_wp_c2_yuv_difference.py",
    ]


def test_nodes_returns_registry_order_and_rejects_unknown_group() -> None:
    assert nodes("help-ui") == ["tests/ui/test_user_guide_help.py"]
    with pytest.raises(ValueError, match="unknown durable test group"):
        nodes("unknown")
