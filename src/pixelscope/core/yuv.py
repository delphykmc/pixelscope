from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.line_profile import LineProfileResult, LineSelection, clamp_line
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds
from pixelscope.core.statistics import HistogramResult, statistics_from_histogram

YuvLayout = Literal["YUV444", "YUV422", "YUV420"]
YUV_CHANNEL_NAMES: tuple[str, str, str] = ("Y", "U", "V")


@dataclass(frozen=True)
class NativeYuvFrame:
    """Native 8-bit Y/U/V authority without replicated chroma planes."""

    y: NDArray[np.uint8]
    u: NDArray[np.uint8]
    v: NDArray[np.uint8]
    layout: YuvLayout

    def __post_init__(self) -> None:
        if any(plane.ndim != 2 for plane in self.planes):
            raise ValueError("YUV planes must be 2-D")
        if any(plane.dtype != np.uint8 for plane in self.planes):
            raise ValueError("WP-C1 YUV planes must use uint8 samples")
        height, width = self.y.shape
        if height <= 0 or width <= 0:
            raise ValueError("YUV dimensions must be positive")
        if self.layout in ("YUV422", "YUV420") and width % 2:
            raise ValueError(f"{self.layout} width must be even")
        if self.layout == "YUV420" and height % 2:
            raise ValueError("YUV420 height must be even")
        scale_x, scale_y = self.chroma_scale
        expected = (height // scale_y, width // scale_x)
        if self.u.shape != expected or self.v.shape != expected:
            raise ValueError(
                f"{self.layout} chroma planes must have shape {expected}, "
                f"got U={self.u.shape}, V={self.v.shape}"
            )

    @property
    def planes(self) -> tuple[NDArray[np.uint8], NDArray[np.uint8], NDArray[np.uint8]]:
        return self.y, self.u, self.v

    @property
    def height(self) -> int:
        return int(self.y.shape[0])

    @property
    def width(self) -> int:
        return int(self.y.shape[1])

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    @property
    def chroma_scale(self) -> tuple[int, int]:
        if self.layout == "YUV444":
            return 1, 1
        if self.layout == "YUV422":
            return 2, 1
        if self.layout == "YUV420":
            return 2, 2
        raise ValueError(f"unsupported YUV layout: {self.layout}")

    @property
    def native_nbytes(self) -> int:
        return int(self.y.size + self.u.size + self.v.size)

    @property
    def sample_cardinality(self) -> tuple[int, int, int]:
        return int(self.y.size), int(self.u.size), int(self.v.size)

    def pixel_at(self, x: int, y: int) -> tuple[int, int, int]:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            raise IndexError("pixel coordinate is outside the YUV frame")
        scale_x, scale_y = self.chroma_scale
        return (
            int(self.y[y, x]),
            int(self.u[y // scale_y, x // scale_x]),
            int(self.v[y // scale_y, x // scale_x]),
        )

    def roi_planes(
        self,
        bounds: RoiBounds,
    ) -> tuple[NDArray[np.uint8], NDArray[np.uint8], NDArray[np.uint8]]:
        """Map a luma-coordinate ROI to the native samples referenced by that ROI."""

        if bounds.right > self.width or bounds.bottom > self.height:
            raise ValueError("ROI extends beyond the YUV frame")
        scale_x, scale_y = self.chroma_scale
        chroma_x0 = bounds.x // scale_x
        chroma_y0 = bounds.y // scale_y
        chroma_x1 = (bounds.right + scale_x - 1) // scale_x
        chroma_y1 = (bounds.bottom + scale_y - 1) // scale_y
        return (
            self.y[bounds.y : bounds.bottom, bounds.x : bounds.right],
            self.u[chroma_y0:chroma_y1, chroma_x0:chroma_x1],
            self.v[chroma_y0:chroma_y1, chroma_x0:chroma_x1],
        )


def bt601_full_rgb_preview(frame: NativeYuvFrame) -> NDArray[np.uint8]:
    """Render an RGB viewer preview without creating full-resolution U/V authorities."""

    rgb = np.empty((frame.height, frame.width, 3), dtype=np.uint8)
    scale_x, scale_y = frame.chroma_scale
    cached_chroma_row = -1
    u_values: NDArray[np.float32] | None = None
    v_values: NDArray[np.float32] | None = None

    for row in range(frame.height):
        chroma_row = row // scale_y
        if chroma_row != cached_chroma_row:
            u_native = frame.u[chroma_row].astype(np.float32) - 128.0
            v_native = frame.v[chroma_row].astype(np.float32) - 128.0
            if scale_x == 2:
                u_values = np.repeat(u_native, 2)
                v_values = np.repeat(v_native, 2)
            else:
                u_values = u_native
                v_values = v_native
            cached_chroma_row = chroma_row
        assert u_values is not None and v_values is not None
        y_values = frame.y[row].astype(np.float32)
        red = y_values + 1.402 * v_values
        green = y_values - 0.344136 * u_values - 0.714136 * v_values
        blue = y_values + 1.772 * u_values
        rgb[row, :, 0] = np.clip(np.rint(red), 0, 255).astype(np.uint8)
        rgb[row, :, 1] = np.clip(np.rint(green), 0, 255).astype(np.uint8)
        rgb[row, :, 2] = np.clip(np.rint(blue), 0, 255).astype(np.uint8)
    return rgb


def analyze_yuv_roi(
    frame: NativeYuvFrame,
    bounds: RoiBounds,
    bins: int = 256,
    histogram_range: tuple[float, float] | None = (0.0, 256.0),
) -> RoiAnalysisResult:
    """Analyze Y/U/V on their native sampling grids for one luma-coordinate ROI."""

    if histogram_range is None:
        histogram_range = (0.0, 256.0)
    if bins < 2:
        raise ValueError("bins must be at least 2")
    if histogram_range[1] <= histogram_range[0]:
        raise ValueError("histogram value range must be increasing")

    regions = frame.roi_planes(bounds)
    counts: list[NDArray[np.int64]] = []
    edges = np.linspace(histogram_range[0], histogram_range[1], bins + 1, dtype=np.float64)
    exact_codes = bins == 256 and histogram_range == (0.0, 256.0)
    for region in regions:
        if exact_codes:
            channel_counts = np.bincount(np.ravel(region), minlength=256)[:256]
        else:
            channel_counts, _ = np.histogram(region, bins=bins, range=histogram_range)
        counts.append(channel_counts.astype(np.int64, copy=False))

    result_histogram = HistogramResult(tuple(counts), edges, YUV_CHANNEL_NAMES)
    if exact_codes:
        channel_statistics = tuple(
            statistics_from_histogram(channel_counts, edges) for channel_counts in counts
        )
        overall_counts = np.sum(np.stack(counts), axis=0, dtype=np.int64)
        overall = statistics_from_histogram(overall_counts, edges)
    else:
        # WP-C1 sources are 8-bit, but custom UI binning can intentionally be coarser.
        from pixelscope.core.statistics import image_statistics

        channel_statistics = tuple(image_statistics(region) for region in regions)
        overall = image_statistics(np.concatenate([np.ravel(region) for region in regions]))

    return RoiAnalysisResult(
        bounds=bounds,
        pixel_count=bounds.width * bounds.height,
        overall=overall,
        channel_statistics=channel_statistics,
        channel_names=YUV_CHANNEL_NAMES,
        histogram=result_histogram,
        channel_sample_counts=tuple(int(region.size) for region in regions),
    )


def selected_yuv_line_profile(
    frame: NativeYuvFrame,
    selection: LineSelection,
) -> LineProfileResult:
    """Sample native Y/U/V along a luma-coordinate line without chroma replication."""

    selected = clamp_line(
        frame.shape,
        selection.x1,
        selection.y1,
        selection.x2,
        selection.y2,
    )
    if selected.is_horizontal:
        direction = 1 if selected.x2 > selected.x1 else -1
        x_coordinates = np.arange(selected.x1, selected.x2 + direction, direction)
        y_values = frame.y[selected.y1, x_coordinates]
        y_positions = np.arange(x_coordinates.size, dtype=np.float64)
        scale_x, scale_y = frame.chroma_scale
        anchors = x_coordinates[x_coordinates % scale_x == 0]
        chroma_row = selected.y1 // scale_y
        u_values = frame.u[chroma_row, anchors // scale_x]
        v_values = frame.v[chroma_row, anchors // scale_x]
        chroma_positions = np.abs(anchors - selected.x1).astype(np.float64)
    else:
        assert selected.y2 is not None
        direction = 1 if selected.y2 > selected.y1 else -1
        y_coordinates = np.arange(selected.y1, selected.y2 + direction, direction)
        y_values = frame.y[y_coordinates, selected.x1]
        y_positions = np.arange(y_coordinates.size, dtype=np.float64)
        scale_x, scale_y = frame.chroma_scale
        anchors = y_coordinates[y_coordinates % scale_y == 0]
        chroma_column = selected.x1 // scale_x
        u_values = frame.u[anchors // scale_y, chroma_column]
        v_values = frame.v[anchors // scale_y, chroma_column]
        chroma_positions = np.abs(anchors - selected.y1).astype(np.float64)

    return LineProfileResult(
        selected.x1,
        selected.y1,
        (
            y_values.astype(np.float64),
            u_values.astype(np.float64),
            v_values.astype(np.float64),
        ),
        YUV_CHANNEL_NAMES,
        (y_positions, chroma_positions, chroma_positions),
    )
