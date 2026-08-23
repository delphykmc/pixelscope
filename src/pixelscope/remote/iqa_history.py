"""Qt-free historical Remote IQA result locator and Recent-entry domain."""

from __future__ import annotations

import ntpath
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, TypeAlias

from pixelscope.remote.iqa_settings import RemoteIqaSettings, validate_storage_root_id
from pixelscope.remote.iqa_storage import (
    StorageResolutionError,
    resolve_result_reference,
    validate_relative_path,
)

RECENT_IQA_ENTRY_VERSION = 1
RECENT_IQA_RESULT_LIMIT = 10
MAX_RECENT_IQA_JSON_CHARS = 64 * 1024
MAX_RESULT_ID_LENGTH = 256
MAX_LOCAL_RESULT_PATH_LENGTH = 4096
MAX_SCHEMA_VERSION = 999


class IqaHistoryMetadataError(ValueError):
    """Persisted historical-IQA observer metadata is malformed or unsupported."""


@dataclass(frozen=True)
class LogicalIqaResultLocator:
    """Portable production locator resolved through current Remote IQA settings."""

    storage_root_id: str
    relative_path: str

    def __post_init__(self) -> None:
        try:
            validate_storage_root_id(self.storage_root_id)
            validate_relative_path(self.relative_path)
        except (ValueError, StorageResolutionError) as exc:
            raise IqaHistoryMetadataError(str(exc)) from exc

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        return (
            "logical",
            self.storage_root_id,
            PurePosixPath(self.relative_path).as_posix(),
        )

    @property
    def display_location(self) -> str:
        return f"{self.storage_root_id}/{self.relative_path}"


@dataclass(frozen=True)
class LocalIqaResultLocator:
    """Machine-dependent absolute local result directory locator."""

    absolute_path: str

    def __post_init__(self) -> None:
        value = self.absolute_path
        if (
            not isinstance(value, str)
            or not value
            or value.strip() != value
            or "\x00" in value
            or len(value) > MAX_LOCAL_RESULT_PATH_LENGTH
            or not _is_absolute_local_path(value)
        ):
            raise IqaHistoryMetadataError("local result path must be a bounded absolute path")

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        return ("local", "", _normalized_local_identity(self.absolute_path))

    @property
    def display_location(self) -> str:
        return self.absolute_path


IqaResultLocator: TypeAlias = LogicalIqaResultLocator | LocalIqaResultLocator


@dataclass(frozen=True)
class IqaResultIdentity:
    result_id: str
    schema_version: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.result_id, str)
            or not self.result_id
            or self.result_id.strip() != self.result_id
            or "\x00" in self.result_id
            or len(self.result_id) > MAX_RESULT_ID_LENGTH
        ):
            raise IqaHistoryMetadataError("result_id must be a non-empty bounded string")
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or not 1 <= self.schema_version <= MAX_SCHEMA_VERSION
        ):
            raise IqaHistoryMetadataError("schema_version must be a bounded positive integer")


@dataclass(frozen=True)
class RecentIqaResultEntry:
    locator: IqaResultLocator
    identity: IqaResultIdentity

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        return self.locator.dedup_key

    @property
    def result_id(self) -> str:
        return self.identity.result_id

    @property
    def schema_version(self) -> int:
        return self.identity.schema_version


def serialize_recent_iqa_entry(entry: RecentIqaResultEntry) -> dict[str, Any]:
    locator: dict[str, Any]
    if isinstance(entry.locator, LogicalIqaResultLocator):
        locator = {
            "kind": "logical",
            "storage_root_id": entry.locator.storage_root_id,
            "relative_path": entry.locator.relative_path,
        }
    else:
        locator = {
            "kind": "local",
            "absolute_path": entry.locator.absolute_path,
        }
    return {
        "version": RECENT_IQA_ENTRY_VERSION,
        "locator": locator,
        "result_id": entry.result_id,
        "schema_version": entry.schema_version,
    }


def parse_recent_iqa_entry(value: object) -> RecentIqaResultEntry | None:
    """Parse one untrusted observer record; malformed/future records are ignored."""

    if not isinstance(value, dict) or set(value) != {
        "version",
        "locator",
        "result_id",
        "schema_version",
    }:
        return None
    if value.get("version") != RECENT_IQA_ENTRY_VERSION:
        return None
    raw_locator = value.get("locator")
    if not isinstance(raw_locator, dict):
        return None
    try:
        locator = _parse_locator(raw_locator)
        identity = IqaResultIdentity(
            _require_string(value.get("result_id")),
            _require_int(value.get("schema_version")),
        )
        return RecentIqaResultEntry(locator, identity)
    except (IqaHistoryMetadataError, TypeError, ValueError):
        return None


def locator_for_manual_result(
    path: Path | str,
    settings: RemoteIqaSettings,
    *,
    schema_version: int,
) -> IqaResultLocator:
    """Canonicalize a successful explicit local open without touching source files.

    Schema-v1 compatibility remains local. Schema-v2 uses lexical matching only to
    propose portable candidates; a candidate becomes logical history only when the
    authoritative P5-C result resolver maps it back to the same canonical directory.
    """

    value = str(path)
    local = LocalIqaResultLocator(_absolute_local_text(value))
    if schema_version == 1:
        return local
    source = PureWindowsPath(value)
    matches: list[tuple[int, str, str]] = []
    source_parts = tuple(part.casefold() for part in source.parts)
    for root in settings.storage_roots:
        root_path = PureWindowsPath(root.client_path)
        root_parts = tuple(part.casefold() for part in root_path.parts)
        if not root_parts or source_parts[: len(root_parts)] != root_parts:
            continue
        relative_parts = source.parts[len(root_path.parts) :]
        if not relative_parts:
            continue
        relative = PurePosixPath(*relative_parts).as_posix()
        try:
            validate_relative_path(relative)
        except StorageResolutionError:
            continue
        matches.append((len(root_path.parts), root.storage_root_id, relative))
    for _length, root_id, relative in sorted(matches, reverse=True):
        try:
            resolved = resolve_result_reference(root_id, relative, settings)
        except (OSError, StorageResolutionError):
            continue
        if _same_existing_directory(Path(value), resolved):
            return LogicalIqaResultLocator(root_id, relative)
    return local


def locator_leaf(locator: IqaResultLocator) -> str:
    if isinstance(locator, LogicalIqaResultLocator):
        return PurePosixPath(locator.relative_path).name or locator.relative_path
    windows = PureWindowsPath(locator.absolute_path)
    if windows.is_absolute():
        return windows.name or locator.absolute_path
    return Path(locator.absolute_path).name or locator.absolute_path


def _parse_locator(value: dict[str, Any]) -> IqaResultLocator:
    kind = value.get("kind")
    if kind == "logical" and set(value) == {
        "kind",
        "storage_root_id",
        "relative_path",
    }:
        return LogicalIqaResultLocator(
            _require_string(value.get("storage_root_id")),
            _require_string(value.get("relative_path")),
        )
    if kind == "local" and set(value) == {"kind", "absolute_path"}:
        return LocalIqaResultLocator(_require_string(value.get("absolute_path")))
    raise IqaHistoryMetadataError("unknown or malformed historical result locator")


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        raise IqaHistoryMetadataError("expected string")
    return value


def _require_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IqaHistoryMetadataError("expected integer")
    return value


def _is_absolute_local_path(value: str) -> bool:
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _absolute_local_text(value: str) -> str:
    if _is_absolute_local_path(value):
        return value
    return str(Path(value).absolute())


def _same_existing_directory(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=True) == right.resolve(strict=True)
    except OSError:
        return False


def _normalized_local_identity(value: str) -> str:
    windows = PureWindowsPath(value)
    if windows.is_absolute():
        normalized = ntpath.normpath(str(windows)).replace("/", "\\")
        return normalized.casefold()
    return os.path.normcase(os.path.normpath(value))
