"""IQA handoff presentation semantics: pure, independent of Qt and private data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
    clipped_cells,
    colorize_spatial_rgba,
    map_polarity_legend,
    roi_statistics,
)


def _grid() -> SpatialMap:
    return SpatialMap(
        values=np.array([[2.0, -3.0], [0.0, np.nan]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )


def test_invalid_spatial_mask_is_not_numeric_zero() -> None:
    grid = _grid()
    stats = roi_statistics(grid, (0, 0, 128, 128))
    assert stats.mean == pytest.approx(-1 / 3)
    assert stats.valid_coverage == pytest.approx(0.75)
    assert stats.valid_area == pytest.approx(3 * 64 * 64)
    assert roi_statistics(grid, (64, 64, 64, 64)).mean is None


def test_partial_grid_cell_overlap_and_clamp_are_independent() -> None:
    grid = _grid()
    stats = roi_statistics(grid, (32, 0, 64, 64))
    assert stats.mean == pytest.approx(-0.5)
    assert stats.valid_coverage == 1.0
    assert clipped_cells(grid, 2.5) == (1, 3)
    # Rendering range never mutates numeric source or ROI aggregation.
    assert roi_statistics(grid, (32, 0, 64, 64)) == stats


@pytest.mark.parametrize(
    "values,mask",
    [
        (np.ones((2, 2)), np.ones((1, 2), dtype=bool)),
        (np.array([[np.inf]]), np.array([[True]])),
        (np.array([["private"]]), np.array([[True]])),
    ],
)
def test_untrusted_grid_shape_and_dtype_rejected(values: np.ndarray, mask: np.ndarray) -> None:
    with pytest.raises(ValueError):
        SpatialMap(values, mask, image_width=64, image_height=64, block_width=64, block_height=64)


def test_result_pair_geometry_and_official_missing_are_explicit() -> None:
    attr = AttributeDisplay(
        attribute_id="synthetic_01",
        label="Example",
        unit="dB",
        group="power",
        official_value=0.0,
        official_availability="available",
        quality_oriented=True,
        fixed_range=6.0,
        spatial=_grid(),
    )
    result = AnalysisResult(
        result_id="public-fixture",
        image_width=128,
        image_height=128,
        source_a_label="Synthetic A",
        source_b_label="Synthetic B",
        source_a=Path("absent_a.png"),
        source_b=Path("absent_b.png"),
        attributes=(attr,),
    )
    assert result.attribute("synthetic_01").official_value == 0.0
    with pytest.raises(ValueError):
        AttributeDisplay("synthetic_missing", "Missing", "dB", "power", 0.0, "missing", True, 6.0)
    with pytest.raises(ValueError):
        AnalysisResult("bad_geometry", 64, 64, "A", "B", attributes=(attr,))


def test_grid_is_defensively_copied_for_immutable_presentation() -> None:
    values = np.array([[2.0]])
    mask = np.array([[True]])
    grid = SpatialMap(values, mask, 64, 64, 64.0, 64.0)
    values[0, 0] = 999.0
    mask[0, 0] = False
    assert grid.values[0, 0] == 2.0
    assert bool(grid.valid_mask[0, 0])
    assert not grid.values.flags.writeable


def test_roi_can_reside_outside_coverage_without_fabricating_zeros() -> None:
    grid = SpatialMap(np.array([[4.0]]), np.array([[True]]), 128, 128, 64.0, 64.0)
    stats = roi_statistics(grid, (0, 0, 128, 128))
    assert stats.mean == 4.0
    assert stats.valid_coverage == 0.25
    assert roi_statistics(grid, (64, 64, 64, 64)).mean is None


def test_quality_oriented_and_signed_polarity_use_distinct_map_colors() -> None:
    grid = SpatialMap(
        values=np.array([[4.0, -4.0, 0.0, np.nan]]),
        valid_mask=np.array([[True, True, True, False]]),
        image_width=256,
        image_height=64,
        block_width=64.0,
        block_height=64.0,
    )

    def attribute(oriented: bool) -> AttributeDisplay:
        return AttributeDisplay(
            "signed_example",
            "Example",
            "delta",
            "signed",
            None,
            "missing",
            oriented,
            4.0,
            grid,
        )

    oriented = colorize_spatial_rgba(attribute(True), 4.0)
    signed = colorize_spatial_rgba(attribute(False), 4.0)
    assert oriented is not None and signed is not None
    assert tuple(oriented[0, 0]) == (245, 0, 0, 255)  # + means A better
    assert tuple(oriented[0, 1]) == (0, 0, 245, 255)  # - means B better
    assert tuple(signed[0, 0]) == (181, 72, 193, 255)  # + signed only
    assert tuple(signed[0, 1]) == (35, 145, 148, 255)  # - signed only
    assert tuple(signed[0, 2]) == (239, 239, 239, 255)
    assert signed[0, 3, 3] == 0  # invalid is transparent, not zero
    assert "A better" in map_polarity_legend(attribute(True))
    assert "NO quality winner" in map_polarity_legend(attribute(False))
    assert not np.shares_memory(signed, grid.values)


def test_vectorized_dense_map_keeps_geometry_and_raw_values() -> None:
    values = np.linspace(-10, 10, 256 * 256).reshape(256, 256)
    original = values.copy()
    grid = SpatialMap(
        values=values,
        valid_mask=np.ones((256, 256), dtype=np.bool_),
        image_width=1024,
        image_height=1024,
        block_width=4,
        block_height=4,
    )
    attr = AttributeDisplay("dense", "Dense", "dB", "power", 0.0, "available", True, 6, grid)
    rgba = colorize_spatial_rgba(attr, 6)
    assert rgba is not None and rgba.shape == (256, 256, 4)
    assert rgba.flags.c_contiguous
    assert np.array_equal(grid.values, original)
    assert clipped_cells(grid, 6)[0] > 0
    with pytest.raises(ValueError):
        colorize_spatial_rgba(attr, 0)


def test_official_chart_axis_is_not_spatial_map_color_scale() -> None:
    from pixelscope_enterprise.iqa.analysis_model import official_chart_fraction

    # Deliberately unrelated scales. The map color range must NOT be reused.
    positive = AttributeDisplay(
        "c",
        "Official",
        "dB",
        "power",
        2.0,
        "available",
        True,
        0.05,
        chart_axis_range=4.0,
    )
    assert official_chart_fraction(positive) == 0.5
    assert positive.fixed_range == 0.05
    zero = AttributeDisplay(
        "zero",
        "Zero",
        "dB",
        "power",
        0.0,
        "available",
        True,
        1.0,
        chart_axis_range=4.0,
    )
    assert official_chart_fraction(zero) == 0.0
    no_axis = AttributeDisplay("axis", "Unknown axis", "dB", "power", 2.0, "available", True, 5.0)
    no_value = AttributeDisplay(
        "missing",
        "Missing",
        "dB",
        "power",
        None,
        "missing",
        True,
        5.0,
        chart_axis_range=4.0,
    )
    assert official_chart_fraction(no_axis) is None
    assert official_chart_fraction(no_value) is None
    negative = AttributeDisplay(
        "neg",
        "Neutral",
        "delta",
        "signed",
        -8.0,
        "available",
        False,
        2.0,
        chart_axis_range=3.0,
    )
    assert official_chart_fraction(negative) == -1.0
    for bad in (-1.0, 0.0, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="official chart axis"):
            AttributeDisplay(
                "bad",
                "Bad",
                "dB",
                "power",
                1.0,
                "available",
                True,
                3.0,
                chart_axis_range=bad,
            )


def test_public_demo_covers_independent_official_and_spatial_availability() -> None:
    from pixelscope_enterprise.iqa.analysis_model import official_chart_fraction

    official_only = AttributeDisplay(
        "official",
        "Official only",
        "dB",
        "power",
        0.0,
        "available",
        True,
        2.0,
        chart_axis_range=3.0,
    )
    assert official_only.spatial is None
    assert official_chart_fraction(official_only) == 0.0
    spatial_only = AttributeDisplay(
        "grid",
        "Grid only",
        "dB",
        "power",
        None,
        "missing",
        True,
        2.0,
        chart_axis_range=3.0,
    )
    assert spatial_only.official_value is None
    assert official_chart_fraction(spatial_only) is None
