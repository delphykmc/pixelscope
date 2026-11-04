"""Versioned, Qt-free viewport intent for a verified Review source set.

Physical scale is *physical screen pixels per reference pixel*, not a Qt ViewBox
range or a device-independent zoom factor.  Runtime document IDs, widgets, arrays,
workers, aliases and original source paths are intentionally absent.

The W09 repository may serialize :meth:`to_dict`; a source resolver must verify
durable keys independently before applying the record to live documents.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any
from uuid import UUID

REVIEW_VIEW_STATE_VERSION = 1
SUPPORTED_LAYOUTS = frozenset(
    {"Auto", "Single", "Focus + 2", "Grid 2x2", "Grid 3x2"}
)
SUPPORTED_PRESENTATIONS = frozenset(
    {"originals", "difference", "difference_focus", "single", "channel_split"}
)


def _source_key(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("source key must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("source key must be a canonical UUID string") from exc
    if str(parsed) != value:
        raise ValueError("source key must be a canonical lowercase UUID")
    return value


def _pair(value: object, *, name: str) -> tuple[float, float]:
    if not isinstance(value, tuple | list) or len(value) != 2:
        raise ValueError(f"{name} must contain exactly two coordinates")
    if any(type(number) not in (float, int) for number in value):
        raise ValueError(f"{name} requires finite numeric coordinates")
    pair = (float(value[0]), float(value[1]))
    if not all(isfinite(number) for number in pair):
        raise ValueError(f"{name} must be finite")
    return pair


def _shape(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, tuple | list)
        or len(value) != 2
        or any(not isinstance(number, int) or isinstance(number, bool) or number <= 0 for number in value)
    ):
        raise ValueError("reference shape must be positive integer (rows, columns)")
    return int(value[0]), int(value[1])


def _center_in_shape(center: tuple[float, float], shape: tuple[int, int]) -> bool:
    return 0 <= center[0] < shape[1] and 0 <= center[1] < shape[0]


def _scale(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise ValueError("physical scale must be a positive finite number")
    scale = float(value)
    if not isfinite(scale) or scale <= 0:
        raise ValueError("physical scale must be a positive finite number")
    return scale


@dataclass(frozen=True)
class ReviewViewportV1:
    center_ref_xy: tuple[float, float]
    physical_scale: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "center_ref_xy", _pair(self.center_ref_xy, name="center"))
        object.__setattr__(self, "physical_scale", _scale(self.physical_scale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_ref_xy": list(self.center_ref_xy),
            "physical_scale": self.physical_scale,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReviewViewportV1:
        if not isinstance(value, Mapping) or set(value) != {
            "center_ref_xy", "physical_scale"
        }:
            raise ValueError("invalid review viewport fields")
        return cls(value["center_ref_xy"], value["physical_scale"])


@dataclass(frozen=True)
class ReviewViewStateV1:
    """Serializable intent; resolution/authorization stays with the owner.

    `source_shapes_ref` and `reference_shape` are native reference-space
    dimensions captured at inspection. They are strict restore preconditions;
    they are not allowed to silently clamp or resize old findings.
    """

    reference_source_key: str
    page_source_keys: tuple[str, ...]
    active_source_key: str
    primary_source_key: str
    layout_kind: str
    presentation_mode: str
    sync_enabled: bool
    center_ref_xy: tuple[float, float]
    physical_scale: float
    reference_shape: tuple[int, int]
    source_shapes_ref: Mapping[str, tuple[int, int]]
    per_source: Mapping[str, ReviewViewportV1]
    visible_bounds_ref: tuple[float, float, float, float] | None = None
    schema_version: int = REVIEW_VIEW_STATE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise ValueError("unsupported ReviewViewState schema_version")
        page = tuple(_source_key(key) for key in self.page_source_keys)
        if not 1 <= len(page) <= 6 or len(page) != len(set(page)):
            raise ValueError("page must contain 1..6 distinct durable source keys")
        object.__setattr__(self, "page_source_keys", page)
        for name in ("reference_source_key", "active_source_key", "primary_source_key"):
            key = _source_key(getattr(self, name))
            if key not in page:
                raise ValueError(f"{name} is not in the comparison page")
        if not isinstance(self.layout_kind, str) or self.layout_kind not in SUPPORTED_LAYOUTS:
            raise ValueError("unknown review layout")
        if (
            not isinstance(self.presentation_mode, str)
            or self.presentation_mode not in SUPPORTED_PRESENTATIONS
        ):
            raise ValueError("unknown review presentation mode")
        if not isinstance(self.sync_enabled, bool):
            raise ValueError("sync_enabled must be bool")
        if self.presentation_mode == "single" and len(page) != 1:
            raise ValueError("single presentation requires exactly one source")
        object.__setattr__(self, "center_ref_xy", _pair(self.center_ref_xy, name="center"))
        object.__setattr__(self, "physical_scale", _scale(self.physical_scale))
        shape = _shape(self.reference_shape)
        object.__setattr__(self, "reference_shape", shape)
        if not isinstance(self.source_shapes_ref, Mapping):
            raise ValueError("source_shapes_ref must be a mapping")
        source_shapes = {
            _source_key(key): _shape(value) for key, value in self.source_shapes_ref.items()
        }
        if set(source_shapes) != set(page):
            raise ValueError("source_shapes_ref must cover exactly the comparison page")
        if source_shapes[self.reference_source_key] != shape:
            raise ValueError("reference shape disagrees with source_shapes_ref")
        if not _center_in_shape(self.center_ref_xy, shape):
            raise ValueError("reference center falls outside reference coordinates")
        if self.sync_enabled and any(
            not _center_in_shape(self.center_ref_xy, dimensions)
            for dimensions in source_shapes.values()
        ):
            raise ValueError("shared center falls outside a page source reference grid")
        object.__setattr__(self, "source_shapes_ref", MappingProxyType(source_shapes))
        if not isinstance(self.per_source, Mapping):
            raise ValueError("per_source must be a mapping")
        viewports: dict[str, ReviewViewportV1] = {}
        for key, viewport in self.per_source.items():
            _source_key(key)
            if not isinstance(viewport, ReviewViewportV1):
                raise ValueError("per_source values must be ReviewViewportV1")
            viewports[key] = viewport
        for key, viewport in viewports.items():
            if not _center_in_shape(viewport.center_ref_xy, source_shapes.get(key, (0, 0))):
                raise ValueError("source center falls outside its reference coordinates")
        if self.sync_enabled and viewports:
            raise ValueError("synchronized capture must use the shared viewport")
        if not self.sync_enabled and set(viewports) != set(page):
            raise ValueError("unsynchronized capture requires every page viewport")
        object.__setattr__(self, "per_source", MappingProxyType(viewports))
        if self.visible_bounds_ref is not None:
            bounds = self.visible_bounds_ref
            if (
                not isinstance(bounds, (tuple, list))
                or len(bounds) != 4
                or any(type(x) not in (int, float) or not isfinite(float(x)) for x in bounds)
                or float(bounds[2]) <= float(bounds[0])
                or float(bounds[3]) <= float(bounds[1])
            ):
                raise ValueError("visible bounds must be finite (left, top, right, bottom)")
            object.__setattr__(self, "visible_bounds_ref", tuple(float(x) for x in bounds))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reference_source_key": self.reference_source_key,
            "page_source_keys": list(self.page_source_keys),
            "active_source_key": self.active_source_key,
            "primary_source_key": self.primary_source_key,
            "layout_kind": self.layout_kind,
            "presentation_mode": self.presentation_mode,
            "sync_enabled": self.sync_enabled,
            "center_ref_xy": list(self.center_ref_xy),
            "physical_scale": self.physical_scale,
            "reference_shape": list(self.reference_shape),
            "source_shapes_ref": {
                key: list(self.source_shapes_ref[key]) for key in self.page_source_keys
            },
            "per_source": {
                key: self.per_source[key].to_dict()
                for key in self.page_source_keys if key in self.per_source
            },
            "visible_bounds_ref": (
                list(self.visible_bounds_ref) if self.visible_bounds_ref is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReviewViewStateV1:
        if not isinstance(value, Mapping):
            raise ValueError("review view state must be a mapping")
        required = {
            "schema_version", "reference_source_key", "page_source_keys",
            "active_source_key", "primary_source_key", "layout_kind",
            "presentation_mode", "sync_enabled", "center_ref_xy",
            "physical_scale", "reference_shape", "source_shapes_ref",
            "per_source", "visible_bounds_ref",
        }
        if set(value) != required:
            raise ValueError("invalid ReviewViewState fields")
        raw_per_source = value["per_source"]
        if not isinstance(raw_per_source, Mapping):
            raise ValueError("per_source must be a mapping")
        page = value["page_source_keys"]
        if not isinstance(page, (tuple, list)):
            raise ValueError("page_source_keys must be an ordered sequence")
        return cls(
            reference_source_key=value["reference_source_key"],
            page_source_keys=tuple(page),
            active_source_key=value["active_source_key"],
            primary_source_key=value["primary_source_key"],
            layout_kind=value["layout_kind"],
            presentation_mode=value["presentation_mode"],
            sync_enabled=value["sync_enabled"],
            center_ref_xy=value["center_ref_xy"],
            physical_scale=value["physical_scale"],
            reference_shape=value["reference_shape"],
            source_shapes_ref=value["source_shapes_ref"],
            per_source={
                key: ReviewViewportV1.from_dict(item)
                for key, item in raw_per_source.items()
            },
            visible_bounds_ref=value["visible_bounds_ref"],
            schema_version=value["schema_version"],
        )
