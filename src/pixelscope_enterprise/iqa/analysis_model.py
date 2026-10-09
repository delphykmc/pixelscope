"""Qt-free, downstream-owned presentation data for the one-pair IQA window.

The adapter supplying these types must already have verified official comparison
semantics and converted them to the documented quality-oriented A/B convention.
This module does not infer a relative metric from per-image scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Availability = Literal["available", "partial", "missing", "failed"]
Roi = tuple[float, float, float, float]

_MAX_CELLS = 4_000_000


@dataclass(frozen=True)
class SpatialMap:
    """One verified 2-D signed spatial grid in original-image coordinates."""

    values: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    image_width: int
    image_height: int
    block_width: float
    block_height: float
    origin_x: float = 0.0
    origin_y: float = 0.0

    def __post_init__(self) -> None:
        values = np.asarray(self.values)
        valid = np.asarray(self.valid_mask)
        if values.ndim != 2 or values.size == 0 or values.size > _MAX_CELLS:
            raise ValueError("spatial grid size or dimensions are invalid")
        if values.dtype.kind not in "fiu" or valid.dtype.kind != "b":
            raise ValueError("spatial grid must contain numeric values and a boolean mask")
        if values.shape != valid.shape:
            raise ValueError("spatial values and mask dimensions differ")
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("original image dimensions must be positive")
        geometry = [self.block_width, self.block_height, self.origin_x, self.origin_y]
        if not np.isfinite(geometry).all():
            raise ValueError("non-finite grid geometry")
        if self.block_width <= 0 or self.block_height <= 0:
            raise ValueError("grid cell extents must be positive")
        if self.origin_x < 0 or self.origin_y < 0:
            raise ValueError("grid origin must lie within nonnegative image coordinates")
        # Guard the adapter boundary. Invalid cells may be NaN; valid ones may not.
        if not np.isfinite(values[valid]).all():
            raise ValueError("valid spatial cells must have finite values")
        frozen_values = np.array(values, dtype=np.float64, copy=True)
        frozen_mask = np.array(valid, dtype=np.bool_, copy=True)
        frozen_values.flags.writeable = False
        frozen_mask.flags.writeable = False
        object.__setattr__(self, "values", frozen_values)
        object.__setattr__(self, "valid_mask", frozen_mask)

    @property
    def rows(self) -> int:
        return int(self.values.shape[0])

    @property
    def columns(self) -> int:
        return int(self.values.shape[1])


@dataclass(frozen=True)
class AttributeDisplay:
    """Already-oriented client view, not the producer's wire schema."""

    attribute_id: str
    label: str
    unit: str
    group: str
    official_value: float | None
    official_availability: Availability
    quality_oriented: bool
    fixed_range: float
    spatial: SpatialMap | None = None
    # Independent display contract for OFFICIAL scalar chart; never inherited
    # from fixed_range (which exclusively controls the spatial map colors).
    chart_axis_range: float | None = None

    def __post_init__(self) -> None:
        if not self.attribute_id or not self.label or not self.unit:
            raise ValueError("attribute identity, label and unit are required")
        if self.official_availability not in {"available", "partial", "missing", "failed"}:
            raise ValueError("invalid official availability")
        if self.official_value is not None and not np.isfinite(self.official_value):
            raise ValueError("official value must be finite when provided")
        if self.official_availability in {"missing", "failed"} and self.official_value is not None:
            raise ValueError("missing/failed official value must be absent")
        if self.official_availability == "available" and self.official_value is None:
            raise ValueError("available official comparison requires a value")
        if not np.isfinite(self.fixed_range) or self.fixed_range <= 0:
            raise ValueError("the adapter must provide a positive fixed color range")
        if self.chart_axis_range is not None and (
            not np.isfinite(self.chart_axis_range) or self.chart_axis_range <= 0
        ):
            raise ValueError("official chart axis range must be finite and positive")


@dataclass(frozen=True)
class AnalysisResult:
    result_id: str
    image_width: int
    image_height: int
    source_a_label: str
    source_b_label: str
    attributes: tuple[AttributeDisplay, ...]
    source_a: Path | None = None
    source_b: Path | None = None

    def __post_init__(self) -> None:
        if not self.result_id or not self.source_a_label or not self.source_b_label:
            raise ValueError("result and source identities must be nonempty")
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image geometry must be positive")
        if not self.attributes:
            raise ValueError("a result must declare at least one attribute")
        ids = [attr.attribute_id for attr in self.attributes]
        if len(ids) != len(set(ids)):
            raise ValueError("attribute IDs must be unique")
        for attr in self.attributes:
            grid = attr.spatial
            if grid is not None and (
                grid.image_width != self.image_width or grid.image_height != self.image_height
            ):
                raise ValueError("spatial and source geometry must match")

    def attribute(self, attribute_id: str) -> AttributeDisplay:
        return next(item for item in self.attributes if item.attribute_id == attribute_id)


@dataclass(frozen=True)
class LoadedAnalysis:
    """Reader outcome: immutable scientific result plus separate user-only view state.

    Real on-disk parsing and integrity validation are strictly H2/downstream work.
    """

    result: AnalysisResult
    analysis_state: dict[str, object] | None = None


def colorize_spatial_rgba(
    attribute: AttributeDisplay, half_range: float
) -> NDArray[np.uint8] | None:
    """Vectorized signed grid -> RGBA; invalid cells are transparent.

    Oriented red/blue encodes A-better/B-better only with verified direction.
    Unoriented purple/teal encodes signed polarity, never a quality winner.
    Color clipping is display-only; raw numbers and mask remain unchanged.
    """

    grid = attribute.spatial
    if grid is None:
        return None
    if not np.isfinite(half_range) or half_range <= 0.0:
        raise ValueError("display half-range must be positive")
    # Compute only within the existing bounded grid, with no 4K RGB upsampling.
    values = np.where(grid.valid_mask, grid.values, 0.0)
    fraction = np.clip(values / half_range, -1.0, 1.0)
    magnitude = np.abs(fraction)
    positive = fraction >= 0.0
    if attribute.quality_oriented:
        plus, minus = (245, 0, 0), (0, 0, 245)
    else:
        plus, minus = (181, 72, 193), (35, 145, 148)
    rgba = np.empty((*grid.values.shape, 4), dtype=np.uint8)
    for channel in range(3):
        endpoint = np.where(positive, plus[channel], minus[channel])
        rgba[..., channel] = np.rint(239 + magnitude * (endpoint - 239)).astype(np.uint8)
    rgba[..., 3] = np.where(grid.valid_mask, 255, 0).astype(np.uint8)
    return np.ascontiguousarray(rgba)


def map_polarity_legend(attribute: AttributeDisplay) -> str:
    """Legend is semantic, not merely a description of the color palette."""

    if attribute.quality_oriented:
        return "Red: A better (+) | Blue: B better (−)"
    return "Purple: positive signed value | Teal: negative (NO quality winner)"


@dataclass(frozen=True)
class GridStatistics:
    """Display-only, area-weighted GRID-DERIVED estimate; never official."""

    mean: float | None
    valid_coverage: float
    valid_area: float
    roi_area: float


def roi_statistics(grid: SpatialMap, roi: Roi) -> GridStatistics:
    """Compute fractional boundary-cell overlap with the source-coordinate ROI."""

    x, y, width, height = roi
    if not np.isfinite([x, y, width, height]).all() or width <= 0 or height <= 0:
        raise ValueError("ROI must have finite positive dimensions")
    x0 = min(max(x, 0.0), float(grid.image_width))
    y0 = min(max(y, 0.0), float(grid.image_height))
    x1 = min(max(x + width, 0.0), float(grid.image_width))
    y1 = min(max(y + height, 0.0), float(grid.image_height))
    region_area = max(x1 - x0, 0) * max(y1 - y0, 0)
    if region_area == 0:
        return GridStatistics(None, 0.0, 0.0, 0.0)
    xs = grid.origin_x + np.arange(grid.columns) * grid.block_width
    ys = grid.origin_y + np.arange(grid.rows) * grid.block_height
    overlap_x = np.maximum(0.0, np.minimum(xs + grid.block_width, x1) - np.maximum(xs, x0))
    overlap_y = np.maximum(0.0, np.minimum(ys + grid.block_height, y1) - np.maximum(ys, y0))
    weights = overlap_y[:, None] * overlap_x[None, :]
    weights = np.where(grid.valid_mask, weights, 0.0)
    valid_area = float(weights.sum())
    if valid_area <= 0.0:
        return GridStatistics(None, 0.0, 0.0, region_area)
    # Mask invalid cells explicitly: NaN in invalid locations must not taint sums.
    value = float(np.sum(np.where(grid.valid_mask, grid.values, 0.0) * weights) / valid_area)
    return GridStatistics(value, min(valid_area / region_area, 1.0), valid_area, region_area)


def clipped_cells(grid: SpatialMap, half_range: float) -> tuple[int, int]:
    """Return clipped valid-cell count and total valid-cell count for display feedback."""

    if not np.isfinite(half_range) or half_range <= 0:
        raise ValueError("color half-range must be positive")
    mask = grid.valid_mask
    return int(np.count_nonzero(mask & (np.abs(grid.values) > half_range))), int(
        np.count_nonzero(mask)
    )


def official_chart_fraction(attribute: AttributeDisplay) -> float | None:
    """Signed ratio on an independently *declared* official chart axis.

    Returns None for missing official values or unknown chart-axis scale.
    This avoids using spatial map color limits as alleged official ranges.
    A true official zero returns 0.0, distinct from None.
    """

    axis = attribute.chart_axis_range
    value = attribute.official_value
    if axis is None or value is None:
        return None
    return float(np.clip(value / axis, -1.0, 1.0))
