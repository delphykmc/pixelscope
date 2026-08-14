from __future__ import annotations

import csv
from pathlib import Path

from pixelscope.io.analysis_export import DifferenceMetricsExport, write_difference_metrics_csv


def _rows(path: Path) -> list[list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def test_difference_metrics_csv_preserves_analysis_context_and_values(tmp_path: Path) -> None:
    target = tmp_path / "metrics.csv"
    result = DifferenceMetricsExport(
        source_a="a.raw",
        source_b="b.raw",
        region="Active ROI",
        channel="Gr",
        domain="normalized",
        bit_depth_a=10,
        bit_depth_b=12,
        values=(("MAE", 0.125), ("PSNR", 42.5), ("Non-zero ratio", 0.75)),
    )

    assert write_difference_metrics_csv(target, result) == target

    rows = _rows(target)
    assert rows[0] == [
        "source_a",
        "source_b",
        "region",
        "channel",
        "domain",
        "bit_depth_a",
        "bit_depth_b",
        "metric",
        "value",
    ]
    assert rows[1:] == [
        ["a.raw", "b.raw", "Active ROI", "Gr", "normalized", "10", "12", "MAE", "0.125"],
        ["a.raw", "b.raw", "Active ROI", "Gr", "normalized", "10", "12", "PSNR", "42.5"],
        [
            "a.raw",
            "b.raw",
            "Active ROI",
            "Gr",
            "normalized",
            "10",
            "12",
            "Non-zero ratio",
            "0.75",
        ],
    ]
