"""Deterministic, PUBLIC-SAFE first-insight ranking for verified official dB data.

This module ranks only already-validated adapter output; it does not infer
original signal levels from an IQA relative score or a spatial map.
"""

from __future__ import annotations

from dataclasses import dataclass

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult

_MIN_MEANINGFUL_DB = 0.3


@dataclass(frozen=True)
class TopDifference:
    """One official full-pair difference eligible for the first-insight cards."""

    rank: int
    attribute_id: str
    label: str
    delta_db: float
    quality_oriented: bool


def rank_top_differences(result: AnalysisResult, *, count: int = 3) -> tuple[TopDifference, ...]:
    """Select comparable verified dB differences, largest magnitude first.

    Signal gate True means a trusted upstream adapter verified that at least
    one of A/B's original-relative signals exceeds -50 dB. None = UNKNOWN,
    False = invalid; neither can enter a conclusive Top 3. No rank across
    different units, no map-derived global score, no quality-direction guess.
    The 0.3 dB threshold is strict, and ties preserve supplied source order.
    """

    if count < 0:
        raise ValueError("count must be nonnegative")
    candidates = [
        attr
        for attr in result.attributes
        if attr.unit == "dB"
        and attr.summary_signal_gate is True
        and attr.official_availability == "available"
        and attr.official_value is not None
        and attr.chart_axis_range is not None
        and abs(attr.official_value) > _MIN_MEANINGFUL_DB
    ]
    candidates.sort(key=lambda attr: -abs(float(attr.official_value or 0.0)))
    return tuple(
        TopDifference(
            rank=index + 1,
            attribute_id=attr.attribute_id,
            label=attr.label,
            delta_db=float(attr.official_value or 0.0),
            quality_oriented=attr.quality_oriented,
        )
        for index, attr in enumerate(candidates[:count])
    )
