from __future__ import annotations

from pathlib import Path

from scripts.profile_validation_tree import summarize_tree


def test_summarize_tree_separates_tracked_and_local_copy_candidates(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/tracked.py").write_bytes(b"abc")
    (tmp_path / "local").mkdir()
    (tmp_path / "local/cache.bin").write_bytes(b"12345")

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

    summary = summarize_tree(tmp_path, tracked={"src/tracked.py"})

    assert summary["files"] == 2
    assert summary["bytes"] == 8
    assert summary["tracked_files"] == 1
    assert summary["tracked_bytes"] == 3
    assert summary["non_tracked_files"] == 1
    assert summary["non_tracked_bytes"] == 5
    assert summary["largest_non_tracked"] == [{"path": "local/cache.bin", "bytes": 5}]

    rows = {row["path"]: row for row in summary["top_level"]}
    assert rows["src"]["tracked_files"] == 1
    assert rows["src"]["non_tracked_files"] == 0
    assert rows["local"]["tracked_files"] == 0
    assert rows["local"]["non_tracked_files"] == 1
    assert ignored.keys().isdisjoint(rows)
