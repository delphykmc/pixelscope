from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core.roi import RoiBounds, analyze_roi, clamp_roi, extract_roi


def test_clamp_roi_uses_half_open_image_bounds() -> None:
    assert clamp_roi((10, 20), -2, 3, 8, 20) == RoiBounds(0, 3, 6, 7)
    with pytest.raises(ValueError, match="does not intersect"):
        clamp_roi((10, 20), 20, 0, 3, 3)


def test_extract_roi_returns_expected_view() -> None:
    image = np.arange(30, dtype=np.uint16).reshape(5, 6)
    region = extract_roi(image, RoiBounds(2, 1, 3, 2))
    assert region.tolist() == [[8, 9, 10], [14, 15, 16]]
    assert np.shares_memory(image, region)


def test_roi_analysis_grayscale() -> None:
    image = np.arange(16, dtype=np.uint8).reshape(4, 4)
    result = analyze_roi(image, RoiBounds(1, 1, 2, 2), bins=16)
    assert result.pixel_count == 4
    assert result.overall.minimum == 5.0
    assert result.overall.maximum == 10.0
    assert result.overall.mean == 7.5
    assert int(result.histogram.counts[0].sum()) == 4


def test_roi_analysis_rgb_has_per_channel_statistics() -> None:
    image = np.zeros((3, 4, 3), dtype=np.uint8)
    image[..., 0] = 10
    image[..., 1] = 20
    image[..., 2] = 30
    result = analyze_roi(image, RoiBounds(1, 1, 2, 2), bins=32)
    assert result.channel_names == ("R", "G", "B")
    assert [statistics.mean for statistics in result.channel_statistics] == [
        10.0,
        20.0,
        30.0,
    ]
    assert result.overall.mean == 20.0
