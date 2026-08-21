from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonMode,
    ComparisonOperator,
    LoadStatus,
    QualityDirection,
    ValueKind,
)
from pixelscope.remote.iqa_v2_domain import ResultV2, build_measurement_context_id
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_manifest import parse_complete_manifest
from pixelscope.remote.iqa_v2_math import compare_v2_sources
from pixelscope.remote.iqa_v2_reader import load_result_v2


def _power_spec(*, epsilon: float = 0.0) -> AttributeSpec:
    return AttributeSpec(
        attribute_id="test_power",
        name="Test power",
        value_kind=ValueKind.POWER,
        comparison_operator=ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB,
        quality_direction=QualityDirection.HIGHER_IS_BETTER,
        unit="dB",
        stabilization_epsilon=epsilon,
        weighting_provenance="test",
    )


def _compact(means: list[float]) -> CompactAttributeData:
    values = np.asarray(means, dtype=np.float64)
    weight = np.ones(values.shape, dtype=np.float64)
    return CompactAttributeData(
        weight_sum=weight,
        weighted_sum=values,
        weighted_square_sum=values * values,
        valid_count=np.ones(values.shape, dtype=np.int32),
        valid_mask=np.ones(values.shape, dtype=np.bool_),
    )


def test_mode2_averages_only_finite_pair_valid_grid_ratios() -> None:
    result = compare_v2_sources(
        _power_spec(epsilon=0.0),
        _compact([0.0, 2.0]),
        _compact([0.0, 1.0]),
    )

    mode2 = result[ComparisonMode.MEAN_OF_GRID_LOG_RATIOS]
    expected = 10.0 * math.log10(2.0)
    assert mode2.raw.valid
    assert mode2.raw.value == pytest.approx(expected)
    assert mode2.quality.value == pytest.approx(expected)


def test_mode2_is_invalid_when_no_finite_grid_ratio_remains() -> None:
    result = compare_v2_sources(
        _power_spec(epsilon=0.0),
        _compact([0.0]),
        _compact([0.0]),
    )

    mode2 = result[ComparisonMode.MEAN_OF_GRID_LOG_RATIOS]
    assert not mode2.raw.valid
    assert mode2.raw.invalid_reason == "no_finite_grid_ratios"


def test_same_concrete_source_may_bind_multiple_variants_in_one_scene(
    tmp_path: Path,
) -> None:
    root = write_golden_result_v2(tmp_path / "golden-v2")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    result = outcome.result

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    scene = result.scenes[0]
    first = scene.sources[0]
    second = scene.sources[1]
    duplicate_second = replace(second, source=first.source)
    measurements = (first, duplicate_second, *scene.sources[2:])

    first_json = manifest["scenes"][0]["sources"][0]
    second_json = manifest["scenes"][0]["sources"][1]
    for key in ("source_id", "relative_path", "sha256", "width", "height"):
        second_json[key] = first_json[key]
    manifest["scenes"][0]["measurement_context_id"] = build_measurement_context_id(
        scene.scene_id,
        measurements,
        result.attributes,
        scene.context_provenance,
    )

    parsed = parse_complete_manifest(root, manifest)
    parsed_scene = parsed.scenes[0]
    assert parsed_scene.sources[0].source.source_id == parsed_scene.sources[1].source.source_id

    same_data = _compact([1.0, 2.0])
    comparison = compare_v2_sources(_power_spec(), same_data, same_data)
    for statistic in comparison.values():
        assert statistic.raw.valid
        assert statistic.raw.value == pytest.approx(0.0)
