"""Schema-v2 absolute reductions, projection checks, and local comparisons."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonMode,
    QualityDirection,
    ScalarStatistic,
    ValueKind,
)
from pixelscope.remote.iqa_math import pairwise_valid_blocks, recompose_statistics
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
    """Compare target/reference using the executable schema-v2 semantics."""
    input_reason = _comparison_input_reason(target) or _comparison_input_reason(
        reference
    )
    if input_reason is not None:
        return _invalid_relative_result(spec.value_kind, input_reason)

    try:
        pair_mask = pairwise_valid_blocks(target, reference)
    except ValueError:
        return _invalid_relative_result(spec.value_kind, "shape_mismatch")
    if not np.any(pair_mask):
        return _invalid_relative_result(spec.value_kind, "no_valid_blocks")

    target_mean, _ = recompose_statistics(target, pair_mask)
    reference_mean, _ = recompose_statistics(reference, pair_mask)
    if not target_mean.valid or not reference_mean.valid:
        reason = (
            target_mean.invalid_reason
            or reference_mean.invalid_reason
            or "missing_data"
        )
        return _invalid_relative_result(spec.value_kind, reason)
    assert target_mean.value is not None and reference_mean.value is not None

    if spec.value_kind is ValueKind.SIGNED:
        raw_value = target_mean.value - reference_mean.value
        raw = (
            ScalarStatistic(raw_value, True)
            if math.isfinite(raw_value)
            else ScalarStatistic.invalid("nonfinite_result")
        )
        return {
            ComparisonMode.SIGNED_DELTA: RelativeStatisticV2(
                raw=raw,
                quality=quality_relative_value(spec, raw),
            )
        }

    epsilon = spec.stabilization_epsilon
    if epsilon is None or not math.isfinite(epsilon) or epsilon < 0.0:
        return _invalid_relative_result(spec.value_kind, "missing_data")

    aggregate_raw = _power_log_ratio(
        target_mean.value,
        reference_mean.value,
        epsilon,
    )
    grid_raw = _mean_finite_grid_log_ratios(
        target,
        reference,
        pair_mask,
        epsilon,
    )
    return {
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS: RelativeStatisticV2(
            raw=aggregate_raw,
            quality=quality_relative_value(spec, aggregate_raw),
        ),
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS: RelativeStatisticV2(
            raw=grid_raw,
            quality=quality_relative_value(spec, grid_raw),
        ),
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


def _comparison_input_reason(data: CompactAttributeData) -> str | None:
    weight = np.asarray(data.weight_sum)
    weighted = np.asarray(data.weighted_sum)
    squared = np.asarray(data.weighted_square_sum)
    count = np.asarray(data.valid_count)
    mask = np.asarray(data.valid_mask, dtype=np.bool_)
    if not (
        weight.shape == weighted.shape == squared.shape == count.shape == mask.shape
    ):
        return "shape_mismatch"
    if (
        np.any(mask & ~np.isfinite(weight))
        or np.any(mask & ~np.isfinite(weighted))
        or np.any(mask & ~np.isfinite(squared))
    ):
        return "nonfinite_input"
    return None


def _mean_finite_grid_log_ratios(
    target: CompactAttributeData,
    reference: CompactAttributeData,
    pair_mask: NDArray[np.bool_],
    epsilon: float,
) -> ScalarStatistic:
    target_weight = np.asarray(target.weight_sum)[pair_mask]
    target_weighted = np.asarray(target.weighted_sum)[pair_mask]
    reference_weight = np.asarray(reference.weight_sum)[pair_mask]
    reference_weighted = np.asarray(reference.weighted_sum)[pair_mask]
    target_means = target_weighted / target_weight
    reference_means = reference_weighted / reference_weight

    finite_values: list[float] = []
    for target_value, reference_value in zip(
        target_means.tolist(), reference_means.tolist(), strict=True
    ):
        cell = _power_log_ratio(
            float(target_value),
            float(reference_value),
            epsilon,
        )
        if cell.valid:
            assert cell.value is not None
            finite_values.append(cell.value)
        elif cell.invalid_reason == "negative_power":
            return cell
        # Undefined 0/0 and non-finite ratios contribute no finite grid dB value.
    if not finite_values:
        return ScalarStatistic.invalid("no_finite_grid_ratios")
    value = math.fsum(finite_values) / len(finite_values)
    if not math.isfinite(value):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(value, True)


def _power_log_ratio(
    target_value: float,
    reference_value: float,
    epsilon: float,
) -> ScalarStatistic:
    if not all(
        math.isfinite(value) for value in (target_value, reference_value, epsilon)
    ):
        return ScalarStatistic.invalid("nonfinite_input")
    if target_value < 0.0 or reference_value < 0.0:
        return ScalarStatistic.invalid("negative_power")
    numerator = target_value + epsilon
    denominator = reference_value + epsilon
    if numerator == 0.0 and denominator == 0.0:
        return ScalarStatistic.invalid("undefined_ratio")
    if numerator <= 0.0 or denominator <= 0.0:
        return ScalarStatistic.invalid("nonfinite_result")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        ratio = float(np.float64(numerator) / np.float64(denominator))
    if not math.isfinite(ratio) or ratio <= 0.0:
        return ScalarStatistic.invalid("nonfinite_result")
    value = 10.0 * math.log10(ratio)
    if not math.isfinite(value):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(value, True)


def _invalid_relative_result(
    value_kind: ValueKind, reason: str
) -> dict[ComparisonMode, RelativeStatisticV2]:
    raw = ScalarStatistic.invalid(reason)
    relative = RelativeStatisticV2(raw=raw, quality=ScalarStatistic.invalid(reason))
    if value_kind is ValueKind.SIGNED:
        return {ComparisonMode.SIGNED_DELTA: relative}
    return {
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS: relative,
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS: relative,
    }


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
