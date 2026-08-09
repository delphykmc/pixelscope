from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.display_transform import (
    apply_display_affine_inplace,
    display_normalization_affine,
)
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds, extract_roi
from pixelscope.core.statistics import (
    HistogramResult,
    histogram,
    image_statistics,
    statistics_from_histogram,
)

BAYER_CHANNEL_NAMES = ("R", "Gr", "Gb", "B")

_PATTERN_POSITIONS: dict[str, dict[str, tuple[int, int]]] = {
    "RGGB": {"R": (0, 0), "Gr": (0, 1), "Gb": (1, 0), "B": (1, 1)},
    "GRBG": {"Gr": (0, 0), "R": (0, 1), "B": (1, 0), "Gb": (1, 1)},
    "GBRG": {"Gb": (0, 0), "B": (0, 1), "R": (1, 0), "Gr": (1, 1)},
    "BGGR": {"B": (0, 0), "Gb": (0, 1), "Gr": (1, 0), "R": (1, 1)},
}


def bayer_channel_positions(pattern: str) -> dict[str, tuple[int, int]]:
    """Return the row/column parity for each Bayer subchannel."""

    try:
        return _PATTERN_POSITIONS[pattern.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported Bayer pattern: {pattern}") from exc


def bayer_channel_at(pattern: str, x: int, y: int) -> str:
    """Return the CFA channel name at one full-resolution source coordinate."""

    parity = (y % 2, x % 2)
    for name, position in bayer_channel_positions(pattern).items():
        if position == parity:
            return name
    raise AssertionError("Bayer parity map is incomplete")


def split_bayer_channels(
    source: NDArray[np.generic],
    pattern: str,
    bounds: RoiBounds | None = None,
) -> tuple[tuple[str, NDArray[np.generic]], ...]:
    """Return non-copying half-resolution CFA planes aligned to source parity."""

    if source.ndim != 2:
        raise ValueError("Bayer source must be a 2-D mosaic")
    height, width = source.shape
    if bounds is None:
        bounds = RoiBounds(0, 0, width, height)
    if bounds.right > width or bounds.bottom > height:
        raise ValueError("ROI extends beyond the Bayer image")

    channels: list[tuple[str, NDArray[np.generic]]] = []
    positions = bayer_channel_positions(pattern)
    for name in BAYER_CHANNEL_NAMES:
        row_parity, column_parity = positions[name]
        start_y = bounds.y + ((row_parity - bounds.y) % 2)
        start_x = bounds.x + ((column_parity - bounds.x) % 2)
        plane = source[start_y : bounds.bottom : 2, start_x : bounds.right : 2]
        if plane.size:
            channels.append((name, plane))
    return tuple(channels)


def analyze_bayer_roi(
    source: NDArray[np.generic],
    bounds: RoiBounds,
    pattern: str,
    bins: int,
    value_range: tuple[float, float] | None,
) -> RoiAnalysisResult:
    """Calculate independent R/Gr/Gb/B statistics for a Bayer ROI."""

    region = extract_roi(source, bounds)
    channels = split_bayer_channels(source, pattern, bounds)
    channel_names = tuple(name for name, _channel in channels)
    channel_histograms = tuple(histogram(channel, bins, value_range) for _name, channel in channels)
    if not channel_histograms:
        raise ValueError("Bayer ROI contains no samples")
    result_histogram = HistogramResult(
        counts=tuple(result.counts[0] for result in channel_histograms),
        edges=channel_histograms[0].edges,
        channel_names=channel_names,
    )
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
        channel_statistics = tuple(image_statistics(channel) for _name, channel in channels)
        overall = image_statistics(region)
    return RoiAnalysisResult(
        bounds=bounds,
        pixel_count=bounds.width * bounds.height,
        overall=overall,
        channel_statistics=channel_statistics,
        channel_names=channel_names,
        histogram=result_histogram,
        channel_sample_counts=tuple(int(channel.size) for _name, channel in channels),
    )


def render_bayer_preview(
    source: NDArray[np.generic],
    pattern: str,
    black_level: int | tuple[int, int, int, int],
    bit_depth: int,
    gain: float = 1.0,
) -> NDArray[np.uint8]:
    """Render a native Bayer mosaic through the generic display-gain affine.

    The source is promoted to one float32 scratch buffer. CFA-specific anchors
    reuse the generic anchor/gain/range affine on parity-plane views, so no
    full-size Black Level map is materialized. Gain and normalization are fused
    before clipping and final uint8 conversion.
    """

    if source.ndim != 2:
        raise ValueError("Bayer source must be a 2-D mosaic")
    if source.size == 0:
        raise ValueError("cannot display an empty Bayer image")
    if not 1 <= bit_depth <= 16:
        raise ValueError("bit_depth must be between 1 and 16")
    if gain <= 0:
        raise ValueError("display gain must be greater than zero")

    if isinstance(black_level, tuple):
        if len(black_level) != 4:
            raise ValueError("Bayer black_level must contain R/Gr/Gb/B values")
        anchors = dict(zip(BAYER_CHANNEL_NAMES, black_level, strict=True))
    else:
        anchors = {name: black_level for name in BAYER_CHANNEL_NAMES}

    working = source.astype(np.float32, copy=True)
    full_scale = float((1 << bit_depth) - 1)
    if gain == 1.0:
        scale, offset = display_normalization_affine(0.0, full_scale)
        apply_display_affine_inplace(working, scale, offset)
    else:
        positions = bayer_channel_positions(pattern)
        for name in BAYER_CHANNEL_NAMES:
            row_parity, column_parity = positions[name]
            plane = working[row_parity::2, column_parity::2]
            scale, offset = display_normalization_affine(
                0.0,
                full_scale,
                gain,
                float(anchors[name]),
            )
            apply_display_affine_inplace(plane, scale, offset)

    np.clip(working, 0.0, 1.0, out=working)
    np.multiply(working, np.float32(255.0), out=working)
    np.rint(working, out=working)

    preview = np.empty((*working.shape, 3), dtype=np.uint8)
    preview[..., 1] = working
    np.multiply(working, np.float32(0.38), out=working)
    np.rint(working, out=working)
    preview[..., 0] = working
    preview[..., 2] = working
    return np.ascontiguousarray(preview)
