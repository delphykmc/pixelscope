"""Schema-v2 absolute reductions, projection checks, and local comparisons."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import replace

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonMode,
    ComparisonOperator,
    QualityDirection,
    ScalarStatistic,
    ValueKind,
)
from pixelscope.remote.iqa_math import compare_sources
from pixelscope.remote.iqa_v2_domain import MeasurementSummary, RelativeStatisticV2

PROJECTION_ABS_TOLERANCE = 1e-12
PROJECTION_REL_TOLERANCE = 1e-9


def projection_matches(actual: float, expected: float) -> bool:
    if not math.isfinite(actual) or not math.isfinite(expected):
        return False
    tolerance = max(
        PROJECTION_ABS_TOLERANCE,
        PROJECTION_REL_TOLERANCE * max(abs(actual), abs(expected)),
    )
    return abs(actual - expected) <= tolerance


def summary_from_accumulators(
    *,
    weight_sum: float,
    weighted_sum: float,
    weighted_square_sum: float,
    valid_count: int,
    valid: bool,
    value_kind: ValueKind,
) -> MeasurementSummary:
    if not valid:
        if (
            valid_count != 0
            or weight_sum != 0.0
            or weighted_sum != 0.0
            or weighted_square_sum != 0.0
        ):
            raise ValueError("invalid summary must use zero accumulators and count")
        return MeasurementSummary.invalid()
    if valid_count <= 0:
        raise ValueError("valid summary requires positive valid_count")
    if not all(
        math.isfinite(value)
        for value in (weight_sum, weighted_sum, weighted_square_sum)
    ):
        raise ValueError("valid summary accumulators must be finite")
    if weight_sum <= 0.0:
        raise ValueError("valid summary requires positive weight_sum")
    if weighted_square_sum < 0.0:
        raise ValueError("weighted_square_sum must be non-negative")
    if value_kind is ValueKind.POWER and weighted_sum < 0.0:
        raise ValueError("power-domain weighted_sum must be non-negative")
    mean = weighted_sum / weight_sum
    if value_kind is ValueKind.POWER and mean < 0.0:
        raise ValueError("power-domain mean must be non-negative")
    variance = _variance(weight_sum, weighted_sum, weighted_square_sum)
    return MeasurementSummary(
        weight_sum=weight_sum,
        weighted_sum=weighted_sum,
        weighted_square_sum=weighted_square_sum,
        valid_count=valid_count,
        valid=True,
        weighted_mean=mean,
        weighted_std=math.sqrt(variance),
    )


def summary_from_grid(
    data: CompactAttributeData, value_kind: ValueKind
) -> MeasurementSummary:
    weight = np.asarray(data.weight_sum)
    weighted = np.asarray(data.weighted_sum)
    squared = np.asarray(data.weighted_square_sum)
    count = np.asarray(data.valid_count)
    mask = np.asarray(data.valid_mask, dtype=np.bool_)
    if not (
        weight.shape == weighted.shape == squared.shape == count.shape == mask.shape
    ):
        raise ValueError("grid sufficient-statistic shapes must match")
    if not np.any(mask):
        return MeasurementSummary.invalid()
    if (
        np.any(~np.isfinite(weight[mask]))
        or np.any(~np.isfinite(weighted[mask]))
        or np.any(~np.isfinite(squared[mask]))
    ):
        raise ValueError("explicit-valid grid cells must contain finite accumulators")
    if np.any(count[mask] <= 0):
        raise ValueError("explicit-valid grid cells require positive valid_count")
    if np.any(weight[mask] <= 0.0):
        raise ValueError("explicit-valid grid cells require positive weight_sum")
    if np.any(squared[mask] < 0.0):
        raise ValueError(
            "explicit-valid grid cells require non-negative weighted_square_sum"
        )
    if value_kind is ValueKind.POWER and np.any(weighted[mask] < 0.0):
        raise ValueError("power-domain grid weighted_sum must be non-negative")
    cell_means = weighted[mask] / weight[mask]
    cell_second = squared[mask] / weight[mask]
    cell_mean_square = cell_means * cell_means
    if value_kind is ValueKind.POWER and np.any(cell_means < 0.0):
        raise ValueError("power-domain grid mean must be non-negative")
    scale = np.maximum(
        np.maximum(np.abs(cell_second), np.abs(cell_mean_square)),
        float(np.finfo(np.float64).tiny),
    )
    tolerance = 64.0 * float(np.finfo(np.float64).eps) * scale
    if np.any(cell_second - cell_mean_square < -tolerance):
        raise ValueError("grid cell has inconsistent weighted moments")
    selected_weight = [float(value) for value in weight[mask].tolist()]
    selected_weighted = [float(value) for value in weighted[mask].tolist()]
    selected_squared = [float(value) for value in squared[mask].tolist()]
    total_weight = math.fsum(selected_weight)
    total_weighted = math.fsum(selected_weighted)
    total_squared = math.fsum(selected_squared)
    total_count = sum(int(value) for value in count[mask].tolist())
    return summary_from_accumulators(
        weight_sum=total_weight,
        weighted_sum=total_weighted,
        weighted_square_sum=total_squared,
        valid_count=total_count,
        valid=True,
        value_kind=value_kind,
    )


def compare_v2_sources(
    spec: AttributeSpec,
    target: CompactAttributeData,
    reference: CompactAttributeData,
) -> dict[ComparisonMode, RelativeStatisticV2]:
    """Compare target/reference using v2-neutral operators and one quality authority."""
    legacy_operator = (
        ComparisonOperator.SIGNED_A_MINUS_B
        if spec.value_kind is ValueKind.SIGNED
        else ComparisonOperator.POWER_RATIO_A_OVER_B_DB
    )
    computed = compare_sources(
        replace(spec, comparison_operator=legacy_operator), target, reference
    )
    if spec.value_kind is ValueKind.SIGNED:
        raw = computed["raw"]
        return {
            ComparisonMode.SIGNED_DELTA: RelativeStatisticV2(
                raw=raw,
                quality=quality_relative_value(spec, raw),
            )
        }
    raw_by_mode = {
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS: computed["raw"],
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS: computed["grid"],
    }
    return {
        mode: RelativeStatisticV2(
            raw=raw,
            quality=quality_relative_value(spec, raw),
        )
        for mode, raw in raw_by_mode.items()
    }


def quality_relative_value(
    spec: AttributeSpec, raw: ScalarStatistic
) -> ScalarStatistic:
    """Convert raw target/reference orientation to +target-better presentation."""
    if not raw.valid:
        return ScalarStatistic.invalid(raw.invalid_reason or "missing_data")
    if spec.quality_direction is QualityDirection.NEUTRAL:
        return ScalarStatistic.invalid("neutral_attribute")
    if raw.value is None or not math.isfinite(raw.value):
        return ScalarStatistic.invalid("nonfinite_result")
    value = float(raw.value)
    if spec.quality_direction is QualityDirection.LOWER_IS_BETTER:
        value = -value
    if not math.isfinite(value):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(value, True)


def reduce_relative_scene_values(values: Iterable[ScalarStatistic]) -> ScalarStatistic:
    finite = [
        float(item.value)
        for item in values
        if item.valid and item.value is not None and math.isfinite(item.value)
    ]
    if not finite:
        return ScalarStatistic.invalid("no_valid_scenes")
    value = math.fsum(finite) / len(finite)
    if not math.isfinite(value):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(value, True)


def _variance(
    weight_sum: float, weighted_sum: float, weighted_square_sum: float
) -> float:
    mean = weighted_sum / weight_sum
    second_moment = weighted_square_sum / weight_sum
    mean_square = mean * mean
    if not all(math.isfinite(value) for value in (mean, second_moment, mean_square)):
        raise ValueError("non-finite weighted moment")
    variance = second_moment - mean_square
    tolerance = (
        64.0
        * float(np.finfo(np.float64).eps)
        * max(
            abs(second_moment),
            abs(mean_square),
            float(np.finfo(np.float64).tiny),
        )
    )
    if variance < -tolerance:
        raise ValueError("inconsistent weighted moments")
    return max(0.0, variance)