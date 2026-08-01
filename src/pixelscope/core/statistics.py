from __future__ import annotations

from dataclasses import dataclass
from math import inf, log10

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.diff_engine import signed_difference


@dataclass(frozen=True)
class ImageStatistics:
    minimum: float
    maximum: float
    mean: float
    standard_deviation: float
    percentiles: dict[float, float]


@dataclass(frozen=True)
class HistogramResult:
    counts: tuple[NDArray[np.int64], ...]
    edges: NDArray[np.float64]
    channel_names: tuple[str, ...]


def image_statistics(
    image: NDArray[np.generic], percentiles: tuple[float, ...] = (1.0, 50.0, 99.0)
) -> ImageStatistics:
    if image.size == 0:
        raise ValueError("cannot calculate statistics for an empty image")
    if any(value < 0 or value > 100 for value in percentiles):
        raise ValueError("percentiles must be between 0 and 100")
    values = image.astype(np.float64)
    calculated = np.percentile(values, percentiles)
    return ImageStatistics(
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        mean=float(np.mean(values)),
        standard_deviation=float(np.std(values)),
        percentiles=dict(zip(percentiles, (float(value) for value in calculated), strict=True)),
    )


def statistics_from_histogram(
    counts: NDArray[np.int64],
    edges: NDArray[np.float64],
    percentiles: tuple[float, ...] = (1.0, 50.0, 99.0),
) -> ImageStatistics:
    """Calculate exact integer-code statistics without a full-size float copy.

    This is exact when every histogram bin represents one integer code, which is
    the native histogram layout used by PixelScope for integer images.
    """

    if counts.ndim != 1 or edges.ndim != 1 or len(edges) != len(counts) + 1:
        raise ValueError("histogram counts and edges do not match")
    if any(value < 0 or value > 100 for value in percentiles):
        raise ValueError("percentiles must be between 0 and 100")
    sample_count = int(np.sum(counts, dtype=np.int64))
    if sample_count == 0:
        raise ValueError("cannot calculate statistics for an empty histogram")
    widths = np.diff(edges)
    if not np.allclose(widths, 1.0):
        raise ValueError("statistics require one integer code per histogram bin")

    values = edges[:-1]
    occupied = np.flatnonzero(counts)
    weighted_sum = float(np.dot(values, counts))
    mean = weighted_sum / sample_count
    variance = float(np.dot(np.square(values - mean), counts)) / sample_count
    cumulative = np.cumsum(counts, dtype=np.int64)

    def order_value(position: int) -> float:
        index = int(np.searchsorted(cumulative, position + 1, side="left"))
        return float(values[index])

    calculated: dict[float, float] = {}
    for percentile in percentiles:
        rank = (percentile / 100.0) * (sample_count - 1)
        lower = int(np.floor(rank))
        upper = int(np.ceil(rank))
        fraction = rank - lower
        low_value = order_value(lower)
        high_value = order_value(upper)
        calculated[percentile] = low_value + ((high_value - low_value) * fraction)
    return ImageStatistics(
        minimum=float(values[occupied[0]]),
        maximum=float(values[occupied[-1]]),
        mean=mean,
        standard_deviation=float(np.sqrt(max(variance, 0.0))),
        percentiles=calculated,
    )


def mean_squared_error(a: NDArray[np.generic], b: NDArray[np.generic]) -> float:
    diff = signed_difference(a, b).astype(np.float64)
    return float(np.mean(np.square(diff)))


def peak_signal_to_noise_ratio(
    a: NDArray[np.generic], b: NDArray[np.generic], data_range: float | None = None
) -> float:
    error = mean_squared_error(a, b)
    if error == 0:
        return inf
    if data_range is None:
        if np.issubdtype(a.dtype, np.integer):
            data_range = float((1 << (a.dtype.itemsize * 8)) - 1)
        else:
            floating = a.astype(np.float64, copy=False)
            data_range = float(np.max(floating) - np.min(floating))
    if data_range <= 0:
        raise ValueError("data_range must be greater than zero")
    return 20.0 * log10(data_range) - 10.0 * log10(error)


def histogram(
    image: NDArray[np.generic],
    bins: int = 256,
    value_range: tuple[float, float] | None = None,
) -> HistogramResult:
    """Calculate whole-image gray or per-channel RGB(A) histograms."""

    if bins < 2:
        raise ValueError("bins must be at least 2")
    if image.ndim not in (2, 3):
        raise ValueError("histogram expects a 2-D or 3-D image")
    if value_range is not None:
        if value_range[1] <= value_range[0]:
            raise ValueError("histogram value range must be increasing")
    elif np.issubdtype(image.dtype, np.integer):
        bits = image.dtype.itemsize * 8
        if np.issubdtype(image.dtype, np.unsignedinteger):
            value_range = (0.0, float(1 << bits))
        else:
            value_range = (float(-(1 << (bits - 1))), float(1 << (bits - 1)))
    else:
        floating = image.astype(np.float64, copy=False)
        minimum, maximum = float(np.nanmin(floating)), float(np.nanmax(floating))
        value_range = (minimum, maximum if maximum > minimum else minimum + 1.0)
    channels = (image,) if image.ndim == 2 else tuple(np.moveaxis(image, -1, 0))
    names = ("Gray",) if image.ndim == 2 else ("R", "G", "B", "A")[: len(channels)]
    counts: list[NDArray[np.int64]] = []
    edges: NDArray[np.float64] | None = None
    for channel in channels:
        use_integer_codes = (
            np.issubdtype(channel.dtype, np.integer)
            and value_range is not None
            and float(value_range[0]).is_integer()
            and float(value_range[1]).is_integer()
            and int(value_range[1] - value_range[0]) == bins
        )
        if use_integer_codes:
            lower = int(value_range[0])
            upper = int(value_range[1])
            flattened = np.ravel(channel)
            all_values_valid = bool(
                flattened.size and np.min(flattened) >= lower and np.max(flattened) < upper
            )
            if (
                all_values_valid
                and lower == 0
                and np.issubdtype(flattened.dtype, np.unsignedinteger)
            ):
                # np.bincount accepts unsigned inputs directly, avoiding an HxW
                # int64 temporary (about 190 MiB for one UHD RGB image).
                channel_counts = np.bincount(flattened, minlength=bins)[:bins]
            else:
                valid = flattened[(flattened >= lower) & (flattened < upper)]
                channel_counts = np.bincount(
                    valid.astype(np.int64, copy=False) - lower,
                    minlength=bins,
                )[:bins]
            channel_edges = np.arange(lower, upper + 1, dtype=np.float64)
        else:
            channel_counts, channel_edges = np.histogram(channel, bins=bins, range=value_range)
        counts.append(channel_counts.astype(np.int64, copy=False))
        edges = channel_edges
    assert edges is not None
    return HistogramResult(tuple(counts), edges, names)
