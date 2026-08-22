"""Qt-free portable shared-storage resolution and safe content-addressed staging."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO

from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot

HASH_CHUNK_BYTES = 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


class StorageResolutionError(ValueError):
    """A source/result cannot be represented by configured shared storage."""


@dataclass(frozen=True)
class LogicalStoragePath:
    storage_root_id: str
    relative_path: str

    def __post_init__(self) -> None:
        validate_relative_path(self.relative_path)


@dataclass(frozen=True)
class ResolvedSource:
    logical_path: LogicalStoragePath
    sha256: str
    local_path: Path
    staged: bool


def validate_relative_path(value: str) -> None:
    if not value or "\x00" in value or len(value) > 2048:
        raise StorageResolutionError("relative_path must be a non-empty bounded path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in posix.parts)
        or "\\" in value
    ):
        raise StorageResolutionError("relative_path must be a contained portable POSIX path")


def sha256_file(path: Path, *, chunk_size: int = HASH_CHUNK_BYTES) -> str:
    """Hash a file without materializing it in memory."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            _update_hash(digest, stream, chunk_size)
    except OSError as exc:
        raise StorageResolutionError(f"unable to read source: {path.name}") from exc
    return digest.hexdigest()


def _update_hash(digest: Any, stream: BinaryIO, chunk_size: int) -> None:
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        digest.update(chunk)


def resolve_existing_source(source: Path | str, settings: RemoteIqaSettings) -> ResolvedSource | None:
    """Resolve a source already under a configured root; longest match wins."""
    source_path = Path(source)
    if not source_path.is_file():
        raise StorageResolutionError(f"source is missing or not a regular file: {source_path.name}")
    candidate = _longest_matching_root(str(source_path), settings.storage_roots)
    if candidate is None:
        return None
    relative = _windows_relative(str(source_path), candidate.client_path)
    return ResolvedSource(
        LogicalStoragePath(candidate.storage_root_id, relative),
        sha256_file(source_path),
        source_path,
        False,
    )


def stage_source(source: Path | str, staging_root: Path | str, storage_root_id: str) -> ResolvedSource:
    """Publish one source as staging/<sha256>/<basename> using a .part and atomic replace."""
    source_path = Path(source)
    if not source_path.is_file() or source_path.is_symlink():
        raise StorageResolutionError(f"source is missing or not a regular file: {source_path.name}")
    digest = sha256_file(source_path)
    root = Path(staging_root)
    final = root / "staging" / digest / source_path.name
    part = final.with_name(final.name + ".part")
    final.parent.mkdir(parents=True, exist_ok=True)
    _assert_contained(root, final)
    if final.exists():
        if not final.is_file() or final.is_symlink():
            raise StorageResolutionError("existing staged target is not a regular file")
        if sha256_file(final) != digest:
            raise StorageResolutionError("existing staged target failed SHA-256 identity verification")
        return ResolvedSource(
            LogicalStoragePath(storage_root_id, _portable_staged_path(digest, source_path.name)),
            digest,
            final,
            True,
        )
    try:
        part.unlink(missing_ok=True)
        with source_path.open("rb") as src, part.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=COPY_CHUNK_BYTES)
            dst.flush()
            os.fsync(dst.fileno())
        if sha256_file(part) != digest:
            raise StorageResolutionError("staging copy failed SHA-256 verification")
        os.replace(part, final)
    except Exception:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return ResolvedSource(
        LogicalStoragePath(storage_root_id, _portable_staged_path(digest, source_path.name)),
        digest,
        final,
        True,
    )


def resolve_or_stage_source(source: Path | str, settings: RemoteIqaSettings) -> ResolvedSource:
    """Resolve a configured source or safely stage it under the selected staging root."""
    existing = resolve_existing_source(source, settings)
    if existing is not None:
        return existing
    if settings.staging_root_id is None:
        raise StorageResolutionError(
            "source is outside configured storage roots and no staging root is selected"
        )
    staging = settings.root(settings.staging_root_id)
    if staging is None:
        raise StorageResolutionError("configured staging root is missing")
    root_path = Path(staging.client_path)
    if not root_path.is_dir():
        raise StorageResolutionError("staging root is unavailable")
    return stage_source(source, root_path, staging.storage_root_id)


def resolve_result_reference(storage_root_id: str, relative_path: str, settings: RemoteIqaSettings) -> Path:
    """Resolve a server logical result reference using the current settings snapshot."""
    validate_relative_path(relative_path)
    root = settings.root(storage_root_id)
    if root is None:
        raise StorageResolutionError(f"storage root '{storage_root_id}' is not configured")
    root_path = Path(root.client_path)
    if not root_path.is_dir():
        raise StorageResolutionError(f"storage root '{storage_root_id}' is unavailable")
    target = root_path.joinpath(*PurePosixPath(relative_path).parts)
    _assert_contained(root_path, target)
    if not target.is_dir():
        raise StorageResolutionError("result directory is unavailable")
    return target


def _longest_matching_root(source: str, roots: tuple[RemoteIqaStorageRoot, ...]) -> RemoteIqaStorageRoot | None:
    """Compare Windows paths case-insensitively without requiring the share to be online."""
    source_path = PureWindowsPath(source)
    matches: list[tuple[int, RemoteIqaStorageRoot]] = []
    for root in roots:
        root_path = PureWindowsPath(root.client_path)
        try:
            relative = source_path.relative_to(root_path)
        except ValueError:
            source_parts = tuple(part.casefold() for part in source_path.parts)
            root_parts = tuple(part.casefold() for part in root_path.parts)
            if source_parts[: len(root_parts)] != root_parts:
                continue
            relative = PureWindowsPath(*source_path.parts[len(root_path.parts) :])
        if not relative.parts:
            continue
        matches.append((len(root_path.parts), root))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _windows_relative(source: str, root: str) -> str:
    source_path = PureWindowsPath(source)
    root_path = PureWindowsPath(root)
    try:
        relative = source_path.relative_to(root_path)
    except ValueError:
        source_parts = source_path.parts
        root_parts = root_path.parts
        if tuple(part.casefold() for part in source_parts[: len(root_parts)]) != tuple(
            part.casefold() for part in root_parts
        ):
            raise StorageResolutionError("source is not contained by configured root")
        relative = PureWindowsPath(*source_parts[len(root_parts) :])
    value = PurePosixPath(*relative.parts).as_posix()
    validate_relative_path(value)
    return value


def _portable_staged_path(digest: str, basename: str) -> str:
    value = PurePosixPath("staging", digest, basename).as_posix()
    validate_relative_path(value)
    return value


def _assert_contained(root: Path, target: Path) -> None:
    try:
        target.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError) as exc:
        raise StorageResolutionError("path escapes configured storage root") from exc
