"""PUBLIC-SAFE deterministic GRID-DERIVED candidate regions (not official ROI IQA).

Computes source-pixel aligned 512px-window spatial difference proposals from
one already-validated signed SpatialMap. The producer's original-relative
A/B signal eligibility is not available yet; this prototype uses the
supplied valid_mask only, never infers SNR from a difference map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from pixelscope_enterprise.iqa.analysis_model import AttributeDisplay, SpatialMap

RankingMode = Literal["aligned", "exploratory_abs"]

# Three UX-only scan presets: detailed / standard / fast. Never accept arbitrary
# pixel strides from a future Qt control or deserialized user settings.
SCAN_STRIDES = (64, 128, 256)
DEFAULT_SCAN_STRIDE = 128

# Upper bounds are checked using Python integers BEFORE any candidate positions,
# grid overlap matrices, dense score maps or sorting lists are constructed.
_MAX_SCAN_WINDOWS = 16_384
_MAX_AXIS_OVERLAP_ELEMENTS = 500_000
_MAX_INTERMEDIATE_ELEMENTS = 500_000


@dataclass(frozen=True)
class SpatialCandidate:
    """One client-derived source-pixel proposal with scientific provenance."""

    rank: int
    x: int
    y: int
    width: int
    height: int
    mean: float
    valid_coverage: float
    valid_area: float
    score: float
    mode: RankingMode

    @property
    def roi(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


def _scan_axis_count(image_length: int, window_length: int, stride: int) -> int:
    """Exact count including the far-edge window, using integers only."""

    remaining = image_length - window_length
    return 1 + (remaining + stride - 1) // stride


def _preflight_scan(
    grid: SpatialMap, width: int, height: int, stride: int
) -> tuple[int, int]:
    """Reject unreasonable workload before allocating any scan-position arrays."""

    count_x = _scan_axis_count(grid.image_width, width, stride)
    count_y = _scan_axis_count(grid.image_height, height, stride)
    count = count_x * count_y
    axis_elements = count_x * grid.columns + count_y * grid.rows
    # wy @ grid is an (n_y × columns) intermediate. Account for both
    # transpose directions to protect later equivalent implementations too.
    intermediate_elements = count_y * grid.columns + count_x * grid.rows
    if (
        count > _MAX_SCAN_WINDOWS
        or axis_elements > _MAX_AXIS_OVERLAP_ELEMENTS
        or intermediate_elements > _MAX_INTERMEDIATE_ELEMENTS
    ):
        raise ValueError(
            "spatial scan workload exceeds supported budget "
            f"({count} windows, {axis_elements} overlap elements, "
            f"{intermediate_elements} intermediate elements)"
        )
    return count_x, count_y


def _scan_positions(image_length: int, window_length: int, stride: int) -> NDArray[np.int64]:
    last = image_length - window_length
    positions = np.arange(0, last + 1, stride, dtype=np.int64)
    if positions[-1] != last:
        positions = np.append(positions, last)
    return positions


def _axis_overlap(
    starts: NDArray[np.int64],
    window: int,
    origin: float,
    block: float,
    cells: int,
    image_length: int,
) -> NDArray[np.float64]:
    """Actual cell/ROI intersection areas, including partial boundary blocks."""

    cell_left = origin + np.arange(cells, dtype=np.float64) * block
    cell_right = np.minimum(cell_left + block, float(image_length))
    roi_left = starts[:, None]
    roi_right = roi_left + window
    left_edge = np.minimum(roi_right, cell_right[None, :])
    right_edge = np.maximum(roi_left, cell_left[None, :])
    return cast(NDArray[np.float64], np.maximum(0.0, left_edge - right_edge))


def _iou(a: SpatialCandidate, b: SpatialCandidate) -> float:
    intersection_width = max(0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x))
    intersection_height = max(0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y))
    intersection = intersection_width * intersection_height
    union = a.width * a.height + b.width * b.height - intersection
    return intersection / union if union else 0.0


def find_spatial_candidates(
    attribute: AttributeDisplay,
    *,
    window_size: int = 512,
    stride: int = DEFAULT_SCAN_STRIDE,
    min_coverage: float = 0.8,
    max_candidates: int = 3,
    max_iou: float = 0.1,
) -> tuple[SpatialCandidate, ...]:
    """Rank sign-aligned, nonoverlapping source-pixel windows for one attribute.

    Weighted-window means are exact to block/ROI geometric overlap: no
    nearest-grid assumption, invalid-as-zero averaging or display clipping.
    Axis-separable matrix multiplication evaluates all candidate windows
    without per-source-pixel Python iteration.

    For a nonzero available official signed scalar, rank only positive
    sign-aligned local means; a window moving in the opposite direction is
    not described as 'lifting' that official difference. Without a usable
    official sign, rank |local mean| as **exploratory**, not as an official
    contribution. Raw local statistics are grid-derived either way.

    This does NOT prove that the official scalar aggregates from this map,
    and is not a substitute for the producer's future per-region A/B signal
    validity gate. Only 64/128/256 px strides are allowed. The scan budget is
    checked before allocating any window positions or overlap matrices.
    """

    if window_size <= 0 or max_candidates < 0:
        raise ValueError("positive window and nonnegative count required")
    if not isinstance(stride, int) or isinstance(stride, bool) or stride not in SCAN_STRIDES:
        raise ValueError("stride must be one of 64, 128, or 256 source pixels")
    if not 0 <= min_coverage <= 1 or not 0 <= max_iou <= 1:
        raise ValueError("coverage and IoU thresholds must be in [0, 1]")
    grid: SpatialMap | None = attribute.spatial
    if grid is None or max_candidates == 0:
        return ()

    width = min(grid.image_width, window_size)
    height = min(grid.image_height, window_size)
    _preflight_scan(grid, width, height, stride)
    xs = _scan_positions(grid.image_width, width, stride)
    ys = _scan_positions(grid.image_height, height, stride)
    wx = _axis_overlap(xs, width, grid.origin_x, grid.block_width, grid.columns, grid.image_width)
    wy = _axis_overlap(ys, height, grid.origin_y, grid.block_height, grid.rows, grid.image_height)
    mask = grid.valid_mask.astype(np.float64)
    valid_values = np.where(grid.valid_mask, grid.values, 0.0)
    weighted_area = (wy @ mask) @ wx.T
    weighted_sum = (wy @ valid_values) @ wx.T
    coverage = weighted_area / float(width * height)
    mean = np.divide(
        weighted_sum,
        weighted_area,
        out=np.zeros_like(weighted_sum),
        where=weighted_area > 0,
    )
    known_sign = (
        attribute.official_availability == "available"
        and attribute.official_value is not None
        and attribute.official_value != 0
    )
    mode: RankingMode = "aligned" if known_sign else "exploratory_abs"
    if known_sign:
        assert attribute.official_value is not None
        scores = np.sign(attribute.official_value) * mean
    else:
        scores = np.abs(mean)

    qualifying = (coverage >= min_coverage) & (weighted_area > 0) & (scores > 0)
    row_indices, col_indices = np.nonzero(qualifying)
    # Ascending (−score, −coverage, source y, source x), stable and reproducible.
    ordered = sorted(
        zip(row_indices.tolist(), col_indices.tolist(), strict=True),
        key=lambda idx: (
            -float(scores[idx]),
            -float(coverage[idx]),
            int(ys[idx[0]]),
            int(xs[idx[1]]),
        ),
    )
    selected: list[SpatialCandidate] = []
    for row, col in ordered:
        candidate = SpatialCandidate(
            rank=len(selected) + 1,
            x=int(xs[col]),
            y=int(ys[row]),
            width=width,
            height=height,
            mean=float(mean[row, col]),
            valid_coverage=float(coverage[row, col]),
            valid_area=float(weighted_area[row, col]),
            score=float(scores[row, col]),
            mode=mode,
        )
        if all(_iou(candidate, previous) <= max_iou for previous in selected):
            selected.append(candidate)
            if len(selected) == max_candidates:
                break
    return tuple(selected)
