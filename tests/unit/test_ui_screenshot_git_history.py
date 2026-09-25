"""Git's real history is the introducing-SHA authority after merge/tag."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.audit_ui_screenshot_git_history import ASSET, MANIFEST, audit_ref


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _write_snapshot(root: Path, name: bytes, source: str) -> None:
    image = root / (ASSET + "single-image.png")
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(name)
    record = {
        "screenshots": [{
            "id": "single-image",
            "filename": "single-image.png",
            "status": "approved",
            "approved": {
                "capture_source_sha": source,
                "image_sha256": hashlib.sha256(name).hexdigest(),
            },
        }]
    }
    (root / MANIFEST).write_text(json.dumps(record), encoding="utf-8")


def _commit(root: Path, message: str) -> str:
    _git(root, "add", ".")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def test_introducing_commit_derived_after_reword_or_squash_and_tag_rollback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Screenshot test")
    _git(root, "config", "user.email", "screenshots@example.test")
    _write_snapshot(root, b"old approved image", "a" * 40)
    old = _commit(root, "old release")
    _git(root, "tag", "old-release")
    _write_snapshot(root, b"new real capture bytes", old)
    promotion = _commit(root, "reviewed image integration")
    report = audit_ref(root, "HEAD")
    assert report["errors"] == []
    assert report["approved_images"][0]["introducing_commit"] == promotion
    assert audit_ref(root, "old-release")["approved_images"][0]["introducing_commit"] == old

    # A reword creates a new commit identity while reviewed PNG bytes persist.
    _git(root, "commit", "--amend", "-m", "rebased/squashed review integration")
    rewritten = _git(root, "rev-parse", "HEAD")
    assert rewritten != promotion
    result = audit_ref(root, "HEAD")
    assert result["errors"] == []
    assert result["approved_images"][0]["introducing_commit"] == rewritten
    assert result["approved_images"][0]["capture_source_sha"] == old
    assert audit_ref(root, "old-release")["errors"] == []


def test_changed_approved_bytes_in_release_ref_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Screenshot test")
    _git(root, "config", "user.email", "screenshots@example.test")
    _write_snapshot(root, b"approved image", "b" * 40)
    _commit(root, "approved capture")
    _git(root, "tag", "approved")
    (root / (ASSET + "single-image.png")).write_bytes(b"silent image replacement")
    _commit(root, "incorrect later tag")
    _git(root, "tag", "bad-release")
    assert any("hash drift" in err for err in audit_ref(root, "bad-release")["errors"])
    assert audit_ref(root, "approved")["errors"] == []
