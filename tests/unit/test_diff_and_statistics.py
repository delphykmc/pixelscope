from __future__ import annotations

from math import inf

import numpy as np
import pytest

from pixelscope.core.diff_engine import absolute_difference, signed_difference
from pixelscope.core.display_transform import render_signed_difference
from pixelscope.core.statistics import (
    histogram,
    image_statistics,
    mean_squared_error,
    peak_signal_to_noise_ratio,
)


def test_uint16_difference_prevents_wraparound() -> None:
    a = np.array([0, 65535], dtype=np.uint16)
    b = np.array([65535, 0], dtype=np.uint16)
    signed = signed_difference(a, b)
    assert signed.tolist() == [-65535, 65535]
    assert signed.dtype == np.dtype(np.int32)
    assert absolute_difference(a, b).tolist() == [65535, 65535]


def test_mixed_dtype_rgb_difference() -> None:
    a = np.zeros((2, 2, 3), dtype=np.uint8)
    b = np.full((2, 2, 3), -2, dtype=np.int16)
    assert np.all(signed_difference(a, b) == 2)


def test_rgb_signed_display_is_a_valid_rgb_image() -> None:
    difference = np.zeros((2, 3, 3), dtype=np.int32)
    difference[..., 0] = -10
    difference[..., 2] = 4
    preview = render_signed_difference(difference)
    assert preview.shape == (2, 3, 3)
    assert preview.dtype == np.dtype(np.uint8)


def test_shape_mismatch_is_explicit() -> None:
    with pytest.raises(ValueError, match="shape mismatch"):
        signed_difference(np.zeros((2, 2)), np.zeros((2, 3)))


def test_metrics_and_statistics() -> None:
    a = np.array([0, 2], dtype=np.uint8)
    b = np.array([0, 0], dtype=np.uint8)
    assert mean_squared_error(a, b) == 2.0
    assert peak_signal_to_noise_ratio(a, a) == inf
    assert peak_signal_to_noise_ratio(a, b) == pytest.approx(45.12050365)
    stats = image_statistics(a, (0.0, 50.0, 100.0))
    assert (stats.minimum, stats.maximum, stats.mean) == (0.0, 2.0, 1.0)
    assert stats.percentiles[50.0] == 1.0


def test_gray_and_rgb_histograms() -> None:
    gray = np.array([[0, 0, 255]], dtype=np.uint8)
    gray_result = histogram(gray, bins=256)
    assert gray_result.channel_names == ("Gray",)
    assert gray_result.counts[0][0] == 2
    assert gray_result.counts[0][-1] == 1
    rgb = np.stack((gray, np.zeros_like(gray), np.full_like(gray, 255)), axis=-1)
    rgb_result = histogram(rgb, bins=256)
    assert rgb_result.channel_names == ("R", "G", "B")
    assert [int(counts.sum()) for counts in rgb_result.counts] == [3, 3, 3]


def test_histogram_accepts_effective_bit_depth_range() -> None:
    raw10 = np.array([[0, 512, 1023]], dtype=np.uint16)
    result = histogram(raw10, bins=1024, value_range=(0.0, 1024.0))
    assert len(result.counts[0]) == 1024
    assert result.edges[0] == 0
    assert result.edges[-1] == 1024
    assert result.counts[0][512] == 1
