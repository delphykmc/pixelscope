"""Offline Memo ROI archive: immutable evidence crops, notes and static HTML.

This is a Qt-free storage/export foundation. It does NOT replace the W09a
source attestation or Session ownership and does not bind historical pixels
to a newly opened source. UI integration must use the canonical review worker.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import struct
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BUNDLE_SCHEMA = "pixelscope-memo-bundle"
BUNDLE_VERSION = 1
MAX_NOTES = 1000
MAX_CROPS_PER_NOTE = 6
MAX_CROP_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SAFE_ASSET = re.compile(r"images/[0-9a-f]{32}\.png\Z")


@dataclass(frozen=True, slots=True)
class MemoCrop:
    """Captured display-preview ROI PNG; NOT a native image sample authority."""

    source_key: str
    display_name: str
    png_bytes: bytes


@dataclass(frozen=True, slots=True)
class MemoRegion:
    """One independent ROI/annotation; multiple regions may share one image."""

    region_id: str
    title: str
    note: str
    roi: tuple[int, int, int, int]
    crops: tuple[MemoCrop, ...]
    # Reference-space viewport metadata for an optional verified original restore.
    center: tuple[float, float] | None = None
    physical_zoom: float | None = None


@dataclass(frozen=True, slots=True)
class MemoBundle:
    regions: tuple[MemoRegion, ...]
    # Private local hints. A verified source resolver must check bytes/profile
    # before any live image can be bound to a historical region.
    local_sources: Mapping[str, str]


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if not isinstance(data, bytes) or len(data) < 24 or not data.startswith(_PNG_SIGNATURE):
        raise ValueError("a Memo ROI crop must be encoded as PNG")
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        raise ValueError("invalid PNG width or height")
    return width, height


def _check_regions(regions: tuple[MemoRegion, ...]) -> list[dict[str, object]]:
    if not regions or len(regions) > MAX_NOTES:
        raise ValueError("Memo must have between 1 and 1000 regions")
    seen: set[str] = set()
    asset_names: set[str] = set()
    serialized: list[dict[str, object]] = []
    for region in regions:
        if not 1 <= len(region.region_id) <= 128 or region.region_id in seen:
            raise ValueError("invalid or duplicated Memo region ID")
        seen.add(region.region_id)
        if len(region.title) > 256 or len(region.note) > 10000:
            raise ValueError("Memo text exceeds maximum length")
        if len(region.roi) != 4 or any(not isinstance(v, int) for v in region.roi):
            raise ValueError("ROI must be a reference-space x/y/width/height tuple")
        x, y, width, height = region.roi
        if min(x, y) < 0 or min(width, height) < 1:
            raise ValueError("invalid ROI reference coordinates")
        if not region.crops or len(region.crops) > MAX_CROPS_PER_NOTE:
            raise ValueError("each ROI needs 1..6 frozen image crops")
        if region.center is not None:
            import math

            if len(region.center) != 2 or not all(math.isfinite(v) for v in region.center):
                raise ValueError("invalid viewport center")
        if region.physical_zoom is not None:
            import math

            if not math.isfinite(region.physical_zoom) or region.physical_zoom <= 0:
                raise ValueError("invalid physical zoom")
        crop_rows = []
        per_note: set[str] = set()
        for crop in region.crops:
            if not crop.source_key or len(crop.source_key) > 128 or crop.source_key in per_note:
                raise ValueError("duplicate or invalid source identity")
            per_note.add(crop.source_key)
            if not crop.display_name or len(crop.display_name) > 512:
                raise ValueError("invalid source label")
            if len(crop.png_bytes) > MAX_CROP_BYTES:
                raise ValueError("ROI PNG is too large")
            actual = _png_dimensions(crop.png_bytes)
            if actual != (width, height):
                raise ValueError("ROI PNG dimensions differ from reference ROI")
            asset = (
                "images/"
                + hashlib.sha256(
                    (region.region_id + "\0" + crop.source_key).encode("utf-8")
                ).hexdigest()[:32]
                + ".png"
            )
            if asset in asset_names:
                raise ValueError("duplicate archive asset")
            asset_names.add(asset)
            crop_rows.append(
                {
                    "source_key": crop.source_key,
                    "display_name": crop.display_name,
                    "asset": asset,
                    "sha256": hashlib.sha256(crop.png_bytes).hexdigest(),
                    "width": width,
                    "height": height,
                }
            )
        serialized.append(
            {
                "id": region.region_id,
                "title": region.title,
                "note": region.note,
                "roi": [x, y, width, height],
                "center": list(region.center) if region.center is not None else None,
                "physical_zoom": region.physical_zoom,
                "crops": crop_rows,
            }
        )
    return serialized


def _render_html(rows: list[dict[str, object]]) -> bytes:
    sections: list[str] = []
    for index, row in enumerate(rows, 1):
        roi = row["roi"]
        crops = row["crops"]
        assert isinstance(roi, list) and isinstance(crops, list)
        images = "".join(
            '<figure><img alt="'
            + html.escape(str(crop["display_name"]), quote=True)
            + '" src="'
            + html.escape(str(crop["asset"]), quote=True)
            + '">'
            + "<figcaption>"
            + html.escape(str(crop["display_name"]))
            + "</figcaption></figure>"
            for crop in crops
        )
        sections.append(
            "<article><h2>"
            + str(index)
            + ". "
            + html.escape(str(row["title"]))
            + '</h2><p class="roi">ROI: ('
            + ", ".join(map(str, roi))
            + ')</p><p class="note">'
            + html.escape(str(row["note"]))
            + '</p><div class="crops">'
            + images
            + "</div></article>"
        )
    document = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="'
        "default-src &#39;none&#39;; img-src &#39;self&#39;; "
        'style-src &#39;unsafe-inline&#39;">'
        "<title>PixelScope Memo</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}"
        "article{border-top:1px solid #aaa;padding:1rem 0}.note{white-space:pre-wrap}"
        ".roi,figcaption{color:#555}.crops{display:flex;flex-wrap:wrap;gap:1rem}"
        "figure{margin:0}img{max-width:100%;height:auto;border:1px solid #888}"
        "</style></head><body><h1>PixelScope Memo</h1>" + "".join(sections) + "</body></html>"
    )
    return document.encode("utf-8")


def save_memo_bundle(
    path: str | Path,
    regions: tuple[MemoRegion, ...],
    *,
    local_sources: Mapping[str, str] | None = None,
) -> Path:
    """Atomically CREATE a private .pxmemo ZIP with all ROI crops and offline HTML.

    Existing targets are never replaced; source paths are optional private
    hints and are never copied into index.html or exported HTML folders.
    """
    target = Path(path)
    if target.suffix.lower() != ".pxmemo":
        raise ValueError("expected .pxmemo destination")
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = _check_regions(regions)
    sources = dict(local_sources or {})
    known_keys: set[str] = set()
    for row in rows:
        crop_rows = row["crops"]
        assert isinstance(crop_rows, list)
        known_keys.update(str(c["source_key"]) for c in crop_rows)
    if any(key not in known_keys or not isinstance(value, str) for key, value in sources.items()):
        raise ValueError("local source hints must reference captured sources")
    manifest = {"schema": BUNDLE_SCHEMA, "version": BUNDLE_VERSION, "regions": rows}
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    local_bytes = json.dumps({"paths": sources}, ensure_ascii=False).encode("utf-8")
    report = _render_html(rows)
    total = (
        len(manifest_bytes)
        + len(local_bytes)
        + len(report)
        + sum(len(c.png_bytes) for region in regions for c in region.crops)
    )
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Memo bundle exceeds size budget")
    fd, temp_name = tempfile.mkstemp(prefix=".pixelscope-memo-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            with zipfile.ZipFile(handle, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", manifest_bytes)
                archive.writestr("sources.local.json", local_bytes)
                archive.writestr("index.html", report)
                for row, region in zip(rows, regions, strict=True):
                    crop_rows = row["crops"]
                    assert isinstance(crop_rows, list)
                    for meta, crop in zip(crop_rows, region.crops, strict=True):
                        archive.writestr(str(meta["asset"]), crop.png_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        # Same-directory hard-link publication is an exclusive atomic create.
        # Fails if target exists, including a race after validation.
        os.link(temp_name, target)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return target


def open_memo_bundle(path: str | Path) -> MemoBundle:
    """Read only allowlisted archive members; verify crop hashes/dimensions."""
    archive_path = Path(path)
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or sum(item.file_size for item in infos) > MAX_TOTAL_BYTES:
            raise ValueError("oversized or duplicated archive entries")
        if "manifest.json" not in names or "index.html" not in names:
            raise ValueError("incomplete Memo archive")
        if any(
            name not in ("manifest.json", "sources.local.json", "index.html")
            and _SAFE_ASSET.fullmatch(name) is None
            for name in names
        ):
            raise ValueError("unexpected or unsafe Memo archive entry")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("version") != BUNDLE_VERSION:
            raise ValueError("unsupported Memo archive schema")
        raw_rows = manifest.get("regions")
        if not isinstance(raw_rows, list):
            raise ValueError("invalid Memo manifest")
        local_sources = {}
        if "sources.local.json" in names:
            local = json.loads(archive.read("sources.local.json"))
            local_sources = local.get("paths", {})
            if not isinstance(local_sources, dict):
                raise ValueError("invalid private source map")
        regions = []
        for row in raw_rows:
            crops = []
            for meta in row["crops"]:
                name = meta["asset"]
                if _SAFE_ASSET.fullmatch(name) is None or name not in names:
                    raise ValueError("invalid or missing ROI asset")
                data = archive.read(name)
                if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                    raise ValueError("ROI asset content changed")
                crops.append(MemoCrop(meta["source_key"], meta["display_name"], data))
            center = row.get("center")
            regions.append(
                MemoRegion(
                    region_id=row["id"],
                    title=row["title"],
                    note=row["note"],
                    roi=tuple(row["roi"]),
                    crops=tuple(crops),
                    center=tuple(center) if center is not None else None,
                    physical_zoom=row.get("physical_zoom"),
                )
            )
        checked = tuple(regions)
        expected_report = _render_html(_check_regions(checked))
        if archive.read("index.html") != expected_report:
            raise ValueError("Memo HTML differs from verified region content")
        if {str(c.source_key) for r in checked for c in r.crops} < set(local_sources):
            raise ValueError("private source map contains unknown keys")
        return MemoBundle(checked, local_sources)


def export_memo_html_directory(bundle_path: str | Path, directory: str | Path) -> Path:
    """Produce a source-path-free index.html + images folder, without PixelScope."""
    bundle = open_memo_bundle(bundle_path)  # integrity preflight
    target = Path(directory)
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pixelscope-html-", dir=target.parent) as work:
        staging = Path(work) / "report"
        staging.mkdir()
        with zipfile.ZipFile(bundle_path) as archive:
            # Never extract user-controlled ZIP member paths.
            (staging / "index.html").write_bytes(archive.read("index.html"))
            for region in bundle.regions:
                for crop in region.crops:
                    name = (
                        "images/"
                        + hashlib.sha256(
                            (region.region_id + "\0" + crop.source_key).encode("utf-8")
                        ).hexdigest()[:32]
                        + ".png"
                    )
                    output = staging / name
                    output.parent.mkdir(exist_ok=True)
                    output.write_bytes(crop.png_bytes)
        staging.rename(target)
    return target
