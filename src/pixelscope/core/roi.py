from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.statistics import (
    HistogramResult,
    ImageStatistics,
    histogram,
    image_statistics,
    statistics_from_histogram,
)


@dataclass(frozen=True)
class RoiBounds:
    """Integer, half-open image coordinates for a rectangular ROI."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("ROI origin must not be negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI width and height must be positive")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class RoiAnalysisResult:
    """Statistics and histogram calculated from one immutable ROI request."""

    bounds: RoiBounds
    pixel_count: int
    overall: ImageStatistics
    channel_statistics: tuple[ImageStatistics, ...]
    channel_names: tuple[str, ...]
    histogram: HistogramResult
    channel_sample_counts: tuple[int, ...] = ()


def clamp_roi(
    image_shape: tuple[int, ...],
    x: int,
    y: int,
    width: int,
    height: int,
) -> RoiBounds:
    """Clip an ROI to HxW image bounds and reject an empty intersection."""

    if len(image_shape) not in (2, 3):
        raise ValueError("ROI expects an HxW or HxWxC image shape")
    image_height, image_width = image_shape[:2]
    left = min(max(x, 0), image_width)
    top = min(max(y, 0), image_height)
    right = min(max(x + width, 0), image_width)
    bottom = min(max(y + height, 0), image_height)
    if right <= left or bottom <= top:
        raise ValueError("ROI does not intersect the image")
    return RoiBounds(left, top, right - left, bottom - top)


def extract_roi(image: NDArray[np.generic], bounds: RoiBounds) -> NDArray[np.generic]:
    """Return a non-copying ROI view after explicit image-bound validation."""

    if image.ndim not in (2, 3):
        raise ValueError("ROI expects an HxW or HxWxC image")
    height, width = image.shape[:2]
    if bounds.right > width or bounds.bottom > height:
        raise ValueError("ROI extends beyond the image boundary")
    return image[bounds.y : bounds.bottom, bounds.x : bounds.right]


def analyze_roi(
    image: NDArray[np.generic],
    bounds: RoiBounds,
    bins: int = 256,
    histogram_range: tuple[float, float] | None = None,
) -> RoiAnalysisResult:
    """Calculate whole-ROI and per-channel statistics plus a histogram."""

    region = extract_roi(image, bounds)
    result_histogram = histogram(region, bins, histogram_range)
    channels = (region,) if region.ndim == 2 else tuple(np.moveaxis(region, -1, 0))
    exact_integer_histogram = (
        np.issubdtype(region.dtype, np.integer)
        and len(result_histogram.edges) == bins + 1
        and np.allclose(np.diff(result_histogram.edges), 1.0)
    )
    if exact_integer_histogram:
        channel_statistics = tuple(
            statistics_from_histogram(counts, result_histogram.edges)
            for counts in result_histogram.counts
        )
        overall_counts = np.sum(np.stack(result_histogram.counts), axis=0, dtype=np.int64)
        overall = statistics_from_histogram(overall_counts, result_histogram.edges)
    else:
        channel_statistics = tuple(image_statistics(channel) for channel in channels)
        overall = image_statistics(region)
    return RoiAnalysisResult(
        bounds=bounds,
        pixel_count=bounds.width * bounds.height,
        overall=overall,
        channel_statistics=channel_statistics,
        channel_names=result_histogram.channel_names,
        histogram=result_histogram,
        channel_sample_counts=tuple(int(channel.size) for channel in channels),
    )
