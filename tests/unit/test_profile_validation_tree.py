from __future__ import annotations

from pathlib import Path

from scripts.profile_validation_tree import summarize_tree


def test_summarize_tree_separates_tracked_and_local_copy_candidates(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/tracked.py").write_bytes(b"abc")
    (tmp_path / "local").mkdir()
    (tmp_path / "local/cache.bin").write_bytes(b"12345")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/ignored.bin").write_bytes(b"ignored")
    (tmp_path / "temp").mkdir()
    (tmp_path / "temp/ignored.txt").write_text("ignored", encoding="utf-8")

    summary = summarize_tree(tmp_path, tracked={"src/tracked.py"})

    assert summary["files"] == 2
    assert summary["bytes"] == 8
    assert summary["tracked_files"] == 1
    assert summary["tracked_bytes"] == 3
    assert summary["non_tracked_files"] == 1
    assert summary["non_tracked_bytes"] == 5

    rows = {row["path"]: row for row in summary["top_level"]}
    assert rows["src"]["tracked_files"] == 1
    assert rows["src"]["non_tracked_files"] == 0
    assert rows["local"]["tracked_files"] == 0
    assert rows["local"]["non_tracked_files"] == 1
    assert ".venv" not in rows
    assert "temp" not in rows
