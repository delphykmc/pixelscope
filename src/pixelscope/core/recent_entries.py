from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

RECENT_ENTRY_LIMIT: Final = 10


class RecentEntryKind(str, Enum):
    IMAGE = "image"
    FOLDER = "folder"
    COMPARISON_SET = "comparison_set"


@dataclass(frozen=True)
class RecentEntry:
    """One typed recent workflow-entry path."""

    kind: RecentEntryKind
    path: Path

    def __post_init__(self) -> None:
        normalized = normalize_recent_path(self.path)
        object.__setattr__(self, "path", normalized)


def normalize_recent_path(path: str | Path) -> Path:
    """Return a normalized absolute path without requiring it to exist."""

    value = str(path)
    if not value or "\x00" in value:
        raise ValueError("recent entry path must be a non-empty path without NUL characters")
    return Path(value).expanduser().resolve(strict=False)


def recent_path_identity(path: str | Path) -> str:
    """Return the platform-appropriate deduplication identity for a recent path."""

    return os.path.normcase(str(normalize_recent_path(path)))


def merge_recent_paths(
    existing: Sequence[Path],
    opened: Iterable[str | Path],
    *,
    limit: int = RECENT_ENTRY_LIMIT,
) -> tuple[Path, ...]:
    """Prepend a batch in supplied order, deduplicate, and enforce a hard bound."""

    if limit <= 0:
        raise ValueError("recent entry limit must be positive")

    merged: list[Path] = []
    seen: set[str] = set()
    for candidate in (*tuple(opened), *existing):
        normalized = normalize_recent_path(candidate)
        identity = recent_path_identity(normalized)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(normalized)
        if len(merged) >= limit:
            break
    return tuple(merged)
