from __future__ import annotations

from threading import Event

import cv2
import numpy as np
import pytest

from pixelscope.core.cancellation import CooperativeCancellation, cancellation_scope
from pixelscope.core.roi import RoiBounds, analyze_roi
from pixelscope.core.statistics import histogram


@pytest.mark.parametrize("channels", [1, 3, 4])
@pytest.mark.parametrize("cropped", [False, True])
def test_cv2_native_uint8_histogram_matches_numpy_counts_and_edges(
    channels: int,
    cropped: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(2026)
    shape = (23, 35) if channels == 1 else (23, 35, channels)
    image = rng.integers(0, 256, size=shape, dtype=np.uint8)
    image.reshape(-1)[:4] = [0, 255, 0, 255]
    if cropped:
        image = image[3:19, 4:31]

    original = cv2.calcHist
    cv_calls: list[int] = []

    def traced_calc_hist(*args: object, **kwargs: object) -> np.ndarray:
        cv_calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(cv2, "calcHist", traced_calc_hist)
    result = histogram(image)
    assert len(cv_calls) == channels
    assert result.channel_names == (("Gray",) if channels == 1 else ("R", "G", "B", "A")[:channels])
    np.testing.assert_array_equal(result.edges, np.arange(257, dtype=np.float64))
    for channel_index, counts in enumerate(result.counts):
        samples = image if channels == 1 else image[..., channel_index]
        expected = np.bincount(samples.ravel(), minlength=256)
        np.testing.assert_array_equal(counts, expected)
        assert counts.dtype == np.int64
        assert int(counts.sum()) == samples.size


def test_cv2_roi_statistics_retain_exact_native_code_semantics() -> None:
    rng = np.random.default_rng(12)
    image = rng.integers(0, 256, (49, 68, 3), dtype=np.uint8)
    bounds = RoiBounds(4, 5, 40, 31)
    result = analyze_roi(image, bounds)
    roi = image[5:36, 4:44]
    assert result.pixel_count == 1240
    for index, stats in enumerate(result.channel_statistics):
        samples = roi[..., index].astype(np.float64)
        assert stats.minimum == np.min(samples)
        assert stats.maximum == np.max(samples)
        assert stats.mean == pytest.approx(np.mean(samples))
        assert stats.standard_deviation == pytest.approx(np.std(samples))
        for percentile in (1.0, 50.0, 99.0):
            assert stats.percentiles[percentile] == pytest.approx(
                np.percentile(samples, percentile)
            )


@pytest.mark.parametrize(
    ("dtype", "bins", "value_range"),
    [
        (np.uint8, 1024, (0.0, 256.0)),
        (np.uint8, 256, (0.0, 128.0)),
        (np.uint16, 256, (0.0, 65536.0)),
    ],
)
def test_non_native_histogram_contract_uses_existing_numpy_path(
    monkeypatch: pytest.MonkeyPatch,
    dtype: np.dtype | type[np.generic],
    bins: int,
    value_range: tuple[float, float],
) -> None:
    def unexpected_calc_hist(*_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("non-native histogram must use NumPy")

    monkeypatch.setattr(cv2, "calcHist", unexpected_calc_hist)
    image = np.arange(100, dtype=dtype).reshape(10, 10)
    counts = histogram(image, bins=bins, value_range=value_range).counts[0]
    expected, _ = np.histogram(image, bins=bins, range=value_range)
    np.testing.assert_array_equal(counts, expected)


def test_float32_count_precision_guard_falls_back_for_more_than_2_pow_24_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cv2.calcHist reports float32 counts, and 2**24 is the last integer
    # magnitude at which every bin count is guaranteed exactly representable.
    image = np.broadcast_to(np.uint8(255), (4096, 4097))
    assert image.size > (1 << 24)

    def unexpected_calc_hist(*_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("too many samples for float32 cv2 counts")

    monkeypatch.setattr(cv2, "calcHist", unexpected_calc_hist)
    result = histogram(image)
    assert int(result.counts[0][255]) == image.size
    assert int(result.counts[0].sum()) == image.size


def test_cancelled_uint8_cv2_histogram_stops_after_current_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = np.full((24, 32, 3), 33, dtype=np.uint8)
    cancel_event = Event()
    original = cv2.calcHist
    channel_calls: list[int] = []

    def cancel_after_first_channel(*args: object, **kwargs: object) -> np.ndarray:
        result = original(*args, **kwargs)
        channel_calls.append(1)
        cancel_event.set()
        return result

    monkeypatch.setattr(cv2, "calcHist", cancel_after_first_channel)
    with cancellation_scope(cancel_event), pytest.raises(CooperativeCancellation):
        analyze_roi(image, RoiBounds(0, 0, 32, 24))
    assert channel_calls == [1]
