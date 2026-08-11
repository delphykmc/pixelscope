from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final, Protocol

from pixelscope.core.recent_entries import (
    RECENT_ENTRY_LIMIT,
    RecentEntryKind,
    merge_recent_paths,
    normalize_recent_path,
    recent_path_identity,
)

RECENT_IMAGES_KEY: Final = "recent/images"
RECENT_FOLDERS_KEY: Final = "recent/folders"
RECENT_COMPARISON_SETS_KEY: Final = "recent/comparison_sets"


class RecentEntriesStorage(Protocol):
    def value(self, key: str, default: object = None) -> object: ...

    def set_value(self, key: str, value: object) -> None: ...

    def remove(self, key: str) -> None: ...

    def sync(self) -> None: ...


class RecentEntriesRepository:
    """Persist bounded typed workflow-entry history outside ApplicationSettings."""

    def __init__(
        self,
        storage: RecentEntriesStorage,
        *,
        limit: int = RECENT_ENTRY_LIMIT,
    ) -> None:
        if limit <= 0:
            raise ValueError("recent entry limit must be positive")
        self._storage = storage
        self._limit = limit

    def load(self, kind: RecentEntryKind) -> tuple[Path, ...]:
        raw = self._storage.value(self._key(kind), [])
        values: list[object]
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, (list, tuple)):
            values = list(raw)
        else:
            values = []

        loaded: list[Path] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value or "\x00" in value:
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                continue
            try:
                normalized = normalize_recent_path(candidate)
            except (OSError, RuntimeError, ValueError):
                continue
            identity = recent_path_identity(normalized)
            if identity in seen:
                continue
            seen.add(identity)
            loaded.append(normalized)
            if len(loaded) >= self._limit:
                break
        return tuple(loaded)

    def record(
        self,
        kind: RecentEntryKind,
        paths: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        merged = merge_recent_paths(self.load(kind), paths, limit=self._limit)
        self._write(kind, merged)
        return merged

    def remove(self, kind: RecentEntryKind, path: str | Path) -> tuple[Path, ...]:
        target = recent_path_identity(path)
        remaining = tuple(
            candidate
            for candidate in self.load(kind)
            if recent_path_identity(candidate) != target
        )
        self._write(kind, remaining)
        return remaining

    def clear(self, kind: RecentEntryKind | None = None) -> None:
        if kind is None:
            for candidate in RecentEntryKind:
                self._storage.remove(self._key(candidate))
        else:
            self._storage.remove(self._key(kind))
        self._storage.sync()

    def _write(self, kind: RecentEntryKind, paths: tuple[Path, ...]) -> None:
        key = self._key(kind)
        if paths:
            self._storage.set_value(key, [str(path) for path in paths])
        else:
            self._storage.remove(key)
        self._storage.sync()

    @staticmethod
    def _key(kind: RecentEntryKind) -> str:
        if kind is RecentEntryKind.IMAGE:
            return RECENT_IMAGES_KEY
        if kind is RecentEntryKind.FOLDER:
            return RECENT_FOLDERS_KEY
        if kind is RecentEntryKind.COMPARISON_SET:
            return RECENT_COMPARISON_SETS_KEY
        raise ValueError(f"unsupported recent entry kind: {kind!r}")
