from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.bayer import BAYER_CHANNEL_NAMES, render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform, to_display_uint8

RawBlackLevel = int | tuple[int, int, int, int]


def raw_full_scale(bit_depth: int) -> int:
    """Return the effective RAW code full scale for *bit_depth*."""

    if not 1 <= bit_depth <= 16:
        raise ValueError("bit_depth must be between 1 and 16")
    return (1 << bit_depth) - 1


def raw_black_anchor(black_level: RawBlackLevel, channel_name: str | None = None) -> int:
    """Return the scalar display-gain anchor for a RAW grayscale/CFA plane."""

    if isinstance(black_level, tuple):
        if len(black_level) != 4:
            raise ValueError("Bayer black_level must contain R/Gr/Gb/B values")
        if channel_name is None:
            raise ValueError("a Bayer channel name is required for tuple black_level")
        try:
            index = BAYER_CHANNEL_NAMES.index(channel_name)
        except ValueError as exc:
            raise ValueError(f"unsupported Bayer channel: {channel_name}") from exc
        return int(black_level[index])
    return int(black_level)


def raw_display_transform(
    bit_depth: int,
    black_level: RawBlackLevel,
    gain: float = 1.0,
    *,
    channel_name: str | None = None,
) -> DisplayTransform:
    """Build native-code RAW display parameters without using white level."""

    return DisplayTransform(
        display_low=0.0,
        display_high=float(raw_full_scale(bit_depth)),
        gain=float(gain),
        gain_anchor=float(raw_black_anchor(black_level, channel_name)),
    )


def _render_bayer_channel_preview(
    source: NDArray[np.generic],
    channel_name: str,
    transform: DisplayTransform,
) -> NDArray[np.uint8]:
    """Preserve the existing colored Split Channels tile presentation."""

    display = to_display_uint8(source, transform)
    preview = np.zeros((*display.shape, 3), dtype=np.uint8)
    if channel_name == "R":
        preview[..., 0] = display
    elif channel_name == "B":
        preview[..., 2] = display
    else:
        preview[..., 1] = display
    return np.ascontiguousarray(preview)


def render_raw_preview(
    source: NDArray[np.generic],
    *,
    channel_layout: str,
    bit_depth: int,
    black_level: RawBlackLevel,
    bayer_pattern: str | None = None,
    gain: float = 1.0,
) -> NDArray[np.uint8]:
    """Render RAW presentation from native samples without changing analysis data."""

    if channel_layout == "BAYER":
        if bayer_pattern is None:
            raise ValueError("Bayer RAW preview requires a CFA pattern")
        return render_bayer_preview(
            source,
            bayer_pattern,
            black_level,
            bit_depth,
            gain,
        )

    channel_name: str | None = None
    if channel_layout.startswith("CHANNEL_"):
        candidate = channel_layout.removeprefix("CHANNEL_")
        if candidate in BAYER_CHANNEL_NAMES:
            channel_name = candidate
    if isinstance(black_level, tuple) and channel_name is None:
        raise ValueError("tuple black_level requires a Bayer mosaic or CFA channel")

    transform = raw_display_transform(
        bit_depth,
        black_level,
        gain,
        channel_name=channel_name,
    )
    if channel_name is not None:
        return _render_bayer_channel_preview(source, channel_name, transform)
    return to_display_uint8(source, transform)
