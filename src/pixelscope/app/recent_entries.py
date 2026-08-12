from __future__ import annotations

import json
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
RECENT_SESSIONS_KEY: Final = "recent/sessions"
LEGACY_RECENT_COMPARISON_SETS_KEY: Final = "recent/comparison_sets"


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
        self._cache: dict[RecentEntryKind, tuple[Path, ...]] = {}

    def load(self, kind: RecentEntryKind) -> tuple[Path, ...]:
        cached = self._cache.get(kind)
        if cached is not None:
            return cached

        raw = self._storage.value(self._key(kind), [])
        if kind is RecentEntryKind.SESSION and not self._decode_values(raw):
            raw = self._storage.value(LEGACY_RECENT_COMPARISON_SETS_KEY, [])
        values = self._decode_values(raw)

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

        result = tuple(loaded)
        self._cache[kind] = result
        return result

    def record(
        self,
        kind: RecentEntryKind,
        paths: Iterable[str | Path],
    ) -> tuple[Path, ...]:
        merged = merge_recent_paths(self.load(kind), paths, limit=self._limit)
        self._write(kind, merged)
        if kind is RecentEntryKind.SESSION:
            self._storage.remove(LEGACY_RECENT_COMPARISON_SETS_KEY)
            self._storage.sync()
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
                self._cache[candidate] = ()
            self._storage.remove(LEGACY_RECENT_COMPARISON_SETS_KEY)
        else:
            self._storage.remove(self._key(kind))
            self._cache[kind] = ()
            if kind is RecentEntryKind.SESSION:
                self._storage.remove(LEGACY_RECENT_COMPARISON_SETS_KEY)
        self._storage.sync()

    @staticmethod
    def _decode_values(raw: object) -> list[object]:
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return [raw]
            if isinstance(decoded, list):
                return list(decoded)
            return [raw]
        if isinstance(raw, list | tuple):
            return list(raw)
        return []

    def _write(self, kind: RecentEntryKind, paths: tuple[Path, ...]) -> None:
        key = self._key(kind)
        if paths:
            payload = json.dumps(
                [str(path) for path in paths],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self._storage.set_value(key, payload)
        else:
            self._storage.remove(key)
        self._storage.sync()
        self._cache[kind] = paths

    @staticmethod
    def _key(kind: RecentEntryKind) -> str:
        if kind is RecentEntryKind.IMAGE:
            return RECENT_IMAGES_KEY
        if kind is RecentEntryKind.FOLDER:
            return RECENT_FOLDERS_KEY
        if kind is RecentEntryKind.SESSION:
            return RECENT_SESSIONS_KEY
        raise ValueError(f"unsupported recent entry kind: {kind!r}")
