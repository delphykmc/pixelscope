"""Issue #156 U7: classify Enterprise IQA changes without hosted native Qt."""

from __future__ import annotations

from scripts.classify_ci_changes import ChangedPath, classify_paths


def _groups(path: str) -> dict[str, bool]:
    return classify_paths([ChangedPath(path)])


def test_handoff_iqa_source_requires_owner_local_but_no_hosted_ui() -> None:
    flags = _groups("src/pixelscope_enterprise/iqa/analysis_window.py")
    assert flags["unknown"]
    assert flags["local_full_required"]
    assert flags["typecheck"]
    assert not flags["windows_native"]
    assert not flags["local_ui_required"]


def test_handoff_iqa_native_test_is_unknown_and_not_hosted() -> None:
    flags = _groups("tests/enterprise/iqa/test_iqa_ux3c_delivery.py")
    assert flags["unknown"]
    assert flags["local_full_required"]
    assert not flags["local_ui_required"]
    assert not flags["windows_native"]
    assert not flags["release"]


def test_handoff_iqa_docs_only_change_selects_docs_not_local_full() -> None:
    flags = _groups("docs/enterprise/iqa/IQA_U7_VALIDATION_MATRIX.md")
    assert flags["docs"]
    assert flags["any_validation"]
    assert not flags["unknown"]
    assert not flags["local_full_required"]
    assert not flags["windows_native"]


def test_handoff_manifest_only_change_does_not_trigger_existing_validation() -> None:
    flags = _groups("enterprise/iqa/handoff_manifest.py")
    assert not flags["any_validation"]
    assert not flags["unknown"]
    assert not flags["local_full_required"]
    assert not flags["windows_native"]


def test_handoff_manifest_and_native_test_combination_remains_owner_local() -> None:
    flags = classify_paths(
        [
            ChangedPath("enterprise/iqa/handoff_manifest.py"),
            ChangedPath("tests/enterprise/iqa/test_handoff_manifest.py"),
        ]
    )
    assert flags["unknown"]
    assert flags["local_full_required"]
    assert not flags["windows_native"]
