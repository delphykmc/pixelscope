"""Metadata-only Memo map with guarded relative external assets."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pixelscope.core.review_record import ReviewDocumentV1
from pixelscope.io.memo_archive import MemoArchive, _canonical_assets
from pixelscope.io.memo_report import (
    _inventory,
    _is_link,
    _remove_staging,
    crop_filename,
    write_memo_report,
)

KIND = "pixelscope-memo-folder"
MAX_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class FolderSaveResult:
    revision: str
    cleanup_warning: str = ""


class MemoRecoveryError(OSError):
    """Publication failed and the complete old folder is retained for recovery."""


def _replace_data(destination: Path, data: bytes, temporary: Path) -> None:
    if destination.is_file() and destination.read_bytes() == data:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="write-", dir=temporary)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(staged, destination)
        except PermissionError:
            if destination.name != "index.html":
                raise
            # A browser can retain a non-delete-sharing HTML handle while still
            # permitting writes. HTML is derived; the map remains the last commit.
            with destination.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    finally:
        staged.unlink(missing_ok=True)


def _publish_existing(root: Path, stage: Path, backup: Path, metadata: str, revision: str) -> None:
    """Keep the directory handle stable; back up files and commit the map last."""
    shutil.copytree(root, backup)
    if (
        load_folder_memo(backup / metadata)[1] != revision
        or load_folder_memo(root / metadata)[1] != revision
    ):
        raise FileExistsError("Memo changed during save")
    old = {p.relative_to(backup): p for p in backup.rglob("*") if p.is_file()}
    new = {p.relative_to(stage): p for p in stage.rglob("*") if p.is_file()}
    old_dirs = {p.relative_to(backup) for p in backup.rglob("*") if p.is_dir()}
    new_dirs = {p.relative_to(stage) for p in stage.rglob("*") if p.is_dir()}
    try:
        for relative, source in new.items():
            if relative.as_posix() != metadata:
                _replace_data(root / relative, source.read_bytes(), stage.parent)
        for relative in old.keys() - new.keys():
            (root / relative).unlink()
        for relative in sorted(old_dirs - new_dirs, key=lambda p: len(p.parts), reverse=True):
            (root / relative).rmdir()
        _replace_data(root / metadata, (stage / metadata).read_bytes(), stage.parent)
    except (OSError, ValueError) as error:
        try:
            for relative in new.keys() - old.keys():
                (root / relative).unlink(missing_ok=True)
            for directory in backup.rglob("*"):
                if directory.is_dir():
                    (root / directory.relative_to(backup)).mkdir(parents=True, exist_ok=True)
            for relative, source in old.items():
                _replace_data(root / relative, source.read_bytes(), stage.parent)
            for relative in sorted(new_dirs - old_dirs, key=lambda p: len(p.parts), reverse=True):
                directory = root / relative
                if directory.exists():
                    directory.rmdir()
            if load_folder_memo(root / metadata)[1] != revision:
                raise OSError("Rollback validation failed")
        except (OSError, ValueError) as rollback_error:
            raise MemoRecoveryError(
                f"Memo recovery copy retained at {backup}: {rollback_error}"
            ) from error
        raise


def metadata_path(chosen: Path) -> Path:
    return (
        chosen if chosen.parent.name == chosen.stem else chosen.parent / chosen.stem / chosen.name
    )


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or pure.is_absolute()
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise ValueError("Invalid Memo relative asset path")
    current = root
    for part in pure.parts:
        current = current / part
        if _is_link(current):
            raise ValueError("Memo asset uses a linked path")
    return current


def load_folder_memo(path: Path) -> tuple[MemoArchive, str]:
    root = path.parent
    if _is_link(root) or _is_link(path) or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Invalid Memo metadata file")
    if (root / ".pixelscope-memo-report.json").exists():
        raise ValueError("Memo folder contains an unrelated ownership file")
    raw = path.read_bytes()
    obj = json.loads(raw)
    if (
        not isinstance(obj, dict)
        or set(obj) != {"kind", "schema_version", "review", "crops", "assets", "directories"}
        or obj.get("kind") != KIND
        or obj.get("schema_version") != 1
    ):
        raise ValueError("Unsupported Memo folder map")
    review = ReviewDocumentV1.from_bytes(json.dumps(obj["review"], ensure_ascii=False).encode())
    assets = obj.get("assets")
    rows = obj.get("crops")
    if (
        not isinstance(assets, dict)
        or len(assets) > 4096
        or not isinstance(rows, list)
        or len(rows) > 1536
    ):
        raise ValueError("Invalid Memo asset map")
    total = 0
    contents: dict[str, bytes] = {}
    for relative, digest in assets.items():
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise ValueError("Invalid Memo asset digest")
        asset = _asset(root, relative)
        total += asset.stat().st_size
        if total > MAX_BYTES:
            raise ValueError("Memo assets exceed byte budget")
        data = asset.read_bytes()
        if _digest(data) != digest:
            raise ValueError("Memo asset is missing or changed")
        contents[relative] = data
    inventory = _inventory(root)
    if obj["directories"] != sorted(
        name for name, digest in inventory.items() if digest == "directory"
    ):
        raise ValueError("Memo folder contains unrelated directories")
    expected = {name: digest for name, digest in inventory.items() if digest != "directory"}
    expected.pop(path.name, None)
    if expected != assets:
        raise ValueError("Memo folder contains unrelated or changed files")
    crops = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"finding_id", "source_key", "path"}:
            raise ValueError("Invalid Memo crop map")
        key = (row["finding_id"], row["source_key"])
        if key in crops or row["path"] not in contents:
            raise ValueError("Invalid or duplicate Memo crop")
        crops[key] = contents[row["path"]]
    archive = MemoArchive(review, crops)
    _canonical_assets(archive)
    if "index.html" not in assets:
        raise ValueError("Memo report is missing")
    return archive, _digest(raw)


def save_folder_memo(
    path: Path,
    archive: MemoArchive,
    expected_revision: str | None,
) -> FolderSaveResult:
    """Publish the complete folder as one generation, keeping unrelated data."""
    root = path.parent
    _canonical_assets(archive)
    before: str | None = None
    if root.exists() or root.is_symlink():
        if expected_revision is None:
            raise FileExistsError("Memo folder already exists; choose another name")
        existing, before = load_folder_memo(path)
        if before != expected_revision or existing.review.document_id != archive.review.document_id:
            raise FileExistsError("Memo folder changed; reopen before saving")
    elif expected_revision is not None:
        raise FileNotFoundError("Memo folder vanished")
    parent = root.parent
    stage_parent = Path(tempfile.mkdtemp(prefix=".memo-report-", dir=parent))
    stage = stage_parent / "next"
    backup = stage_parent / "previous"
    published = False
    recovery_needed = False
    cleanup_warning = ""
    try:
        generated = write_memo_report(
            stage_parent / "presentation.pxmemo",
            archive,
            "staged",
            lambda data, _name, _coords: data,
        )
        generated.rename(stage)
        (stage / ".pixelscope-memo-report.json").unlink()
        src = stage / "src"
        src.mkdir()
        if (stage / "images").exists():
            (stage / "images").rename(src / "crops")
        if (stage / "statistics").exists():
            (stage / "statistics").rename(src / "statistics")
        html = (stage / "index.html").read_text(encoding="utf-8")
        html = html.replace('src="images/', 'src="src/crops/').replace(
            'href="statistics/', 'href="src/statistics/'
        )
        (stage / "index.html").write_text(html, encoding="utf-8")
        rows = []
        sources = {source.source_key: source for source in archive.review.sources}
        for ordinal, finding in enumerate(archive.review.findings, 1):
            for number, source in enumerate(finding.source_keys, 1):
                if (finding.id, source) not in archive.crops or finding.roi_ref is None:
                    continue
                relative = "src/crops/" + crop_filename(
                    ordinal, number, sources[source].locator.basename, finding.roi_ref
                )
                if (stage / relative).read_bytes() != archive.crops[(finding.id, source)]:
                    raise ValueError("Report crop must be the exact recorded PNG")
                rows.append({"finding_id": finding.id, "source_key": source, "path": relative})
        inventory = _inventory(stage)
        assets = {name: digest for name, digest in inventory.items() if digest != "directory"}
        obj = {
            "kind": KIND,
            "schema_version": 1,
            "review": json.loads(archive.review.to_bytes()),
            "crops": rows,
            "assets": assets,
            "directories": sorted(
                name for name, digest in inventory.items() if digest == "directory"
            ),
        }
        raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        (stage / path.name).write_bytes(raw)
        load_folder_memo(stage / path.name)
        for item in stage.rglob("*"):
            if item.is_file():
                with item.open("rb+") as stream:
                    os.fsync(stream.fileno())
        if before is not None:
            if load_folder_memo(path)[1] != before:
                raise FileExistsError("Memo changed during save")
            try:
                _publish_existing(root, stage, backup, path.name, before)
            except MemoRecoveryError:
                recovery_needed = True
                raise
            published = True
        else:
            os.rename(stage, root)
            published = True
    finally:
        # If rollback failed, retain the only previous copy for recovery.
        if recovery_needed:
            raise MemoRecoveryError(f"Memo recovery copy retained at {backup}")
        try:
            _remove_staging(stage_parent, parent)
        except OSError as exc:
            if not published:
                raise
            cleanup_warning = f"Temporary backup cleanup pending at {stage_parent}: {exc}"
    return FolderSaveResult(_digest(raw), cleanup_warning)
