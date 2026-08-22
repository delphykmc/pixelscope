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
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_math import compare_v2_sources, reduce_relative_scene_values
from pixelscope.remote.iqa_v2_reader import load_grid_scene

ABSOLUTE_REFERENCE_ID: None = None


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
        relative_cache: dict[tuple[str, ComparisonMode, str, str], tuple[RelativeTrendPoint, ...]]
        | None = None,
        prepared_references: frozenset[str] | None = None,
    ) -> None:
        self.result = result
        self._legacy_comparisons: dict[tuple[str, str], Comparison] = {}
        self._relative_cache = dict(relative_cache or {})
        self._dataset_cache: dict[tuple[str, ComparisonMode, str, str], ScalarStatistic] = {}
        self._prepared_references = prepared_references or frozenset()
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
    def scene_ids(self) -> tuple[str, ...]:
        """Return schema-independent ordered Scene identities."""
        if isinstance(self.result, ResultV2):
            return tuple(scene.scene_id for scene in self.result.scenes)
        return tuple(scene.scene_id for scene in self.result.scenes)

    @property
    def relative_ready(self) -> bool:
        """Compatibility shorthand: any v2 Reference has been prepared."""
        return not self.is_v2 or bool(self._prepared_references)

    def reference_ready(self, reference_variant_id: str) -> bool:
        if not self.is_v2:
            return reference_variant_id in {"A", "B"}
        return reference_variant_id in self._prepared_references

    def prepare_reference(self, reference_variant_id: str) -> IqaExplorerModel:
        """Compute one Reference lazily while holding at most one Scene grid artifact."""
        if not isinstance(self.result, ResultV2):
            return self
        result = self.result
        variant_ids = {item.variant_id for item in result.variants}
        if reference_variant_id not in variant_ids:
            raise ValueError(f"unknown Reference variant {reference_variant_id}")
        if self.reference_ready(reference_variant_id):
            return self

        rows: dict[tuple[str, ComparisonMode, str, str], list[RelativeTrendPoint]] = {}
        for attribute in result.attributes:
            modes = _modes_for(attribute.value_kind)
            for target_variant_id in variant_ids:
                if target_variant_id == reference_variant_id:
                    continue
                for mode in modes:
                    rows[
                        (
                            attribute.attribute_id,
                            mode,
                            reference_variant_id,
                            target_variant_id,
                        )
                    ] = []

        for scene in result.scenes:
            outcome = load_grid_scene(result, scene.scene_id)
            if not outcome.succeeded or outcome.data is None:
                reason = outcome.reason or "unable to load Scene grid artifact"
                raise ValueError(f"{scene.scene_id}: {reason}")
            grid = outcome.data
            for attribute in result.attributes:
                reference = grid.attribute_for_variant(
                    reference_variant_id,
                    attribute.attribute_id,
                )
                for target in result.variants:
                    if target.variant_id == reference_variant_id:
                        continue
                    target_data = grid.attribute_for_variant(
                        target.variant_id,
                        attribute.attribute_id,
                    )
                    comparisons = compare_v2_sources(
                        attribute,
                        target_data,
                        reference,
                    )
                    for mode, relative in comparisons.items():
                        rows[
                            (
                                attribute.attribute_id,
                                mode,
                                reference_variant_id,
                                target.variant_id,
                            )
                        ].append(
                            RelativeTrendPoint(
                                scene.scene_id,
                                reference_variant_id,
                                target.variant_id,
                                relative.raw,
                                relative.quality,
                            )
                        )
            del grid

        cache = dict(self._relative_cache)
        cache.update({key: tuple(values) for key, values in rows.items()})
        return IqaExplorerModel(
            result,
            relative_cache=cache,
            prepared_references=(self._prepared_references | frozenset({reference_variant_id})),
        )

    def absolute_dataset_stat(self, variant_id: str, attribute_id: str) -> ScalarStatistic:
        """Return the canonical absolute Dataset Overview statistic."""
        if not isinstance(self.result, ResultV2):
            return ScalarStatistic.invalid("legacy_v1_has_no_absolute_measurement")
        summary = self.result.dataset_summary(variant_id, attribute_id).pooled
        return _measurement_mean(summary.valid, summary.weighted_mean)

    def absolute_scene_stat(
        self,
        scene_id: str,
        variant_id: str,
        attribute_id: str,
    ) -> ScalarStatistic:
        if not isinstance(self.result, ResultV2):
            return ScalarStatistic.invalid("legacy_v1_has_no_absolute_measurement")
        summary = self.result.scene(scene_id).source_for_variant(variant_id).summary(attribute_id)
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
        selected_mode = _applicable_mode(
            self.result.attribute(attribute_id).value_kind,
            mode,
        )
        key = (
            attribute_id,
            selected_mode,
            reference_variant_id,
            target_variant_id,
        )
        cached = self._relative_cache.get(key)
        if cached is not None:
            return cached
        if isinstance(self.result, ResultV2):
            if not self.reference_ready(reference_variant_id):
                raise RuntimeError(f"Reference {reference_variant_id} has not been prepared")
            raise KeyError(key)
        points = self._legacy_relative_trend(
            attribute_id,
            selected_mode,
            reference_variant_id,
            target_variant_id,
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
        selected_mode = _applicable_mode(
            self.result.attribute(attribute_id).value_kind,
            mode,
        )
        key = (
            attribute_id,
            selected_mode,
            reference_variant_id,
            target_variant_id,
        )
        cached = self._dataset_cache.get(key)
        if cached is not None:
            return cached
        reduced = reduce_relative_scene_values(
            point.raw
            for point in self.relative_trend(
                attribute_id,
                selected_mode,
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
            attribute_id,
            mode,
            reference_variant_id,
            target_variant_id,
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
        values = np.asarray(
            [point.quality.value for point in valid],
            dtype=np.float64,
        )
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
            point.scene_id for point, is_flagged in zip(valid, flagged, strict=True) if is_flagged
        )

    def display_unit(self, attribute_id: str, *, relative: bool) -> str:
        spec = self.result.attribute(attribute_id)
        if relative and spec.value_kind is ValueKind.POWER:
            return "dB"
        return spec.unit

    def scene_sources(self, scene_id: str) -> tuple[tuple[str, str, Source], ...]:
        if isinstance(self.result, ResultV2):
            v2_scene = self.result.scene(scene_id)
            return tuple(
                (
                    measurement.variant_id,
                    self.result.variant(measurement.variant_id).label,
                    measurement.source,
                )
                for measurement in v2_scene.sources
            )
        legacy = self.result
        legacy_scene = legacy.scene(scene_id)
        if len(legacy_scene.sources) < 2:
            raise UnsupportedIqaExplorerResult(
                f"Scene {legacy_scene.scene_id} has fewer than two ordered sources"
            )
        return (
            ("A", "A — first source", legacy_scene.sources[0]),
            ("B", "B — second source", legacy_scene.sources[1]),
        )

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
        points: list[RelativeTrendPoint] = []
        for scene in legacy.scenes:
            comparison = self._legacy_comparisons[(scene.scene_id, attribute_id)]
            raw = comparison.official[mode]
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


def _modes_for(value_kind: ValueKind) -> tuple[ComparisonMode, ...]:
    if value_kind is ValueKind.SIGNED:
        return (ComparisonMode.SIGNED_DELTA,)
    return (
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
    )


def _applicable_mode(value_kind: ValueKind, mode: ComparisonMode) -> ComparisonMode:
    if value_kind is ValueKind.SIGNED:
        return ComparisonMode.SIGNED_DELTA
    if mode not in _modes_for(value_kind):
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
