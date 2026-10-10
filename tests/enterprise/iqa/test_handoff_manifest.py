"""Synthetic Git and SUB sibling-safety contract for Issue #156 H1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HANDOFF_SCRIPT = REPO_ROOT / "enterprise" / "iqa" / "handoff_manifest.py"
SPEC = importlib.util.spec_from_file_location("handoff_manifest", HANDOFF_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _write(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _commit(root: Path, title: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", title)
    return _git(root, "rev-parse", "HEAD")


def _tag(root: Path, name: str) -> None:
    _git(root, "tag", "-a", name, "-m", name)


def _fixture(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "PixelScope Fixture")
    _git(root, "config", "user.email", "test@example.invalid")
    _write(
        root, "src/pixelscope/remote/iqa_public_contract.py",
        "IQA_PUBLIC_CONTRACT_REVISION = 1\n",
    )
    _write(root, "src/pixelscope/core.py", "core = True\n")
    base = _commit(root, "synthetic public main")
    _write(root, "src/pixelscope_enterprise/__init__.py", '"""public-safe."""\n')
    _write(root, "src/pixelscope_enterprise/iqa/a.py", "a = True\n")
    _write(root, "tests/enterprise/iqa/test_a.py", "def test_a(): pass\n")
    _write(root, "docs/enterprise/iqa/a.md", "# a\n")
    _write(root, "enterprise/iqa/README.md", "# manifest\n")
    approved = _commit(root, "synthetic handoff v1")
    _tag(root, "handoff/iqa/v1")
    return root, base, approved


def _make_manifest(
    tmp_path: Path,
    root: Path,
    base: str,
    approved: str,
    version: int,
    *,
    previous: Path | None = None,
    mode: str = "manifest-delta",
) -> tuple[Path, dict[str, object]]:
    evidence = tmp_path / f"evidence-v{version}.json"
    evidence.write_text(
        json.dumps(
            [
                {
                    "command": "python -m pytest -q tests/enterprise/iqa",
                    "platform": "Windows",
                    "python": "3.10",
                    "qt": "PySide6 6.4.2",
                    "outcome": "pass",
                }
            ]
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        repo=root,
        main_base_sha=base,
        handoff_sha=approved,
        tag=f"handoff/iqa/v{version}",
        reviewed_by="synthetic-reviewer",
        approved_at="2026-10-10T00:00:00+00:00",
        evidence=evidence,
        previous_manifest=previous,
        transfer_mode=mode,
    )
    manifest = handoff.generate(args)
    path = tmp_path / f"manifest-v{version}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def test_first_approved_manifest_import_keeps_downstream_siblings(tmp_path: Path) -> None:
    root, base, sha = _fixture(tmp_path)
    path, manifest = _make_manifest(tmp_path, root, base, sha, 1)
    assert handoff._read(path)["handoff_sha"] == sha
    assert manifest["main_base_sha"] == base
    assert all(entry["operation"] == "add" for entry in manifest["imported_paths"])
    assert manifest["removed_paths"] == []
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "enterprise/other_team/sibling.py", "dont_touch = 1\n")
    _write(destination, "tests/enterprise/other_team/test_sibling.py", "# keep\n")

    planned = handoff.plan_import(root, destination, manifest)
    assert planned and all(action == "write" for action, _, _, _ in planned)
    # Planning is read-only; no IQA files appear until explicit apply.
    assert not (destination / "enterprise/iqa/README.md").exists()
    handoff.apply_import(planned)
    assert (destination / "enterprise/other_team/sibling.py").read_text() == (
        "dont_touch = 1\n"
    )
    assert (destination / "tests/enterprise/other_team/test_sibling.py").exists()
    assert (destination / "src/pixelscope_enterprise/iqa/a.py").read_text() == "a = True\n"
    assert handoff.plan_import(root, destination, manifest) == []


def test_incremental_explicit_update_and_deletion(tmp_path: Path) -> None:
    root, base, sha1 = _fixture(tmp_path)
    old_path, old = _make_manifest(tmp_path, root, base, sha1, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "docs/enterprise/unrelated.md", "retain me\n")
    handoff.apply_import(handoff.plan_import(root, destination, old))

    (root / "src/pixelscope_enterprise/iqa/a.py").unlink()
    _write(root, "tests/enterprise/iqa/test_a.py", "def test_a(): assert True\n")
    _write(root, "src/pixelscope_enterprise/iqa/b.py", "b = True\n")
    sha2 = _commit(root, "synthetic handoff v2")
    _tag(root, "handoff/iqa/v2")
    _, new = _make_manifest(tmp_path, root, base, sha2, 2, previous=old_path)
    assert new["previous_approved_handoff_sha"] == sha1
    with pytest.raises(handoff.HandoffError, match="requires previous approved manifest"):
        handoff.plan_import(root, destination, new)
    assert new["removed_paths"] == [
        {
            "path": "src/pixelscope_enterprise/iqa/a.py",
            "previous_sha256": hashlib.sha256(b"a = True\n").hexdigest(),
        }
    ]
    operations = handoff.plan_import(root, destination, new, old)
    assert any(kind == "delete" for kind, _, _, _ in operations)
    handoff.apply_import(operations)
    assert not (destination / "src/pixelscope_enterprise/iqa/a.py").exists()
    assert (destination / "src/pixelscope_enterprise/iqa/b.py").is_file()
    assert (destination / "docs/enterprise/unrelated.md").read_text() == "retain me\n"


def test_private_collisions_and_tampered_manifest_are_rejected(tmp_path: Path) -> None:
    root, base, sha = _fixture(tmp_path)
    _, manifest = _make_manifest(tmp_path, root, base, sha, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    _write(destination, "enterprise/iqa/README.md", "# private version\n")
    with pytest.raises(handoff.HandoffError, match="unowned existing path collision"):
        handoff.plan_import(root, destination, manifest)
    assert (destination / "enterprise/iqa/README.md").read_text() == "# private version\n"

    tampered = json.loads(json.dumps(manifest))
    tampered["imported_paths"][0]["sha256"] = "0" * 64
    with pytest.raises(handoff.HandoffError, match="source SHA-256 mismatch"):
        handoff.plan_import(root, tmp_path / "empty", tampered)

    traversal = json.loads(json.dumps(manifest))
    traversal["imported_paths"][0]["path"] = "enterprise/iqa/../other_team/sibling.py"
    with pytest.raises(handoff.HandoffError, match="outside IQA-owned"):
        handoff.plan_import(root, tmp_path / "empty", traversal)


def test_nonancestor_history_merge_and_wrong_tag_fail(tmp_path: Path) -> None:
    root, base, sha1 = _fixture(tmp_path)
    old_path, _ = _make_manifest(tmp_path, root, base, sha1, 1)
    _git(root, "checkout", "-q", "-b", "parallel", base)
    _write(root, "tests/enterprise/iqa/parallel.py", "parallel = 1\n")
    sha2 = _commit(root, "non-descendant independent handoff")
    _tag(root, "handoff/iqa/v2")
    with pytest.raises(handoff.HandoffError, match="history-merge requires"):
        _make_manifest(tmp_path, root, base, sha2, 2, previous=old_path, mode="history-merge")

    _, manifest = _make_manifest(tmp_path, root, base, sha2, 2, previous=old_path)
    manifest["approved_tag"] = "handoff/iqa/v1"
    with pytest.raises(handoff.HandoffError, match="approved tag"):
        handoff.plan_import(root, tmp_path / "sub", manifest, handoff._read(old_path))


def test_symlink_parent_is_not_a_transfer_target(tmp_path: Path) -> None:
    root, base, sha = _fixture(tmp_path)
    _, manifest = _make_manifest(tmp_path, root, base, sha, 1)
    destination = tmp_path / "sub"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (destination / "enterprise").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("cannot create directory symlink on this platform")
    with pytest.raises(handoff.HandoffError, match="symlink"):
        handoff.plan_import(root, destination, manifest)
    assert list(outside.iterdir()) == []
