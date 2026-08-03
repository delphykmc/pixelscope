from __future__ import annotations

from math import inf, sqrt

import numpy as np
import pytest

from pixelscope.core.diff_engine import absolute_difference_metrics


def test_chunked_uint16_metrics_match_direct_exact_statistics() -> None:
    absolute = np.array(
        [
            [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
            [[9, 10, 11], [12, 13, 14], [15, 16, 1023]],
        ],
        dtype=np.uint16,
    )
    metrics = absolute_difference_metrics(
        absolute,
        1023.0,
        chunk_elements=4,
    )
    direct = absolute.astype(np.float64).reshape(-1)
    expected_mse = float(np.mean(direct * direct))

    assert metrics.mae == pytest.approx(float(np.mean(direct)))
    assert metrics.mse == pytest.approx(expected_mse)
    assert metrics.rmse == pytest.approx(sqrt(expected_mse))
    assert metrics.p95 == pytest.approx(float(np.percentile(direct, 95.0)))
    assert metrics.p99 == pytest.approx(float(np.percentile(direct, 99.0)))
    assert metrics.maximum_absolute == 1023.0
    assert metrics.nonzero_ratio == pytest.approx(float(np.count_nonzero(direct) / direct.size))


def test_chunked_metrics_support_noncontiguous_channel_roi() -> None:
    source = np.arange(8 * 10 * 3, dtype=np.uint16).reshape(8, 10, 3)
    channel = source[..., 1]
    assert not channel.flags.c_contiguous
    bounds = (2, 1, 5, 4)

    metrics = absolute_difference_metrics(
        channel,
        65535.0,
        bounds,
        chunk_elements=3,
    )
    direct = channel[1:5, 2:7].astype(np.float64).reshape(-1)

    assert metrics.mae == pytest.approx(float(np.mean(direct)))
    assert metrics.mse == pytest.approx(float(np.mean(direct * direct)))
    assert metrics.p95 == pytest.approx(float(np.percentile(direct, 95.0)))
    assert metrics.p99 == pytest.approx(float(np.percentile(direct, 99.0)))
    assert metrics.maximum_absolute == float(np.max(direct))
    assert metrics.nonzero_ratio == 1.0


def test_zero_absolute_map_reports_infinite_psnr_and_zero_nonzero_ratio() -> None:
    absolute = np.zeros((17, 19, 3), dtype=np.uint8)

    metrics = absolute_difference_metrics(absolute, 255.0, chunk_elements=11)

    assert metrics.mae == 0.0
    assert metrics.mse == 0.0
    assert metrics.rmse == 0.0
    assert metrics.psnr == inf
    assert metrics.p95 == 0.0
    assert metrics.p99 == 0.0
    assert metrics.maximum_absolute == 0.0
    assert metrics.nonzero_ratio == 0.0


def test_chunked_metrics_do_not_use_full_square_temporary(monkeypatch: object) -> None:
    absolute = np.arange(4096, dtype=np.uint16).reshape(64, 64)

    def fail_square(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("np.square should not be used by chunked Difference metrics")

    monkeypatch.setattr(np, "square", fail_square)  # type: ignore[attr-defined]
    metrics = absolute_difference_metrics(
        absolute,
        65535.0,
        chunk_elements=128,
    )

    assert metrics.maximum_absolute == 4095.0
    assert metrics.rmse > 0.0
