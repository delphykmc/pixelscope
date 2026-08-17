"""Deterministic Remote IQA v1 recomposition in the server's linear domain."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
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
    weight = float(np.sum(np.asarray(data.weight_sum)[mask], dtype=np.float64))
    if weight <= 0.0:
        invalid = ScalarStatistic.invalid("zero_weight")
        return invalid, invalid
    weighted_sum = float(np.sum(np.asarray(data.weighted_sum)[mask], dtype=np.float64))
    square_sum = float(np.sum(np.asarray(data.weighted_square_sum)[mask], dtype=np.float64))
    mean = weighted_sum / weight
    variance = max(0.0, square_sum / weight - mean * mean)
    return ScalarStatistic(mean, True), ScalarStatistic(math.sqrt(variance), True)


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
        raw = ScalarStatistic(mean_a.value - mean_b.value, True)
        return {"raw": raw, "quality": ScalarStatistic.invalid("neutral_attribute"), "grid": raw}
    epsilon = spec.stabilization_epsilon
    if epsilon is None:
        invalid = ScalarStatistic.invalid("missing_data")
        return {"raw": invalid, "quality": invalid, "grid": invalid}
    raw_value = 10.0 * math.log10((mean_a.value + epsilon) / (mean_b.value + epsilon))
    raw = ScalarStatistic(raw_value, True)
    quality_value = raw_value
    if spec.quality_direction is QualityDirection.LOWER_IS_BETTER:
        quality_value = -raw_value
    quality = ScalarStatistic(quality_value, True)
    a_cell_means = np.asarray(a.weighted_sum)[pair_mask] / np.asarray(a.weight_sum)[pair_mask]
    b_cell_means = np.asarray(b.weighted_sum)[pair_mask] / np.asarray(b.weight_sum)[pair_mask]
    per_cell = 10.0 * np.log10((a_cell_means + epsilon) / (b_cell_means + epsilon))
    grid = ScalarStatistic(float(np.mean(per_cell, dtype=np.float64)), True)
    return {"raw": raw, "quality": quality, "grid": grid}
