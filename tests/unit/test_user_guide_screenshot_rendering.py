"""E5 real MkDocs/offline omission regressions from a full repository copy.

These tests deliberately remove each *declared* guide PNG without touching
Markdown or the manifest. No fake screenshots and no live GUI are involved.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
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


def _assert_clean_repo(clone: Path) -> None:
    """The shared clone may not retain generated site/cache, PNG or source edits."""
    assert not (clone / "site").exists()
    assert not (clone / ".cache/plugin/privacy").exists()
    for shot in _REGISTERED:
        image = clone / ASSETS / shot["filename"]
        assert image.is_file(), f"unrestored screenshot: {shot['id']}"
        assert hashlib.sha256(image.read_bytes()).hexdigest() == shot["approved"][
            "image_sha256"
        ], f"modified approved screenshot: {shot['id']}"
    for page in {name for shot in _REGISTERED for name in shot["pages"]}:
        source = GUIDE / page
        assert (clone / source).read_bytes() == (ROOT / source).read_bytes(), (
            f"unrestored guide Markdown: {page}"
        )


@pytest.fixture
def _clean_repo(_shared_omission_repo: Path) -> Iterator[Path]:
    """Before/after isolation for sequential shared-clone unit/integration tests."""
    _assert_clean_repo(_shared_omission_repo)
    yield _shared_omission_repo
    _assert_clean_repo(_shared_omission_repo)


@contextmanager
def _without_png(image: Path) -> Iterator[None]:
    original = image.read_bytes()
    image.unlink()
    try:
        yield
    finally:
        image.write_bytes(original)


@contextmanager
def _replaced_png(image: Path, payload: bytes) -> Iterator[None]:
    original = image.read_bytes()
    image.write_bytes(payload)
    try:
        yield
    finally:
        image.write_bytes(original)


def _clear_generated_site(clone: Path) -> None:
    shutil.rmtree(clone / "site", ignore_errors=True)
    shutil.rmtree(clone / ".cache/plugin/privacy", ignore_errors=True)


@pytest.mark.parametrize("screenshot", _REGISTERED, ids=lambda row: row["id"])
def test_missing_each_declared_png_keeps_full_repo_links_and_hook_valid(
    _clean_repo: Path, screenshot: dict
) -> None:
    """Fast per-ID contract; expensive strict/offline integration is shared below."""
    clone = _clean_repo
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


def test_all_declared_pngs_absent_keeps_real_offline_site_valid(_clean_repo: Path) -> None:
    """One cold-cache build; restore each of the 14 approved PNGs on any failure."""
    clone = _clean_repo
    try:
        with ExitStack() as missing:
            with measure_phase("all-absent-remove-pngs"):
                for row in _REGISTERED:
                    missing.enter_context(_without_png(clone / ASSETS / row["filename"]))
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
                    html = (clone / "site" / Path(page).with_suffix(".html")).read_text(
                        encoding="utf-8"
                    )
                    assert row["filename"] not in html
    finally:
        _clear_generated_site(clone)


def test_all_present_declared_topic_images_render_with_relative_paths(
    _clean_repo: Path,
) -> None:
    clone = _clean_repo
    try:
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
                html = (clone / "site" / Path(page).with_suffix(".html")).read_text(
                    encoding="utf-8"
                )
                assert shot["filename"] in html
                assert (clone / "site" / ASSETS.relative_to(GUIDE) / shot["filename"]).is_file()
    finally:
        _clear_generated_site(clone)


def test_hook_keeps_source_markers_and_omits_only_absent_declared_png(
    _clean_repo: Path,
) -> None:
    # Pure rendering coverage can reuse the full validated clone; do not
    # weaken pre-build's authoritative whole-manifest validation.
    clone = _clean_repo
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

    with _without_png(clone / ASSETS / "raw-profile-dialog.png"):
        with measure_phase("hook-only-pre-build-absent"):
            on_pre_build(config)
        with measure_phase("hook-only-render-absent"):
            absent = on_page_markdown(original, page=page, config=config, files=None)
        assert marker not in absent and "raw-profile-dialog.png" not in absent
        assert "Keep this explanation." in absent


def test_direct_strict_mkdocs_rejects_corrupt_declared_image(_clean_repo: Path) -> None:
    clone = _clean_repo
    try:
        with _replaced_png(clone / ASSETS / "raw-profile-dialog.png", b"corrupt"):
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
    finally:
        _clear_generated_site(clone)


def test_unrelated_link_still_fails_when_declared_png_is_missing(_clean_repo: Path) -> None:
    """A missing declared image may not exempt an unrelated broken Markdown link."""
    clone = _clean_repo
    image = clone / ASSETS / "single-image.png"
    guide_page = clone / GUIDE / "features/image-view.md"
    original = guide_page.read_bytes()
    with _without_png(image):
        try:
            guide_page.write_bytes(
                original
                + b"\\n[E8 intentionally broken local link](../reference/__e8_missing__.md)\\n"
            )
            problems = find_problems(clone)
            assert any(
                "broken local link" in problem and "__e8_missing__.md" in problem
                for problem in problems
            )
        finally:
            guide_page.write_bytes(original)


def test_png_recovery_after_unexpected_failure(_clean_repo: Path) -> None:
    """The shared clone survives mid-test errors without changing approved bytes."""
    image = _clean_repo / ASSETS / "raw-profile-dialog.png"
    original_sha = hashlib.sha256(image.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="intentional interruption"):
        with _without_png(image):
            assert not image.exists()
            raise RuntimeError("intentional interruption")
    assert hashlib.sha256(image.read_bytes()).hexdigest() == original_sha
