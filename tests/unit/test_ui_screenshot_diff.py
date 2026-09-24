"""Qt-free E4 contract tests: never conflate pixel diff and incomparable baselines."""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from scripts.compare_ui_screenshots import (
    compare_pair,
    documentation_relation,
    fingerprint,
    scene_contract,
)
from scripts.run_ui_screenshot_diff import _env, _pinned, _write_report, capture_scene


def _picture(path: Path, changed: bool = False) -> None:
    image = Image.new("RGB", (500, 400))
    image.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(400) for x in range(500)])
    if changed:
        image.putpixel((10, 20), (0, 0, 0))
    image.save(path)


@pytest.fixture
def captures(tmp_path: Path):
    base, head = tmp_path / "base.png", tmp_path / "head.png"
    _picture(base)
    _picture(head)
    meta = {
        "scenario": "single_image",
        "capture_profile": "windows-e1-poc-v1",
        "python": "3.10.21",
        "qt": "6.4.2",
        "pyside6": "6.4.2",
        "pyqtgraph": "0.13.7",
        "fixture_sha256": "a" * 64,
        "source_sha": "b" * 40,
        "application_version": "0.1.0",
        "geometry": {
            "logical_widget": [500, 400],
            "pixel_png": [500, 400],
            "device_pixel_ratio": 1.0,
        },
        "screen": {
            "logical_dpi": 96.0,
            "physical_dpi": 96.0,
            "device_pixel_ratio": 1.0,
            "name": "Windows",
        },
    }
    record = {"scenario": "single_image", "viewport": {"width": 500, "height": 400}}
    return base, head, meta, record, tmp_path / "comparison"


def _compare(captures, *, before=None, after=None, old=None, new=None, left="a", right="a"):
    base, head, meta, record, output = captures
    return compare_pair(
        base,
        head,
        before or meta,
        after or meta,
        {"font": "Default"},
        {"font": "Default"},
        left,
        right,
        old or record,
        new or record,
        output,
    )


def test_identical_decoded_pixels_ignore_source_sha_and_app_version(captures) -> None:
    base, head, meta, record, output = captures
    after = copy.deepcopy(meta)
    after["source_sha"] = "c" * 40
    after["application_version"] = "0.1.1"
    after["screen"]["name"] = "nondeterministic machine ID"
    result = _compare(captures, after=after)
    assert result["status"] == "UNCHANGED"
    assert result["changed_pixel_fraction"] == 0
    assert not output.exists()


def test_changed_pixels_are_not_silenced_by_small_diagnostic_fraction(captures) -> None:
    base, head, meta, record, output = captures
    _picture(head, changed=True)
    result = _compare(captures)
    assert result["status"] == "CHANGED"
    assert 0 < result["changed_pixel_fraction"] < 0.01
    assert result["max_channel_error"] > 0
    assert (output / "side-by-side.png").is_file()
    assert (output / "diff.png").is_file()


def test_geometry_change_reports_changed_dimensions_not_identical(captures) -> None:
    base, head, meta, record, output = captures
    Image.new("RGB", (600, 400), (0, 50, 100)).save(head)
    result = _compare(captures)
    assert result["status"] == "CHANGED"
    assert result["dimension_changed"] is True
    assert result["base_size"] == [500, 400]
    assert result["head_size"] == [600, 400]
    assert result["diagnostic_note"] == "padded visual artifact; dimensions differ"
    side_by_side = output / "side-by-side.png"
    diff = output / "diff.png"
    assert side_by_side.is_file() and diff.is_file()
    with Image.open(side_by_side) as side:
        assert side.size == (1200, 400)
    with Image.open(diff) as delta:
        assert delta.size == (600, 400)


@pytest.mark.parametrize("field", ["fixture", "scenario", "viewport", "scene_contract"])
def test_incompatible_inputs_do_not_get_pixel_diffs(captures, field: str) -> None:
    base, head, meta, record, output = captures
    after, newer = copy.deepcopy(meta), copy.deepcopy(record)
    left, right = "a", "a"
    if field == "fixture":
        after["fixture_sha256"] = "c" * 64
    elif field == "scenario":
        newer["scenario"] = "different_scene"
    elif field == "viewport":
        newer["viewport"]["width"] = 600
    else:
        right = "builder changed"
    result = _compare(captures, after=after, new=newer, left=left, right=right)
    assert result["status"] == "BASELINE_INCOMPATIBLE"
    assert not output.exists()


@pytest.mark.parametrize("field", ["qt", "dpi", "font"])
def test_runtime_or_renderer_mismatch_does_not_get_pixel_diffs(captures, field: str) -> None:
    base, head, meta, record, output = captures
    after = copy.deepcopy(meta)
    first_env, second_env = {"font": "Default"}, {"font": "Default"}
    if field == "qt":
        after["qt"] = "6.5.0"
    elif field == "dpi":
        after["screen"]["logical_dpi"] = 120.0
    else:
        second_env = {"font": "Different"}
    result = compare_pair(
        base,
        head,
        meta,
        after,
        first_env,
        second_env,
        "a",
        "a",
        record,
        record,
        output,
    )
    assert result["status"] == "ENVIRONMENT_MISMATCH"
    assert not output.exists()


def test_capture_fingerprint_requires_geometry_and_probe(captures) -> None:
    _, _, meta, _, _ = captures
    with pytest.raises(ValueError, match="environment probe"):
        fingerprint(meta, {})
    bad = copy.deepcopy(meta)
    bad.pop("screen")
    with pytest.raises(ValueError, match="geometry"):
        fingerprint(bad, {"font": "Default"})


def test_scene_ast_ignores_whitespace_but_tracks_behavior(tmp_path: Path) -> None:
    script = tmp_path / "scripts/capture_ui_scene.py"
    script.parent.mkdir()
    script.write_text("def _single_image(app):\n    return 1\n", encoding="utf-8")
    baseline = scene_contract(tmp_path, "single_image")
    script.write_text("def _single_image( app ):\n  return 1  # same AST\n", encoding="utf-8")
    assert scene_contract(tmp_path, "single_image") == baseline
    script.write_text("def _single_image(app):\n    return 2\n", encoding="utf-8")
    assert scene_contract(tmp_path, "single_image") != baseline
    with pytest.raises(ValueError, match="unregistered scene"):
        scene_contract(tmp_path, "planned_scene")


def test_legacy_pixel_relation_is_review_debt_without_artifact_side_effect(
    tmp_path: Path, captures
) -> None:
    _, head, _, _, _ = captures
    asset = tmp_path / "docs/user-guide/assets/screenshots"
    asset.mkdir(parents=True)
    record = {
        "filename": "single-image.png",
        "status": "legacy-unverified",
        "approved": None,
    }
    assert documentation_relation(tmp_path, record, head)["state"] == "MISSING"
    _picture(asset / "single-image.png", changed=True)
    relation = documentation_relation(tmp_path, record, head)
    assert relation["state"] == "DIFFERENT_PIXELS_REVIEW"
    assert relation["provenance"] == "legacy-unverified"
    assert not (Path.cwd() / "__no_diff_artifacts__").exists()


def test_failed_native_child_is_capture_failed_not_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import run_ui_screenshot_diff as runner

    monkeypatch.setattr(
        runner,
        "_execute",
        lambda *_args: subprocess.CompletedProcess([], 3221225477, "", "native crash"),
    )
    meta, evidence = capture_scene(tmp_path, "a" * 40, "single_image", tmp_path / "out")
    assert meta is None
    assert evidence["exit_code"] == 3221225477
    assert evidence["failure"] == "ValueError"


def test_pinned_sha_rejects_wrong_checkout(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "e4@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "E4"], check=True)
    (tmp_path / "file.txt").write_text("main", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "first"], check=True)
    sha = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    _pinned(tmp_path, sha)
    with pytest.raises(ValueError, match="immutable"):
        _pinned(tmp_path, "HEAD")


def test_offscreen_is_not_a_real_windows_gui(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    with pytest.raises(ValueError, match="offscreen"):
        _env(tmp_path)


def test_no_affected_scenes_still_emit_inspectable_report(tmp_path: Path) -> None:
    report = {
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "status": "no affected screenshots",
        "screenshots": [],
        "warnings": [],
    }
    _write_report(tmp_path, report)
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["status"] == (
        "no affected screenshots"
    )
    assert "no affected screenshots" in (tmp_path / "summary.md").read_text(encoding="utf-8")
