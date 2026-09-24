"""E6 decision inventory is not equivalent to approval or real GUI evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scripts.audit_ui_screenshot_coverage import (
    ASSETS,
    DECISIONS,
    MANIFEST,
    ROOT,
    audit,
    decision_problems,
)


def _fixtures() -> tuple[dict, dict]:
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    decisions = json.loads((ROOT / DECISIONS).read_text(encoding="utf-8"))
    return manifest, decisions


def test_real_e6_entry_is_valid_but_not_falsely_complete() -> None:
    result = audit()
    assert result["errors"] == []
    assert result["complete"] is False
    assert len(result["pending_ids"]) == 14
    strict = audit(require_complete=True)
    assert strict["complete"] is False
    assert any("14 individual owner decisions pending" in error for error in strict["errors"])


def test_each_gap_requires_its_own_record_and_real_owner_decision() -> None:
    manifest, records = _fixtures()
    records["gaps"].pop()
    errors = decision_problems(manifest, records, ROOT / ASSETS)
    assert any("missing individual gaps decision" in error for error in errors)
    records["gaps"].append(copy.deepcopy(records["gaps"][0]))
    assert any("duplicate decision" in error for error in decision_problems(manifest, records, ROOT / ASSETS))


def test_blanket_defer_without_reason_owner_reference_followup_is_rejected() -> None:
    manifest, records = _fixtures()
    for record in records["gaps"]:
        record["decision"] = "deferred"
    errors = decision_problems(manifest, records, ROOT / ASSETS)
    assert sum("owner review reference required" in error for error in errors) == 7
    assert sum("rationale required" in error for error in errors) == 7
    assert sum("future follow-up URL" in error for error in errors) == 7


def test_a_url_does_not_make_unapproved_image_a_promoted_capture() -> None:
    manifest, records = _fixtures()
    item = records["existing"][0]
    item["decision"] = "promoted"
    item["review_ref"] = "https://github.com/owner/repo/pull/100#issuecomment-101"
    errors = decision_problems(manifest, records, ROOT / ASSETS)
    assert any("promoted requires approved manifest" in error for error in errors)


def test_hash_and_external_ref_are_both_bound_to_reviewed_image(tmp_path: Path) -> None:
    manifest, records = _fixtures()
    item = records["existing"][0]
    row = manifest["screenshots"][0]
    item["decision"] = "promoted"
    item["review_ref"] = "https://github.com/owner/repo/pull/100#issuecomment-101"
    image = tmp_path / row["filename"]
    image.write_bytes(b"fixture PNG hash bytes for audit only")
    image_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    row["status"] = "approved"
    row["approved"] = {
        "capture_source_sha": "a" * 40,
        "application_version": "0.1.0",
        "comparison_profile_id": "windows-e1-poc-v1",
        "scenario_contract_id": "single_image-v1",
        "image_sha256": image_hash,
        "approval_ref": item["review_ref"],
    }
    assert decision_problems(manifest, records, tmp_path) == []
    image.write_bytes(b"wrong bytes")
    assert any(
        "approval ref or image bytes disagree" in error
        for error in decision_problems(manifest, records, tmp_path)
    )
    image.write_bytes(b"fixture PNG hash bytes for audit only")
    item["review_ref"] = "https://github.com/owner/repo/pull/100#issuecomment-102"
    assert any(
        "approval ref or image bytes disagree" in error
        for error in decision_problems(manifest, records, tmp_path)
    )


def test_planned_gap_cannot_be_promoted_without_actual_isolated_scene(tmp_path: Path) -> None:
    manifest, records = _fixtures()
    row = manifest["screenshots"][7]
    item = records["gaps"][0]
    item["decision"] = "promoted"
    item["review_ref"] = "https://github.com/owner/repo/pull/100#issuecomment-101"
    image = tmp_path / row["filename"]
    image.write_bytes(b"fixture PNG hash bytes")
    row["status"] = "approved"
    row["approved"] = {
        "capture_source_sha": "b" * 40,
        "application_version": "0.1.0",
        "comparison_profile_id": "windows-e1-poc-v1",
        "scenario_contract_id": "window_overview-v1",
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "approval_ref": item["review_ref"],
    }
    errors = decision_problems(manifest, records, tmp_path)
    assert any("lacks verified real isolated scene" in error for error in errors)
    row["capture_mode"] = "isolated"
    row["placement"] = "required"
    assert decision_problems(manifest, records, tmp_path) == []


def test_per_id_defer_with_explicit_followup_remains_honest() -> None:
    manifest, records = _fixtures()
    item = records["gaps"][5]
    item.update(
        decision="deferred",
        review_ref="https://github.com/owner/repo/pull/100#issuecomment-101",
        reason="Neutral IQA cannot display a real server result without approved fixtures.",
        follow_up="https://github.com/owner/repo/issues/101",
    )
    assert decision_problems(manifest, records, ROOT / ASSETS) == []
    item["decision"] = "retained"
    assert any("invalid decision" in e for e in decision_problems(manifest, records, ROOT / ASSETS))
