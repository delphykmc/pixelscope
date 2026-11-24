from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from scripts import refresh_user_guide_screenshots as refresh


def test_capture_environment_prioritizes_reviewed_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "other-checkout")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    env = refresh.capture_environment()
    assert env["PYTHONPATH"].split(os.pathsep) == [str(refresh.ROOT / "src"), "other-checkout"]
    assert "QT_QPA_PLATFORM" not in env
    assert env["QT_SCALE_FACTOR"] == "1"
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_resume_requires_matching_successful_process_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = tmp_path / "scene.png"
    result = {"image_sha256": "a" * 64}
    monkeypatch.setattr(refresh, "validate_row", lambda *args: result)
    marker = png.with_suffix(".validated.json")
    with pytest.raises(FileNotFoundError):
        refresh.verified_row({}, png, "source", "profile")
    for source, digest, code in (
        ("old", "a" * 64, 0),
        ("source", "b" * 64, 0),
        ("source", "a" * 64, 1),
    ):
        marker.write_text(
            json.dumps({"source_sha": source, "image_sha256": digest, "process_exit": code})
        )
        with pytest.raises(ValueError, match="successful child-process"):
            refresh.verified_row({}, png, "source", "profile")
    marker.write_text(
        json.dumps({"source_sha": "source", "image_sha256": "a" * 64, "process_exit": 0})
    )
    assert refresh.verified_row({}, png, "source", "profile") == result


def test_candidate_rejects_changed_fixture_and_unrepeatable_pixels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {"target_capture_profile": "profile", "screenshots": [{"id": "scene"}]}
    monkeypatch.setattr(
        refresh, "verified_row", lambda row, path, *args: {"fixture_sha256": str(path.parent)}
    )
    with pytest.raises(ValueError, match="fixture changed"):
        refresh.candidate_rows(tmp_path, manifest, "source")
    monkeypatch.setattr(refresh, "verified_row", lambda *args: {"fixture_sha256": "fixture"})
    monkeypatch.setattr(refresh, "changed_fraction", lambda *args: 0.02)
    with pytest.raises(ValueError, match="repeatability exceeded"):
        refresh.candidate_rows(tmp_path, manifest, "source")
    monkeypatch.setattr(refresh, "changed_fraction", lambda *args: 0)
    assert refresh.candidate_rows(tmp_path, manifest, "source") == [{"fixture_sha256": "fixture"}]
