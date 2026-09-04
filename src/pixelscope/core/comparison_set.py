from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds

SESSION_KIND = "pixelscope-session"
LEGACY_COMPARISON_SET_KIND = "pixelscope-comparison-set"
SESSION_SCHEMA_VERSION = 1
SESSION_LAYOUTS = frozenset({"Auto", "Single View", "Multi View"})
SESSION_DISPLAY_GAINS = frozenset({1.0, 2.0, 4.0, 8.0, 16.0})
SESSION_DIFFERENCE_CHANNELS = frozenset(
    {"All", "R", "G", "B", "Gray", "Mosaic", "Gr", "Gb", "Y", "U", "V"}
)
SESSION_DIFFERENCE_MODES = frozenset({"Absolute", "Mask"})
SESSION_DIFFERENCE_REGIONS = frozenset({"Full image", "Active ROI"})
SESSION_DIFFERENCE_MAX_THRESHOLD = 65535.0
SESSION_DIFFERENCE_MAX_GAIN = 1000

COMPARISON_SET_KIND = SESSION_KIND
COMPARISON_SET_SCHEMA_VERSION = SESSION_SCHEMA_VERSION
COMPARISON_SET_LAYOUTS = SESSION_LAYOUTS


class ComparisonSetError(ValueError):
    """Raised when a PixelScope Session artifact cannot be validated."""


SessionError = ComparisonSetError


def normalize_source_path(path: str | Path) -> str:
    """Return the canonical absolute local source reference used by Session v1."""

    if isinstance(path, str) and not path.strip():
        raise ComparisonSetError("session source path must not be empty")
    return str(Path(path).expanduser().resolve(strict=False))


@dataclass(frozen=True)
class SessionSource:
    """One persistent source reference plus optional resolved RAW profile payload."""

    path: str
    raw_profile: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        normalized = normalize_source_path(self.path)
        if not Path(normalized).is_absolute():
            raise ComparisonSetError("session source path must be absolute")
        object.__setattr__(self, "path", normalized)


@dataclass(frozen=True)
class SessionDifference:
    """Regenerable Difference recipe; calculated maps/cache are never persisted."""

    image_a_path: str
    image_b_path: str
    channel: str = "All"
    mode: str = "Absolute"
    threshold: float = 10.0
    gain: int = 1
    region: str = "Full image"

    def __post_init__(self) -> None:
        a = normalize_source_path(self.image_a_path)
        b = normalize_source_path(self.image_b_path)
        if a.casefold() == b.casefold():
            raise ComparisonSetError("session Difference sources must be different")
        if not isinstance(self.channel, str) or self.channel not in SESSION_DIFFERENCE_CHANNELS:
            raise ComparisonSetError(f"unsupported Difference channel: {self.channel!r}")
        if not isinstance(self.mode, str) or self.mode not in SESSION_DIFFERENCE_MODES:
            raise ComparisonSetError(f"unsupported Difference mode: {self.mode!r}")
        if not isinstance(self.region, str) or self.region not in SESSION_DIFFERENCE_REGIONS:
            raise ComparisonSetError(f"unsupported Difference region: {self.region!r}")
        if (
            not isinstance(self.threshold, int | float)
            or isinstance(self.threshold, bool)
            or not isfinite(float(self.threshold))
            or not 0.0 <= float(self.threshold) <= SESSION_DIFFERENCE_MAX_THRESHOLD
        ):
            raise ComparisonSetError("session Difference threshold is invalid")
        if (
            not isinstance(self.gain, int)
            or isinstance(self.gain, bool)
            or not 1 <= self.gain <= SESSION_DIFFERENCE_MAX_GAIN
        ):
            raise ComparisonSetError("session Difference gain is invalid")
        object.__setattr__(self, "image_a_path", a)
        object.__setattr__(self, "image_b_path", b)
        object.__setattr__(self, "threshold", float(self.threshold))


@dataclass(frozen=True)
class Session:
    """Durable user workspace intent; runtime/derived resources remain transient."""

    registered_sources: tuple[SessionSource, ...]
    selected_paths: tuple[str, ...] = ()
    page_anchor_path: str | None = None
    active_path: str | None = None
    primary_path: str | None = None
    layout_mode: str = "Auto"
    roi: RoiBounds | None = None
    line: LineSelection | None = None
    display_gain: float = 1.0
    split_channels: bool = False
    difference: SessionDifference | None = None
    kind: str = SESSION_KIND
    schema_version: int = SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind != SESSION_KIND:
            raise ComparisonSetError(f"unsupported session kind: {self.kind!r}")
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version != SESSION_SCHEMA_VERSION
        ):
            raise ComparisonSetError(f"unsupported session schema version: {self.schema_version!r}")
        if not self.registered_sources:
            raise ComparisonSetError("session must contain at least one registered source")
        if self.layout_mode not in SESSION_LAYOUTS:
            raise ComparisonSetError(f"unsupported layout mode: {self.layout_mode!r}")
        if (
            not isinstance(self.display_gain, int | float)
            or isinstance(self.display_gain, bool)
            or not isfinite(float(self.display_gain))
            or float(self.display_gain) not in SESSION_DISPLAY_GAINS
        ):
            raise ComparisonSetError(f"unsupported display gain: {self.display_gain!r}")

        registered_ids = [source.path.casefold() for source in self.registered_sources]
        if len(registered_ids) != len(set(registered_ids)):
            raise ComparisonSetError("session contains duplicate registered source paths")
        registered = set(registered_ids)

        selected = tuple(normalize_source_path(path) for path in self.selected_paths)
        selected_ids = [path.casefold() for path in selected]
        if len(selected_ids) != len(set(selected_ids)):
            raise ComparisonSetError("session contains duplicate Selected source paths")
        if any(identity not in registered for identity in selected_ids):
            raise ComparisonSetError("Selected source is not registered in the session")

        active = normalize_source_path(self.active_path) if self.active_path else None
        primary = normalize_source_path(self.primary_path) if self.primary_path else None
        selected_set = set(selected_ids)
        if active is not None and active.casefold() not in selected_set:
            raise ComparisonSetError("active source is not a Selected session member")
        if primary is not None and primary.casefold() not in selected_set:
            raise ComparisonSetError("primary source is not a Selected session member")
        if self.difference is not None:
            for path in (
                self.difference.image_a_path,
                self.difference.image_b_path,
            ):
                if path.casefold() not in selected_set:
                    raise ComparisonSetError("Difference source is not a Selected session member")
            if self.difference.region == "Active ROI" and self.roi is None:
                raise ComparisonSetError("Active ROI Difference requires a saved ROI")

        page_anchor = (
            normalize_source_path(self.page_anchor_path) if self.page_anchor_path else None
        )
        if page_anchor is None:
            if primary is not None:
                page_anchor = primary
            elif active is not None:
                page_anchor = active
            elif self.difference is not None:
                page_anchor = self.difference.image_a_path
            elif selected:
                page_anchor = selected[0]
        if page_anchor is not None and page_anchor.casefold() not in selected_set:
            raise ComparisonSetError("page anchor is not a Selected session member")

        object.__setattr__(self, "selected_paths", selected)
        object.__setattr__(self, "page_anchor_path", page_anchor)
        object.__setattr__(self, "active_path", active)
        object.__setattr__(self, "primary_path", primary)
        object.__setattr__(self, "display_gain", float(self.display_gain))

    @property
    def sources(self) -> tuple[SessionSource, ...]:
        """Legacy P4-B view of Selected members in logical Selected order."""

        by_path = {source.path.casefold(): source for source in self.registered_sources}
        return tuple(by_path[path.casefold()] for path in self.selected_paths)


ComparisonSetSource = SessionSource


def ComparisonSet(
    *,
    sources: tuple[SessionSource, ...],
    active_path: str | None = None,
    primary_path: str | None = None,
    layout_mode: str = "Auto",
) -> Session:
    """Legacy P4-B constructor facade returning the new Session domain object."""

    return Session(
        registered_sources=sources,
        selected_paths=tuple(source.path for source in sources),
        page_anchor_path=active_path,
        active_path=active_path,
        primary_path=primary_path,
        layout_mode=layout_mode,
    )
