"""Quality presentation is optional, signed, and scientifically non-mutating."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
    roi_statistics,
)
from pixelscope_enterprise.iqa.insights import rank_top_differences
from pixelscope_enterprise.iqa.quality_presentation import (
    INFERIOR_RGB,
    MUTED_RGB,
    NEUTRAL_RGB,
    REFERENCE_TINT_MAX_ALPHA,
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


@pytest.mark.parametrize("value", [0.49999, -0.49999, 0.0])
def test_below_threshold_or_exact_zero_is_muted(value: float) -> None:
    verdict = verdict_for_value(_attribute(), value)
    assert verdict.verdict == "Not visible"
    assert verdict.tone == "muted"
    assert verdict.opacity < 0.5


@pytest.mark.parametrize("value", [0.5, -0.5])
def test_exact_visibility_threshold_is_included(value: float) -> None:
    verdict = verdict_for_value(_attribute(), value)
    assert verdict.visible
    assert verdict.tone in ("superior", "inferior")
    rgba = quality_spatial_rgba(_attribute(), 2.0)
    assert rgba is not None
    assert rgba[0, 2, 3] == rgba[0, 3, 3] == 255


def test_non_db_whole_image_color_does_not_need_original_signal_gate() -> None:
    attr = replace(_attribute(), unit="color", summary_signal_gate=None)
    assert verdict_for_value(attr, -2.0).verdict == "Inferior"
    rgba = quality_spatial_rgba(attr, 2.0)
    assert rgba is not None
    assert tuple(rgba[0, 0]) == (*SUPERIOR_RGB, 255)
    assert tuple(rgba[0, 1]) == (*INFERIOR_RGB, 255)
    assert tuple(rgba[0, 4]) == (*MUTED_RGB, 82)


def test_enterprise_quality_verdict_palette_is_shared() -> None:
    assert SUPERIOR_RGB == (58, 111, 216)  # #3a6fd8
    assert INFERIOR_RGB == (192, 57, 43)  # #c0392b


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
    assert rgba[0, 2, 3] == rgba[0, 3, 3] == 255  # inclusive at ±0.5
    assert tuple(rgba[0, 2, :3]) != MUTED_RGB
    assert tuple(rgba[0, 3, :3]) != MUTED_RGB
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
    assert tuple(neutral[0, 0]) == (*NEUTRAL_RGB, 217)
    assert tuple(neutral[0, 1]) == (*NEUTRAL_RGB, 217)
    assert NEUTRAL_RGB == (94, 94, 94)  # same visible neutral as request 4
    assert all(a < b for a, b in zip(NEUTRAL_RGB, MUTED_RGB, strict=True))


def test_top3_combines_request3_direction_exclusion_with_muted_gate() -> None:
    base = _attribute()
    items = (
        replace(base, attribute_id="neutral", official_value=200.0, quality_direction="none"),
        replace(base, attribute_id="not-oriented", official_value=30.0, quality_oriented=False),
        replace(base, attribute_id="untrusted", official_value=-2.0, summary_signal_gate=None),
        replace(base, attribute_id="trusted", official_value=1.0),
    )
    result = AnalysisResult("policy-top", 384, 64, "A", "B", items)
    # Legacy uses the existing quality_oriented flag; the new metadata is
    # intentionally consulted only in the opt-in direction-aware policy.
    assert [item.attribute_id for item in rank_top_differences(result)] == [
        "neutral",
        "trusted",
    ]
    assert [item.attribute_id for item in rank_top_differences(result, quality_policy=True)] == [
        "trusted",
    ]


def test_quality_map_reference_underlay_composition_alpha_and_raw_invariants() -> None:
    attr = _attribute()
    assert attr.spatial is not None
    original_values = attr.spatial.values.copy()
    original_mask = attr.spatial.valid_mask.copy()
    original_stats = roi_statistics(attr.spatial, (0, 0, 384, 64))
    quality_only = quality_spatial_rgba(attr, 2.0)
    tint = quality_spatial_rgba(attr, 2.0, translucent=True)
    assert quality_only is not None and tint is not None
    assert np.array_equal(quality_only[..., :3], tint[..., :3])
    assert tint[0, 0, 3] == REFERENCE_TINT_MAX_ALPHA  # +2: blue, visible
    assert tint[0, 1, 3] == REFERENCE_TINT_MAX_ALPHA  # -2: red, visible
    assert tuple(tint[0, 0, :3]) == SUPERIOR_RGB
    assert tuple(tint[0, 1, :3]) == INFERIOR_RGB
    assert tint[0, 2, 3] == tint[0, 3, 3] == 44  # inclusive ±0.5
    assert tuple(tint[0, 2, :3]) != MUTED_RGB
    assert tuple(tint[0, 3, :3]) != MUTED_RGB
    assert tint[0, 4, 3] == 0  # signed zero reveals the photograph
    assert tint[0, 5, 3] == 0  # invalid mask also reveals the photograph
    assert quality_only[0, 2, 3] == 255  # visibility starts at +0.5
    assert quality_only[0, 4, 3] == 82  # exact zero stays a non-difference

    # Source A's dimmed-gray pixel is unaffected by transparent tint. The
    # requested RGBA variant composes without replacing request 1's renderer.
    underlay = np.array((101, 101, 101), dtype=np.float64)
    fraction = tint[0, :, 3:4].astype(np.float64) / 255.0
    composited = np.rint(
        fraction * tint[0, :, :3].astype(np.float64) + (1.0 - fraction) * underlay
    ).astype(np.uint8)
    assert tuple(composited[4]) == (101, 101, 101)
    assert tuple(composited[5]) == (101, 101, 101)
    assert tuple(composited[0]) != (101, 101, 101)
    assert tuple(composited[1]) != (101, 101, 101)
    assert np.array_equal(attr.spatial.values, original_values, equal_nan=True)
    np.testing.assert_array_equal(attr.spatial.valid_mask, original_mask)
    assert roi_statistics(attr.spatial, (0, 0, 384, 64)) == original_stats

    untrusted = replace(attr, summary_signal_gate=None)
    untrusted_tint = quality_spatial_rgba(untrusted, 2.0, translucent=True)
    assert untrusted_tint is not None
    assert tuple(untrusted_tint[0, 0, :3]) == MUTED_RGB
    assert 0 < untrusted_tint[0, 0, 3] <= 82
    assert untrusted_tint[0, 4, 3] == untrusted_tint[0, 5, 3] == 0


def test_invalid_direction_and_threshold_rejected() -> None:
    with pytest.raises(ValueError, match="quality direction"):
        _attribute("unknown")
    with pytest.raises(ValueError, match="threshold"):
        verdict_for_value(_attribute(), 1.0, threshold=float("nan"))
    with pytest.raises(ValueError, match="threshold"):
        quality_spatial_rgba(_attribute(), 4.0, threshold=-0.1)
