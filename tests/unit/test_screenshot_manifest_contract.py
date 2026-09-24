"""E2 screenshot inventory tests. No Qt, Pillow, network or application import."""

from __future__ import annotations

import copy
import json
import struct
import zlib
from pathlib import Path

import pytest
from scripts.check_screenshot_manifest import find_problems, png_problems

ROOT = Path(__file__).resolve().parents[2]
ASSET = Path("docs/user-guide/assets/screenshots")
GUIDE = Path("docs/user-guide")


def _png(path: Path, *, color: int = 2, interlace: int = 0) -> None:
    """Write a tiny valid RGB PNG with stdlib to exercise real CRC/IDAT checks."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"\x00" + b"\x80\x40\x10" * 2
    raw += b"\x00" + b"\x20\x80\x40" * 2
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, color, 0, 0, interlace))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Construct the full E2 contract from the real versioned inventory."""
    document = json.loads((ROOT / ASSET / "manifest.json").read_text(encoding="utf-8"))
    assets = tmp_path / ASSET
    assets.mkdir(parents=True)
    (assets / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "capture_ui_scene.py").write_text(
        'BUILDERS = {"single_image": object(), "raw_profile_dialog": object()}\n',
        encoding="utf-8",
    )
    legacy = [s["legacy_output"] for s in document["screenshots"] if s["capture_mode"] != "planned"]
    legacy += document["diagnostic_legacy_outputs"]
    (scripts / "capture_ui_review.py").write_text(
        "OUTPUTS = [" + ", ".join(repr(name) for name in legacy) + "]\n",
        encoding="utf-8",
    )
    for screenshot in document["screenshots"]:
        for page in screenshot["pages"]:
            destination = tmp_path / GUIDE / page
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.write_text("# Page\n", encoding="utf-8")
            if screenshot["placement"] == "legacy-literal":
                path = "../assets/screenshots/" + screenshot["filename"]
                with destination.open("a", encoding="utf-8") as handle:
                    handle.write(f"![{screenshot['alt']}]({path})\n")
        if screenshot["capture_mode"] != "planned":
            _png(assets / screenshot["filename"])
    return tmp_path


def _modify(root: Path, modifier: object) -> None:
    manifest = root / ASSET / "manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    modifier(value)  # type: ignore[operator]
    manifest.write_text(json.dumps(value), encoding="utf-8")


def test_checked_in_manifest_and_legacy_assets_are_consistent() -> None:
    assert find_problems(ROOT) == []


def test_fixture_manifest_and_qt_free_registry_valid(repo: Path) -> None:
    assert find_problems(repo) == []


def test_missing_or_corrupted_legacy_png_fails_before_e5(repo: Path) -> None:
    image = repo / ASSET / "single-image.png"
    image.unlink()
    assert any("legacy literal/unreferenced PNG is missing" in e for e in find_problems(repo))
    _png(image)
    damaged = bytearray(image.read_bytes())
    damaged[-8] ^= 1
    image.write_bytes(damaged)
    assert any("PNG chunk CRC mismatch" in e for e in find_problems(repo))
    image.write_bytes(b"not a PNG")
    assert png_problems(image) == ["invalid PNG signature"]


def test_unknown_duplicate_and_orphan_guide_assets_fail(repo: Path) -> None:
    image = repo / ASSET / "unknown.png"
    _png(image)
    assert any("unexpected screenshot PNG" in e for e in find_problems(repo))
    image.unlink()
    (repo / GUIDE / "features/image-view.md").write_text(
        "# Page\n<!-- pixelscope:screenshot missing-id -->\n", encoding="utf-8"
    )
    errors = find_problems(repo)
    assert any("unknown screenshot ID" in e for e in errors)
    assert any("missing required screenshot reference" in e for e in errors)
    _modify(
        repo,
        lambda m: m["screenshots"].append(copy.deepcopy(m["screenshots"][0])),
    )
    assert any("duplicate screenshot ID" in e for e in find_problems(repo))


def test_missing_page_and_stale_literal_mapping_fail(repo: Path) -> None:
    (repo / GUIDE / "features/difference.md").unlink()
    assert any("invalid or missing declared page" in e for e in find_problems(repo))
    replacement = repo / GUIDE / "features/difference.md"
    replacement.write_text(
        "# Page\n![old](../assets/screenshots/difference-analysis.png)\n",
        encoding="utf-8",
    )
    _modify(
        repo,
        lambda m: m["screenshots"][2].update(pages=["features/image-view.md"]),
    )
    errors = find_problems(repo)
    assert any("screenshot literal not declared for page" in e for e in errors)


def test_unregistered_scene_and_unaccounted_manual_output_fail(repo: Path) -> None:
    _modify(repo, lambda m: m["screenshots"][0].update(scenario="does_not_exist"))
    assert any("no isolated real-UI builder" in e for e in find_problems(repo))
    _modify(
        repo,
        lambda m: m.update(diagnostic_legacy_outputs=["empty_state.png"]),
    )
    assert any("manual capture outputs not classified" in e for e in find_problems(repo))


def test_planned_image_does_not_fabricate_capture_or_provenance(repo: Path) -> None:
    _png(repo / ASSET / "iqa-neutral.png")
    assert any("planned scene has an unexpected committed PNG" in e for e in find_problems(repo))
    (repo / ASSET / "iqa-neutral.png").unlink()
    _modify(
        repo,
        lambda m: m["screenshots"][12].update(
            status="approved", approved={"approval_commit": "future"}
        ),
    )
    errors = find_problems(repo)
    assert any("planned placement needs planned capture/status" in e for e in errors)
    assert any("invalid approved provenance fields" in e for e in errors)


def test_approved_hash_and_e3_ownership_gate(repo: Path) -> None:
    import hashlib

    image = repo / ASSET / "single-image.png"
    approved = {
        "capture_source_sha": "a" * 40,
        "application_version": "0.1.0",
        "comparison_profile_id": "windows-e1-poc-v1",
        "scenario_contract_id": "single_image-v1",
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "approval_ref": "https://github.com/example/pull/1#review",
    }
    _modify(
        repo,
        lambda m: m["screenshots"][0].update(status="approved", approved=approved),
    )
    assert find_problems(repo) == []
    _png(repo / ASSET / "single-image.png")
    # The same deterministic bytes are still valid; different bytes are not.
    image.write_bytes(image.read_bytes() + b"extra")
    assert any("PNG missing IEND" in e or "hash mismatch" in e for e in find_problems(repo))
    _modify(repo, lambda m: m.update(impact_ownership_status="complete"))
    assert any("E3-complete impact ownership requires globs" in e for e in find_problems(repo))


def test_malformed_marker_and_swapped_legacy_output_are_detected(repo: Path) -> None:
    page = repo / GUIDE / "features/image-view.md"
    page.write_text(
        "# Page\n![single](../assets/screenshots/single-image.png)\n"
        "<!-- pixelscope:screenshot single-image\nnext paragraph\n",
        encoding="utf-8",
    )
    assert any("malformed screenshot marker" in e for e in find_problems(repo))
    page.write_text(
        "# Page\n![single](../assets/screenshots/single-image.png)\n", encoding="utf-8"
    )
    _modify(repo, lambda m: m["screenshots"][0].update(legacy_output="histogram_docked.png"))
    assert any("no matching output" in e for e in find_problems(repo))


def test_planned_scene_can_become_new_isolated_without_manual_capture(repo: Path) -> None:
    scene_source = repo / "scripts/capture_ui_scene.py"
    scene_source.write_text(
        'BUILDERS = {"single_image": object(), "raw_profile_dialog": object(), '
        '"window_overview": object()}\n',
        encoding="utf-8",
    )
    _modify(
        repo,
        lambda m: m["screenshots"][7].update(
            capture_mode="isolated", placement="required", status="capture-ready"
        ),
    )
    page = repo / GUIDE / "features/image-view.md"
    with page.open("a", encoding="utf-8") as handle:
        handle.write("<!-- pixelscope:screenshot window-overview -->\n")
    assert find_problems(repo) == []

    # A new isolated scene may be unapproved and missing, but must not commit
    # its candidate PNG as approved documentation without a provenance review.
    _png(repo / ASSET / "window-overview.png")
    assert any("unapproved capture-ready PNG" in e for e in find_problems(repo))
    (repo / ASSET / "window-overview.png").unlink()

    # Historical outputs must never become unowned while adding new builders.
    _modify(
        repo,
        lambda m: m["screenshots"][0].pop("legacy_output"),
    )
    assert any("legacy scene missing historical manual output" in e for e in find_problems(repo))


def test_diagnostic_and_guide_manual_capture_ownership_must_not_overlap(repo: Path) -> None:
    _modify(
        repo,
        lambda m: m["diagnostic_legacy_outputs"].append("single_image.png"),
    )
    assert any(
        "manual output declared as both guide screenshot and diagnostic" in e
        for e in find_problems(repo)
    )


@pytest.mark.parametrize(
    ("color", "interlace"),
    [(3, 0), (2, 1)],
)
def test_crc_valid_unsupported_png_encoding_fails(
    tmp_path: Path, color: int, interlace: int
) -> None:
    png = tmp_path / "invalid.png"
    _png(png, color=color, interlace=interlace)
    assert png_problems(png) == [
        "unsupported PNG encoding: expected non-interlaced 8-bit RGB/RGBA"
    ]


def test_target_profile_is_not_historical_capture_provenance(repo: Path) -> None:
    _modify(repo, lambda m: m.update(target_capture_profile=""))
    assert any("target_capture_profile is required" in e for e in find_problems(repo))
