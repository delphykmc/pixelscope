"""Opt-in Git ancestry/inventory acceptance for the E2B MAIN->Handoff merge.

This test is intentionally not part of normal PUBLIC MAIN/full pytest. It
compares Git OBJECTS, not the Windows checkout's newline-normalized files.
Owner explicitly supplies immutable commit pins and enables the acceptance.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN_FLAG = "PIXELSCOPE_RUN_IQA_MAIN_SYNC"
PIN_MAIN = "PIXELSCOPE_PUBLIC_MAIN_SHA"
PIN_HANDOFF = "PIXELSCOPE_HANDOFF_PRE_SYNC_SHA"
PIN_MERGE = "PIXELSCOPE_HANDOFF_MAIN_MERGE_SHA"
PRIVATE_ROOTS = (
    "src/pixelscope_enterprise/",
    "tests/enterprise/",
    "docs/enterprise/",
    "enterprise/",
)
OWNED_LEAVES = (
    "src/pixelscope_enterprise/iqa/",
    "tests/enterprise/iqa/",
    "docs/enterprise/iqa/",
    "enterprise/iqa/",
)
SHARED_INIT = "src/pixelscope_enterprise/__init__.py"

pytestmark = pytest.mark.skipif(
    os.environ.get(RUN_FLAG) != "1",
    reason="E2B real Git ancestry/inventory acceptance is owner opt-in",
)


def _git(*args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"git {args[0]} failed with exit={result.returncode}: "
        f"{result.stderr.decode(errors='replace')}"
    )
    return result.stdout


def _pin(name: str) -> str:
    value = os.environ.get(name, "")
    assert SHA.fullmatch(value), f"{name} must name an exact lowercase Git SHA"
    return value


def _entries(ref: str) -> dict[str, tuple[bytes, bytes]]:
    entries: dict[str, tuple[bytes, bytes]] = {}
    for record in _git("ls-tree", "-r", "-z", "--full-tree", ref).split(b"\x00"):
        if not record:
            continue
        mode_kind_sha, encoded_path = record.split(b"\t", 1)
        mode, kind, sha = mode_kind_sha.split(b" ")
        assert kind == b"blob", f"unsupported Git tree entry: {encoded_path!r}"
        path = encoded_path.decode("utf-8")
        entries[path] = mode, sha
    return entries


def _is_enterprise(path: str) -> bool:
    return path.startswith(PRIVATE_ROOTS)


def test_main_and_original_handoff_are_real_ancestors_and_blobs_unchanged() -> None:
    main = _pin(PIN_MAIN)
    handoff = _pin(PIN_HANDOFF)
    merger = _pin(PIN_MERGE)

    # Check the *actual two-parent commit*. A synthetic SHA marker in a
    # document, a squash PR or merely identical files cannot satisfy this.
    parents = _git("rev-list", "--parents", "-n", "1", merger).decode("ascii").split()
    assert parents == [
        merger,
        handoff,
        main,
    ], "E2B must have an exact two-parent, Handoff-first, MAIN-second merge"
    for ref in (main, handoff, merger):
        _git("merge-base", "--is-ancestor", ref, "HEAD")

    main_entries = _entries(main)
    old_entries = _entries(handoff)
    actual_entries = _entries("HEAD")

    # No PUBLIC MAIN-owned code/files were reverted or overridden by a
    # Handoff-only integration and no extra MAIN-owned paths were introduced.
    main_public = {p: v for p, v in main_entries.items() if not _is_enterprise(p)}
    actual_public = {p: v for p, v in actual_entries.items() if not _is_enterprise(p)}
    assert actual_public == main_public, "combined branch alters pinned PUBLIC MAIN tree"

    # All previously reviewed Enterprise Git blob identities are retained.
    old_enterprise = {p: v for p, v in old_entries.items() if _is_enterprise(p)}
    assert all(
        actual_entries.get(p) == v for p, v in old_enterprise.items()
    ), "previous Handoff IQA blobs were modified, removed or had modes changed"

    # New Enterprise-only documents/tests are allowed, not new unowned SUB
    # siblings or private files outside the reviewed IQA leaf scope.
    for path in actual_entries:
        if _is_enterprise(path):
            assert path == SHARED_INIT or path.startswith(
                OWNED_LEAVES
            ), f"unowned Enterprise path introduced by upstream sync: {path}"
    assert all(not _is_enterprise(path) for path in main_entries)
