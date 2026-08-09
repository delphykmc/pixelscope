from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class DisplayTransform:
    """Non-destructive source-to-display conversion parameters."""

    black_level: float | None = None
    white_level: float | None = None
    gamma: float = 1.0

    def __post_init__(self) -> None:
        if self.gamma <= 0:
            raise ValueError("gamma must be greater than zero")
        if (
            self.black_level is not None
            and self.white_level is not None
            and self.white_level <= self.black_level
        ):
            raise ValueError("white_level must be greater than black_level")


def _default_range(array: NDArray[np.generic]) -> tuple[float, float]:
    if np.issubdtype(array.dtype, np.integer):
        bits = array.dtype.itemsize * 8
        if np.issubdtype(array.dtype, np.unsignedinteger):
            return 0.0, float((1 << bits) - 1)
        return float(-(1 << (bits - 1))), float((1 << (bits - 1)) - 1)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 0.0, 1.0
    low, high = float(finite.min()), float(finite.max())
    return (low, high) if high > low else (low, low + 1.0)


def to_display_uint8(
    source: NDArray[np.generic], transform: DisplayTransform | None = None
) -> NDArray[np.uint8]:
    """Return a C-contiguous uint8 preview without modifying *source*."""

    if source.size == 0:
        raise ValueError("cannot display an empty image")
    parameters = transform or DisplayTransform()
    default_low, default_high = _default_range(source)
    low = default_low if parameters.black_level is None else parameters.black_level
    high = default_high if parameters.white_level is None else parameters.white_level
    if high <= low:
        high = low + 1.0
    normalized = np.clip(
        (source.astype(np.float32) - np.float32(low)) / np.float32(high - low),
        0.0,
        1.0,
    )
    if parameters.gamma != 1.0:
        normalized = np.power(normalized, np.float32(1.0 / parameters.gamma))
    return np.ascontiguousarray(np.rint(normalized * 255.0).astype(np.uint8))


def render_signed_difference(diff: NDArray[Any]) -> NDArray[np.uint8]:
    """Render signed values as blue-negative, gray-zero, red-positive RGB."""

    if diff.size == 0:
        raise ValueError("cannot display an empty difference")
    display_values = diff.astype(np.float32)
    if display_values.ndim == 3:
        display_values = np.mean(display_values, axis=-1)
    maximum = max(float(np.max(np.abs(display_values.astype(np.float64)))), 1.0)
    normalized = np.clip(display_values / maximum, -1.0, 1.0)
    base = 127.0
    red = base + np.maximum(normalized, 0.0) * 128.0
    blue = base + np.maximum(-normalized, 0.0) * 128.0
    green = base - np.abs(normalized) * 127.0
    rgb = np.stack((red, green, blue), axis=-1)
    return np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))


def render_absolute_difference(diff: NDArray[Any], gain: float = 1.0) -> NDArray[np.uint8]:
    """Render absolute numerical difference with an independent display gain."""

    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    maximum = max(float(np.max(diff)), 1.0)
    scaled = np.clip(diff.astype(np.float32) * gain / maximum, 0.0, 1.0)
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


def render_absolute_difference_range(
    diff: NDArray[Any], low: int, high: int, gain: int = 1
) -> NDArray[np.uint8]:
    """Render an absolute map using an explicit integer display range."""

    if high <= low:
        raise ValueError("high must be greater than low")
    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    scaled = np.clip(
        (diff.astype(np.float32) - np.float32(low)) * np.float32(gain / (high - low)),
        0.0,
        1.0,
    )
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


def render_threshold_mask(diff: NDArray[Any], threshold: float) -> NDArray[np.uint8]:
    """Render red where any selected channel exceeds *threshold*, black elsewhere."""

    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    selected = np.greater(diff, threshold)
    mask = np.any(selected, axis=2) if selected.ndim == 3 else selected
    preview = np.zeros((*mask.shape, 3), dtype=np.uint8)
    preview[mask, 0] = 255
    return preview
