"""Focused contracts for repository-level CI change classification."""

from __future__ import annotations

from scripts.classify_ci_changes import ChangedPath, classify_paths


def classify(*paths: str) -> dict[str, bool]:
    return classify_paths([ChangedPath(path) for path in paths])


def test_docs_prose_only_wakes_core_docs_validation() -> None:
    groups = classify("docs/user-guide/formats/raw.md")

    assert groups["docs"]
    assert groups["docs_core"]
    assert not groups["screenshots"]
    assert not groups["publication"]
    assert not groups["raw"]
    assert not groups["windows_native"]


def test_raw_source_wakes_only_relevant_native_group() -> None:
    groups = classify("src/pixelscope/io/raw_reader.py")

    assert groups["raw"]
    assert groups["static"]
    assert groups["src_changed"]
    assert groups["windows_native"]
    assert not groups["help_ui"]
    assert not groups["release"]
    assert not groups["yuv"]


def test_yuv_source_and_test_wake_yuv_group() -> None:
    groups = classify(
        "src/pixelscope/app/yuv_input_semantics.py",
        "tests/ui/test_wp_c1_yuv_semantics.py",
    )

    assert groups["yuv"]
    assert groups["windows_native"]
    assert not groups["raw"]


def test_help_and_release_paths_have_separate_ownership() -> None:
    help_groups = classify("src/pixelscope/ui/user_guide_help.py")
    release_groups = classify("scripts/build_release_candidate.py")

    assert help_groups["help_ui"] and not help_groups["release"]
    assert release_groups["release"] and not release_groups["help_ui"]


def test_runtime_contract_change_conservatively_wakes_all_native_groups() -> None:
    groups = classify("requirements/runtime.txt")

    assert groups["help_ui"]
    assert groups["release"]
    assert groups["raw"]
    assert groups["yuv"]
    assert groups["windows_native"]


def test_unrelated_python_change_gets_static_validation_without_native_runner() -> None:
    groups = classify("src/pixelscope/core/metrics.py")

    assert groups["static"]
    assert groups["src_changed"]
    assert groups["any_validation"]
    assert not groups["windows_native"]


def test_rename_checks_both_old_and_new_ownership() -> None:
    groups = classify_paths(
        [
            ChangedPath(
                "src/pixelscope/core/legacy_reader.py",
                old_path="src/pixelscope/io/raw_reader.py",
            )
        ]
    )

    assert groups["raw"]
    assert groups["windows_native"]


def test_ci_workflow_change_runs_policy_without_docs_bundle() -> None:
    groups = classify(".github/workflows/validation.yml")

    assert groups["ci_policy"]
    assert groups["any_validation"]
    assert not groups["docs"]


def test_screenshot_and_publication_paths_are_separate_docs_families() -> None:
    screenshot = classify("docs/user-guide/assets/screenshots/manifest.json")
    publication = classify("scripts/prepare_user_guide_publication.py")

    assert screenshot["docs"] and screenshot["screenshots"]
    assert not screenshot["publication"]
    assert publication["docs"] and publication["publication"]
    assert not publication["screenshots"]


def test_examples_and_pr_template_stay_in_docs_contract() -> None:
    examples = classify("examples/raw_profiles/example_packed_stream_raw10.json")
    template = classify(".github/pull_request_template.md")

    assert examples["docs"] and examples["any_validation"]
    assert template["docs"] and template["any_validation"]
