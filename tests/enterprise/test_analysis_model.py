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
def test_untrusted_grid_shape_and_dtype_rejected(
    values: np.ndarray, mask: np.ndarray
) -> None:
    with pytest.raises(ValueError):
        SpatialMap(
            values, mask, image_width=64, image_height=64, block_width=64, block_height=64
        )


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
        AttributeDisplay(
            "synthetic_missing", "Missing", "dB", "power", 0.0, "missing", True, 6.0
        )
    with pytest.raises(ValueError):
        AnalysisResult(
            "bad_geometry", 64, 64, "A", "B", attributes=(attr,)
        )


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
    grid = SpatialMap(
        np.array([[4.0]]), np.array([[True]]), 128, 128, 64.0, 64.0
    )
    stats = roi_statistics(grid, (0, 0, 128, 128))
    assert stats.mean == 4.0
    assert stats.valid_coverage == 0.25
    assert roi_statistics(grid, (64, 64, 64, 64)).mean is None
