from __future__ import annotations

from math import inf

import numpy as np
import pytest

from pixelscope.core.diff_engine import (
    absolute_difference,
    absolute_difference_metrics,
    analyze_difference,
    compact_absolute_difference,
    difference_compatibility,
    difference_metrics,
    normalized_absolute_difference,
    signed_difference,
    validate_difference_documents,
)
from pixelscope.core.display_transform import render_signed_difference, render_threshold_mask
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.statistics import (
    histogram,
    image_statistics,
    mean_squared_error,
    peak_signal_to_noise_ratio,
    statistics_from_histogram,
)


def test_uint16_difference_prevents_wraparound() -> None:
    a = np.array([0, 65535], dtype=np.uint16)
    b = np.array([65535, 0], dtype=np.uint16)
    signed = signed_difference(a, b)
    assert signed.tolist() == [-65535, 65535]
    assert signed.dtype == np.dtype(np.int32)
    assert absolute_difference(a, b).tolist() == [65535, 65535]

    compact = compact_absolute_difference(a, b)
    assert compact.dtype == np.dtype(np.uint16)
    assert compact.tolist() == [65535, 65535]
    metrics = absolute_difference_metrics(compact.reshape(1, 2), 65535.0)
    assert metrics.mae == 65535.0


def test_threshold_mask_ors_selected_channels_and_uses_red_only() -> None:
    absolute = np.array([[[0, 11, 0], [10, 0, 0]], [[0, 0, 0], [0, 0, 12]]], dtype=np.uint8)
    preview = render_threshold_mask(absolute, 10)
    assert preview.tolist() == [
        [[255, 0, 0], [0, 0, 0]],
        [[0, 0, 0], [255, 0, 0]],
    ]


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


@pytest.mark.parametrize("dtype,bins", ((np.uint8, 256), (np.uint16, 1024)))
def test_native_histogram_statistics_match_direct_statistics(
    dtype: type[np.generic], bins: int
) -> None:
    rng = np.random.default_rng(1234)
    image = rng.integers(0, bins, size=(73, 91), dtype=dtype)
    result = histogram(image, bins=bins, value_range=(0.0, float(bins)))
    direct = image_statistics(image)
    derived = statistics_from_histogram(result.counts[0], result.edges)

    assert derived.minimum == direct.minimum
    assert derived.maximum == direct.maximum
    assert derived.mean == pytest.approx(direct.mean)
    assert derived.standard_deviation == pytest.approx(direct.standard_deviation)
    assert derived.percentiles == pytest.approx(direct.percentiles)


def _bayer_document(name: str, pattern: str, bit_depth: int = 10) -> ImageDocument:
    return ImageDocument.from_array(
        np.zeros((4, 5), dtype=np.uint16),
        name,
        channel_layout="BAYER",
        bit_depth=bit_depth,
        raw_profile=type("Profile", (), {"bayer_pattern": pattern})(),
    )


def test_difference_compatibility_families_and_domains_are_structured() -> None:
    gray8 = ImageDocument.from_array(np.zeros((4, 5), dtype=np.uint8), "gray8.png")
    gray10 = ImageDocument.from_array(np.zeros((4, 5), dtype=np.uint16), "gray10.raw", bit_depth=10)
    rgb = ImageDocument.from_array(np.zeros((4, 5, 3), dtype=np.uint8), "rgb.png")
    rgba = ImageDocument.from_array(np.zeros((4, 5, 4), dtype=np.uint8), "rgba.png")
    rgb10 = ImageDocument.from_array(
        np.zeros((4, 5, 3), dtype=np.uint16), "rgb10.png", bit_depth=10
    )
    bayer_rggb = _bayer_document("rggb.raw", "RGGB")
    bayer_bggr = _bayer_document("bggr.raw", "BGGR")
    mismatched = ImageDocument.from_array(np.zeros((3, 5, 3), dtype=np.uint8), "small.png")

    gray_native = difference_compatibility(gray8, gray8)
    gray_normalized = difference_compatibility(gray8, gray10)
    rgb_rgba = difference_compatibility(rgb, rgba)
    bayer = difference_compatibility(bayer_rggb, bayer_rggb)

    assert (gray_native.compatible, gray_native.family, gray_native.domain) == (
        True,
        "GRAY",
        "native",
    )
    assert gray_native.data_range == 255.0
    assert (gray_normalized.compatible, gray_normalized.domain) == (True, "normalized")
    assert gray_normalized.data_range == 1.0
    assert (rgb_rgba.compatible, rgb_rgba.family, rgb_rgba.domain) == (True, "RGB", "native")
    assert (bayer.compatible, bayer.family) == (True, "BAYER")
    assert difference_compatibility(gray8, rgb).reason_code == "layout-mismatch"
    assert difference_compatibility(gray8, bayer_rggb).reason_code == "layout-mismatch"
    assert difference_compatibility(rgb, bayer_rggb).reason_code == "layout-mismatch"
    assert difference_compatibility(rgb, mismatched).reason_code == "size-mismatch"
    assert difference_compatibility(bayer_rggb, bayer_bggr).reason_code == "cfa-mismatch"
    assert difference_compatibility(rgb, rgb10).domain == "normalized"
    assert validate_difference_documents(rgb, rgb10) is None


def test_difference_analysis_metrics_and_normalized_domain() -> None:
    a = np.array([[0, 10], [20, 30]], dtype=np.uint8)
    b = np.array([[0, 8], [25, 30]], dtype=np.uint8)
    result = analyze_difference(a, b, mode="absolute", data_range=255.0)
    assert result.numerical.tolist() == [[0, 2], [5, 0]]
    assert result.metrics.mae == pytest.approx(1.75)
    assert result.metrics.mse == pytest.approx(7.25)
    assert result.metrics.minimum_signed == -5
    assert result.metrics.maximum_signed == 2
    assert result.metrics.minimum_absolute == 0
    assert result.metrics.maximum_absolute == 5
    assert int(result.histogram_counts.sum()) == a.size

    normalized = analyze_difference(
        np.array([[255]], dtype=np.uint8),
        np.array([[65535]], dtype=np.uint16),
        mode="signed",
        domain="normalized",
        bit_depth_a=8,
        bit_depth_b=16,
    )
    assert normalized.numerical.dtype == np.dtype(np.float32)
    assert normalized.numerical[0, 0] == pytest.approx(0.0)
    assert normalized.metrics.psnr == inf


def test_normalized_absolute_difference_uses_each_effective_full_scale() -> None:
    full8 = np.array([[255, 128]], dtype=np.uint8)
    full16 = np.array([[65535, 32768]], dtype=np.uint16)
    result = normalized_absolute_difference(full8, full16, 8, 16, chunk_elements=1)
    assert result.dtype == np.dtype(np.float32)
    assert result[0, 0] == pytest.approx(0.0)
    assert result[0, 1] == pytest.approx(abs(128 / 255 - 32768 / 65535), abs=1e-7)

    full10 = np.array([[1023]], dtype=np.uint16)
    full12 = np.array([[4095]], dtype=np.uint16)
    assert normalized_absolute_difference(full10, full12, 10, 12)[0, 0] == pytest.approx(0.0)


def test_difference_metrics_use_roi_and_all_selected_rgb_samples() -> None:
    signed = np.array(
        [
            [[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]],
            [[-1.0, -2.0, -3.0], [4.0, 5.0, 6.0]],
        ]
    )
    metrics = difference_metrics(signed, 255.0, (1, 0, 1, 1))
    assert metrics.mae == pytest.approx(20.0)
    assert metrics.mse == pytest.approx((100.0 + 400.0 + 900.0) / 3.0)
    assert metrics.minimum_signed == 10.0
    assert metrics.maximum_signed == 30.0
    assert metrics.minimum_absolute == 10.0
    assert metrics.maximum_absolute == 30.0

    with pytest.raises(ValueError, match="extends beyond"):
        difference_metrics(signed, 255.0, (2, 0, 1, 1))
