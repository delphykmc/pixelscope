from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from pixelscope.io.analysis_export import (
    HistogramExportSeries,
    LineProfileExportSeries,
    write_difference_png,
    write_histogram_csv,
    write_line_profile_csv,
)


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def test_histogram_csv_preserves_canonical_counts_and_current_display_axes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "histogram.csv"
    item = HistogramExportSeries(
        scope="Active ROI",
        bounds=(2, 3, 4, 5),
        source=r"C:\images\gray.raw",
        series="1 · gray.raw",
        channel="Gray",
        x_mode="Normalized 0–1",
        y_mode="Normalized",
        native_edges=np.asarray([0.0, 128.0, 256.0]),
        display_edges=np.asarray([0.0, 0.5, 1.0]),
        counts=np.asarray([3, 1], dtype=np.int64),
        display_values=np.asarray([0.75, 0.25]),
    )

    assert write_histogram_csv(target, (item,)) == target

    rows = _csv_rows(target)
    assert rows[0] == [
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
    ]
    assert rows[1] == [
        "Active ROI",
        "2",
        "3",
        "4",
        "5",
        r"C:\images\gray.raw",
        "1 · gray.raw",
        "Gray",
        "Normalized 0–1",
        "Normalized",
        "0",
        "0",
        "128",
        "0",
        "0.5",
        "3",
        "0.75",
    ]
    assert rows[2][-7:] == ["1", "128", "256", "0.5", "1", "1", "0.25"]


def test_line_profile_csv_preserves_current_sample_order_and_modes(tmp_path: Path) -> None:
    target = tmp_path / "line.csv"
    first = LineProfileExportSeries(
        selection=(1, 4, 5, 4),
        source="first.png",
        series="1 · first.png",
        channel="R",
        x_mode="Distance px",
        y_mode="Difference from reference",
        positions=np.asarray([0.0, 1.0, 2.0]),
        values=np.asarray([-2.0, 0.0, 3.5]),
    )
    second = LineProfileExportSeries(
        selection=(1, 4, 5, 4),
        source="second.png",
        series="2 · second.png",
        channel="B",
        x_mode="Distance px",
        y_mode="Difference from reference",
        positions=np.asarray([0.0]),
        values=np.asarray([1.0]),
    )

    write_line_profile_csv(target, (first, second))

    rows = _csv_rows(target)
    assert rows[0][-3:] == ["sample_index", "position", "value"]
    assert [row[4:7] for row in rows[1:]] == [
        ["first.png", "1 · first.png", "R"],
        ["first.png", "1 · first.png", "R"],
        ["first.png", "1 · first.png", "R"],
        ["second.png", "2 · second.png", "B"],
    ]
    assert [row[-3:] for row in rows[1:]] == [
        ["0", "0", "-2"],
        ["1", "1", "0"],
        ["2", "2", "3.5"],
        ["0", "0", "1"],
    ]


def test_difference_png_preserves_rgb_presentation_pixels(tmp_path: Path) -> None:
    target = tmp_path / "difference.png"
    preview = np.asarray(
        [
            [[255, 0, 0], [0, 255, 0]],
            [[0, 0, 255], [20, 40, 60]],
        ],
        dtype=np.uint8,
    )

    assert write_difference_png(target, preview) == target

    decoded = cv2.imread(str(target), cv2.IMREAD_UNCHANGED)
    assert decoded is not None
    restored = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    np.testing.assert_array_equal(restored, preview)
