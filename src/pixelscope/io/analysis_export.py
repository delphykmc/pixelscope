from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class HistogramExportSeries:
    """One currently presented Histogram series plus its canonical raw counts."""

    scope: str
    bounds: tuple[int, int, int, int]
    source: str
    series: str
    channel: str
    x_mode: str
    y_mode: str
    native_edges: NDArray[np.float64]
    display_edges: NDArray[np.float64]
    counts: NDArray[np.int64]
    display_values: NDArray[np.float64]


@dataclass(frozen=True)
class LineProfileExportSeries:
    """One currently presented Line Profile series."""

    selection: tuple[int, int, int, int]
    source: str
    series: str
    channel: str
    x_mode: str
    y_mode: str
    positions: NDArray[np.float64]
    values: NDArray[np.float64]


def _format_float(value: float) -> str:
    return format(float(value), ".17g")


def write_histogram_csv(path: Path, series: tuple[HistogramExportSeries, ...]) -> Path:
    """Serialize visible Histogram series without recalculating their analysis data."""

    if not series:
        raise ValueError("no Histogram series to export")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "scope",
                "roi_x",
                "roi_y",
                "roi_width",
                "roi_height",
                "source",
                "series",
                "channel",
                "x_mode",
                "y_mode",
                "bin_index",
                "native_bin_start",
                "native_bin_end",
                "display_bin_start",
                "display_bin_end",
                "count",
                "display_value",
            )
        )
        for item in series:
            bin_count = len(item.counts)
            if (
                len(item.native_edges) != bin_count + 1
                or len(item.display_edges) != bin_count + 1
                or len(item.display_values) != bin_count
            ):
                raise ValueError("Histogram export series dimensions do not match")
            x, y, width, height = item.bounds
            for index in range(bin_count):
                writer.writerow(
                    (
                        item.scope,
                        x,
                        y,
                        width,
                        height,
                        item.source,
                        item.series,
                        item.channel,
                        item.x_mode,
                        item.y_mode,
                        index,
                        _format_float(item.native_edges[index]),
                        _format_float(item.native_edges[index + 1]),
                        _format_float(item.display_edges[index]),
                        _format_float(item.display_edges[index + 1]),
                        int(item.counts[index]),
                        _format_float(item.display_values[index]),
                    )
                )
    return path


def write_line_profile_csv(path: Path, series: tuple[LineProfileExportSeries, ...]) -> Path:
    """Serialize the currently presented Line Profile samples in stable series order."""

    if not series:
        raise ValueError("no Line Profile series to export")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "line_x1",
                "line_y1",
                "line_x2",
                "line_y2",
                "source",
                "series",
                "channel",
                "x_mode",
                "y_mode",
                "sample_index",
                "position",
                "value",
            )
        )
        for item in series:
            if len(item.positions) != len(item.values):
                raise ValueError("Line Profile export series dimensions do not match")
            x1, y1, x2, y2 = item.selection
            for index, (position, value) in enumerate(
                zip(item.positions, item.values, strict=True)
            ):
                writer.writerow(
                    (
                        x1,
                        y1,
                        x2,
                        y2,
                        item.source,
                        item.series,
                        item.channel,
                        item.x_mode,
                        item.y_mode,
                        index,
                        _format_float(position),
                        _format_float(value),
                    )
                )
    return path


def write_difference_png(path: Path, preview: NDArray[np.uint8]) -> Path:
    """Encode one current Difference presentation preview as PNG."""

    if preview.dtype != np.uint8 or preview.ndim not in (2, 3):
        raise ValueError("Difference export requires a uint8 presentation image")
    if preview.ndim == 3:
        if preview.shape[2] == 3:
            encoded_source = cv2.cvtColor(preview, cv2.COLOR_RGB2BGR)
        elif preview.shape[2] == 4:
            encoded_source = cv2.cvtColor(preview, cv2.COLOR_RGBA2BGRA)
        else:
            raise ValueError("Difference export supports Gray, RGB, or RGBA presentation")
    else:
        encoded_source = preview
    success, encoded = cv2.imencode(".png", encoded_source)
    if not success:
        raise OSError("PNG encoding failed")
    with path.open("wb") as stream:
        stream.write(encoded.tobytes())
    return path
