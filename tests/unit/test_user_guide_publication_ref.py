from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from scripts import validate_user_guide_publication_ref as guard

MAIN_SHA = "a" * 40
TAG_SHA = "b" * 40


def test_preflight_rejects_arbitrary_refs_before_git_or_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        return MAIN_SHA

    monkeypatch.setattr(guard, "_git", fake_git)
    for revision in (
        "feature/unreviewed",
        "pull/123/head",
        "refs/heads/main",
        "main;echo unsafe",
        "v0.1.0/other",
        "v0.1.0^{commit}",
        "v0.1.0\nmalicious=ref",
        "v0.1.0-evil",
        "",
    ):
        with pytest.raises(ValueError, match="Revision must be main"):
            guard.validate_publication_source(revision, MAIN_SHA)
    assert calls == []


def test_preflight_requires_trusted_main_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guard, "_git", lambda *_args: TAG_SHA)
    with pytest.raises(ValueError, match="Trusted workflow checkout"):
        guard.validate_publication_source("main", MAIN_SHA)


def test_preflight_main_reads_literal_version_without_exec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        if args == ("rev-parse", "--verify", "HEAD"):
            return MAIN_SHA
        if args == ("show", f"{MAIN_SHA}:src/pixelscope/version.py"):
            return '__version__ = "0.1.0"'
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(guard, "_git", fake_git)
    assert guard.validate_publication_source("main", MAIN_SHA) == (MAIN_SHA, "0.1.0")
    assert all("refs/tags/" not in " ".join(call) for call in calls)


def test_preflight_tag_checks_ancestry_literal_version_and_tooling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        if args == ("rev-parse", "--verify", "HEAD"):
            return MAIN_SHA
        if args == ("rev-parse", "--verify", "refs/tags/v0.1.0^{commit}"):
            return TAG_SHA
        if args == ("show", f"{TAG_SHA}:src/pixelscope/version.py"):
            return '"""The version contract."""\n__version__ = "0.1.0"'
        if args[:2] == ("cat-file", "-e"):
            return ""
        raise AssertionError(f"unexpected git command: {args}")

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        assert command == ["git", "merge-base", "--is-ancestor", TAG_SHA, MAIN_SHA]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guard, "_git", fake_git)
    monkeypatch.setattr(guard.subprocess, "run", fake_run)
    assert guard.validate_publication_source("v0.1.0", MAIN_SHA) == (TAG_SHA, "0.1.0")
    for path in guard._REQUIRED_TAG_FILES:
        assert ("cat-file", "-e", f"{TAG_SHA}:{path}") in calls


def test_preflight_tag_version_mismatch_fails_without_running_selected_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "--verify", "HEAD"):
            return MAIN_SHA
        if args == ("rev-parse", "--verify", "refs/tags/v0.1.0^{commit}"):
            return TAG_SHA
        if args == ("show", f"{TAG_SHA}:src/pixelscope/version.py"):
            return '__version__ = "0.2.0"'
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(guard, "_git", fake_git)
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    with pytest.raises(ValueError, match="does not match source version"):
        guard.validate_publication_source("v0.1.0", MAIN_SHA)


def test_workflow_rejects_untrusted_ref_before_selected_checkout_or_install() -> None:
    workflow = (guard.REPO_ROOT / ".github/workflows/user-guide-publication.yml").read_text(
        encoding="utf-8"
    )
    trusted = workflow.index("ref: ${{ github.sha }}")
    preflight = workflow.index("scripts/validate_user_guide_publication_ref.py")
    selected = workflow.index("ref: ${{ steps.source.outputs.source_sha }}")
    setup = workflow.index("uses: actions/setup-python@")
    pip_install = workflow.index("python -m pip install -r requirements/docs.txt")
    assert trusted < preflight < selected < setup < pip_install
    assert "ref: ${{ inputs.revision }}" not in workflow
    assert "if: ${{ github.ref == 'refs/heads/main' }}" in workflow
    assert "persist-credentials: false" in workflow
    assert '--expected-commit "$DOC_SOURCE_SHA"' in workflow
    assert "workflow_dispatch:" in workflow
    assert not re.search(r"(?m)^  (?:push|pull_request|schedule):", workflow)
