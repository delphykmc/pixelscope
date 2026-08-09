from __future__ import annotations

import numpy as np

from pixelscope.core.display_transform import (
    DisplayTransform,
    apply_display_gain_inplace,
    display_gain_affine,
    display_normalization_affine,
    to_display_uint8,
)


def test_display_gain_affine_matches_anchor_formula_in_float32() -> None:
    source = np.array([48.0, 60.0, 64.0, 68.0, 88.0], dtype=np.float32)
    scale, offset = display_gain_affine(4.0, 64.0)

    recovered = (source - offset) / scale
    expected_source = np.array([60.0, 63.0, 64.0, 65.0, 70.0], dtype=np.float32)

    assert scale.dtype == np.float32
    assert offset.dtype == np.float32
    assert np.array_equal(recovered, expected_source)


def test_display_normalization_affine_fuses_gain_and_range_mapping() -> None:
    source = np.array([60.0, 64.0, 70.0], dtype=np.float32)
    scale, offset = display_normalization_affine(0.0, 4095.0, 4.0, 64.0)
    values = source.copy()
    values *= scale
    values += offset

    gained = np.array([48.0, 64.0, 88.0], dtype=np.float32)
    expected = gained / np.float32(4095.0)
    assert np.allclose(values, expected, rtol=0.0, atol=1e-7)


def test_generic_display_gain_supports_anchor_zero_for_gray_and_rgb() -> None:
    gray = np.array([[10, 20, 120]], dtype=np.uint8)
    rgb = np.array([[[10, 20, 30], [60, 90, 120]]], dtype=np.uint8)
    transform = DisplayTransform(
        display_low=0.0,
        display_high=255.0,
        gain=2.0,
        gain_anchor=0.0,
    )

    assert np.array_equal(to_display_uint8(gray, transform), np.array([[20, 40, 240]], dtype=np.uint8))
    assert np.array_equal(
        to_display_uint8(rgb, transform),
        np.array([[[20, 40, 60], [120, 180, 240]]], dtype=np.uint8),
    )


def test_generic_gain_can_target_rgb_view_without_changing_alpha() -> None:
    rgba = np.array([[[10.0, 20.0, 30.0, 77.0]]], dtype=np.float32)
    alpha = rgba[..., 3].copy()

    apply_display_gain_inplace(rgba[..., :3], gain=2.0, anchor=0.0)

    assert np.array_equal(rgba[..., :3], np.array([[[20.0, 40.0, 60.0]]], dtype=np.float32))
    assert np.array_equal(rgba[..., 3], alpha)
