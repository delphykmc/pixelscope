"""Qt-free portable shared-storage resolution and safe content-addressed staging."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO

from pixelscope.core.cancellation import cancellation_checkpoint
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


@dataclass(frozen=True)
class _StorageRootMatch:
    root: RemoteIqaStorageRoot
    relative_path: str
    specificity: tuple[int, int]


class _CheckpointReader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream

    def read(self, size: int = -1) -> bytes:
        cancellation_checkpoint()
        return self._stream.read(size)


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

    cancellation_checkpoint()
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            _update_hash(digest, stream, chunk_size)
    except OSError as exc:
        raise StorageResolutionError(f"unable to read source: {path.name}") from exc
    cancellation_checkpoint()
    return digest.hexdigest()


def _update_hash(digest: Any, stream: BinaryIO, chunk_size: int) -> None:
    while True:
        cancellation_checkpoint()
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        digest.update(chunk)


def resolve_existing_source(
    source: Path | str,
    settings: RemoteIqaSettings,
) -> ResolvedSource | None:
    """Resolve a source already under a configured root; longest safe match wins."""

    cancellation_checkpoint()
    source_path = Path(source)
    if not source_path.is_file():
        raise StorageResolutionError(f"source is missing or not a regular file: {source_path.name}")
    match = _longest_matching_root(source_path, settings.storage_roots)
    if match is None:
        return None
    return ResolvedSource(
        LogicalStoragePath(match.root.storage_root_id, match.relative_path),
        sha256_file(source_path),
        source_path,
        False,
    )


def stage_source(
    source: Path | str,
    staging_root: Path | str,
    storage_root_id: str,
) -> ResolvedSource:
    """Publish one source using content-addressed staging and atomic replacement."""

    cancellation_checkpoint()
    source_path = Path(source)
    if not source_path.is_file() or source_path.is_symlink():
        raise StorageResolutionError(f"source is missing or not a regular file: {source_path.name}")
    digest = sha256_file(source_path)
    relative_path = _portable_staged_path(digest, source_path.name)
    root = Path(staging_root)
    root_resolved = _resolve_existing_directory(root, "staging root")
    final_parent = _ensure_contained_directory(root, root_resolved, ("staging", digest))
    final = final_parent / source_path.name
    _assert_resolved_contained(root_resolved, _resolve_for_containment(final, strict=False))

    if _existing_staged_target_is_valid(final, digest):
        return _staged_source(storage_root_id, relative_path, digest, final)

    cancellation_checkpoint()
    part: Path | None = None
    fd = -1
    try:
        fd, part_name = tempfile.mkstemp(
            prefix=".pixelscope-iqa-",
            suffix=".part",
            dir=final_parent,
        )
        part = Path(part_name)
        output = os.fdopen(fd, "wb")
        fd = -1
        with source_path.open("rb") as src, output as dst:
            shutil.copyfileobj(
                _CheckpointReader(src),
                dst,
                length=COPY_CHUNK_BYTES,
            )
            cancellation_checkpoint()
            dst.flush()
            os.fsync(dst.fileno())
        if sha256_file(part) != digest:
            raise StorageResolutionError("staging copy failed SHA-256 verification")

        if _existing_staged_target_is_valid(final, digest):
            return _staged_source(storage_root_id, relative_path, digest, final)

        cancellation_checkpoint()
        try:
            os.replace(part, final)
        except OSError as publish_error:
            if _existing_staged_target_is_valid(final, digest):
                return _staged_source(storage_root_id, relative_path, digest, final)
            raise StorageResolutionError("unable to publish staged source") from publish_error
        part = None
        if not _existing_staged_target_is_valid(final, digest):
            raise StorageResolutionError(
                "published staged target failed SHA-256 identity verification"
            )
    except StorageResolutionError:
        raise
    except OSError as exc:
        raise StorageResolutionError("unable to publish staged source") from exc
    finally:
        if fd >= 0:
            with suppress(OSError):
                os.close(fd)
        if part is not None:
            with suppress(OSError):
                part.unlink(missing_ok=True)

    return _staged_source(storage_root_id, relative_path, digest, final)


def resolve_or_stage_source(
    source: Path | str,
    settings: RemoteIqaSettings,
) -> ResolvedSource:
    """Resolve a configured source or safely stage it under the selected staging root."""

    cancellation_checkpoint()
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
    cancellation_checkpoint()
    return stage_source(source, root_path, staging.storage_root_id)


def resolve_result_reference(
    storage_root_id: str,
    relative_path: str,
    settings: RemoteIqaSettings,
) -> Path:
    """Resolve a server logical result reference using the current settings snapshot."""

    validate_relative_path(relative_path)
    root = settings.root(storage_root_id)
    if root is None:
        raise StorageResolutionError(f"storage root '{storage_root_id}' is not configured")
    root_path = Path(root.client_path)
    root_resolved = _resolve_existing_directory(root_path, f"storage root '{storage_root_id}'")
    target = root_path.joinpath(*PurePosixPath(relative_path).parts)
    target_resolved = _resolve_for_containment(target, strict=True)
    _assert_resolved_contained(root_resolved, target_resolved)
    if not target_resolved.is_dir():
        raise StorageResolutionError("result directory is unavailable")
    return target


def _longest_matching_root(
    source: Path,
    roots: tuple[RemoteIqaStorageRoot, ...],
) -> _StorageRootMatch | None:
    """Choose the most specific root whose resolved path safely contains source."""

    cancellation_checkpoint()
    source_resolved = _resolve_for_containment(source, strict=True)
    matches: list[_StorageRootMatch] = []
    for root in roots:
        cancellation_checkpoint()
        root_windows = PureWindowsPath(root.client_path)
        try:
            root_resolved = _resolve_for_containment(Path(root.client_path), strict=True)
        except StorageResolutionError:
            continue
        if not _resolved_is_within(root_resolved, source_resolved):
            continue
        relative_path = _relative_for_matching_root(
            source,
            root.client_path,
            source_resolved,
            root_resolved,
        )
        matches.append(
            _StorageRootMatch(
                root=root,
                relative_path=relative_path,
                specificity=(len(root_resolved.parts), len(root_windows.parts)),
            )
        )
    if not matches:
        return None
    return max(matches, key=lambda item: item.specificity)


def _relative_for_matching_root(
    source: Path,
    root: str,
    source_resolved: Path,
    root_resolved: Path,
) -> str:
    try:
        return _windows_relative(str(source), root)
    except StorageResolutionError:
        return _resolved_relative(source_resolved, root_resolved)


def _resolved_relative(source_resolved: Path, root_resolved: Path) -> str:
    try:
        relative = source_resolved.relative_to(root_resolved)
    except ValueError:
        try:
            relative = Path(
                os.path.relpath(
                    os.fspath(source_resolved),
                    os.fspath(root_resolved),
                )
            )
        except ValueError as exc:
            raise StorageResolutionError(
                "source is not contained by configured root"
            ) from exc
    value = PurePosixPath(*relative.parts).as_posix()
    validate_relative_path(value)
    return value


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
            raise StorageResolutionError("source is not contained by configured root") from None
        relative = PureWindowsPath(*source_parts[len(root_parts) :])
    value = PurePosixPath(*relative.parts).as_posix()
    validate_relative_path(value)
    return value


def _portable_staged_path(digest: str, basename: str) -> str:
    value = PurePosixPath("staging", digest, basename).as_posix()
    validate_relative_path(value)
    return value


def _staged_source(
    storage_root_id: str,
    relative_path: str,
    digest: str,
    final: Path,
) -> ResolvedSource:
    return ResolvedSource(
        LogicalStoragePath(storage_root_id, relative_path),
        digest,
        final,
        True,
    )


def _existing_staged_target_is_valid(final: Path, digest: str) -> bool:
    cancellation_checkpoint()
    if final.is_symlink():
        raise StorageResolutionError("existing staged target is not a regular file")
    if not final.exists():
        return False
    if not final.is_file():
        raise StorageResolutionError("existing staged target is not a regular file")
    if sha256_file(final) != digest:
        raise StorageResolutionError("existing staged target failed SHA-256 identity verification")
    return True


def _ensure_contained_directory(
    root: Path,
    root_resolved: Path,
    relative_parts: tuple[str, ...],
) -> Path:
    """Create child directories only after their parent resolves inside root."""

    current = root
    current_resolved = root_resolved
    for part in relative_parts:
        cancellation_checkpoint()
        _assert_resolved_contained(root_resolved, current_resolved)
        candidate = current / part
        try:
            candidate.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise StorageResolutionError("unable to create staging directory") from exc

        candidate_resolved = _resolve_for_containment(candidate, strict=True)
        _assert_resolved_contained(root_resolved, candidate_resolved)
        if not candidate_resolved.is_dir():
            raise StorageResolutionError("staging path is not a directory")

        current = candidate
        current_resolved = candidate_resolved
    return current_resolved


def _resolve_existing_directory(path: Path, label: str) -> Path:
    resolved = _resolve_for_containment(path, strict=True)
    if not resolved.is_dir():
        raise StorageResolutionError(f"{label} is unavailable")
    return resolved


def _resolve_for_containment(path: Path, *, strict: bool) -> Path:
    try:
        return path.resolve(strict=strict)
    except (OSError, RuntimeError) as exc:
        raise StorageResolutionError("unable to resolve storage path") from exc


def _assert_resolved_contained(root_resolved: Path, target_resolved: Path) -> None:
    if not _resolved_is_within(root_resolved, target_resolved):
        raise StorageResolutionError("path escapes configured storage root")


def _resolved_is_within(root_resolved: Path, target_resolved: Path) -> bool:
    try:
        common = os.path.commonpath((os.fspath(root_resolved), os.fspath(target_resolved)))
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(os.fspath(root_resolved))
