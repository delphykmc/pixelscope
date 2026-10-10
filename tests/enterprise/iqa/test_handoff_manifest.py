"""Fast synthetic contracts for IQA manifest ownership and SUB-safe transfer.

Unit tests intentionally use an in-memory Git object model. Run the separate,
opt-in real-Git smoke before approving a handoff release.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HANDOFF_SCRIPT = REPO_ROOT / "enterprise" / "iqa" / "handoff_manifest.py"
SPEC = importlib.util.spec_from_file_location("handoff_manifest", HANDOFF_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def _write(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class FakeGit:
    """Deterministic Git graph and blobs; no subprocess or Git repository setup."""

    main = "a" * 40
    v1 = "b" * 40
    v2 = "c" * 40
    parallel = "d" * 40

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.blobs: dict[str, bytes] = {}
        self.snapshots: dict[str, dict[str, tuple[str, str]]] = {}
        first = {
            "src/pixelscope_enterprise/__init__.py": b"enterprise package\n",
            "src/pixelscope_enterprise/iqa/a.py": b"a = True\n",
            "tests/enterprise/iqa/test_a.py": b"def test_a(): pass\n",
            "docs/enterprise/iqa/a.md": b"# a\n",
            "enterprise/iqa/README.md": b"# manifest\n",
        }
        second = dict(first)
        del second["src/pixelscope_enterprise/iqa/a.py"]
        second["src/pixelscope_enterprise/iqa/b.py"] = b"b = True\n"
        second["tests/enterprise/iqa/test_a.py"] = b"def test_a(): assert True\n"
        self.snapshots[self.v1] = self._snapshot(first)
        self.snapshots[self.v2] = self._snapshot(second)
        self.snapshots[self.parallel] = self._snapshot(
            {"tests/enterprise/iqa/parallel.py": b"parallel = 1\n"}
        )
        self.tags = {
            "handoff/iqa/v1": self.v1,
            "handoff/iqa/v2": self.v2,
            "handoff/iqa/v3": self.parallel,
        }
        monkeypatch.setattr(handoff, "_git", self.git)
        monkeypatch.setattr(handoff, "_ancestor", self.ancestor)
        monkeypatch.setattr(handoff, "_tree", self.tree)
        monkeypatch.setattr(handoff, "_blobs", self.read_blobs)

    def _snapshot(self, files: dict[str, bytes]) -> dict[str, tuple[str, str]]:
        snapshot = {}
        for path, content in files.items():
            blob = hashlib.sha1(content).hexdigest()
            self.blobs[blob] = content
            snapshot[path] = ("100644", blob)
        return snapshot

    def git(self, _root: Path, *args: str) -> bytes:
        if args[:2] == ("rev-parse", "--verify"):
            ref = args[2]
            suffix = "^{commit}"
            assert ref.endswith(suffix)
            ref = ref[: -len(suffix)]
            if ref.startswith("refs/tags/"):
                sha = self.tags.get(ref[len("refs/tags/") :])
            else:
                sha = ref if ref in (self.main, self.v1, self.v2, self.parallel) else None
            if sha is None:
                raise handoff.HandoffError("unknown synthetic commit or tag")
            return (sha + "\n").encode("ascii")
        if args[0] == "show":
            assert args[1] == (f"{self.main}:src/pixelscope/remote/iqa_public_contract.py")
            return b"IQA_PUBLIC_CONTRACT_REVISION = 1\n"
        raise AssertionError(f"unexpected synthetic Git call: {args}")

    def ancestor(self, _root: Path, earlier: str, later: str) -> bool:
        if earlier == later:
            return True
        return (
            earlier == self.main
            and later in (self.v1, self.v2, self.parallel)
            or earlier == self.v1
            and later == self.v2
        )

    def tree(self, _root: Path, sha: str) -> dict[str, tuple[str, str]]:
        return dict(self.snapshots[sha])

    def read_blobs(self, _root: Path, shas: list[str]) -> dict[str, bytes]:
        return {sha: self.blobs[sha] for sha in shas}


@pytest.fixture
def fake_git(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    return FakeGit(monkeypatch)


def _make_manifest(
    tmp_path: Path,
    fake: FakeGit,
    sha: str,
    version: int,
    *,
    previous: Path | None = None,
    mode: str = "manifest-delta",
) -> tuple[Path, dict[str, object]]:
    evidence = tmp_path / f"synthetic-evidence-v{version}.json"
    evidence.write_text(
        json.dumps(
            [
                {
                    "command": "synthetic manifest unit test",
                    "platform": "in-memory",
                    "python": "3.10",
                    "outcome": "pass",
                }
            ]
        ),
        encoding="utf-8",
    )
    tag = {
        fake.v1: "handoff/iqa/v1",
        fake.v2: "handoff/iqa/v2",
        fake.parallel: "handoff/iqa/v3",
    }[sha]
    args = argparse.Namespace(
        repo=tmp_path,
        main_base_sha=fake.main,
        handoff_sha=sha,
        tag=tag,
        reviewed_by="synthetic-test-not-real-approval",
        approved_at="2026-10-10T00:00:00+00:00",
        evidence=evidence,
        previous_manifest=previous,
        transfer_mode=mode,
    )
    manifest = handoff.generate(args)
    path = tmp_path / f"manifest-v{version}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def test_first_approved_manifest_import_keeps_downstream_siblings(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    path, manifest = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    assert handoff._read(path)["handoff_sha"] == fake_git.v1
    assert manifest["main_base_sha"] == fake_git.main
    assert all(entry["operation"] == "add" for entry in manifest["imported_paths"])
    assert manifest["removed_paths"] == []
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "enterprise/other_team/sibling.py", "dont_touch = 1\n")
    _write(destination, "tests/enterprise/other_team/test_sibling.py", "# keep\n")

    planned = handoff.plan_import(tmp_path, destination, manifest)
    assert planned and all(action == "write" for action, _, _, _ in planned)
    assert not (destination / "enterprise/iqa/README.md").exists()
    handoff.apply_import(planned)
    assert (destination / "enterprise/other_team/sibling.py").read_text() == ("dont_touch = 1\n")
    assert (destination / "tests/enterprise/other_team/test_sibling.py").exists()
    assert (destination / "src/pixelscope_enterprise/iqa/a.py").read_text() == "a = True\n"
    assert handoff.plan_import(tmp_path, destination, manifest) == []


def test_incremental_explicit_update_and_deletion(tmp_path: Path, fake_git: FakeGit) -> None:
    old_path, old = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "docs/enterprise/unrelated.md", "retain me\n")
    handoff.apply_import(handoff.plan_import(tmp_path, destination, old))

    _, new = _make_manifest(tmp_path, fake_git, fake_git.v2, 2, previous=old_path)
    assert new["previous_approved_handoff_sha"] == fake_git.v1
    with pytest.raises(handoff.HandoffError, match="requires previous approved manifest"):
        handoff.plan_import(tmp_path, destination, new)
    assert new["removed_paths"] == [
        {
            "path": "src/pixelscope_enterprise/iqa/a.py",
            "previous_sha256": hashlib.sha256(b"a = True\n").hexdigest(),
        }
    ]
    operations = handoff.plan_import(tmp_path, destination, new, old)
    assert any(kind == "delete" for kind, _, _, _ in operations)
    handoff.apply_import(operations)
    assert not (destination / "src/pixelscope_enterprise/iqa/a.py").exists()
    assert (destination / "src/pixelscope_enterprise/iqa/b.py").is_file()
    assert (destination / "docs/enterprise/unrelated.md").read_text() == "retain me\n"


def test_private_collisions_and_tampered_manifest_are_rejected(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    _, manifest = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "enterprise/iqa/README.md", "# private version\n")
    with pytest.raises(handoff.HandoffError, match="unowned existing path collision"):
        handoff.plan_import(tmp_path, destination, manifest)
    assert (destination / "enterprise/iqa/README.md").read_text() == "# private version\n"

    tampered = json.loads(json.dumps(manifest))
    tampered["imported_paths"][0]["sha256"] = "0" * 64
    with pytest.raises(handoff.HandoffError, match="approved manifest SHA-256 differs"):
        handoff.plan_import(tmp_path, tmp_path / "empty", tampered)

    traversal = json.loads(json.dumps(manifest))
    traversal["imported_paths"][0]["path"] = "enterprise/iqa/../other_team/sibling.py"
    with pytest.raises(handoff.HandoffError, match="outside IQA-owned"):
        handoff.plan_import(tmp_path, tmp_path / "empty", traversal)
    assert not handoff._owned_path("enterprise/iqa/CON.txt")


def test_nonancestor_history_merge_and_wrong_tag_fail(tmp_path: Path, fake_git: FakeGit) -> None:
    old_path, _ = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    for mode in ("manifest-delta", "history-merge"):
        with pytest.raises(handoff.HandoffError, match="must descend from prior approved SHA"):
            _make_manifest(
                tmp_path,
                fake_git,
                fake_git.parallel,
                3,
                previous=old_path,
                mode=mode,
            )
    _, manifest = _make_manifest(tmp_path, fake_git, fake_git.v2, 2, previous=old_path)
    manifest["approved_tag"] = "handoff/iqa/v1"
    with pytest.raises(handoff.HandoffError, match="approved tag"):
        handoff.plan_import(tmp_path, tmp_path / "sub", manifest, handoff._read(old_path))


def test_symlink_parent_is_not_a_transfer_target(tmp_path: Path, fake_git: FakeGit) -> None:
    _, manifest = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (destination / "enterprise").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("cannot create directory symlink on this platform")
    with pytest.raises(handoff.HandoffError, match="symlink"):
        handoff.plan_import(tmp_path, destination, manifest)
    assert list(outside.iterdir()) == []


def test_post_import_verify_is_read_only_and_rejects_missing_or_tampered_files(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    _, manifest = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    sibling = "enterprise/other_team/sibling.py"
    _write(destination, sibling, "private_sibling_untouched = True\n")
    sibling_before = (destination / sibling).read_bytes()

    # A manifest with a valid pinned tree is not proof of actual installation.
    with pytest.raises(handoff.HandoffError, match="operations remain unapplied"):
        handoff.verify_import(tmp_path, destination, manifest)
    assert not (destination / "src/pixelscope_enterprise/iqa/a.py").exists()
    assert (destination / sibling).read_bytes() == sibling_before

    handoff.apply_import(handoff.plan_import(tmp_path, destination, manifest))
    assert handoff.verify_import(tmp_path, destination, manifest) == (
        len(manifest["imported_paths"]),
        0,
    )
    # Auditing must not touch unrelated PRIVATE SUB sibling files.
    assert (destination / sibling).read_bytes() == sibling_before
    approved_file = destination / "src/pixelscope_enterprise/iqa/a.py"
    approved_file.write_bytes(b"modified after approval\n")
    with pytest.raises(handoff.HandoffError, match="existing path collision"):
        handoff.verify_import(tmp_path, destination, manifest)
    assert approved_file.read_bytes() == b"modified after approval\n"


def test_post_import_verify_requires_explicit_incremental_deletions(
    tmp_path: Path, fake_git: FakeGit
) -> None:
    old_path, old = _make_manifest(tmp_path, fake_git, fake_git.v1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    sibling = "tests/enterprise/other_team/test_sibling.py"
    _write(destination, sibling, "keep_me = True\n")
    sibling_before = (destination / sibling).read_bytes()
    handoff.apply_import(handoff.plan_import(tmp_path, destination, old))

    _, current = _make_manifest(tmp_path, fake_git, fake_git.v2, 2, previous=old_path)
    with pytest.raises(handoff.HandoffError, match="requires previous approved manifest"):
        handoff.verify_import(tmp_path, destination, current)
    with pytest.raises(handoff.HandoffError, match="operations remain unapplied"):
        handoff.verify_import(tmp_path, destination, current, old)

    handoff.apply_import(handoff.plan_import(tmp_path, destination, current, old))
    assert handoff.verify_import(tmp_path, destination, current, old) == (
        len(current["imported_paths"]),
        len(current["removed_paths"]),
    )
    removed = destination / "src/pixelscope_enterprise/iqa/a.py"
    assert not removed.exists()
    assert (destination / sibling).read_bytes() == sibling_before
    # A previously approved file reappearing must fail the post-import audit.
    _write(destination, "src/pixelscope_enterprise/iqa/a.py", "a = True\n")
    with pytest.raises(handoff.HandoffError, match="operations remain unapplied"):
        handoff.verify_import(tmp_path, destination, current, old)
    assert removed.read_text(encoding="utf-8") == "a = True\n"
    assert (destination / sibling).read_bytes() == sibling_before
