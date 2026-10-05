from scripts.classify_ci_changes import ChangedPath, classify_paths


def _groups(*paths: str) -> dict[str, bool]:
    return classify_paths([ChangedPath(path) for path in paths])


def test_docs_only_change_stays_out_of_native_and_full_validation() -> None:
    groups = _groups("docs/QUALITY.md", "tests/integration/test_ui_screenshot_git_history.py")

    assert groups["docs"]
    assert not groups["windows_native"]
    assert not groups["full"]
    assert not groups["unknown"]


def test_issue_113_profile_policy_is_documentation_owned() -> None:
    groups = _groups(
        "scripts/profile_validation_tree.py",
        "tests/unit/test_profile_validation_tree.py",
        "tests/integration/test_user_guide_screenshot_rendering.py",
    )

    assert groups["docs"]
    assert not groups["full"]


def test_help_raw_yuv_and_release_paths_select_focused_windows_groups() -> None:
    groups = _groups(
        "src/pixelscope/ui/user_guide_help.py",
        "src/pixelscope/io/raw_reader.py",
        "tests/unit/test_yuv_semantics.py",
        "scripts/build_release_candidate.py",
    )

    assert groups["help_ui"]
    assert groups["raw"]
    assert groups["yuv"]
    assert groups["release"]
    assert groups["windows_native"]
    assert groups["typecheck"]
    assert not groups["full"]


def test_unknown_source_test_script_and_workflow_changes_fail_wide() -> None:
    for path in (
        "src/pixelscope/core/image_document.py",
        "tests/ui/test_something_new.py",
        "scripts/new_shared_maintenance.py",
        ".github/workflows/user-guide.yml",
    ):
        groups = _groups(path)
        assert groups["unknown"], path
        assert groups["full"], path


def test_shared_runtime_and_ci_policy_changes_require_full_validation() -> None:
    for path in (
        "pyproject.toml",
        "requirements/runtime.txt",
        "requirements/dev.txt",
        ".github/workflows/validation.yml",
        "scripts/ci_test_groups.py",
    ):
        groups = _groups(path)
        assert groups["full"], path


def test_lifecycle_change_is_full_and_explicitly_identified() -> None:
    groups = _groups("tests/ui/test_issue81_qt_lifecycle.py")

    assert groups["full"]
    assert groups["lifecycle"]


def test_rename_considers_both_old_and_new_ownership() -> None:
    groups = classify_paths(
        [ChangedPath("tests/integration/test_new_name.py", "tests/unit/test_raw_reader.py")]
    )

    assert groups["raw"]
    assert groups["full"]  # the new unknown destination conservatively widens scope


def test_no_change_produces_no_validation_scope() -> None:
    groups = classify_paths([])

    assert not groups["any_validation"]
    assert not groups["full"]
