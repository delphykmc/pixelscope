"""Qt-free Tier-1 projections for browsing a published IQA result."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    Comparison,
    ComparisonMode,
    QualityDirection,
    Result,
    ScalarStatistic,
    ValueKind,
)


@dataclass(frozen=True)
class TrendPoint:
    """One Scene comparison for its ordered first/second-source pair."""

    scene_id: str
    source_a_id: str
    source_b_id: str
    raw: ScalarStatistic
    quality: ScalarStatistic


@dataclass(frozen=True)
class RelativeTrendPoint:
    """Target-versus-reference value for one Scene."""

    scene_id: str
    reference_source_id: str
    target_source_id: str
    value: ScalarStatistic


class UnsupportedIqaExplorerResult(ValueError):
    """A valid published result that the two-source P5-B explorer cannot present."""


class IqaExplorerModel:
    """Feature-local projection of published Tier-1 comparisons only."""

    def __init__(self, result: Result) -> None:
        self.result = result
        self._comparisons = _canonical_comparisons(result)

    def trend(self, attribute_id: str, mode: ComparisonMode) -> tuple[TrendPoint, ...]:
        """Return the published A-versus-B comparison in canonical Scene order."""

        spec = self.result.attribute(attribute_id)
        official_mode = _applicable_mode(spec, mode)
        points: list[TrendPoint] = []
        for scene in self.result.scenes:
            comparison = self._comparisons[(scene.scene_id, attribute_id)]
            raw = comparison.official[official_mode]
            points.append(
                TrendPoint(
                    scene.scene_id,
                    comparison.source_a_id,
                    comparison.source_b_id,
                    raw,
                    _quality_value(spec, raw),
                )
            )
        return tuple(points)

    def relative_trend(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_index: int,
    ) -> tuple[RelativeTrendPoint, ...]:
        """Return target-versus-reference values for reference slot A(0) or B(1)."""

        if reference_index not in (0, 1):
            raise ValueError("reference_index must be 0 (A) or 1 (B)")
        relative: list[RelativeTrendPoint] = []
        for point in self.trend(attribute_id, mode):
            if reference_index == 0:
                reference_source_id = point.source_a_id
                target_source_id = point.source_b_id
                value = _negated(point.raw)
            else:
                reference_source_id = point.source_b_id
                target_source_id = point.source_a_id
                value = point.raw
            relative.append(
                RelativeTrendPoint(
                    point.scene_id,
                    reference_source_id,
                    target_source_id,
                    value,
                )
            )
        return tuple(relative)

    def relative_attribute_mean(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_index: int,
    ) -> ScalarStatistic:
        return _mean_statistic(
            tuple(
                point.value
                for point in self.relative_trend(attribute_id, mode, reference_index)
            )
        )

    def outlier_scene_ids(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_index: int = 1,
    ) -> tuple[str, ...]:
        """Return only conservative robust outliers; this is a visual hint, not selection."""

        valid = [
            point
            for point in self.relative_trend(attribute_id, mode, reference_index)
            if point.value.valid
            and point.value.value is not None
            and math.isfinite(point.value.value)
        ]
        if len(valid) < 4:
            return ()
        values = np.asarray([point.value.value for point in valid], dtype=np.float64)
        median = float(np.median(values))
        deviations = np.abs(values - median)
        mad = float(np.median(deviations))
        if mad > 0.0 and math.isfinite(mad):
            modified_z = 0.6744897501960817 * deviations / mad
            flagged = modified_z > 3.5
        else:
            q1, q3 = np.percentile(values, (25.0, 75.0))
            iqr = float(q3 - q1)
            if iqr <= 0.0 or not math.isfinite(iqr):
                return ()
            flagged = (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
        return tuple(
            point.scene_id
            for point, is_flagged in zip(valid, flagged, strict=True)
            if is_flagged
        )

    def display_unit(self, attribute_id: str) -> str:
        spec = self.result.attribute(attribute_id)
        if spec.value_kind is ValueKind.POWER:
            return "dB"
        return spec.unit


def _canonical_comparisons(result: Result) -> dict[tuple[str, str], Comparison]:
    comparisons: dict[tuple[str, str], Comparison] = {}
    for scene in result.scenes:
        if len(scene.sources) < 2:
            raise UnsupportedIqaExplorerResult(
                f"Scene {scene.scene_id} has fewer than two ordered sources"
            )
        source_a_id = scene.sources[0].source_id
        source_b_id = scene.sources[1].source_id
        for attribute in result.attributes:
            match = next(
                (
                    item
                    for item in scene.comparisons
                    if item.attribute_id == attribute.attribute_id
                    and item.source_a_id == source_a_id
                    and item.source_b_id == source_b_id
                ),
                None,
            )
            if match is None:
                raise UnsupportedIqaExplorerResult(
                    f"Scene {scene.scene_id} does not publish the ordered "
                    f"{source_a_id}/{source_b_id} comparison required by P5-B"
                )
            comparisons[(scene.scene_id, attribute.attribute_id)] = match
    return comparisons


def _applicable_mode(spec: AttributeSpec, mode: ComparisonMode) -> ComparisonMode:
    if spec.value_kind is ValueKind.SIGNED:
        return ComparisonMode.SIGNED_DELTA
    if mode not in (
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
    ):
        raise ValueError(f"unsupported power aggregation mode {mode.value}")
    return mode


def _quality_value(spec: AttributeSpec, raw: ScalarStatistic) -> ScalarStatistic:
    if not raw.valid or raw.value is None:
        return raw
    if spec.quality_direction is QualityDirection.NEUTRAL:
        return ScalarStatistic.invalid("neutral_attribute")
    value = raw.value
    if spec.quality_direction is QualityDirection.LOWER_IS_BETTER:
        value = -value
    return ScalarStatistic(value, True)


def _negated(statistic: ScalarStatistic) -> ScalarStatistic:
    if not statistic.valid or statistic.value is None:
        return statistic
    return ScalarStatistic(-statistic.value, True)


def _mean_statistic(statistics: tuple[ScalarStatistic, ...]) -> ScalarStatistic:
    values = [
        statistic.value
        for statistic in statistics
        if statistic.valid
        and statistic.value is not None
        and math.isfinite(statistic.value)
    ]
    if not values:
        return ScalarStatistic.invalid("no_valid_scenes")
    value = float(np.mean(np.asarray(values, dtype=np.float64)))
    if not math.isfinite(value):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(value, True)
