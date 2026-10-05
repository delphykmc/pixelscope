from pathlib import Path

import pytest
from scripts.ci_test_groups import DURABLE_TEST_GROUPS, nodes

ROOT = Path(__file__).resolve().parents[2]


def test_durable_groups_are_small_explicit_and_resolve_to_files() -> None:
    assert set(DURABLE_TEST_GROUPS) == {"help", "release", "raw", "yuv"}

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


def test_nodes_returns_registry_order_and_rejects_unknown_group() -> None:
    assert nodes("help") == ["tests/ui/test_user_guide_help.py"]
    with pytest.raises(ValueError, match="unknown durable CI test group"):
        nodes("unknown")
