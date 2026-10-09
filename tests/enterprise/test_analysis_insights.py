"""Public-safe, Qt-free UX-2A official Top-3 policy regression."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay
from pixelscope_enterprise.iqa.insights import rank_top_differences


def _attr(identifier: str, value: float, **overrides: object) -> AttributeDisplay:
    baseline = AttributeDisplay(
        attribute_id=identifier,
        label=identifier,
        unit="dB",
        group="Relative",
        official_value=value,
        official_availability="available",
        quality_oriented=True,
        fixed_range=8.0,
        chart_axis_range=8.0,
        summary_signal_gate=True,
    )
    return replace(baseline, **overrides)


def _result(*attributes: AttributeDisplay) -> AnalysisResult:
    return AnalysisResult("synthetic", 3840, 2160, "A", "B", attributes)


def test_top_three_requires_trusted_signal_gate_and_strict_db_threshold() -> None:
    items = (
        _attr("unknown", 100.0, summary_signal_gate=None),
        _attr("rejected", 90.0, summary_signal_gate=False),
        _attr("other-unit", 80.0, unit="delta"),
        _attr("partial", 70.0, official_availability="partial"),
        _attr("unscaled", 60.0, chart_axis_range=None),
        _attr("boundary", 0.3),
        _attr("first", -7.0),
        _attr("second", 7.0),
        _attr("third", -0.30001, quality_oriented=False),
        _attr("fourth", 0.4),
    )
    assert [(x.attribute_id, x.rank) for x in rank_top_differences(_result(*items))] == [
        ("first", 1),
        ("second", 2),
        ("fourth", 3),
    ]
    assert rank_top_differences(_result(*items), count=0) == ()


def test_top_three_never_infers_signal_validity_from_large_official_delta() -> None:
    item = _attr("not-verified", -50.0, summary_signal_gate=None)
    assert rank_top_differences(_result(item)) == ()
    assert rank_top_differences(_result(_attr("valid", -2.0)))[0].delta_db == -2.0


def test_top_three_empty_and_invalid_request() -> None:
    result = _result(_attr("below", 0.05))
    assert rank_top_differences(result) == ()
    with pytest.raises(ValueError, match="nonnegative"):
        rank_top_differences(result, count=-1)


def test_signal_gate_requires_explicit_boolean_or_unknown() -> None:
    with pytest.raises(ValueError, match="summary signal gate"):
        _attr("invalid", 1.0, summary_signal_gate=1)
