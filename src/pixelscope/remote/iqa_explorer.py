"""Qt-free projections for browsing published Remote IQA results."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy as np

from pixelscope.remote.iqa_domain import (
    Comparison,
    ComparisonMode,
    Result,
    ScalarStatistic,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_v2_domain import GridSceneDataV2, ResultV2
from pixelscope.remote.iqa_v2_math import compare_v2_sources, reduce_relative_scene_values
from pixelscope.remote.iqa_v2_reader import load_grid_scene

ABSOLUTE_REFERENCE_ID = "__absolute__"


@dataclass(frozen=True)
class ExplorerVariant:
    """One stable result-level comparison slot exposed by the workspace."""

    variant_id: str
    label: str


@dataclass(frozen=True)
class RelativeTrendPoint:
    """One target-versus-reference Scene comparison."""

    scene_id: str
    reference_variant_id: str
    target_variant_id: str
    raw: ScalarStatistic
    quality: ScalarStatistic


class UnsupportedIqaExplorerResult(ValueError):
    """A valid published result that the P5-B explorer cannot present."""


class IqaExplorerModel:
    """Feature-local projection over schema-v2 or legacy schema-v1 results."""

    def __init__(
        self,
        result: Result | ResultV2,
        *,
        grids: dict[str, GridSceneDataV2] | None = None,
    ) -> None:
        self.result = result
        self._grids = dict(grids or {})
        self._legacy_comparisons: dict[tuple[str, str], Comparison] = {}
        self._relative_cache: dict[
            tuple[str, ComparisonMode, str, str], tuple[RelativeTrendPoint, ...]
        ] = {}
        self._dataset_cache: dict[
            tuple[str, ComparisonMode, str, str], ScalarStatistic
        ] = {}
        if isinstance(result, ResultV2):
            self._variants = tuple(
                ExplorerVariant(item.variant_id, item.label) for item in result.variants
            )
        else:
            self._variants = (
                ExplorerVariant("A", "A — first source"),
                ExplorerVariant("B", "B — second source"),
            )
            self._legacy_comparisons = _canonical_v1_comparisons(result)

    @property
    def is_v2(self) -> bool:
        return isinstance(self.result, ResultV2)

    @property
    def variants(self) -> tuple[ExplorerVariant, ...]:
        return self._variants

    @property
    def relative_ready(self) -> bool:
        return not self.is_v2 or len(self._grids) == len(self.result.scenes)

    def prepare_relative(self) -> IqaExplorerModel:
        """Load v2 Scene grids sequentially for later target/reference comparisons."""
        if not isinstance(self.result, ResultV2) or self.relative_ready:
            return self
        grids: dict[str, GridSceneDataV2] = dict(self._grids)
        for scene in self.result.scenes:
            outcome = load_grid_scene(self.result, scene.scene_id)
            if not outcome.succeeded or outcome.data is None:
                reason = outcome.reason or "unable to load Scene grid artifact"
                raise ValueError(f"{scene.scene_id}: {reason}")
            grids[scene.scene_id] = outcome.data
        return IqaExplorerModel(self.result, grids=grids)

    def absolute_dataset_stat(self, variant_id: str, attribute_id: str) -> ScalarStatistic:
        """Return the canonical absolute Dataset Overview statistic."""
        if not isinstance(self.result, ResultV2):
            return ScalarStatistic.invalid("legacy_v1_has_no_absolute_measurement")
        summary = self.result.dataset_summary(variant_id, attribute_id).pooled
        return _measurement_mean(summary.valid, summary.weighted_mean)

    def absolute_scene_stat(
        self, scene_id: str, variant_id: str, attribute_id: str
    ) -> ScalarStatistic:
        if not isinstance(self.result, ResultV2):
            return ScalarStatistic.invalid("legacy_v1_has_no_absolute_measurement")
        summary = (
            self.result.scene(scene_id)
            .source_for_variant(variant_id)
            .summary(attribute_id)
        )
        return _measurement_mean(summary.valid, summary.weighted_mean)

    def relative_trend(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_variant_id: str,
        target_variant_id: str,
    ) -> tuple[RelativeTrendPoint, ...]:
        if reference_variant_id == target_variant_id:
            raise ValueError("reference and target variant must differ")
        key = (attribute_id, mode, reference_variant_id, target_variant_id)
        cached = self._relative_cache.get(key)
        if cached is not None:
            return cached
        if isinstance(self.result, ResultV2):
            points = self._v2_relative_trend(
                attribute_id, mode, reference_variant_id, target_variant_id
            )
        else:
            points = self._legacy_relative_trend(
                attribute_id, mode, reference_variant_id, target_variant_id
            )
        self._relative_cache[key] = points
        return points

    def relative_dataset_stat(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_variant_id: str,
        target_variant_id: str,
    ) -> ScalarStatistic:
        """Equal-Scene reduction of valid Scene comparison values."""
        key = (attribute_id, mode, reference_variant_id, target_variant_id)
        cached = self._dataset_cache.get(key)
        if cached is not None:
            return cached
        reduced = reduce_relative_scene_values(
            point.raw
            for point in self.relative_trend(
                attribute_id,
                mode,
                reference_variant_id,
                target_variant_id,
            )
        )
        self._dataset_cache[key] = reduced
        return reduced

    def outlier_scene_ids(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_variant_id: str,
        target_variant_id: str,
    ) -> tuple[str, ...]:
        """Return conservative quality-oriented visual hints, never logical selection."""
        points = self.relative_trend(
            attribute_id, mode, reference_variant_id, target_variant_id
        )
        valid = [
            point
            for point in points
            if point.quality.valid
            and point.quality.value is not None
            and math.isfinite(point.quality.value)
        ]
        if len(valid) < 4:
            return ()
        values = np.asarray([point.quality.value for point in valid], dtype=np.float64)
        median = float(np.median(values))
        deviations = np.abs(values - median)
        mad = float(np.median(deviations))
        if mad > 0.0 and math.isfinite(mad):
            flagged = 0.6744897501960817 * deviations / mad > 3.5
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

    def display_unit(self, attribute_id: str, *, relative: bool) -> str:
        spec = self.result.attribute(attribute_id)
        if relative and spec.value_kind is ValueKind.POWER:
            return "dB"
        return spec.unit

    def scene_sources(self, scene_id: str) -> tuple[tuple[str, str, Source], ...]:
        if isinstance(self.result, ResultV2):
            scene = self.result.scene(scene_id)
            return tuple(
                (
                    measurement.variant_id,
                    self.result.variant(measurement.variant_id).label,
                    measurement.source,
                )
                for measurement in scene.sources
            )
        legacy = cast(Result, self.result)
        scene = legacy.scene(scene_id)
        if len(scene.sources) < 2:
            raise UnsupportedIqaExplorerResult(
                f"Scene {scene.scene_id} has fewer than two ordered sources"
            )
        return (
            ("A", "A — first source", scene.sources[0]),
            ("B", "B — second source", scene.sources[1]),
        )

    def _v2_relative_trend(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_variant_id: str,
        target_variant_id: str,
    ) -> tuple[RelativeTrendPoint, ...]:
        result = cast(ResultV2, self.result)
        if not self.relative_ready:
            raise RuntimeError("relative grids are not loaded")
        spec = result.attribute(attribute_id)
        selected_mode = _applicable_mode(spec.value_kind, mode)
        points: list[RelativeTrendPoint] = []
        for scene in result.scenes:
            grid = self._grids[scene.scene_id]
            target = grid.attribute_for_variant(target_variant_id, attribute_id)
            reference = grid.attribute_for_variant(reference_variant_id, attribute_id)
            relative = compare_v2_sources(spec, target, reference)[selected_mode]
            points.append(
                RelativeTrendPoint(
                    scene.scene_id,
                    reference_variant_id,
                    target_variant_id,
                    relative.raw,
                    relative.quality,
                )
            )
        return tuple(points)

    def _legacy_relative_trend(
        self,
        attribute_id: str,
        mode: ComparisonMode,
        reference_variant_id: str,
        target_variant_id: str,
    ) -> tuple[RelativeTrendPoint, ...]:
        if {reference_variant_id, target_variant_id} != {"A", "B"}:
            raise ValueError("legacy v1 supports only A/B Reference slots")
        legacy = cast(Result, self.result)
        spec = legacy.attribute(attribute_id)
        selected_mode = _applicable_mode(spec.value_kind, mode)
        points: list[RelativeTrendPoint] = []
        for scene in legacy.scenes:
            comparison = self._legacy_comparisons[(scene.scene_id, attribute_id)]
            raw = comparison.official[selected_mode]
            if reference_variant_id == "A":
                raw = _negated(raw)
            quality = _legacy_quality(spec.quality_direction.value, raw)
            points.append(
                RelativeTrendPoint(
                    scene.scene_id,
                    reference_variant_id,
                    target_variant_id,
                    raw,
                    quality,
                )
            )
        return tuple(points)


def _canonical_v1_comparisons(result: Result) -> dict[tuple[str, str], Comparison]:
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
                    f"{source_a_id}/{source_b_id} comparison required by legacy v1"
                )
            comparisons[(scene.scene_id, attribute.attribute_id)] = match
    return comparisons


def _applicable_mode(value_kind: ValueKind, mode: ComparisonMode) -> ComparisonMode:
    if value_kind is ValueKind.SIGNED:
        return ComparisonMode.SIGNED_DELTA
    if mode not in (
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
    ):
        raise ValueError(f"unsupported power aggregation mode {mode.value}")
    return mode


def _measurement_mean(valid: bool, value: float | None) -> ScalarStatistic:
    if not valid or value is None or not math.isfinite(value):
        return ScalarStatistic.invalid("missing_data")
    return ScalarStatistic(float(value), True)


def _negated(statistic: ScalarStatistic) -> ScalarStatistic:
    if not statistic.valid or statistic.value is None:
        return statistic
    return ScalarStatistic(-statistic.value, True)


def _legacy_quality(direction: str, raw: ScalarStatistic) -> ScalarStatistic:
    if not raw.valid or raw.value is None:
        return ScalarStatistic.invalid(raw.invalid_reason or "missing_data")
    if direction == "neutral":
        return ScalarStatistic.invalid("neutral_attribute")
    value = raw.value
    if direction == "lower_is_better":
        value = -value
    return ScalarStatistic(value, True)
