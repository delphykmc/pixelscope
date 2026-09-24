"""E5 real MkDocs/offline omission regressions from a full repository copy.

These tests deliberately remove each *declared* guide PNG without touching
Markdown or the manifest. No fake screenshots and no live GUI are involved.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.check_docs import find_problems
from scripts.user_guide_screenshot_hook import on_page_markdown, on_pre_build

ROOT = Path(__file__).resolve().parents[2]
GUIDE = Path("docs/user-guide")
ASSETS = GUIDE / "assets/screenshots"
_MANIFEST = json.loads((ROOT / ASSETS / "manifest.json").read_text(encoding="utf-8"))
_REGISTERED = [row for row in _MANIFEST["screenshots"] if row["placement"] != "planned"]
_REFERENCED = [row for row in _REGISTERED if row["placement"] == "required"]


def _clone_repo(tmp_path: Path) -> Path:
    # Full repository, not a narrowed MkDocs-only tree: check_docs can still
    # enforce unrelated Markdown local links and durable harness references.
    clone = tmp_path / "pixelscope"
    shutil.copytree(
        ROOT,
        clone,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            ".cache",
            "build",
            "dist",
            "site",
            "temp",
        ),
    )
    return clone


@pytest.mark.parametrize("screenshot", _REGISTERED, ids=lambda row: row["id"])
def test_missing_each_declared_png_keeps_full_repo_and_network_blocked_help_valid(
    tmp_path: Path, screenshot: dict
) -> None:
    clone = _clone_repo(tmp_path)
    filename = screenshot["filename"]
    if screenshot["id"] == "single-image":
        # Exercise an absent last-approved image through BOTH whole-repository
        # link checking and the actual network-blocked strict MkDocs build.
        manifest_path = clone / ASSETS / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        row = next(item for item in manifest["screenshots"] if item["id"] == screenshot["id"])
        row["status"] = "approved"
        row["approved"] = {
            "capture_source_sha": "a" * 40,
            "application_version": "0.1.0",
            "comparison_profile_id": "windows-e1-poc-v1",
            "scenario_contract_id": "single_image-v1",
            "image_sha256": hashlib.sha256((clone / ASSETS / filename).read_bytes()).hexdigest(),
            "approval_ref": "https://github.com/example/pull/1#review",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (clone / ASSETS / filename).unlink()
    assert find_problems(clone) == []

    process = subprocess.run(
        [sys.executable, "scripts/check_user_guide_build_offline.py"],
        cwd=clone,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stdout[-2500:] + process.stderr[-2500:]

    # In a generated page the missing marker becomes NO img and NO fallback.
    for page in screenshot["pages"]:
        html = (clone / "site" / Path(page).with_suffix(".html")).read_text(encoding="utf-8")
        assert filename not in html
    assert not (clone / "site" / ASSETS.relative_to(GUIDE) / filename).exists()


def test_all_six_present_declared_topic_images_still_render_with_relative_paths(
    tmp_path: Path,
) -> None:
    clone = _clone_repo(tmp_path)
    assert find_problems(clone) == []
    process = subprocess.run(
        [sys.executable, "scripts/check_user_guide_build_offline.py"],
        cwd=clone,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stdout[-2500:] + process.stderr[-2500:]
    for shot in _REFERENCED:
        for page in shot["pages"]:
            html = (clone / "site" / Path(page).with_suffix(".html")).read_text(encoding="utf-8")
            assert shot["filename"] in html
            assert (clone / "site" / ASSETS.relative_to(GUIDE) / shot["filename"]).is_file()


def test_hook_keeps_source_markers_and_omits_only_absent_declared_png(tmp_path: Path) -> None:
    clone = _clone_repo(tmp_path)
    page = SimpleNamespace(file=SimpleNamespace(src_path="formats/raw.md"))
    config = {"docs_dir": str(clone / GUIDE)}
    marker = "<!-- pixelscope:screenshot raw-profile-dialog -->"
    original = "# RAW\n\n" + marker + "\n\nKeep this explanation.\n"
    on_pre_build(config)
    present = on_page_markdown(original, page=page, config=config, files=None)
    assert marker not in present
    assert "![RAW profile dialog](../assets/screenshots/raw-profile-dialog.png)" in present
    assert "Keep this explanation." in present
    assert original.endswith("Keep this explanation.\n")  # source never rewritten

    (clone / ASSETS / "raw-profile-dialog.png").unlink()
    on_pre_build(config)
    absent = on_page_markdown(original, page=page, config=config, files=None)
    assert marker not in absent and "raw-profile-dialog.png" not in absent
    assert "Keep this explanation." in absent


def test_direct_strict_mkdocs_rejects_corrupt_declared_image(tmp_path: Path) -> None:
    clone = _clone_repo(tmp_path)
    (clone / ASSETS / "raw-profile-dialog.png").write_bytes(b"corrupt")
    process = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict"],
        cwd=clone,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert process.returncode != 0
    assert "Screenshot manifest contract failed" in process.stdout + process.stderr
