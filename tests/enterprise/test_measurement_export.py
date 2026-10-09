"""Qt-free UX-3A export conformance: no server format or UI dependency."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.measurement_export import (
    COLUMNS,
    build_measurements_csv,
    write_measurements_csv,
)


def _result() -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[4.0, np.nan], [2.0, -2.0]], dtype=np.float64),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=128,
        image_height=128,
        block_width=64.0,
        block_height=64.0,
    )
    return AnalysisResult(
        result_id="pair-001",
        image_width=128,
        image_height=128,
        source_a_label="A, source",
        source_b_label="B\nsource",
        attributes=(
            AttributeDisplay(
                "snr",
                "Relative SNR",
                "dB",
                "SNR",
                0.0,
                "available",
                True,
                6.0,
                grid,
            ),
            AttributeDisplay(
                "edge",
                "Edge delta",
                "Δ",
                "Detail",
                None,
                "missing",
                False,
                3.0,
                None,
            ),
        ),
    )


def _rows(payload: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload)))


def test_official_and_grid_derived_rows_are_distinct_and_masked() -> None:
    result = _result()
    payload = build_measurements_csv(result, (0.0, 0.0, 128.0, 128.0))
    assert payload.startswith(",".join(COLUMNS).replace("\n", ""))
    assert "\r\n" in payload
    rows = _rows(payload)
    assert len(rows) == 3
    assert [r["measurement_scope"] for r in rows] == [
        "OFFICIAL_FULL_PAIR",
        "GRID_DERIVED_ROI",
        "OFFICIAL_FULL_PAIR",
    ]
    assert all(r["source_a_label"] == "A, source" for r in rows)
    assert all(r["source_b_label"] == "B\nsource" for r in rows)
    official, region, missing = rows
    assert official["attribute_id"] == region["attribute_id"] == "snr"
    assert official["unit"] == region["unit"] == "dB"
    assert official["quality_oriented"] == "yes"
    assert official["value"] == "0.0"  # real zero, not missing
    assert official["availability"] == "available"
    assert official["roi_x_px"] == official["roi_valid_coverage"] == ""
    assert float(region["value"]) == pytest.approx(4.0 / 3.0)
    assert float(region["roi_valid_area_px2"]) == pytest.approx(12288.0)
    assert float(region["roi_total_area_px2"]) == pytest.approx(16384.0)
    assert float(region["roi_valid_coverage"]) == pytest.approx(0.75)
    assert region["availability"] == "available"
    assert missing["value"] == ""
    assert missing["availability"] == "missing"
    assert missing["quality_oriented"] == "no"


def test_no_roi_exports_official_only() -> None:
    assert [r["measurement_scope"] for r in _rows(build_measurements_csv(_result()))] == [
        "OFFICIAL_FULL_PAIR",
        "OFFICIAL_FULL_PAIR",
    ]


@pytest.mark.parametrize(
    "roi",
    [
        (-1.0, 0.0, 40.0, 40.0),
        (0.0, 0.0, 129.0, 50.0),
        (4.0, 4.0, 0.0, 10.0),
        (4.0, 4.0, float("nan"), 10.0),
        (0.0, 0.0, 10.0, float("inf")),
    ],
)
def test_bad_roi_rejected_before_writing(roi: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="ROI must lie within"):
        build_measurements_csv(_result(), roi)


def test_spreadsheet_injection_escaped_only_in_untrusted_text() -> None:
    original = _result()
    bad = AnalysisResult(
        "=SUM(1+1)",
        original.image_width,
        original.image_height,
        "+evil",
        "@evil",
        (
            AttributeDisplay(
                "-danger-id",
                '=HYPERLINK("https://invalid.example")',
                "@bad",
                "group",
                -1.5,
                "partial",
                False,
                6.0,
            ),
        ),
    )
    row = _rows(build_measurements_csv(bad))[0]
    assert row["result_id"] == "'=SUM(1+1)"
    assert row["source_a_label"] == "'+evil"
    assert row["source_b_label"] == "'@evil"
    assert row["attribute_id"] == "'-danger-id"
    assert row["attribute_label"].startswith("'=HYPERLINK")
    assert row["unit"] == "'@bad"
    assert row["value"] == "-1.5"  # trusted numeric values remain numeric
    assert row["availability"] == "partial"


def test_zero_valid_grid_is_missing_not_a_fake_zero() -> None:
    invalid = SpatialMap(
        values=np.full((2, 2), np.nan),
        valid_mask=np.zeros((2, 2), dtype=np.bool_),
        image_width=128,
        image_height=128,
        block_width=64.0,
        block_height=64.0,
    )
    result = AnalysisResult(
        "no-valid-cell",
        128,
        128,
        "A",
        "B",
        (AttributeDisplay("m", "Mask", "dB", "group", 1.0, "available", False, 3.0, invalid),),
    )
    official, local = _rows(build_measurements_csv(result, (0, 0, 128, 128)))
    assert official["value"] == "1.0"
    assert local["value"] == ""
    assert local["availability"] == "missing"
    assert local["roi_valid_area_px2"] == "0.0"
    assert local["roi_valid_coverage"] == "0.0"


def test_atomic_bom_export_roundtrip_and_temporary_cleanup(tmp_path: Path) -> None:
    destination = tmp_path / "measurements.csv"
    write_measurements_csv(_result(), (0, 0, 128, 128), destination)
    content = destination.read_bytes()
    assert content.startswith(b"\xef\xbb\xbf")
    assert _rows(content.decode("utf-8-sig")) == _rows(
        build_measurements_csv(_result(), (0, 0, 128, 128))
    )
    assert list(tmp_path.glob("*.tmp")) == []

    # Failed atomic replacement must preserve the existing destination directory
    # and clean up the provisional temporary file.
    invalid_destination = tmp_path / "existing-directory"
    invalid_destination.mkdir()
    with pytest.raises(OSError):
        write_measurements_csv(_result(), None, invalid_destination)
    assert invalid_destination.is_dir()
    assert list(tmp_path.glob("*.tmp")) == []
