"""Qt-free E3 impact selection regressions: source, refs, assets and real Git renames."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from scripts.select_ui_screenshots import (
    ChangedFile,
    git_changed_files,
    parse_name_status_z,
    resolve_sha,
    screenshot_references,
    select_changes,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/user-guide/assets/screenshots/manifest.json"
FULL = "a" * 40
NEXT = "b" * 40


@pytest.fixture
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def report(manifest: dict, *paths: str, old: dict | None = None, read=None) -> dict:
    return select_changes(
        [ChangedFile("M", p) for p in paths],
        old or manifest,
        manifest,
        base_sha=FULL,
        head_sha=NEXT,
        read_at_revision=read,
    )


def test_parse_git_name_status_nul_rename_delete_unicode_and_space() -> None:
    changes = parse_name_status_z(
        b"M\x00src/pixelscope/ui/image_viewer.py\x00"
        b"R100\x00docs/user-guide/assets/screenshots/old image.png\x00"
        b"docs/user-guide/assets/screenshots/new image.png\x00"
        b"D\x00src/pixelscope/io/yuv_reader.py\x00"
    )
    assert changes == [
        ChangedFile("M", "src/pixelscope/ui/image_viewer.py"),
        ChangedFile(
            "R100",
            "docs/user-guide/assets/screenshots/new image.png",
            "docs/user-guide/assets/screenshots/old image.png",
        ),
        ChangedFile("D", "src/pixelscope/io/yuv_reader.py"),
    ]
    assert parse_name_status_z(b"") == []
    with pytest.raises(ValueError, match="truncated"):
        parse_name_status_z(b"M\x00file")
    with pytest.raises(ValueError, match="unsupported"):
        parse_name_status_z(b"U\x00file\x00")


def test_single_feature_owner_and_shared_shell(manifest: dict) -> None:
    scoped = report(manifest, "src/pixelscope/ui/raw_open_dialog.py")
    assert scoped["selected_ids"] == ["raw-profile-dialog"]
    assert scoped["warnings"] == []
    assert scoped["selected_screenshots"][0]["capture_eligible"] is True

    shared = report(manifest, "src/pixelscope/app/main_window.py")
    assert len(shared["selected_ids"]) == 14
    assert "shared-rendering-or-capture-dependency" in shared["changed_paths"][0]["reasons"]
    for path in (
        "src/pixelscope/ui/design_tokens.py",
        "src/pixelscope/assets/icons/pixelscope.svg",
        "requirements/runtime.txt",
        "src/pixelscope/core/image_document.py",
        "scripts/capture_ui_scene.py",
    ):
        assert len(report(manifest, path)["selected_ids"]) == 14


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/pixelscope/io/yuv_reader.py", "yuv-profile-dialog"),
        ("src/pixelscope/core/yuv_difference.py", "difference-analysis"),
        ("src/pixelscope/io/raw_reader.py", "raw-profile-dialog"),
        ("src/pixelscope/core/statistics.py", "statistics-workspace"),
        ("src/pixelscope/remote/iqa_v2_reader.py", "iqa-neutral"),
        ("src/pixelscope/app/yuv_input_semantics.py", "yuv-profile-dialog"),
        ("src/pixelscope/ui/settings_dialog.py", "settings-dialog"),
    ],
)
def test_rendering_beyond_ui_maps_to_correct_surfaces(
    manifest: dict, path: str, expected: str
) -> None:
    result = report(manifest, path)
    assert expected in result["selected_ids"]
    assert result["warnings"] == []


@pytest.mark.parametrize(
    "path",
    [
        "src/pixelscope/ui/new_workspace.py",
        "src/pixelscope/app/new_controller.py",
        "src/pixelscope/io/unknown_pixel_decoder.py",
        "src/pixelscope/core/new_pixel_semantics.py",
        "src/pixelscope/remote/new_renderer.py",
        "src/pixelscope/workers/worker_visual_state.py",
        "scripts/capture_new_scene.py",
    ],
)
def test_unmapped_rendering_source_fails_open(manifest: dict, path: str) -> None:
    selection = report(manifest, path)
    assert len(selection["selected_ids"]) == 14
    assert selection["warnings"] == [f"unmapped-ui-impact: {path}"]


def test_docs_prose_only_and_test_only_do_not_force_capture(manifest: dict) -> None:
    assert report(manifest, "tests/unit/test_core.py")["selected_ids"] == []
    assert report(manifest, "docs/user-guide/features/raw.md")["selected_ids"] == []
    assert report(
        manifest,
        "docs/user-guide/formats/raw.md",
        read=lambda sha, path: "# Same prose-only page in both revisions\\n",
    )["selected_ids"] == []
    assert report(manifest, "docs/ROADMAP.md")["no_selection_reason"] is not None
    old_text = "## Guide\n<!-- pixelscope:screenshot raw-profile-dialog -->\nBody old\n"
    new_text = "## Guide\n<!-- pixelscope:screenshot raw-profile-dialog -->\nBody changed\n"
    def get_text(sha: str, path: str) -> str:
        return old_text if sha == FULL else new_text
    assert report(manifest, "docs/user-guide/formats/raw.md", read=get_text)["selected_ids"] == []


def test_markdown_screenshot_reference_changes_select_declared_ids(manifest: dict) -> None:
    before = "![RAW](../assets/screenshots/raw-profile-dialog.png)\n"
    after = "<!-- pixelscope:screenshot raw-profile-dialog -->\n"
    def get_text(sha: str, path: str) -> str:
        return before if sha == FULL else after
    result = report(manifest, "docs/user-guide/formats/raw.md", read=get_text)
    # Even a literal -> ID-marker migration is a screenshot Markdown change.
    assert result["selected_ids"] == ["raw-profile-dialog"]
    after = "<!-- pixelscope:screenshot yuv-profile-dialog -->\n"
    result = report(
        manifest,
        "docs/user-guide/formats/raw.md",
        read=lambda sha, path: before if sha == FULL else after,
    )
    assert set(result["selected_ids"]) == {"raw-profile-dialog", "yuv-profile-dialog"}
    assert "screenshot-markdown-reference" in result["changed_paths"][0]["reasons"]
    assert screenshot_references("This is unrelated prose.") == set()


def test_changed_image_add_delete_and_rename_are_first_class(manifest: dict) -> None:
    base = "docs/user-guide/assets/screenshots/"
    selection = select_changes(
        [
            ChangedFile("M", base + "single-image.png"),
            ChangedFile("D", base + "plots-floating.png"),
            ChangedFile(
                "R100", base + "difference-analysis.png", base + "histogram-docked.png"
            ),
            ChangedFile("A", base + "unlisted-new.png"),
        ],
        manifest,
        manifest,
        base_sha=FULL,
        head_sha=NEXT,
    )
    assert selection["requires_image_review"]
    assert len(selection["committed_png_changes"]) == 5
    assert len(selection["selected_ids"]) == 14  # unknown PNG name -> all, with warning
    assert any("unmapped-screenshot-asset" in x for x in selection["warnings"])
    exact = report(manifest, base + "raw-profile-dialog.png")
    assert exact["selected_ids"] == ["raw-profile-dialog"]
    assert exact["selected_screenshots"][0]["status"] == "legacy-unverified"
    assert exact["requires_image_review"] is True


def test_manifest_single_id_change_and_shared_profile_change(manifest: dict) -> None:
    previous = copy.deepcopy(manifest)
    manifest["screenshots"][6]["alt"] = "RAW updated"
    assert report(manifest, "docs/user-guide/assets/screenshots/manifest.json", old=previous)[
        "selected_ids"
    ] == ["raw-profile-dialog"]
    manifest["target_capture_profile"] = "new-profile"
    result = report(manifest, "docs/user-guide/assets/screenshots/manifest.json", old=previous)
    assert len(result["selected_ids"]) == 14


def test_screenshot_readme_and_no_changes(manifest: dict) -> None:
    result = report(manifest, "docs/user-guide/assets/screenshots/README.md")
    assert len(result["selected_ids"]) == 14
    empty = select_changes([], manifest, manifest, base_sha=FULL, head_sha=NEXT)
    assert empty["selected_ids"] == []
    assert empty["no_selection_reason"] == "no changed paths"


def test_missing_mapping_must_not_claim_complete(manifest: dict) -> None:
    manifest["screenshots"][0]["source_globs"] = []
    with pytest.raises(ValueError, match="missing E3 source ownership"):
        report(manifest, "src/pixelscope/ui/image_viewer.py")
    manifest["screenshots"][0]["source_globs"] = ["src/pixelscope/ui/image_viewer.py"]
    manifest["impact_ownership_status"] = "e3-pending"
    with pytest.raises(ValueError, match="complete manifest ownership"):
        report(manifest, "src/pixelscope/ui/image_viewer.py")


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_real_git_pinned_rename_deletion_and_new_file(tmp_path: Path, manifest: dict) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "e3@example.invalid")
    _git(tmp_path, "config", "user.name", "E3 test")
    src = tmp_path / "src/pixelscope/ui"
    src.mkdir(parents=True)
    (src / "raw_open_dialog.py").write_text("before\n", encoding="utf-8")
    (src / "settings_dialog.py").write_text("delete\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "mv", "src/pixelscope/ui/raw_open_dialog.py", "src/pixelscope/ui/new_dialog.py")
    (src / "settings_dialog.py").unlink()
    (src / "new_ui_feature.py").write_text("new\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "head")
    head = _git(tmp_path, "rev-parse", "HEAD")
    entries = git_changed_files(tmp_path, resolve_sha(tmp_path, base), resolve_sha(tmp_path, head))
    assert any(
        x.status.startswith("R") and x.old_path.endswith("raw_open_dialog.py")
        for x in entries
    )
    assert any(x.status == "D" for x in entries)
    assert any(x.status == "A" for x in entries)
    selection = select_changes(entries, manifest, manifest, base_sha=base, head_sha=head)
    assert len(selection["selected_ids"]) == 14
    assert any(x.startswith("unmapped-ui-impact:") for x in selection["warnings"])
    with pytest.raises(ValueError, match="40-character"):
        resolve_sha(tmp_path, "HEAD")
