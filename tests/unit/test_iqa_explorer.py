from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.remote.iqa_domain import ComparisonMode, LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_fixture import write_golden_result
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2


def _v2_model(tmp_path: Path) -> IqaExplorerModel:
    outcome = load_result(write_golden_result_v2(tmp_path / "v2", scene_count=4))
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is not None
    return IqaExplorerModel(outcome.result)


def test_v2_explorer_opens_summary_first_and_exposes_nway_absolute_values(tmp_path: Path) -> None:
    model = _v2_model(tmp_path)

    assert model.is_v2
    assert [item.variant_id for item in model.variants] == [
        "baseline",
        "candidate_fast",
        "candidate_quality",
    ]
    assert not model.relative_ready

    dataset = model.absolute_dataset_stat("baseline", "luma_noise")
    scene = model.absolute_scene_stat("scene_000000", "baseline", "luma_noise")

    assert dataset.valid and dataset.value is not None
    assert scene.valid and scene.value is not None
    assert model.display_unit("luma_noise", relative=False) == "linear-power"


def test_v2_relative_preparation_loads_scene_grids_only_when_requested(tmp_path: Path) -> None:
    model = _v2_model(tmp_path)

    with pytest.raises(RuntimeError, match="relative grids are not loaded"):
        model.relative_trend(
            "luma_noise",
            ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
            "baseline",
            "candidate_fast",
        )

    relative = model.prepare_relative()

    assert relative.relative_ready
    points = relative.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        "baseline",
        "candidate_fast",
    )
    assert len(points) == 4
    assert all(point.reference_variant_id == "baseline" for point in points)
    assert all(point.target_variant_id == "candidate_fast" for point in points)
    assert all(point.raw.valid for point in points)
    assert all(point.quality.valid for point in points)


def test_v2_relative_dataset_value_is_equal_scene_reduction(tmp_path: Path) -> None:
    model = _v2_model(tmp_path).prepare_relative()
    points = model.relative_trend(
        "luma_detail",
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
        "baseline",
        "candidate_quality",
    )
    overview = model.relative_dataset_stat(
        "luma_detail",
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
        "baseline",
        "candidate_quality",
    )

    valid = [point.raw.value for point in points if point.raw.valid and point.raw.value is not None]
    assert overview.valid and overview.value is not None
    assert overview.value == pytest.approx(sum(valid) / len(valid))
    assert model.display_unit("luma_detail", relative=True) == "dB"


def test_v2_reference_reversal_uses_canonical_target_reference_math(tmp_path: Path) -> None:
    model = _v2_model(tmp_path).prepare_relative()
    forward = model.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        "baseline",
        "candidate_fast",
    )
    reverse = model.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        "candidate_fast",
        "baseline",
    )

    for left, right in zip(forward, reverse, strict=True):
        assert left.raw.valid and right.raw.valid
        assert left.raw.value == pytest.approx(-right.raw.value)
        assert left.quality.value == pytest.approx(-right.quality.value)


def test_v2_source_cards_preserve_variant_identity_separately_from_source_identity(
    tmp_path: Path,
) -> None:
    model = _v2_model(tmp_path)
    rows = model.scene_sources("scene_000000")

    assert [row[0] for row in rows] == [
        "baseline",
        "candidate_fast",
        "candidate_quality",
    ]
    assert all(row[2].source_id for row in rows)
    assert all(row[0] != row[2].source_id for row in rows)


def test_v1_remains_explicit_two_source_read_only_compatibility(tmp_path: Path) -> None:
    outcome = load_result(write_golden_result(tmp_path / "v1"))
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is not None
    model = IqaExplorerModel(outcome.result)

    assert not model.is_v2
    assert [item.variant_id for item in model.variants] == ["A", "B"]
    assert model.relative_ready
    assert not model.absolute_dataset_stat("A", "luma_noise").valid

    points = model.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        "A",
        "B",
    )
    assert points
    assert all(point.reference_variant_id == "A" for point in points)
