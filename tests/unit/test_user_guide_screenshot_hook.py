from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.user_guide_screenshot_hook import on_page_markdown


def _write_manifest(docs_root: Path) -> None:
    assets = docs_root / "assets/screenshots"
    assets.mkdir(parents=True)
    screenshot = {
        "id": "raw-profile-dialog",
        "placement": "required",
        "pages": ["formats/raw.md"],
        "filename": "raw-profile-dialog.png",
        "alt": "RAW profile dialog",
    }
    manifest = {"screenshots": [screenshot]}
    payload = json.dumps(manifest)
    (assets / "manifest.json").write_text(payload, encoding="utf-8")


def _page(path: str = "formats/raw.md") -> object:
    return SimpleNamespace(file=SimpleNamespace(src_path=path))


def test_page_markdown_expands_present_declared_screenshot(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs/user-guide"
    _write_manifest(docs_root)
    image = docs_root / "assets/screenshots/raw-profile-dialog.png"
    image.write_bytes(b"png")
    marker = "<!-- pixelscope:screenshot raw-profile-dialog -->"
    source = f"# RAW\n\n{marker}\n\nKeep this explanation.\n"

    rendered = on_page_markdown(
        source,
        page=_page(),
        config={"docs_dir": str(docs_root)},
        files=None,
    )

    expected = "![RAW profile dialog](../assets/screenshots/raw-profile-dialog.png)"
    assert marker not in rendered
    assert expected in rendered
    assert "Keep this explanation." in rendered
    assert source.endswith("Keep this explanation.\n")


def test_page_markdown_omits_missing_declared_screenshot(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs/user-guide"
    _write_manifest(docs_root)
    marker = "<!-- pixelscope:screenshot raw-profile-dialog -->"
    source = f"Before\n\n{marker}\n\nAfter\n"

    rendered = on_page_markdown(
        source,
        page=_page(),
        config={"docs_dir": str(docs_root)},
        files=None,
    )

    assert "raw-profile-dialog" not in rendered
    assert "raw-profile-dialog.png" not in rendered
    assert "Before" in rendered and "After" in rendered


def test_page_markdown_rejects_marker_on_wrong_page(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs/user-guide"
    _write_manifest(docs_root)
    marker = "<!-- pixelscope:screenshot raw-profile-dialog -->"
    error = "invalid screenshot marker: raw-profile-dialog"

    with pytest.raises(ValueError, match=error):
        on_page_markdown(
            marker,
            page=_page("features/image-view.md"),
            config={"docs_dir": str(docs_root)},
            files=None,
        )
