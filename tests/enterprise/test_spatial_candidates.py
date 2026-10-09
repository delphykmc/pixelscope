"""Pure, deterministic source-pixel Top-3 spatial ROI regression gates."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.spatial_candidates import find_spatial_candidates


def _attribute(
    values: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    block_width: float = 64.0,
    block_height: float = 64.0,
    official: float | None = 2.0,
) -> AttributeDisplay:
    height = image_height if image_height is not None else int(values.shape[0] * block_height)
    width = image_width if image_width is not None else int(values.shape[1] * block_width)
    grid = SpatialMap(
        values=np.asarray(values, dtype=np.float64),
        valid_mask=np.ones(values.shape, dtype=bool) if mask is None else mask,
        image_width=width,
        image_height=height,
        block_width=block_width,
        block_height=block_height,
    )
    return AttributeDisplay(
        attribute_id="synthetic",
        label="Synthetic",
        unit="dB",
        group="Grid-derived",
        official_value=official,
        official_availability="missing" if official is None else "available",
        quality_oriented=True,
        fixed_range=10.0,
        chart_axis_range=10.0,
        spatial=grid,
    )


def test_two_separated_positive_hotspots_are_selected_with_source_roi() -> None:
    values = np.zeros((4, 4), dtype=np.float64)
    values[:2, :2] = 5.0
    values[2:, 2:] = 4.0
    regions = find_spatial_candidates(_attribute(values), window_size=128, stride=64)
    assert [region.roi for region in regions[:2]] == [
        (0, 0, 128, 128),
        (128, 128, 128, 128),
    ]
    assert regions[0].mean == pytest.approx(5.0)
    assert regions[1].mean == pytest.approx(4.0)
    assert all(item.mode == "aligned" for item in regions)
    assert all(item.valid_coverage == pytest.approx(1.0) for item in regions)
    assert len(regions) == 2


def test_negative_official_selects_negative_local_mean_not_positive() -> None:
    values = np.zeros((4, 4), dtype=np.float64)
    values[:2, :2] = -8
    values[2:, 2:] = 6
    regions = find_spatial_candidates(_attribute(values, official=-3.0), window_size=128, stride=64)
    assert regions[0].roi == (0, 0, 128, 128)
    assert regions[0].mean == pytest.approx(-8)
    assert all(region.mean < 0 for region in regions)
    assert all(region.score > 0 for region in regions)


def test_grid_validity_is_not_zero_imputation() -> None:
    values = np.array([[4.0, 100.0], [100.0, 100.0]], dtype=np.float64)
    mask = np.array([[True, False], [False, False]], dtype=bool)
    attr = _attribute(values, mask=mask)
    assert find_spatial_candidates(attr, window_size=128, min_coverage=0.8) == ()
    regions = find_spatial_candidates(attr, window_size=128, min_coverage=0.25)
    assert len(regions) == 1
    assert regions[0].mean == pytest.approx(4.0)
    assert regions[0].valid_coverage == pytest.approx(0.25)
    assert regions[0].valid_area == pytest.approx(64 * 64)


def test_partial_edge_cells_and_small_image_source_geometry() -> None:
    values = np.ones((2, 3), dtype=np.float64)
    attr = _attribute(values, image_width=130, image_height=100)
    regions = find_spatial_candidates(attr)
    assert len(regions) == 1
    assert regions[0].roi == (0, 0, 130, 100)
    assert regions[0].valid_area == pytest.approx(13000.0)
    assert regions[0].valid_coverage == pytest.approx(1.0)
    assert regions[0].mean == pytest.approx(1.0)


def test_missing_or_zero_official_produces_labeled_exploratory_candidates() -> None:
    values = np.array([[-4.0, -4.0], [-4.0, -4.0]], dtype=np.float64)
    missing = _attribute(values, official=None)
    zero = replace(missing, official_value=0.0, official_availability="available")
    for attr in (missing, zero):
        regions = find_spatial_candidates(attr)
        assert len(regions) == 1
        assert regions[0].mode == "exploratory_abs"
        assert regions[0].mean == pytest.approx(-4.0)
        assert regions[0].score == pytest.approx(4.0)


def test_uniform_ties_are_ordered_by_y_then_x_and_nms_is_deterministic() -> None:
    attr = _attribute(np.ones((4, 4), dtype=np.float64))
    first = find_spatial_candidates(attr, window_size=128, stride=64)
    second = find_spatial_candidates(attr, window_size=128, stride=64)
    assert first == second
    assert [item.roi for item in first] == [
        (0, 0, 128, 128),
        (128, 0, 128, 128),
        (0, 128, 128, 128),
    ]


def test_edge_scan_position_and_4k_grid_smoke() -> None:
    rows, cols = 34, 60
    values = np.sin(np.arange(rows)[:, None] / 3.0) + np.cos(np.arange(cols)[None, :] / 4.0)
    attr = _attribute(values, image_width=3840, image_height=2160, official=1)
    regions = find_spatial_candidates(attr)
    assert 0 < len(regions) <= 3
    assert all(0 <= c.x <= 3840 - 512 for c in regions)
    assert all(0 <= c.y <= 2160 - 512 for c in regions)
    assert all(c.width == c.height == 512 for c in regions)


def test_no_grid_no_candidate_and_validation() -> None:
    attr = replace(_attribute(np.ones((2, 2))), spatial=None)
    assert find_spatial_candidates(attr) == ()
    with pytest.raises(ValueError, match="positive window"):
        find_spatial_candidates(attr, stride=0)
    with pytest.raises(ValueError, match="thresholds"):
        find_spatial_candidates(attr, min_coverage=1.2)
