"""Deterministic Remote IQA v1 recomposition in the server's linear domain."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonOperator,
    QualityDirection,
    ScalarStatistic,
    ValueKind,
)

BoolArray = NDArray[np.bool_]
FloatArray = NDArray[np.float64]


def valid_blocks(data: CompactAttributeData) -> BoolArray:
    weight = np.asarray(data.weight_sum)
    weighted = np.asarray(data.weighted_sum)
    squared = np.asarray(data.weighted_square_sum)
    count = np.asarray(data.valid_count)
    mask = np.asarray(data.valid_mask)
    result = (
        mask
        & (count > 0)
        & (weight > 0.0)
        & np.isfinite(weight)
        & np.isfinite(weighted)
        & np.isfinite(squared)
    )
    return np.asarray(result, dtype=np.bool_)


def recompose_statistics(
    data: CompactAttributeData, selected: BoolArray | None = None
) -> tuple[ScalarStatistic, ScalarStatistic]:
    explicit = np.asarray(data.valid_mask, dtype=np.bool_)
    required_finite = (
        np.isfinite(np.asarray(data.weight_sum))
        & np.isfinite(np.asarray(data.weighted_sum))
        & np.isfinite(np.asarray(data.weighted_square_sum))
    )
    if np.any(explicit & ~required_finite):
        invalid = ScalarStatistic.invalid("nonfinite_input")
        return invalid, invalid
    eligible = explicit & (np.asarray(data.valid_count) > 0) & required_finite
    if selected is not None:
        eligible &= selected
    if np.any(eligible) and not np.any(np.asarray(data.weight_sum)[eligible] > 0.0):
        invalid = ScalarStatistic.invalid("zero_weight")
        return invalid, invalid
    mask = valid_blocks(data)
    if selected is not None:
        mask &= selected
    if not np.any(mask):
        invalid = ScalarStatistic.invalid("no_valid_blocks")
        return invalid, invalid
    moment_reason = _cell_moment_invalid_reason(data, mask)
    if moment_reason is not None:
        invalid = ScalarStatistic.invalid(moment_reason)
        return invalid, invalid
    with np.errstate(over="ignore", invalid="ignore"):
        weight = float(np.sum(np.asarray(data.weight_sum)[mask], dtype=np.float64))
        weighted_sum = float(np.sum(np.asarray(data.weighted_sum)[mask], dtype=np.float64))
        square_sum = float(np.sum(np.asarray(data.weighted_square_sum)[mask], dtype=np.float64))
    if not all(math.isfinite(value) for value in (weight, weighted_sum, square_sum)):
        invalid = ScalarStatistic.invalid("nonfinite_input")
        return invalid, invalid
    if weight <= 0.0:
        invalid = ScalarStatistic.invalid("zero_weight")
        return invalid, invalid
    mean = weighted_sum / weight
    second_moment = square_sum / weight
    mean_square = mean * mean
    if not all(math.isfinite(value) for value in (mean, second_moment, mean_square)):
        invalid = ScalarStatistic.invalid("nonfinite_input")
        return invalid, invalid
    variance = second_moment - mean_square
    roundoff_tolerance = (
        64.0
        * float(np.finfo(np.float64).eps)
        * max(abs(second_moment), abs(mean_square), float(np.finfo(np.float64).tiny))
    )
    if variance < -roundoff_tolerance:
        invalid = ScalarStatistic.invalid("inconsistent_moments")
        return invalid, invalid
    variance = max(0.0, variance)
    return ScalarStatistic(mean, True), ScalarStatistic(math.sqrt(variance), True)


def _cell_moment_invalid_reason(data: CompactAttributeData, mask: BoolArray) -> str | None:
    weights = np.asarray(data.weight_sum)[mask]
    first = np.asarray(data.weighted_sum)[mask]
    second = np.asarray(data.weighted_square_sum)[mask]
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        means = first / weights
        second_moments = second / weights
        mean_squares = means * means
        variances = second_moments - mean_squares
    if not (
        np.all(np.isfinite(means))
        and np.all(np.isfinite(second_moments))
        and np.all(np.isfinite(mean_squares))
    ):
        return "nonfinite_input"
    scale = np.maximum(
        np.maximum(np.abs(second_moments), np.abs(mean_squares)),
        float(np.finfo(np.float64).tiny),
    )
    tolerance = 64.0 * float(np.finfo(np.float64).eps) * scale
    return "inconsistent_moments" if np.any(variances < -tolerance) else None


def pairwise_valid_blocks(a: CompactAttributeData, b: CompactAttributeData) -> BoolArray:
    a_shape = np.asarray(a.valid_mask).shape
    if a_shape != np.asarray(b.valid_mask).shape:
        raise ValueError("shape_mismatch")
    return valid_blocks(a) & valid_blocks(b)


def compare_sources(
    spec: AttributeSpec,
    a: CompactAttributeData,
    b: CompactAttributeData,
) -> dict[str, ScalarStatistic]:
    try:
        pair_mask = pairwise_valid_blocks(a, b)
    except ValueError:
        invalid = ScalarStatistic.invalid("shape_mismatch")
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    if not np.any(pair_mask):
        invalid = ScalarStatistic.invalid("no_valid_blocks")
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    mean_a, _ = recompose_statistics(a, pair_mask)
    mean_b, _ = recompose_statistics(b, pair_mask)
    if not mean_a.valid or not mean_b.valid:
        reason = mean_a.invalid_reason or mean_b.invalid_reason or "missing_data"
        invalid = ScalarStatistic.invalid(reason)
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    assert mean_a.value is not None and mean_b.value is not None
    if spec.value_kind is ValueKind.SIGNED:
        if spec.comparison_operator is not ComparisonOperator.SIGNED_A_MINUS_B:
            invalid = ScalarStatistic.invalid("unsupported_operator")
            return {"raw": invalid, "quality": invalid, "grid": invalid}
        raw_value = mean_a.value - mean_b.value
        if not math.isfinite(raw_value):
            invalid = ScalarStatistic.invalid("nonfinite_result")
            return {"raw": invalid, "quality": invalid, "grid": invalid}
        raw = ScalarStatistic(raw_value, True)
        return {"raw": raw, "quality": ScalarStatistic.invalid("neutral_attribute"), "grid": raw}
    if spec.comparison_operator is not ComparisonOperator.POWER_RATIO_A_OVER_B_DB:
        invalid = ScalarStatistic.invalid("unsupported_operator")
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    epsilon = spec.stabilization_epsilon
    if epsilon is None or not math.isfinite(epsilon) or epsilon < 0.0:
        invalid = ScalarStatistic.invalid("missing_data")
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    aggregate = _power_log_ratio(mean_a.value, mean_b.value, epsilon)
    if not aggregate.valid:
        return {"raw": aggregate, "quality": aggregate, "grid": aggregate}
    assert aggregate.value is not None
    raw_value = aggregate.value
    raw = ScalarStatistic(raw_value, True)
    if spec.quality_direction is QualityDirection.NEUTRAL:
        quality = ScalarStatistic.invalid("neutral_attribute")
    else:
        quality_value = raw_value
        if spec.quality_direction is QualityDirection.LOWER_IS_BETTER:
            quality_value = -raw_value
        quality = ScalarStatistic(quality_value, True)
    a_cell_means = np.asarray(a.weighted_sum)[pair_mask] / np.asarray(a.weight_sum)[pair_mask]
    b_cell_means = np.asarray(b.weighted_sum)[pair_mask] / np.asarray(b.weight_sum)[pair_mask]
    per_cell_values: list[float] = []
    for a_value, b_value in zip(a_cell_means.tolist(), b_cell_means.tolist(), strict=True):
        cell = _power_log_ratio(float(a_value), float(b_value), epsilon)
        if not cell.valid:
            return {"raw": raw, "quality": quality, "grid": cell}
        assert cell.value is not None
        per_cell_values.append(cell.value)
    grid_value = float(np.mean(np.asarray(per_cell_values, dtype=np.float64)))
    grid = (
        ScalarStatistic(grid_value, True)
        if math.isfinite(grid_value)
        else ScalarStatistic.invalid("nonfinite_result")
    )
    return {"raw": raw, "quality": quality, "grid": grid}


def _power_log_ratio(a_value: float, b_value: float, epsilon: float) -> ScalarStatistic:
    if not all(math.isfinite(value) for value in (a_value, b_value, epsilon)):
        return ScalarStatistic.invalid("nonfinite_input")
    if a_value < 0.0 or b_value < 0.0:
        return ScalarStatistic.invalid("negative_power")
    numerator = a_value + epsilon
    denominator = b_value + epsilon
    if numerator == 0.0 and denominator == 0.0:
        return ScalarStatistic.invalid("undefined_ratio")
    if numerator <= 0.0 or denominator <= 0.0:
        return ScalarStatistic.invalid("nonfinite_result")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        ratio = float(np.float64(numerator) / np.float64(denominator))
    if not math.isfinite(ratio) or ratio <= 0.0:
        return ScalarStatistic.invalid("nonfinite_result")
    result = 10.0 * math.log10(ratio)
    if not math.isfinite(result):
        return ScalarStatistic.invalid("nonfinite_result")
    return ScalarStatistic(result, True)
