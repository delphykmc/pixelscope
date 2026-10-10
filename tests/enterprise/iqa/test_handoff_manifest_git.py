"""Opt-in real Git handoff smoke; run once before a frozen handoff release.

Normal focused/CI tests use the fast synthetic contract. This test is skipped
unless PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION=1 to avoid repeated Windows Git
process startup/AV overhead on every development run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "handoff_manifest", REPO_ROOT / "enterprise" / "iqa" / "handoff_manifest.py"
)
assert SPEC is not None and SPEC.loader is not None
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)

pytestmark = pytest.mark.skipif(
    os.environ.get("PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION") != "1",
    reason="real-Git handoff smoke is reserved for release/transfer validation",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def _write(root: Path, name: str, data: bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_real_git_manifest_generation_and_safe_import(tmp_path: Path) -> None:
    """One actual Git/tree/tag/blob round trip, including binary payload."""
    repo = tmp_path / "git"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "PixelScope Synthetic Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _write(
        repo,
        "src/pixelscope/remote/iqa_public_contract.py",
        b"IQA_PUBLIC_CONTRACT_REVISION = 1\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic MAIN baseline")
    main_sha = _git(repo, "rev-parse", "HEAD")

    binary = b"\x00\n\xff\x01\r\ntrailing\x00"
    _write(repo, "src/pixelscope_enterprise/iqa/binary.dat", binary)
    _write(repo, "tests/enterprise/iqa/test_smoke.py", b"def test_smoke(): pass\n")
    _write(repo, "docs/enterprise/iqa/README.md", b"safe handoff\n")
    _write(repo, "enterprise/iqa/README.md", b"transfer manifest\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic IQA handoff")
    approved = _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", "-a", "handoff/iqa/v1", "-m", "synthetic approval tag")

    evidence = tmp_path / "synthetic-validation.json"
    evidence.write_text(
        json.dumps(
            [
                {
                    "command": "opt-in real-Git synthetic smoke",
                    "platform": "synthetic",
                    "python": "3.10",
                    "outcome": "pass",
                }
            ]
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        repo=repo,
        main_base_sha=main_sha,
        handoff_sha=approved,
        tag="handoff/iqa/v1",
        reviewed_by="synthetic-test-only",
        approved_at="2026-10-10T00:00:00+00:00",
        evidence=evidence,
        previous_manifest=None,
        transfer_mode="manifest-delta",
    )
    manifest = handoff.generate(args)
    manifest_path = tmp_path / "approved-synthetic-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    destination = tmp_path / "sub"
    destination.mkdir()
    sibling = destination / "enterprise" / "unrelated" / "sibling.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(b"must survive\n")

    # Exercise the actual command-line parser and exit code, not just the
    # verify_import() function. This is an intentionally incomplete transfer.
    command = [
        sys.executable,
        str(REPO_ROOT / "enterprise" / "iqa" / "handoff_manifest.py"),
        "verify",
        "--repo",
        str(repo),
        "--destination",
        str(destination),
        "--manifest",
        str(manifest_path),
    ]
    incomplete = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert incomplete.returncode != 0
    assert "post-import verification failed" in incomplete.stderr
    assert "POST-IMPORT VERIFIED" not in incomplete.stdout
    assert sibling.read_bytes() == b"must survive\n"

    actions = handoff.plan_import(repo, destination, manifest)
    assert len(actions) == len(manifest["imported_paths"])
    assert not (destination / "src/pixelscope_enterprise/iqa/binary.dat").exists()
    handoff.apply_import(actions)
    assert (destination / "src/pixelscope_enterprise/iqa/binary.dat").read_bytes() == binary
    assert sibling.read_bytes() == b"must survive\n"
    assert handoff.plan_import(repo, destination, manifest) == []
    assert handoff.verify_import(repo, destination, manifest) == (
        len(manifest["imported_paths"]),
        len(manifest["removed_paths"]),
    )
    verified = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert verified.returncode == 0, verified.stderr
    assert f"POST-IMPORT VERIFIED: {len(manifest['imported_paths'])} approved IQA files" in (
        verified.stdout
    )
    assert f"external manifest SHA-256 {manifest_digest}" in verified.stdout
    assert "SUB sibling integrity" in verified.stdout
    assert sibling.read_bytes() == b"must survive\n"
