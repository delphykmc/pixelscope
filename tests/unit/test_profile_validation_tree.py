from __future__ import annotations

from pathlib import Path

from scripts.profile_validation_tree import (
    copytree_ignore,
    summarize_tree,
    tracked_paths,
    tracked_paths_hidden_by_copy_policy,
)

ROOT = Path(__file__).resolve().parents[2]


def test_summarize_tree_separates_tracked_and_local_copy_candidates(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/tracked.py").write_bytes(b"abc")
    (tmp_path / "local").mkdir()
    (tmp_path / "local/cache.bin").write_bytes(b"12345")
    (tmp_path / "docs/temp").mkdir(parents=True)
    (tmp_path / "docs/temp/tracked.png").write_bytes(b"xy")

    ignored = {
        ".venv": "ignored",
        ".venv-release": "release-env",
        ".codex": "agent-state",
        ".test-results": "test-state",
        "release": "release-artifact",
        "temp": "temp-state",
    }
    for directory, payload in ignored.items():
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "ignored.bin").write_text(payload, encoding="utf-8")

    tracked = {"src/tracked.py", "docs/temp/tracked.png"}
    summary = summarize_tree(tmp_path, tracked=tracked)

    assert summary["files"] == 3
    assert summary["bytes"] == 10
    assert summary["tracked_files"] == 2
    assert summary["tracked_bytes"] == 5
    assert summary["non_tracked_files"] == 1
    assert summary["non_tracked_bytes"] == 5
    assert summary["largest_non_tracked"] == [{"path": "local/cache.bin", "bytes": 5}]

    rows = {row["path"]: row for row in summary["top_level"]}
    assert rows["src"]["tracked_files"] == 1
    assert rows["docs"]["tracked_files"] == 1
    assert rows["local"]["non_tracked_files"] == 1
    assert ignored.keys().isdisjoint(rows)


def test_copytree_ignore_scopes_local_artifacts_to_repository_root(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    ignore = copytree_ignore(tmp_path)

    root_ignored = set(ignore(str(tmp_path), ["temp", "release", "docs"]))
    assert root_ignored == {"temp", "release"}

    nested_ignored = ignore(str(tmp_path / "docs"), ["temp", "release", "__pycache__"])
    assert nested_ignored == ["__pycache__"]


def test_hidden_tracked_path_detection_matches_copy_policy() -> None:
    tracked = {
        "src/visible.py",
        "docs/release/visible.md",
        "docs/temp/visible.png",
        "build/tracked.txt",
        "release/tracked.bin",
        "nested/__pycache__/state.py",
    }

    assert tracked_paths_hidden_by_copy_policy(tracked) == [
        "build/tracked.txt",
        "nested/__pycache__/state.py",
        "release/tracked.bin",
    ]


def test_repository_copy_policy_does_not_hide_tracked_paths() -> None:
    assert tracked_paths_hidden_by_copy_policy(tracked_paths(ROOT)) == []
