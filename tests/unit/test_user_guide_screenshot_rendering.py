"""E5 real MkDocs/offline omission regressions from a full repository copy.

These tests deliberately remove each *declared* guide PNG without touching
Markdown or the manifest. No fake screenshots and no live GUI are involved.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.check_docs import find_problems
from scripts.e8_profile import measure_phase
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
    with measure_phase("repository-copytree"):
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
    if os.environ.get("PIXELSCOPE_E8_PROFILE") == "1":
        with measure_phase("repository-copied-file-inventory"):
            files = [path for path in clone.rglob("*") if path.is_file()]
            print(
                "PIXELSCOPE_E8_REPO "
                + json.dumps(
                    {
                        "files": len(files),
                        "bytes": sum(path.stat().st_size for path in files),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    return clone


@pytest.fixture(scope="module")
def _shared_omission_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Clone once; always restore the one removed PNG before the next ID."""
    return _clone_repo(tmp_path_factory.mktemp("screenshot-omission"))


@pytest.mark.parametrize("screenshot", _REGISTERED, ids=lambda row: row["id"])
def test_missing_each_declared_png_keeps_full_repo_links_and_hook_valid(
    _shared_omission_repo: Path, screenshot: dict
) -> None:
    """Fast per-ID contract; expensive strict/offline integration is shared below."""
    clone = _shared_omission_repo
    image = clone / ASSETS / screenshot["filename"]
    with measure_phase("per-id-png-remove", screenshot_id=screenshot["id"]):
        original = image.read_bytes()
        image.unlink()
    try:
        with measure_phase("per-id-check-docs", screenshot_id=screenshot["id"]):
            assert find_problems(clone) == []
        config = {"docs_dir": str(clone / GUIDE)}
        with measure_phase("per-id-pre-build", screenshot_id=screenshot["id"]):
            on_pre_build(config)
        for page in screenshot["pages"]:
            source = (clone / GUIDE / page).read_text(encoding="utf-8")
            with measure_phase("per-id-render-markdown", screenshot_id=screenshot["id"], page=page):
                rendered = on_page_markdown(
                    source,
                    page=SimpleNamespace(file=SimpleNamespace(src_path=page)),
                    config=config,
                    files=None,
                )
            assert screenshot["filename"] not in rendered
            assert f"<!-- pixelscope:screenshot {screenshot['id']} -->" not in rendered
            for other in _REFERENCED:
                if other["id"] != screenshot["id"] and page in other["pages"]:
                    assert other["filename"] in rendered
    finally:
        with measure_phase("per-id-png-restore", screenshot_id=screenshot["id"]):
            image.write_bytes(original)


def test_all_declared_pngs_absent_keeps_real_offline_site_valid(tmp_path: Path) -> None:
    """One full-repo cold-cache build covers every missing declared ID together."""
    clone = _clone_repo(tmp_path)
    with measure_phase("all-absent-remove-pngs"):
        for row in _REGISTERED:
            (clone / ASSETS / row["filename"]).unlink()
    with measure_phase("all-absent-check-docs"):
        assert find_problems(clone) == []
    with measure_phase("all-absent-offline-build-subprocess"):
        process = subprocess.run(
            [sys.executable, "scripts/check_user_guide_build_offline.py"],
            cwd=clone,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if os.environ.get("PIXELSCOPE_E8_PROFILE") == "1":
        print(process.stdout, end="", flush=True)
        print(process.stderr, end="", flush=True)
    assert process.returncode == 0, process.stdout[-2500:] + process.stderr[-2500:]
    for row in _REGISTERED:
        assert not (clone / "site" / ASSETS.relative_to(GUIDE) / row["filename"]).exists()
        for page in row["pages"]:
            html = (clone / "site" / Path(page).with_suffix(".html")).read_text(encoding="utf-8")
            assert row["filename"] not in html


def test_all_present_declared_topic_images_render_with_relative_paths(
    tmp_path: Path,
) -> None:
    clone = _clone_repo(tmp_path)
    with measure_phase("all-present-check-docs"):
        assert find_problems(clone) == []
    with measure_phase("all-present-offline-build-subprocess"):
        process = subprocess.run(
            [sys.executable, "scripts/check_user_guide_build_offline.py"],
            cwd=clone,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if os.environ.get("PIXELSCOPE_E8_PROFILE") == "1":
        print(process.stdout, end="", flush=True)
        print(process.stderr, end="", flush=True)
    assert process.returncode == 0, process.stdout[-2500:] + process.stderr[-2500:]
    present = [shot for shot in _REFERENCED if (clone / ASSETS / shot["filename"]).is_file()]
    for shot in present:
        for page in shot["pages"]:
            html = (clone / "site" / Path(page).with_suffix(".html")).read_text(encoding="utf-8")
            assert shot["filename"] in html
            assert (clone / "site" / ASSETS.relative_to(GUIDE) / shot["filename"]).is_file()


def test_hook_keeps_source_markers_and_omits_only_absent_declared_png(
    _shared_omission_repo: Path,
) -> None:
    # Pure rendering coverage can reuse the full validated clone; do not
    # weaken pre-build's authoritative whole-manifest validation.
    clone = _shared_omission_repo
    page = SimpleNamespace(file=SimpleNamespace(src_path="formats/raw.md"))
    config = {"docs_dir": str(clone / GUIDE)}
    marker = "<!-- pixelscope:screenshot raw-profile-dialog -->"
    original = "# RAW\n\n" + marker + "\n\nKeep this explanation.\n"
    with measure_phase("hook-only-pre-build-present"):
        on_pre_build(config)
    with measure_phase("hook-only-render-present"):
        present = on_page_markdown(original, page=page, config=config, files=None)
    assert marker not in present
    assert "![RAW profile dialog](../assets/screenshots/raw-profile-dialog.png)" in present
    assert "Keep this explanation." in present
    assert original.endswith("Keep this explanation.\n")  # source never rewritten

    image = clone / ASSETS / "raw-profile-dialog.png"
    original_image = image.read_bytes()
    image.unlink()
    try:
        with measure_phase("hook-only-pre-build-absent"):
            on_pre_build(config)
        with measure_phase("hook-only-render-absent"):
            absent = on_page_markdown(original, page=page, config=config, files=None)
        assert marker not in absent and "raw-profile-dialog.png" not in absent
        assert "Keep this explanation." in absent
    finally:
        image.write_bytes(original_image)


def test_direct_strict_mkdocs_rejects_corrupt_declared_image(tmp_path: Path) -> None:
    clone = _clone_repo(tmp_path)
    (clone / ASSETS / "raw-profile-dialog.png").write_bytes(b"corrupt")
    with measure_phase("corrupt-direct-strict-build-subprocess"):
        process = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict"],
            cwd=clone,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if os.environ.get("PIXELSCOPE_E8_PROFILE") == "1":
        print(process.stdout, end="", flush=True)
        print(process.stderr, end="", flush=True)
    assert process.returncode != 0
    assert "Screenshot manifest contract failed" in process.stdout + process.stderr
