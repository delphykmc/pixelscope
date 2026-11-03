# fmt: off
# ruff: noqa: E721, E501  # Strict JSON primitives: bool must not pass as int
"""Bounded, path-safe, atomic analysis ZIP writer reused by W10.

Only typed immutable snapshots enter this API. Raw source images, paths and user
provided CSV strings are not accepted. Legacy standalone CSV writers are unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.core.review_analysis import (
    AnalysisSnapshotV1,
    parse_analysis_context,
    serialize_analysis_context,
)

MAX_BUNDLE_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 16
BUNDLE_KIND = "pixelscope-analysis-bundle"
SCHEMA_VERSION = 1


def _json_bytes(data: object) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _measurements_csv(contexts: list[dict[str, Any]]) -> bytes:
    result = io.StringIO(newline="")
    writer = csv.writer(result, lineterminator="\r\n")
    writer.writerow((
        "snapshot_id", "feature", "source", "channel", "metric", "state",
        "value", "sample_count", "definition_revision",
    ))
    for context in contexts:
        source_ids = {
            source["source_key"]: f"Source {index + 1}"
            for index, source in enumerate(context["sources"])
        }
        for item in context["measurements"]:
            writer.writerow((
                context["snapshot_id"], context["feature"],
                source_ids[item["source_key"]], item["channel"], item["metric"],
                item["state"], "" if item["value"] is None else repr(item["value"]),
                "" if item["sample_count"] is None else item["sample_count"],
                item["definition_revision"],
            ))
    return ("\ufeff" + result.getvalue()).encode("utf-8")


def _safe_entry(name: str) -> bool:
    parts = name.split("/")
    return bool(name and not name.startswith("/")
                and "\\" not in name and ":" not in name
                and not any(p in ("", ".", "..") for p in parts))


def _payloads(snapshots: tuple[AnalysisSnapshotV1, ...]) -> dict[str, bytes]:
    if not 1 <= len(snapshots) <= 4:
        raise ValueError("bundle requires 1–4 frozen analysis snapshots")
    contexts = [parse_analysis_context(serialize_analysis_context(s)) for s in snapshots]
    if len({s.snapshot_id for s in snapshots}) != len(snapshots):
        raise ValueError("duplicate snapshot IDs")
    context_root = {
        "kind": "pixelscope-analysis-context-bundle",
        "schema_version": 1,
        "snapshots": contexts,
    }
    measurements_root = {
        "kind": "pixelscope-analysis-measurements",
        "schema_version": 1,
        "snapshots": [
            {"snapshot_id": c["snapshot_id"], "feature": c["feature"],
             "measurements": c["measurements"]}
            for c in contexts
        ],
    }
    return {
        "data/context.json": _json_bytes(context_root),
        "data/measurements.json": _json_bytes(measurements_root),
        "data/measurements.csv": _measurements_csv(contexts),
    }


def write_analysis_bundle(
    path: Path,
    snapshots: tuple[AnalysisSnapshotV1, ...],
    *,
    cancelled: Callable[[], bool] | None = None,
    expected_existing: tuple[int, int, int] | None = None,
) -> Path:
    """Write and publish one complete bundle; failure leaves old target unchanged.

    The worker should call this function, not the UI thread. expected_existing is
    the (device, inode, mtime_ns) observed after explicit overwrite confirmation.
    Absence of this token means that only a new destination may be created.
    """
    destination = Path(path)
    if destination.suffix.casefold() != ".zip":
        raise ValueError("analysis bundle requires a .zip destination")
    entries = _payloads(snapshots)
    if len(entries) + 1 > MAX_ENTRIES or any(
        not _safe_entry(name) for name in entries
    ):
        raise ValueError("invalid ZIP entries")
    if sum(len(data) for data in entries.values()) > MAX_BUNDLE_BYTES:
        raise ValueError("analysis bundle exceeds size budget")

    manifest = {
        "kind": BUNDLE_KIND,
        "schema_version": SCHEMA_VERSION,
        "redaction_policy": "portable-default",
        "source_names_included": False,
        "user_text_included": False,
        "snapshot_count": len(snapshots),
        "entries": [
            {"path": name, "size": len(content),
             "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(entries.items())
        ],
    }
    entries["manifest.json"] = _json_bytes(manifest)
    cancellation_checkpoint()
    if cancelled is not None and cancelled():
        raise RuntimeError("analysis export cancelled")
    # The user chose an existing destination directory; never create unrelated paths.
    fd, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w+b") as stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6, allowZip64=False) as archive:
                for name, content in sorted(entries.items()):
                    cancellation_checkpoint()
                    if cancelled is not None and cancelled():
                        raise RuntimeError("analysis export cancelled")
                    archive.writestr(name, content)
            stream.flush()
            os.fsync(stream.fileno())
        cancellation_checkpoint()
        if cancelled is not None and cancelled():
            raise RuntimeError("analysis export cancelled")
        try:
            existing = destination.stat()
        except FileNotFoundError:
            existing = None
        if expected_existing is None:
            if existing is not None:
                raise FileExistsError(f"destination appeared after confirmation: {destination.name}")
        elif existing is None or (
            existing.st_dev, existing.st_ino, existing.st_mtime_ns
        ) != expected_existing:
            raise FileExistsError("destination changed after overwrite confirmation")
        cancellation_checkpoint()
        os.replace(temporary, destination)
        if os.name != "nt":
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def verify_analysis_bundle(path: Path) -> dict[str, Any]:
    """Read-only validation. Never extract archive entries onto the filesystem."""
    if Path(path).stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("ZIP too large")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if (len(names) > MAX_ENTRIES or len(names) != len(set(names))
                or not all(_safe_entry(name) for name in names)
                or "manifest.json" not in names):
            raise ValueError("invalid ZIP paths or duplicate entries")
        if any(info.file_size > MAX_BUNDLE_BYTES
               or info.compress_size > MAX_BUNDLE_BYTES for info in infos):
            raise ValueError("ZIP entry exceeds budget")
        if sum(info.file_size for info in infos) > MAX_BUNDLE_BYTES:
            raise ValueError("ZIP expands beyond size budget")
        if any((info.external_attr >> 16) & 0o170000 == 0o120000 for info in infos):
            raise ValueError("symlink entry forbidden")
        manifest = json.loads(archive.read("manifest.json"))
        if type(manifest) is not dict or set(manifest) != {
            "kind", "schema_version", "redaction_policy", "source_names_included",
            "user_text_included", "snapshot_count", "entries",
        } or manifest["kind"] != BUNDLE_KIND or type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported ZIP manifest")
        if manifest["redaction_policy"] != "portable-default" or manifest["source_names_included"] is not False or manifest["user_text_included"] is not False:
            raise ValueError("unexpected ZIP disclosure policy")
        expected = manifest["entries"]
        if type(expected) is not list or len(expected) + 1 != len(names):
            raise ValueError("manifest cardinality mismatch")
        declared: set[str] = set()
        for row in expected:
            if type(row) is not dict or set(row) != {"path", "size", "sha256"}:
                raise ValueError("invalid manifest record")
            name = row["path"]
            if (type(name) is not str or name == "manifest.json"
                    or name in declared or name not in names):
                raise ValueError("invalid manifest path")
            declared.add(name)
            content = archive.read(name)
            if row["size"] != len(content) or row["sha256"] != hashlib.sha256(content).hexdigest():
                raise ValueError("ZIP content hash mismatch")
        if declared != set(names) - {"manifest.json"}:
            raise ValueError("unmanifested ZIP content")
        context = json.loads(archive.read("data/context.json"))
        if type(context) is not dict or set(context) != {"kind", "schema_version", "snapshots"} or context["kind"] != "pixelscope-analysis-context-bundle" or type(context["schema_version"]) is not int or context["schema_version"] != 1:
            raise ValueError("invalid context container")
        if type(context["snapshots"]) is not list or not 1 <= len(context["snapshots"]) <= 4 or manifest["snapshot_count"] != len(context["snapshots"]):
            raise ValueError("invalid snapshot count")
        for item in context["snapshots"]:
            parse_analysis_context(_json_bytes(item))
        return manifest
