from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.classify_ci_changes import ChangedPath, classify_paths, git_changed_paths


def _groups(*paths: str) -> dict[str, bool]:
    return classify_paths([ChangedPath(path) for path in paths])


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, relative: str, content: str, message: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(root, "add", relative)
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def test_docs_only_change_stays_out_of_native_and_local_full_validation() -> None:
    groups = _groups("docs/QUALITY.md", "tests/integration/test_ui_screenshot_git_history.py")

    assert groups["docs"]
    assert not groups["windows_native"]
    assert not groups["local_full_required"]
    assert not groups["unknown"]


def test_issue_113_profile_policy_is_documentation_owned() -> None:
    groups = _groups(
        "scripts/profile_validation_tree.py",
        "tests/unit/test_profile_validation_tree.py",
        "tests/integration/test_user_guide_screenshot_rendering.py",
    )

    assert groups["docs"]
    assert not groups["local_full_required"]


def test_help_raw_yuv_and_release_paths_select_focused_windows_groups() -> None:
    groups = _groups(
        "src/pixelscope/ui/user_guide_help.py",
        "src/pixelscope/io/raw_reader.py",
        "src/pixelscope/core/yuv.py",
        "scripts/release_contract.py",
        "scripts/publication_contract.py",
        "scripts/build_third_party_notices.py",
        "requirements/release.txt",
    )

    assert groups["help_ui"]
    assert groups["raw"]
    assert groups["yuv"]
    assert groups["release"]
    assert groups["windows_native"]
    assert groups["typecheck"]
    assert not groups["unknown"]


def test_release_contract_tests_are_owned_by_release_group() -> None:
    for path in (
        "tests/unit/test_release_candidate_provenance.py",
        "tests/unit/test_release_distribution.py",
        "tests/unit/test_release_publication.py",
        "scripts/validate_release_publication.py",
    ):
        groups = _groups(path)
        assert groups["release"], path
        assert groups["windows_native"], path
        assert not groups["unknown"], path


def test_unknown_changes_require_broader_owner_local_validation_only() -> None:
    for path in (
        "src/pixelscope/core/image_document.py",
        "tests/ui/test_something_new.py",
        "scripts/new_shared_maintenance.py",
        ".github/workflows/user-guide.yml",
    ):
        groups = _groups(path)
        assert groups["unknown"], path
        assert groups["local_full_required"], path


def test_shared_runtime_and_ci_policy_changes_require_local_full_validation() -> None:
    for path in (
        "pyproject.toml",
        "requirements/runtime.txt",
        "requirements/dev.txt",
        ".github/workflows/validation.yml",
        "scripts/ci_test_groups.py",
    ):
        groups = _groups(path)
        assert groups["local_full_required"], path


def test_lifecycle_change_requires_local_full_and_is_explicitly_identified() -> None:
    groups = _groups("tests/ui/test_issue81_qt_lifecycle.py")

    assert groups["local_full_required"]
    assert groups["lifecycle"]


def test_rename_considers_both_old_and_new_ownership() -> None:
    groups = classify_paths(
        [ChangedPath("tests/integration/test_new_name.py", "tests/unit/test_raw_reader.py")]
    )

    assert groups["raw"]
    assert groups["local_full_required"]  # unknown destination widens owner/local validation


def test_pr_merge_base_excludes_unrelated_changes_added_to_base(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "ci@example.invalid")
    _git(tmp_path, "config", "user.name", "CI Test")
    _commit(tmp_path, "README.md", "base\n", "base")

    _git(tmp_path, "switch", "-c", "feature")
    head = _commit(tmp_path, "docs/QUALITY.md", "feature docs\n", "feature docs")

    _git(tmp_path, "switch", "main")
    base = _commit(
        tmp_path,
        "scripts/release_contract.py",
        "base-only release change\n",
        "advance main release contract",
    )

    direct_groups = classify_paths(git_changed_paths(tmp_path, base, head))
    pr_groups = classify_paths(
        git_changed_paths(tmp_path, base, head, use_merge_base=True)
    )

    assert direct_groups["release"]
    assert pr_groups["docs"]
    assert not pr_groups["release"]
    assert not pr_groups["windows_native"]


def test_no_change_produces_no_validation_scope() -> None:
    groups = classify_paths([])

    assert not groups["any_validation"]
    assert not groups["local_full_required"]
