from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import prepare_user_guide_publication as publication

_SHA = "a" * 40


def _site(root: Path) -> Path:
    site = root / "site"
    vendor = site / "assets"
    vendor.mkdir(parents=True)
    (vendor / "iframe-worker.js").write_text("// local", encoding="utf-8")
    (site / "index.html").write_text(
        '<script src="assets/iframe-worker.js"></script>'
        '<a href="features/image-view.html#view">Image View</a>',
        encoding="utf-8",
    )
    guide = site / "features" / "image-view.html"
    guide.parent.mkdir()
    guide.write_text("<h1>Image View</h1>", encoding="utf-8")
    (site / "llms.txt").write_text("- index.html\n", encoding="utf-8")
    return site


def test_selected_docs_revision_accepts_main_or_canonical_release_tag() -> None:
    publication.validate_selected_revision(
        "main", version="0.1.0", source_commit=_SHA, ref_commit=_SHA
    )
    publication.validate_selected_revision(
        "v0.1.0", version="0.1.0", source_commit=_SHA, ref_commit=_SHA
    )
    with pytest.raises(ValueError, match="main or the canonical tag"):
        publication.validate_selected_revision(
            "feature/docs", version="0.1.0", source_commit=_SHA, ref_commit=_SHA
        )
    with pytest.raises(ValueError, match="main or the canonical tag"):
        publication.validate_selected_revision(
            "v0.0.9", version="0.1.0", source_commit=_SHA, ref_commit=_SHA
        )
    with pytest.raises(ValueError, match="does not match"):
        publication.validate_selected_revision(
            "main", version="0.1.0", source_commit=_SHA, ref_commit="b" * 40
        )


def test_publication_inventory_catches_missing_or_tampered_linked_page(
    tmp_path: Path,
) -> None:
    site = _site(tmp_path)
    metadata = publication.build_publication_manifest(
        site, revision="main", version="0.1.0", source_commit=_SHA
    )
    publication.validate_publication_manifest(site, metadata)
    guide = site / "features" / "image-view.html"
    guide.write_text("<h1>Changed</h1>", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory/identity mismatch"):
        publication.validate_publication_manifest(site, metadata)
    guide.unlink()
    updated = publication.build_publication_manifest(
        site, revision="main", version="0.1.0", source_commit=_SHA
    )
    with pytest.raises(ValueError, match="missing linked page"):
        publication.validate_publication_manifest(site, updated)


def test_prepare_publication_records_source_identity_without_release_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = _site(tmp_path)
    destination = tmp_path / "build" / "user-guide-publication"
    monkeypatch.setattr(publication, "release_version", lambda: "0.1.0")
    monkeypatch.setattr(publication, "_git_rev_parse", lambda _ref: _SHA)
    monkeypatch.setattr(publication, "resolved_revision_commit", lambda _ref, _version: _SHA)
    monkeypatch.setattr(publication, "build_user_guide", lambda: site)

    staged = publication.prepare_publication("v0.1.0", destination=destination)
    metadata = json.loads((staged / "publication.json").read_text(encoding="utf-8"))
    assert staged == destination
    assert metadata["version"] == "0.1.0"
    assert metadata["source_ref"] == "v0.1.0"
    assert metadata["source_commit"] == _SHA
    assert {path.name for path in staged.iterdir()} == {"site", "publication.json"}
    publication.validate_publication_manifest(staged / "site", metadata)


def test_docs_publication_workflow_is_manual_and_pages_is_opt_in() -> None:
    script = (
        publication.REPO_ROOT / ".github/workflows/user-guide-publication.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in script
    assert "\non:\n  workflow_dispatch:" in script
    assert "PIXELSCOPE_DOCS_PAGES_ENABLED" in script
    assert "actions/upload-artifact@v4" in script
    assert "actions/deploy-pages@v4" in script
    assert "environment:" in script
    assert "github-pages" in script
