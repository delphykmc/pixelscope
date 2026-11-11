"""Bounded, atomic editable Memo ZIP with embedded immutable ROI crop PNGs.

This Qt-free infrastructure is intentionally separate from W09b's V1 .pxreview
repository. GUI capture/export wiring is owned by the Memo V2 feature slice.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, cast
from urllib.parse import quote

import cv2
import numpy as np

from pixelscope.core.review_analysis import parse_analysis_context
from pixelscope.core.review_record import MAX_REVIEW_BYTES, ReviewDocumentV1, ReviewValidationError

MEMO_SUFFIX = ".pxmemo"
MEMO_KIND = "pixelscope-memo"
MEMO_SCHEMA = 1
_MAX_ASSETS = 1536
_MAX_PNG = 64 * 1024 * 1024
_MAX_TOTAL = 256 * 1024 * 1024
_MAX_MANIFEST = 1024 * 1024
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")
_WRITE_LOCK = RLock()


@dataclass(frozen=True)
class MemoArchive:
    """Local-private notebook; crops remain usable when originals are absent."""

    review: ReviewDocumentV1
    crops: Mapping[tuple[str, str], bytes]

    def __post_init__(self) -> None:
        object.__setattr__(self, "crops", MappingProxyType(dict(self.crops)))


def _asset_path(finding_id: str, source_key: str) -> str:
    if not _UUID.fullmatch(finding_id) or not _UUID.fullmatch(source_key):
        raise ReviewValidationError("invalid Memo asset identity")
    return f"images/{finding_id}/{source_key}.png"


def _validate_png(payload: bytes, width: int, height: int) -> None:
    if (
        not isinstance(payload, bytes)
        or payload[:8] != _PNG_MAGIC
        or not 32 <= len(payload) <= _MAX_PNG
    ):
        raise ReviewValidationError("invalid or oversized Memo PNG")
    # Check dimensions before any potentially expensive decode.
    if payload[12:16] != b"IHDR":
        raise ReviewValidationError("Memo PNG lacks IHDR")
    w = int.from_bytes(payload[16:20], "big")
    h = int.from_bytes(payload[20:24], "big")
    if (w, h) != (width, height):
        raise ReviewValidationError("Memo PNG dimensions differ from ROI")
    if w * h > _MAX_PNG // 4:
        raise ReviewValidationError("Memo PNG decoded pixels exceed budget")
    decoded = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if (
        decoded is None
        or decoded.shape[:2] != (height, width)
        or decoded.dtype != np.uint8
        or (decoded.ndim != 2 and (decoded.ndim != 3 or decoded.shape[2] not in (3, 4)))
    ):
        raise ReviewValidationError("Memo PNG failed to decode")


def _canonical_assets(archive: MemoArchive) -> dict[str, bytes]:
    review = archive.review
    if not isinstance(review, ReviewDocumentV1):
        raise TypeError("ReviewDocumentV1 expected")
    expected: dict[tuple[str, str], tuple[int, int]] = {}
    for finding in review.findings:
        present = {key for fid, key in archive.crops if fid == finding.id}
        # Legacy .pxreview imports have metadata but no captured images. Never
        # synthesize historical evidence from the current original on migration.
        if not present:
            continue
        if finding.roi_ref is None:
            raise ReviewValidationError("Memo entries require an explicit ROI")
        _, _, width, height = finding.roi_ref
        for key in finding.source_keys:
            expected[(finding.id, key)] = (width, height)
    if set(archive.crops) != set(expected) or len(expected) > _MAX_ASSETS:
        raise ReviewValidationError("missing, extra or excessive Memo ROI crops")
    result: dict[str, bytes] = {}
    total = len(review.to_bytes())
    for pair, dims in expected.items():
        data = archive.crops[pair]
        _validate_png(data, *dims)
        total += len(data)
        if total > _MAX_TOTAL:
            raise ReviewValidationError("Memo archive exceeds bounded byte budget")
        result[_asset_path(*pair)] = data
    return result


def statistics_csvs(review: ReviewDocumentV1) -> dict[str, bytes]:
    """Portable CSVs derived solely from frozen, validated native ROI Statistics."""
    outputs: dict[str, bytes] = {}
    labels = {s.source_key: s.locator.basename for s in review.sources}
    for finding in review.findings:
        contexts = [
            cast(dict[str, Any], parse_analysis_context(c.context_json))
            for c in finding.analysis
            if c.context_json is not None
        ]
        contexts = [
            c
            for c in contexts
            if c["feature"] == "statistics" and c["roi_ref"] == list(finding.roi_ref or ())
        ]
        if not contexts:
            continue
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(
            (
                "Source",
                "Image",
                "Channel",
                "Metric",
                "Value",
                "State",
                "Samples",
                "Domain",
                "Native dtype",
                "Effective bits",
                "Definition",
                "X",
                "Y",
                "Width",
                "Height",
                "Captured UTC",
            )
        )
        ordinals = {key: i for i, key in enumerate(finding.source_keys, 1)}
        for context in contexts:
            source_metadata = {s["source_key"]: s for s in context["sources"]}
            for row in context["measurements"]:
                label = labels[row["source_key"]]
                if label.startswith(("=", "+", "-", "@", "\t", "\r")):
                    label = "'" + label
                native = source_metadata[row["source_key"]]
                writer.writerow(
                    (
                        ordinals[row["source_key"]],
                        label,
                        row["channel"],
                        row["metric"],
                        row["value"],
                        row["state"],
                        row["sample_count"],
                        context["domain"],
                        native["native_dtype"],
                        native["effective_bits"],
                        row["definition_revision"],
                        *(finding.roi_ref or ()),
                        finding.captured_utc,
                    )
                )
        outputs[f"statistics/{finding.id}.csv"] = stream.getvalue().encode("utf-8-sig")
    return outputs


def memo_thumbnails(crops: Mapping[tuple[str, str], bytes]) -> dict[tuple[str, str], bytes]:
    """Worker-only small PNGs: the GUI never decodes full-size evidence crops."""
    result = {}
    for key, payload in crops.items():
        image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ReviewValidationError("Memo crop cannot be decoded")
        height, width = image.shape[:2]
        factor = min(1.0, 240 / width, 160 / height)
        small = cv2.resize(
            image,
            (max(1, round(width * factor)), max(1, round(height * factor))),
            interpolation=cv2.INTER_AREA,
        )
        ok, encoded = cv2.imencode(".png", small)
        if not ok:
            raise ReviewValidationError("Memo preview cannot be encoded")
        result[key] = encoded.tobytes()
    return result


def _legacy_memo_html(archive: MemoArchive) -> bytes:
    """Static report saved inside the same notebook; no separate export choice."""
    labels = {s.source_key: s.display_tag or s.locator.basename for s in archive.review.sources}
    csvs = statistics_csvs(archive.review)
    rows = []
    for ordinal, finding in enumerate(archive.review.findings, 1):
        images = []
        for image_number, key in enumerate(finding.source_keys, 1):
            if (finding.id, key) in archive.crops:
                images.append(
                    f'<figure><img src="{_asset_path(finding.id, key)}" alt="ROI crop">'
                    f"<figcaption>{image_number}. {html.escape(labels[key])}</figcaption></figure>"
                )
        csv = f"statistics/{finding.id}.csv"
        link = f'<p><a href="{csv}">ROI Statistics CSV</a></p>' if csv in csvs else ""
        rows.append(
            f"<section><h2>ROI {ordinal}: {html.escape(finding.title)}</h2>"
            f"<p>ROI {finding.roi_ref} · {html.escape(finding.captured_utc)}</p>"
            f'<p class="note">{html.escape(finding.note)}</p>'
            + ("".join(images) or "<p>No stored crop (legacy memo).</p>")
            + link
            + "</section>"
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'img-src &#39;self&#39;; style-src &#39;unsafe-inline&#39;">'
        "<title>PixelScope Memo</title><style>body{font-family:system-ui;max-width:1100px;"
        "margin:2rem auto;padding:1rem}section{border-top:1px solid #aaa;padding:1rem 0}"
        ".note{white-space:pre-wrap}figure{display:inline-block;margin:0 1rem 1rem 0;"
        "vertical-align:top}img{max-width:100%;height:auto}</style></head>"
        "<body><h1>PixelScope Memo</h1><p>Saved 8-bit ROI preview images</p>"
        + "".join(rows)
        + "</body></html>"
    ).encode("utf-8")


def memo_html(
    archive: MemoArchive, *, image_paths: Mapping[tuple[str, str], str] | None = None
) -> bytes:
    """Version-two presentation with a filename and explicit crop coordinates."""
    sources = {source.source_key: source for source in archive.review.sources}
    report = _legacy_memo_html(archive).decode("utf-8")
    report = report.replace(
        "<title>", '<meta name="pixelscope-report-version" content="2"><title>', 1
    )
    for finding in archive.review.findings:
        if finding.roi_ref is None:
            continue
        x, y, width, height = finding.roi_ref
        for number, key in enumerate(finding.source_keys, 1):
            if (finding.id, key) not in archive.crops:
                continue
            asset = _asset_path(finding.id, key)
            label = sources[key].display_tag or sources[key].locator.basename
            old = (
                f'<figure><img src="{asset}" alt="ROI crop">'
                f"<figcaption>{number}. {html.escape(label)}</figcaption></figure>"
            )
            relative = asset if image_paths is None else image_paths[(finding.id, key)]
            caption = f"{number}. {html.escape(sources[key].locator.basename)}"
            tag = sources[key].display_tag
            if tag:
                caption += f" · {html.escape(tag)}"
            url = html.escape(quote(relative, safe="/"), quote=True)
            replacement = (
                f'<figure><img src="{url}" alt="ROI crop">'
                f"<figcaption>{caption}<br>x={x} · y={y} · width={width} · height={height}"
                "</figcaption></figure>"
            )
            report = report.replace(old, replacement, 1)
    return report.encode("utf-8")


def _payloads(archive: MemoArchive) -> dict[str, bytes]:
    assets = _canonical_assets(archive)
    assets.update(statistics_csvs(archive.review))
    assets["index.html"] = memo_html(archive)
    manifest = {
        "kind": MEMO_KIND,
        "schema_version": MEMO_SCHEMA,
        "document_id": archive.review.document_id,
        "assets": [
            {"path": path, "sha256": hashlib.sha256(value).hexdigest()}
            for path, value in sorted(assets.items())
        ],
    }
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(manifest_bytes) > _MAX_MANIFEST:
        raise ReviewValidationError("Memo manifest is too large")
    result = {"manifest.json": manifest_bytes, "review.json": archive.review.to_bytes(), **assets}
    if sum(map(len, result.values())) > _MAX_TOTAL:
        raise ReviewValidationError("Memo archive exceeds bounded byte budget")
    return result


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_memo_archive(
    path: Path,
    archive: MemoArchive,
    *,
    expected_revision: str | None = None,
) -> str:
    """Atomic save; replacing an existing notebook requires a matching revision.

    Returns the SHA-256 of committed bytes for a subsequent CAS update.
    """
    if not isinstance(path, Path) or path.suffix.lower() != MEMO_SUFFIX:
        raise ValueError("Select a .pxmemo destination")
    payloads = _payloads(archive)
    if not path.parent.is_dir():
        raise FileNotFoundError(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=".memo-", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for name, data in sorted(payloads.items()):
                    z.writestr(name, data)
            stream.flush()
            os.fsync(stream.fileno())
        with _WRITE_LOCK:
            lock = path.with_name(f".{path.name}.lock")
            fd_lock = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                if path.is_symlink():
                    raise FileExistsError("Memo destination is a symlink")
                revision = _digest(temp)
                if path.exists():
                    if expected_revision is None or _digest(path) != expected_revision:
                        raise FileExistsError("Memo destination changed; reload before replacing")
                    existing, parsed_revision = load_memo_archive(path)
                    if parsed_revision != expected_revision:
                        raise FileExistsError(
                            "Memo destination changed during save; reload before replacing"
                        )
                    if existing.review.document_id != archive.review.document_id:
                        raise FileExistsError("Memo document identity changed")
                    os.replace(temp, path)
                else:
                    if expected_revision is not None:
                        raise FileNotFoundError("Memo destination vanished during edit")
                    os.link(temp, path)
                return revision
            finally:
                os.close(fd_lock)
                lock.unlink(missing_ok=True)
    finally:
        temp.unlink(missing_ok=True)


def load_memo_archive(path: Path) -> tuple[MemoArchive, str]:
    if not isinstance(path, Path) or path.suffix.lower() != MEMO_SUFFIX:
        raise ValueError("Select an existing .pxmemo")
    if path.is_file():
        with path.open("rb") as stream:
            folder_map = stream.read(2) != b"PK"
        if folder_map:
            from pixelscope.io.memo_folder import load_folder_memo

            return load_folder_memo(path)
    if not isinstance(path, Path) or path.suffix.lower() != MEMO_SUFFIX:
        raise ValueError("Select an existing .pxmemo")
    if not path.is_file() or path.stat().st_size > _MAX_TOTAL:
        raise ReviewValidationError("Missing or oversized Memo archive")
    # Read once from one descriptor: returned revision and parsed evidence must
    # describe the same bytes even if another process replaces the path.
    with path.open("rb") as stream:
        raw = stream.read(_MAX_TOTAL + 1)
    if len(raw) > _MAX_TOTAL:
        raise ReviewValidationError("Memo input exceeds byte budget")
    revision = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
        infos = z.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or len(names) > _MAX_ASSETS + 1002:
            raise ReviewValidationError("duplicate or excessive Memo ZIP members")
        if "manifest.json" not in names or "review.json" not in names:
            raise ReviewValidationError("Memo ZIP missing manifest or review")
        if any(
            info.is_dir() or (info.file_size > _MAX_PNG and info.filename.endswith(".png"))
            for info in infos
        ):
            raise ReviewValidationError("invalid Memo ZIP member")
        if sum(info.file_size for info in infos) > _MAX_TOTAL:
            raise ReviewValidationError("Memo ZIP expanded size exceeds budget")
        if z.getinfo("manifest.json").file_size > _MAX_MANIFEST:
            raise ReviewValidationError("oversized Memo manifest")
        if z.getinfo("review.json").file_size > MAX_REVIEW_BYTES:
            raise ReviewValidationError("oversized Memo review metadata")
        manifest = json.loads(z.read("manifest.json"))
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"kind", "schema_version", "document_id", "assets"}
            or manifest["kind"] != MEMO_KIND
            or not isinstance(manifest["schema_version"], int)
            or isinstance(manifest["schema_version"], bool)
            or manifest["schema_version"] != MEMO_SCHEMA
            or not isinstance(manifest["assets"], list)
        ):
            raise ReviewValidationError("unknown or malformed Memo schema")
        review = ReviewDocumentV1.from_bytes(z.read("review.json"))
        if manifest["document_id"] != review.document_id:
            raise ReviewValidationError("Memo document identity mismatch")
        items: dict[tuple[str, str], bytes] = {}
        csvs = statistics_csvs(review)
        allowed = {"manifest.json", "review.json"}
        for item in manifest["assets"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str)
                or not isinstance(item["sha256"], str)
            ):
                raise ReviewValidationError("invalid Memo asset manifest")
            name = item["path"]
            if name == "index.html":
                if name in allowed:
                    raise ReviewValidationError("duplicate Memo report")
                data = z.read(name)
                if hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ReviewValidationError("Memo report digest mismatch")
                allowed.add(name)
                continue
            if name in csvs:
                data = z.read(name)
                if (
                    name in allowed
                    or data != csvs[name]
                    or hashlib.sha256(data).hexdigest() != item["sha256"]
                ):
                    raise ReviewValidationError("Memo statistics CSV mismatch")
                allowed.add(name)
                continue
            match = re.fullmatch(r"images/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})\.png", name)
            if match is None or name in allowed:
                raise ReviewValidationError("unsafe or duplicated Memo asset path")
            allowed.add(name)
            data = z.read(name)
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ReviewValidationError("Memo asset digest mismatch")
            items[match.group(1), match.group(2)] = data
        if set(names) != allowed:
            raise ReviewValidationError("Memo ZIP has unexpected members")
    archive = MemoArchive(review, items)
    expected = _payloads(archive)
    if set(expected) - {"index.html"} != set(names) - {"index.html"}:
        raise ReviewValidationError("Memo ZIP missing required evidence")
    if "index.html" in names:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
            if z.read("index.html") not in (memo_html(archive), _legacy_memo_html(archive)):
                raise ReviewValidationError("Memo report differs from recorded ROI evidence")
    return archive, revision
