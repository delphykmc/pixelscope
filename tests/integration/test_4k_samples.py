from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pixelscope.core.diff_engine import absolute_difference
from pixelscope.core.statistics import mean_squared_error, peak_signal_to_noise_ratio
from pixelscope.io.image_reader import read_image, read_raw_document

SAMPLES = Path(__file__).parents[2] / "samples"
pytestmark = pytest.mark.skipif(
    not SAMPLES.is_dir(),
    reason="optional samples directory is not available",
)


def test_supplied_4k_reference_degraded_and_raw_match_manifest() -> None:
    expected = json.loads((SAMPLES / "expected_metrics.json").read_text(encoding="utf-8"))
    reference = read_image(SAMPLES / "scene_reference_4k.png")
    degraded = read_image(SAMPLES / "scene_degraded_4k.png")
    assert reference.shape == (2160, 3840, 3)
    assert degraded.shape == reference.shape
    assert reference.document_id != degraded.document_id
    assert reference.source is not None and degraded.source is not None
    assert not np.array_equal(reference.source, degraded.source)

    assert mean_squared_error(reference.source, degraded.source) == pytest.approx(
        expected["mse_rgb"], abs=1e-9
    )
    assert peak_signal_to_noise_ratio(reference.source, degraded.source) == pytest.approx(
        expected["psnr_rgb_db"], abs=1e-9
    )
    difference = absolute_difference(reference.source, degraded.source)
    assert float(np.mean(difference)) == pytest.approx(expected["abs_diff_mean"], abs=1e-9)
    assert int(np.max(difference)) == expected["abs_diff_max"]

    raw = read_raw_document(
        SAMPLES / "scene_reference_4k_rggb10_u16le.raw",
        SAMPLES / "scene_reference_4k_rggb10_u16le.json",
    )
    assert raw.shape == (2160, 3840)
    assert raw.original_dtype == np.dtype("<u2")
    assert raw.source is not None
    assert int(np.min(raw.source)) == expected["raw_min"]
    assert int(np.max(raw.source)) == expected["raw_max"]
    assert raw.bit_depth == expected["raw_effective_bit_depth"]
