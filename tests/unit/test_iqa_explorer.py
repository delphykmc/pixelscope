from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pixelscope.remote.iqa_domain import ComparisonMode, LoadStatus
from pixelscope.remote.iqa_explorer import (
    IqaExplorerModel,
    UnsupportedIqaExplorerResult,
)
from pixelscope.remote.iqa_fixture import write_golden_result
from pixelscope.remote.iqa_reader import load_result


def _model(tmp_path: Path) -> IqaExplorerModel:
    return IqaExplorerModel(_result(tmp_path))


def _result(tmp_path: Path):  # type annotation would obscure assertion narrowing
    outcome = load_result(write_golden_result(tmp_path / "result"))
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is not None
    return outcome.result


def test_explorer_projects_attribute_scene_trends_and_both_official_modes(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path)

    ratio = model.trend("luma_detail", ComparisonMode.RATIO_OF_WEIGHTED_MEANS)
    grid = model.trend("luma_detail", ComparisonMode.MEAN_OF_GRID_LOG_RATIOS)

    assert len(ratio) == len(grid) == 11
    assert [point.scene_id for point in ratio] == [
        scene.scene_id for scene in model.result.scenes
    ]
    assert any(left.raw.value != right.raw.value for left, right in zip(ratio, grid, strict=True))
    assert all(point.source_a_id != point.source_b_id for point in ratio)


def test_explorer_does_not_require_tier2_compact_scenes(tmp_path: Path) -> None:
    result = _result(tmp_path)
    for scene in result.scenes:
        (result.root / scene.compact_artifact).unlink()

    model = IqaExplorerModel(result)
    points = model.relative_trend(
        "luma_detail",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        1,
    )

    assert len(points) == 11
    assert all(point.reference_source_id != point.target_source_id for point in points)


def test_reference_projection_reverses_the_published_orientation(tmp_path: Path) -> None:
    model = _model(tmp_path)
    published = model.trend("luma_noise", ComparisonMode.RATIO_OF_WEIGHTED_MEANS)
    reference_a = model.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        0,
    )
    reference_b = model.relative_trend(
        "luma_noise",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        1,
    )

    for raw, b_vs_a, a_vs_b in zip(published, reference_a, reference_b, strict=True):
        assert a_vs_b.value == raw.raw
        if raw.raw.valid and raw.raw.value is not None:
            assert b_vs_a.value.value == pytest.approx(-raw.raw.value)
            assert a_vs_b.value.value == pytest.approx(raw.raw.value)


def test_signed_reference_projection_is_mode_independent(tmp_path: Path) -> None:
    model = _model(tmp_path)
    ratio = model.relative_trend("luma_bias", ComparisonMode.RATIO_OF_WEIGHTED_MEANS, 1)
    grid = model.relative_trend("luma_bias", ComparisonMode.MEAN_OF_GRID_LOG_RATIOS, 1)

    assert [point.value for point in ratio] == [point.value for point in grid]
    assert model.display_unit("luma_bias") == "normalized-code"


def test_outlier_hint_is_conservative_and_deterministic(tmp_path: Path) -> None:
    model = _model(tmp_path)
    first = model.outlier_scene_ids(
        "luma_detail",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        1,
    )
    second = model.outlier_scene_ids(
        "luma_detail",
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        1,
    )
    valid_count = sum(
        point.value.valid
        for point in model.relative_trend(
            "luma_detail",
            ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
            1,
        )
    )

    assert first == second
    assert len(first) < valid_count
    assert len(first) == len(set(first))
    assert "scene_000007" in first


def test_explorer_selects_ordered_first_second_pair_when_records_are_reordered(
    tmp_path: Path,
) -> None:
    result = _result(tmp_path)
    scene = result.scenes[-1]
    attribute_id = result.attributes[0].attribute_id
    canonical = next(
        item
        for item in scene.comparisons
        if item.attribute_id == attribute_id
        and item.source_a_id == scene.sources[0].source_id
        and item.source_b_id == scene.sources[1].source_id
    )
    other = next(
        item
        for item in scene.comparisons
        if item.attribute_id == attribute_id and item.source_b_id == scene.sources[2].source_id
    )
    reordered = (other, canonical) + tuple(
        item for item in scene.comparisons if item not in (canonical, other)
    )
    model = IqaExplorerModel(replace(result, scenes=(replace(scene, comparisons=reordered),)))

    point = model.trend(attribute_id, ComparisonMode.RATIO_OF_WEIGHTED_MEANS)[0]

    assert (point.source_a_id, point.source_b_id) == (
        scene.sources[0].source_id,
        scene.sources[1].source_id,
    )
    assert point.raw == canonical.official[ComparisonMode.RATIO_OF_WEIGHTED_MEANS]


def test_explorer_rejects_missing_ordered_first_second_pair(tmp_path: Path) -> None:
    result = _result(tmp_path)
    scene = result.scenes[-1]
    attribute_id = result.attributes[0].attribute_id
    comparisons = tuple(
        item
        for item in scene.comparisons
        if not (
            item.attribute_id == attribute_id
            and item.source_a_id == scene.sources[0].source_id
            and item.source_b_id == scene.sources[1].source_id
        )
    )

    with pytest.raises(
        UnsupportedIqaExplorerResult,
        match="ordered .* comparison required by P5-B",
    ):
        IqaExplorerModel(replace(result, scenes=(replace(scene, comparisons=comparisons),)))
