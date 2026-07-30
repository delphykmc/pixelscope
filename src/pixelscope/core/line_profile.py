from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.bayer import BAYER_CHANNEL_NAMES, bayer_channel_positions
from pixelscope.core.roi import RoiBounds, extract_roi


@dataclass(frozen=True)
class LineProfileResult:
    """Horizontal source-pixel profile through the center of a region."""

    x_start: int
    y: int
    values: tuple[NDArray[np.float64], ...]
    channel_names: tuple[str, ...]
    positions: tuple[NDArray[np.float64], ...]


@dataclass(frozen=True)
class LineSelection:
    """Inclusive horizontal source-image line selected by Alt+drag."""

    x1: int
    y: int
    x2: int

    def __post_init__(self) -> None:
        if self.x1 < 0 or self.x2 < 0 or self.y < 0:
            raise ValueError("line coordinates must not be negative")
        if self.x1 == self.x2:
            raise ValueError("line profile requires two different X coordinates")

    @property
    def left(self) -> int:
        return min(self.x1, self.x2)

    @property
    def right(self) -> int:
        return max(self.x1, self.x2)


def clamp_line(image_shape: tuple[int, ...], x1: int, y: int, x2: int) -> LineSelection:
    """Clamp a horizontal line to an HxW image while preserving drag direction."""

    if len(image_shape) not in (2, 3):
        raise ValueError("line profile expects an HxW or HxWxC image shape")
    height, width = image_shape[:2]
    if width < 2 or height < 1:
        raise ValueError("image is too small for a line profile")
    clipped_y = min(max(y, 0), height - 1)
    clipped_x1 = min(max(x1, 0), width - 1)
    clipped_x2 = min(max(x2, 0), width - 1)
    return LineSelection(clipped_x1, clipped_y, clipped_x2)


def selected_line_profile(
    image: NDArray[np.generic], selection: LineSelection
) -> LineProfileResult:
    """Extract the exact Alt-dragged horizontal segment, including both endpoints."""

    selected = clamp_line(image.shape, selection.x1, selection.y, selection.x2)
    if selected.x2 > selected.x1:
        line = image[selected.y, selected.x1 : selected.x2 + 1]
    else:
        stop = selected.x2 - 1 if selected.x2 > 0 else None
        line = image[selected.y, selected.x1 : stop : -1]
    names: tuple[str, ...]
    if line.ndim == 1:
        values = (line.astype(np.float64),)
        names = ("Gray",)
    else:
        values = tuple(channel.astype(np.float64) for channel in np.moveaxis(line, -1, 0))
        names = ("R", "G", "B", "A")[: len(values)]
    positions = tuple(np.arange(len(channel), dtype=np.float64) for channel in values)
    return LineProfileResult(selected.x1, selected.y, values, names, positions)


def selected_bayer_line_profile(
    image: NDArray[np.generic],
    selection: LineSelection,
    pattern: str,
) -> LineProfileResult:
    """Sample all CFA planes along a line, retaining their every-other-pixel X positions."""

    if image.ndim != 2:
        raise ValueError("Bayer line profile expects a 2-D mosaic")
    selected = clamp_line(image.shape, selection.x1, selection.y, selection.x2)
    direction = 1 if selected.x2 > selected.x1 else -1
    source_x = np.arange(selected.x1, selected.x2 + direction, direction)
    distances = np.arange(len(source_x), dtype=np.float64)
    channel_values: list[NDArray[np.float64]] = []
    channel_positions: list[NDArray[np.float64]] = []
    channel_names: list[str] = []
    height = image.shape[0]
    positions = bayer_channel_positions(pattern)
    for name in BAYER_CHANNEL_NAMES:
        row_parity, column_parity = positions[name]
        row_candidates = [
            row
            for row in (selected.y, selected.y - 1, selected.y + 1)
            if 0 <= row < height and row % 2 == row_parity
        ]
        if not row_candidates:
            continue
        row = min(row_candidates, key=lambda candidate: abs(candidate - selected.y))
        mask = source_x % 2 == column_parity
        if not np.any(mask):
            continue
        channel_names.append(name)
        channel_values.append(image[row, source_x[mask]].astype(np.float64))
        channel_positions.append(distances[mask])
    return LineProfileResult(
        selected.x1,
        selected.y,
        tuple(channel_values),
        tuple(channel_names),
        tuple(channel_positions),
    )


def horizontal_line_profile(
    image: NDArray[np.generic], bounds: RoiBounds | None = None
) -> LineProfileResult:
    """Extract a horizontal line through the ROI/image center without pixel loops."""

    if image.ndim not in (2, 3):
        raise ValueError("line profile expects an HxW or HxWxC image")
    if bounds is None:
        bounds = RoiBounds(0, 0, image.shape[1], image.shape[0])
    region = extract_roi(image, bounds)
    local_y = region.shape[0] // 2
    source_y = bounds.y + local_y
    line = region[local_y]
    names: tuple[str, ...]
    if line.ndim == 1:
        values = (line.astype(np.float64),)
        names = ("Gray",)
    else:
        values = tuple(channel.astype(np.float64) for channel in np.moveaxis(line, -1, 0))
        names = ("R", "G", "B", "A")[: len(values)]
    positions = tuple(np.arange(len(channel), dtype=np.float64) for channel in values)
    return LineProfileResult(bounds.x, source_y, values, names, positions)
