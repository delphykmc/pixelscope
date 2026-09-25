"""E8: empty E3 selection skips Qt only when pinned and fail-closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.preflight_ui_screenshot_diff import capture_required, main, write_no_selection_report

BASE = "a" * 40
HEAD = "b" * 40


def _selection(**changes: object) -> dict:
    value = {
        "schema_version": 1,
        "base_sha": BASE,
        "head_sha": HEAD,
        "selected_ids": [],
        "changed_paths": [{"status": "M", "path": "docs/user-guide/index.md"}],
        "selected_screenshots": [],
        "capture_eligible_ids": [],
        "capture_deferred": [],
        "warnings": [],
        "requires_image_review": False,
        "committed_png_changes": [],
        "manifest_review_ids": [],
        "removed_ids": [],
        "target_profile_changed": False,
        "no_selection_reason": "no screenshot-affecting change detected",
    }
    value.update(changes)
    return value


def test_no_impact_skips_gui_but_preserves_pinned_report(tmp_path: Path) -> None:
    selected = _selection()
    assert capture_required(selected, BASE, HEAD) is False
    write_no_selection_report(selected, tmp_path, BASE, HEAD)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "no affected screenshots"
    assert report["base_sha"] == BASE and report["head_sha"] == HEAD
    assert report["selection"] == selected
    assert report["screenshots"] == []
    assert "no affected screenshots" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert capture_required(_selection(no_selection_reason="no changed paths"), BASE, HEAD) is False


@pytest.mark.parametrize(
    "changed",
    [
        {"selected_ids": ["single-image"], "no_selection_reason": None},
        {
            "selected_ids": ["removed-id"],
            "removed_ids": ["removed-id"],
            "no_selection_reason": None,
        },
        {
            "selected_ids": ["planned-id"],
            "requires_image_review": True,
            "no_selection_reason": None,
        },
    ],
)
def test_any_selected_id_runs_e4_even_if_removed_or_deferred(changed: dict) -> None:
    assert capture_required(_selection(**changed), BASE, HEAD) is True


@pytest.mark.parametrize(
    "changed",
    [
        {"requires_image_review": True},
        {"requires_image_review": None},
        {"selected_screenshots": [{"id": "single-image"}]},
        {"capture_eligible_ids": ["single-image"]},
        {"capture_deferred": [{"id": "single-image"}]},
        {"warnings": ["unknown impact"]},
        {"warnings": [None]},
        {"changed_paths": None},
        {"changed_paths": ["not a structured path"]},
        {"committed_png_changes": [{"path": "asset.png"}]},
        {"committed_png_changes": None},
        {"manifest_review_ids": ["single-image"]},
        {"manifest_review_ids": None},
        {"removed_ids": ["single-image"]},
        {"target_profile_changed": True},
        {"no_selection_reason": None},
        {"no_selection_reason": "untrusted"},
        {"selected_ids": None},
        {"warnings": None},
        {"schema_version": 2},
        {"base_sha": HEAD},
        {"head_sha": BASE},
    ],
)
def test_uncertain_or_mismatched_empty_selection_must_fail(changed: dict) -> None:
    with pytest.raises(ValueError):
        capture_required(_selection(**changed), BASE, HEAD)


@pytest.mark.parametrize(
    "field",
    [
        "selected_screenshots",
        "capture_eligible_ids",
        "capture_deferred",
        "requires_image_review",
        "committed_png_changes",
        "manifest_review_ids",
        "removed_ids",
        "target_profile_changed",
    ],
)
def test_missing_e3_impact_field_fails_closed(field: str) -> None:
    selection = _selection()
    del selection[field]
    with pytest.raises(ValueError, match="missing/invalid E3 field"):
        capture_required(selection, BASE, HEAD)


def test_preflight_cli_emits_job_output_and_no_impact_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(json.dumps(_selection()), encoding="utf-8")
    output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--selection",
            str(selection_path),
            "--base",
            BASE,
            "--head",
            HEAD,
            "--output-dir",
            str(tmp_path / "artifact"),
        ],
    )
    assert main() == 0
    assert output.read_text(encoding="utf-8") == "capture_required=false\n"
    assert (tmp_path / "artifact/report.json").exists()


def test_preflight_cli_fail_closed_without_false_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(_selection(warnings=["unknown"])), encoding="utf-8")
    output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--selection",
            str(selection),
            "--base",
            BASE,
            "--head",
            HEAD,
            "--output-dir",
            str(tmp_path / "artifact"),
        ],
    )
    assert main() == 1
    assert not output.exists()
    assert not (tmp_path / "artifact/report.json").exists()
