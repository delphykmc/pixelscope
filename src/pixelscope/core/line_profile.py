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
    """Inclusive axis-aligned source-image line selected by Alt+drag."""

    x1: int
    y1: int
    x2: int
    y2: int | None = None

    def __post_init__(self) -> None:
        if self.y2 is None:
            object.__setattr__(self, "y2", self.y1)
        assert self.y2 is not None
        if self.x1 < 0 or self.x2 < 0 or self.y1 < 0 or self.y2 < 0:
            raise ValueError("line coordinates must not be negative")
        if self.x1 == self.x2 and self.y1 == self.y2:
            raise ValueError("line profile requires two different coordinates")

    @property
    def y(self) -> int:
        """Backward-compatible start row for existing integrations."""

        return self.y1

    @property
    def is_horizontal(self) -> bool:
        return self.y1 == self.y2

    @property
    def left(self) -> int:
        return min(self.x1, self.x2)

    @property
    def right(self) -> int:
        return max(self.x1, self.x2)


def clamp_line(
    image_shape: tuple[int, ...], x1: int, y1: int, x2: int, y2: int | None = None
) -> LineSelection:
    """Clamp a line and snap it to the dominant horizontal or vertical axis."""

    if len(image_shape) not in (2, 3):
        raise ValueError("line profile expects an HxW or HxWxC image shape")
    height, width = image_shape[:2]
    if width < 2 or height < 1:
        raise ValueError("image is too small for a line profile")
    y2 = y1 if y2 is None else y2
    clipped_y1 = min(max(y1, 0), height - 1)
    clipped_y2 = min(max(y2, 0), height - 1)
    clipped_x1 = min(max(x1, 0), width - 1)
    clipped_x2 = min(max(x2, 0), width - 1)
    if abs(clipped_x2 - clipped_x1) >= abs(clipped_y2 - clipped_y1):
        return LineSelection(clipped_x1, clipped_y1, clipped_x2, clipped_y1)
    return LineSelection(clipped_x1, clipped_y1, clipped_x1, clipped_y2)


def selected_line_profile(
    image: NDArray[np.generic], selection: LineSelection
) -> LineProfileResult:
    """Extract the exact Alt-dragged horizontal segment, including both endpoints."""

    selected = clamp_line(image.shape, selection.x1, selection.y1, selection.x2, selection.y2)
    if selected.is_horizontal and selected.x2 > selected.x1:
        line = image[selected.y1, selected.x1 : selected.x2 + 1]
    elif selected.is_horizontal:
        stop = selected.x2 - 1 if selected.x2 > 0 else None
        line = image[selected.y1, selected.x1 : stop : -1]
    elif selected.y2 is not None and selected.y2 > selected.y1:
        line = image[selected.y1 : selected.y2 + 1, selected.x1]
    else:
        assert selected.y2 is not None
        stop = selected.y2 - 1 if selected.y2 > 0 else None
        line = image[selected.y1 : stop : -1, selected.x1]
    names: tuple[str, ...]
    if line.ndim == 1:
        values = (line.astype(np.float64),)
        names = ("Gray",)
    else:
        values = tuple(channel.astype(np.float64) for channel in np.moveaxis(line, -1, 0))
        names = ("R", "G", "B", "A")[: len(values)]
    positions = tuple(np.arange(len(channel), dtype=np.float64) for channel in values)
    return LineProfileResult(selected.x1, selected.y1, values, names, positions)


def selected_bayer_line_profile(
    image: NDArray[np.generic],
    selection: LineSelection,
    pattern: str,
) -> LineProfileResult:
    """Sample all CFA planes along a line, retaining their every-other-pixel X positions."""

    if image.ndim != 2:
        raise ValueError("Bayer line profile expects a 2-D mosaic")
    selected = clamp_line(image.shape, selection.x1, selection.y1, selection.x2, selection.y2)
    channel_values: list[NDArray[np.float64]] = []
    channel_positions: list[NDArray[np.float64]] = []
    channel_names: list[str] = []
    height, width = image.shape
    positions = bayer_channel_positions(pattern)
    for name in BAYER_CHANNEL_NAMES:
        row_parity, column_parity = positions[name]
        if selected.is_horizontal:
            direction = 1 if selected.x2 > selected.x1 else -1
            source_axis = np.arange(selected.x1, selected.x2 + direction, direction)
            fixed_candidates = [
                row
                for row in (selected.y1, selected.y1 - 1, selected.y1 + 1)
                if 0 <= row < height and row % 2 == row_parity
            ]
            if not fixed_candidates:
                continue
            fixed = min(fixed_candidates, key=lambda candidate: abs(candidate - selected.y1))
            mask = source_axis % 2 == column_parity
            sampled = image[fixed, source_axis[mask]]
        else:
            assert selected.y2 is not None
            direction = 1 if selected.y2 > selected.y1 else -1
            source_axis = np.arange(selected.y1, selected.y2 + direction, direction)
            fixed_candidates = [
                column
                for column in (selected.x1, selected.x1 - 1, selected.x1 + 1)
                if 0 <= column < width and column % 2 == column_parity
            ]
            if not fixed_candidates:
                continue
            fixed = min(fixed_candidates, key=lambda candidate: abs(candidate - selected.x1))
            mask = source_axis % 2 == row_parity
            sampled = image[source_axis[mask], fixed]
        if not np.any(mask):
            continue
        distances = np.arange(len(source_axis), dtype=np.float64)
        channel_names.append(name)
        channel_values.append(sampled.astype(np.float64))
        channel_positions.append(distances[mask])
    return LineProfileResult(
        selected.x1,
        selected.y1,
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
