"""Quality presentation is optional, signed, and scientifically non-mutating."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.quality_presentation import (
    INFERIOR_RGB,
    MUTED_RGB,
    SUPERIOR_RGB,
    quality_spatial_rgba,
    verdict_for_value,
)


def _attribute(direction: str = "higher_is_better", gate: bool | None = True) -> AttributeDisplay:
    grid = SpatialMap(
        np.array([[2.0, -2.0, 0.5, -0.5, 0.0, np.nan]]),
        np.array([[True, True, True, True, True, False]]),
        384,
        64,
        64.0,
        64.0,
    )
    return AttributeDisplay(
        "relative",
        "Relative",
        "dB",
        "power",
        -2.0,
        "available",
        True,
        4.0,
        grid,
        chart_axis_range=4.0,
        summary_signal_gate=gate,
        quality_direction=direction,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("direction", "value", "expected"),
    [
        ("higher_is_better", 2.0, "Superior"),
        ("higher_is_better", -2.0, "Inferior"),
        ("lower_is_better", 2.0, "Inferior"),
        ("lower_is_better", -2.0, "Superior"),
        ("none", 2.0, "No quality direction"),
        ("none", -2.0, "No quality direction"),
    ],
)
def test_verdict_direction_does_not_reorient_supplied_difference(
    direction: str, value: float, expected: str
) -> None:
    attr = _attribute(direction)
    assert verdict_for_value(attr, value).verdict == expected
    assert attr.official_value == -2.0


@pytest.mark.parametrize("value", [0.5, -0.5, 0.0])
def test_threshold_is_inclusive(value: float) -> None:
    verdict = verdict_for_value(_attribute(), value)
    assert verdict.verdict == "Not visible"
    assert verdict.tone == "muted"
    assert verdict.opacity < 0.5


@pytest.mark.parametrize("gate", [None, False])
def test_unknown_or_false_signal_gate_never_claims_a_quality_verdict(
    gate: bool | None,
) -> None:
    attr = _attribute("lower_is_better", gate)
    assert verdict_for_value(attr, -25.0).verdict == "Not visible"
    rgba = quality_spatial_rgba(attr, 4.0)
    assert rgba is not None
    assert tuple(rgba[0, 0]) == (*MUTED_RGB, 82)


def test_rgba_preserves_raw_sign_mask_statistics_and_inclusive_visibility() -> None:
    attr = _attribute()
    assert attr.spatial is not None
    before = attr.spatial.values.copy()
    mask = attr.spatial.valid_mask.copy()
    rgba = quality_spatial_rgba(attr, 2.0)
    assert rgba is not None
    assert tuple(rgba[0, 0]) == (*SUPERIOR_RGB, 255)
    assert tuple(rgba[0, 1]) == (*INFERIOR_RGB, 255)
    assert tuple(rgba[0, 2]) == (*MUTED_RGB, 82)
    assert tuple(rgba[0, 3]) == (*MUTED_RGB, 82)
    assert tuple(rgba[0, 4]) == (*MUTED_RGB, 82)
    assert rgba[0, 5, 3] == 0  # invalid mask remains transparent
    assert np.array_equal(attr.spatial.values, before, equal_nan=True)
    assert np.array_equal(attr.spatial.valid_mask, mask)


def test_lower_direction_flips_only_color_and_neutral_has_no_winner() -> None:
    base = _attribute()
    high = quality_spatial_rgba(base, 2.0)
    low = quality_spatial_rgba(replace(base, quality_direction="lower_is_better"), 2.0)
    neutral = quality_spatial_rgba(replace(base, quality_direction="none"), 2.0)
    assert high is not None and low is not None and neutral is not None
    assert tuple(low[0, 0, :3]) == INFERIOR_RGB
    assert tuple(low[0, 1, :3]) == SUPERIOR_RGB
    assert tuple(neutral[0, 0]) == (153, 158, 165, 217)


def test_invalid_direction_and_threshold_rejected() -> None:
    with pytest.raises(ValueError, match="quality direction"):
        _attribute("unknown")
    with pytest.raises(ValueError, match="threshold"):
        verdict_for_value(_attribute(), 1.0, threshold=float("nan"))
    with pytest.raises(ValueError, match="threshold"):
        quality_spatial_rgba(_attribute(), 4.0, threshold=-0.1)
