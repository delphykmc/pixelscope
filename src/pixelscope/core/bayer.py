from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.display_transform import DisplayTransform, to_display_uint8
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds, extract_roi
from pixelscope.core.statistics import HistogramResult, histogram, image_statistics

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
    channel_statistics = tuple(image_statistics(channel) for _name, channel in channels)
    channel_names = tuple(name for name, _channel in channels)
    channel_histograms = tuple(histogram(channel, bins, value_range) for _name, channel in channels)
    if not channel_histograms:
        raise ValueError("Bayer ROI contains no samples")
    return RoiAnalysisResult(
        bounds=bounds,
        pixel_count=bounds.width * bounds.height,
        overall=image_statistics(region),
        channel_statistics=channel_statistics,
        channel_names=channel_names,
        histogram=HistogramResult(
            counts=tuple(result.counts[0] for result in channel_histograms),
            edges=channel_histograms[0].edges,
            channel_names=channel_names,
        ),
    )


def render_bayer_preview(
    source: NDArray[np.generic],
    transform: DisplayTransform,
) -> NDArray[np.uint8]:
    """Render a Bayer mosaic with a restrained green tint."""

    gray = to_display_uint8(source, transform)
    red_blue = np.rint(gray.astype(np.float32) * 0.38).astype(np.uint8)
    return np.ascontiguousarray(np.stack((red_blue, gray, red_blue), axis=-1))
