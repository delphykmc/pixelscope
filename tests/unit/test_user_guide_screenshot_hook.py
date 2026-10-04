from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.user_guide_screenshot_hook import on_page_markdown


def _write_manifest(docs_root: Path) -> None:
    assets = docs_root / "assets/screenshots"
    assets.mkdir(parents=True)
    manifest = {
        "screenshots": [
            {
                "id": "raw-profile-dialog",
                "placement": "required",
                "pages": ["formats/raw.md"],
                "filename": "raw-profile-dialog.png",
                "alt": "RAW profile dialog",
            }
        ]
    }
    (assets / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _page(path: str = "formats/raw.md") -> object:
    return SimpleNamespace(file=SimpleNamespace(src_path=path))


def test_page_markdown_expands_present_declared_screenshot(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs/user-guide"
    _write_manifest(docs_root)
    (docs_root / "assets/screenshots/raw-profile-dialog.png").write_bytes(b"png")
    source = (
        "# RAW\n\n<!-- pixelscope:screenshot raw-profile-dialog -->\n\n"
        "Keep this explanation.\n"
    )

    rendered = on_page_markdown(
        source,
        page=_page(),
        config={"docs_dir": str(docs_root)},
        files=None,
    )

    assert "<!-- pixelscope:screenshot raw-profile-dialog -->" not in rendered
    assert "![RAW profile dialog](../assets/screenshots/raw-profile-dialog.png)" in rendered
    assert "Keep this explanation." in rendered
    assert source.endswith("Keep this explanation.\n")


def test_page_markdown_omits_missing_declared_screenshot(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs/user-guide"
    _write_manifest(docs_root)
    source = "Before\n\n<!-- pixelscope:screenshot raw-profile-dialog -->\n\nAfter\n"

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

    with pytest.raises(ValueError, match="invalid screenshot marker: raw-profile-dialog"):
        on_page_markdown(
            "<!-- pixelscope:screenshot raw-profile-dialog -->",
            page=_page("features/image-view.md"),
            config={"docs_dir": str(docs_root)},
            files=None,
        )
