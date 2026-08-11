from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPARISON_SET_KIND = "pixelscope-comparison-set"
COMPARISON_SET_SCHEMA_VERSION = 1
COMPARISON_SET_LAYOUTS = frozenset({"Auto", "Single View", "Multi View"})


class ComparisonSetError(ValueError):
    """Raised when a comparison-set artifact cannot be validated."""


def normalize_source_path(path: str | Path) -> str:
    """Return the canonical absolute local source reference used by v1 artifacts."""

    if isinstance(path, str) and not path.strip():
        raise ComparisonSetError("comparison-set source path must not be empty")
    return str(Path(path).expanduser().resolve(strict=False))


@dataclass(frozen=True)
class ComparisonSetSource:
    """One persistent source reference plus optional resolved RAW profile payload."""

    path: str
    raw_profile: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        normalized = normalize_source_path(self.path)
        if not Path(normalized).is_absolute():
            raise ComparisonSetError("comparison-set source path must be absolute")
        object.__setattr__(self, "path", normalized)


@dataclass(frozen=True)
class ComparisonSet:
    """Qt-free v1 logical comparison state; the comparison page stays derived."""

    sources: tuple[ComparisonSetSource, ...]
    active_path: str | None = None
    primary_path: str | None = None
    layout_mode: str = "Auto"
    kind: str = COMPARISON_SET_KIND
    schema_version: int = COMPARISON_SET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind != COMPARISON_SET_KIND:
            raise ComparisonSetError(
                f"unsupported comparison-set kind: {self.kind!r}"
            )
        if self.schema_version != COMPARISON_SET_SCHEMA_VERSION:
            raise ComparisonSetError(
                f"unsupported comparison-set schema version: {self.schema_version}"
            )
        if not self.sources:
            raise ComparisonSetError("comparison set must contain at least one source")
        if self.layout_mode not in COMPARISON_SET_LAYOUTS:
            raise ComparisonSetError(
                f"unsupported layout mode: {self.layout_mode!r}"
            )

        identities = [source.path.casefold() for source in self.sources]
        if len(identities) != len(set(identities)):
            raise ComparisonSetError("comparison set contains duplicate source paths")

        source_identities = set(identities)
        active = normalize_source_path(self.active_path) if self.active_path else None
        primary = (
            normalize_source_path(self.primary_path) if self.primary_path else None
        )
        if active is not None and active.casefold() not in source_identities:
            raise ComparisonSetError(
                "active source is not a member of the comparison set"
            )
        if primary is not None and primary.casefold() not in source_identities:
            raise ComparisonSetError(
                "primary source is not a member of the comparison set"
            )
        object.__setattr__(self, "active_path", active)
        object.__setattr__(self, "primary_path", primary)
