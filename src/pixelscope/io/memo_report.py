"""Derived, managed report folder for the one Memo save operation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pixelscope.io.memo_archive import MemoArchive, memo_html, statistics_csvs

_MARKER = ".pixelscope-memo-report.json"


def _is_link(path: Path) -> bool:
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def safe_memo_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:80]
    return value or "images"


def suggested_memo_name(archive: MemoArchive, now: datetime | None = None) -> str:
    first = archive.review.sources[0].locator.basename if archive.review.sources else "images"
    stem = safe_memo_name(Path(first).stem)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"Memo_{stem}_{stamp}.pxmemo"


def report_directory(path: Path) -> Path:
    return path.with_name(f"{path.stem}_report")


def _inventory(directory: Path) -> dict[str, str]:
    if _is_link(directory) or not directory.is_dir():
        raise FileExistsError("Report destination is not a regular generated folder")
    result: dict[str, str] = {}
    total = 0
    for item in directory.rglob("*"):
        if _is_link(item):
            raise FileExistsError("Report destination contains a symlink")
        if item.is_dir():
            result[item.relative_to(directory).as_posix() + "/"] = "directory"
        elif item.is_file() and item != directory / _MARKER:
            total += item.stat().st_size
            if total > 256 * 1024 * 1024 or len(result) >= 4096:
                raise FileExistsError("Report destination exceeds generated report budget")
            result[item.relative_to(directory).as_posix()] = hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
    return result


def _check_existing(directory: Path, document_id: str) -> dict[str, str] | None:
    if not directory.exists() and not directory.is_symlink():
        return None
    marker = directory / _MARKER
    if _is_link(directory) or not marker.is_file() or _is_link(marker):
        raise FileExistsError("Report folder already exists and is not owned by this Memo")
    if marker.stat().st_size > 1024 * 1024:
        raise FileExistsError("Report ownership record is invalid")
    owned = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(owned, dict):
        raise FileExistsError("Report ownership record is invalid")
    inventory = _inventory(directory)
    if (
        owned.get("kind") != "pixelscope-memo-report"
        or owned.get("document_id") != document_id
        or owned.get("files") != inventory
    ):
        raise FileExistsError(
            "Report folder has other or edited files; move or rename it to regenerate"
        )
    return inventory


def _remove_staging(directory: Path, parent: Path) -> None:
    # Only delete our explicit temporary directory directly under the selected
    # output parent. Never recursively remove the user-facing report path.
    if (
        directory.parent.resolve() != parent.resolve()
        or not directory.name.startswith(".memo-report-")
        or (directory.exists() and _is_link(directory))
    ):
        raise ValueError("Invalid temporary report directory")
    if directory.exists():
        shutil.rmtree(directory)


def write_memo_report(
    path: Path,
    archive: MemoArchive,
    revision: str,
    render: Callable[[bytes, str, str], bytes],
) -> Path:
    """Stage a complete report and refuse to replace edited/unrelated output.

    The caller already committed the canonical notebook. Errors must be reported
    as a report-only failure, preserving that notebook's new revision.
    """
    target = report_directory(path)
    document_id = archive.review.document_id
    before = _check_existing(target, document_id)
    stage = Path(tempfile.mkdtemp(prefix=".memo-report-", dir=path.parent))
    backup: Path | None = None
    try:
        sources = {source.source_key: source for source in archive.review.sources}
        image_paths: dict[tuple[str, str], str] = {}
        payloads = statistics_csvs(archive.review)
        for ordinal, finding in enumerate(archive.review.findings, 1):
            for number, key in enumerate(finding.source_keys, 1):
                crop = archive.crops.get((finding.id, key))
                if crop is None or finding.roi_ref is None:
                    continue
                basename = sources[key].locator.basename
                x, y, width, height = finding.roi_ref
                caption = f"x={x}  y={y}  width={width}  height={height}"
                filename = (
                    f"ROI_{ordinal:02d}_{number:02d}_{safe_memo_name(basename)[:48]}"
                    f"_x{x}_y{y}_w{width}_h{height}.png"
                )
                relative = f"images/{filename}"
                payloads[relative] = render(crop, basename, caption)
                if sum(len(data) for data in payloads.values()) > 256 * 1024 * 1024:
                    raise ValueError("Generated report exceeds the bounded byte budget")
                image_paths[(finding.id, key)] = relative
        payloads["index.html"] = memo_html(archive, image_paths=image_paths)
        for relative, data in payloads.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        inventory = _inventory(stage)
        (stage / _MARKER).write_text(
            json.dumps(
                {
                    "kind": "pixelscope-memo-report",
                    "document_id": document_id,
                    "revision": revision,
                    "files": inventory,
                }
            ),
            encoding="utf-8",
        )
        if _check_existing(target, document_id) != before:
            raise FileExistsError("Report destination changed during save")
        if before is not None:
            backup = stage.with_name(stage.name + "-previous")
            os.rename(target, backup)
        try:
            if backup is not None and _check_existing(backup, document_id) != before:
                raise FileExistsError("Report files changed during publication")
            os.rename(stage, target)
        except (OSError, ValueError):
            if backup is not None:
                os.rename(backup, target)
                backup = None
            raise
        if backup is not None:
            _remove_staging(backup, path.parent)
            backup = None
        return target
    finally:
        _remove_staging(stage, path.parent)
