from __future__ import annotations

import json
import math
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import (
    CompactAttributeData,
    ComparisonMode,
    LoadStatus,
    QualityDirection,
    ValueKind,
)
from pixelscope.remote.iqa_fixture import ATTRIBUTE_ROWS, write_golden_result
from pixelscope.remote.iqa_geometry import (
    analysis_cell_polygon,
    analysis_to_source,
    source_cell_polygon,
    source_to_analysis,
)
from pixelscope.remote.iqa_math import compare_sources, pairwise_valid_blocks, recompose_statistics
from pixelscope.remote.iqa_reader import ARRAY_LIMIT, SCENE_LIMIT, load_compact_scene, load_result


@pytest.fixture()
def golden_root(tmp_path: Path) -> Path:
    return write_golden_result(tmp_path / "golden")


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")


def _loaded(root: Path):  # type annotation would obscure assertion narrowing
    outcome = load_result(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert outcome.result is not None
    return outcome.result


def _source_data(data: CompactAttributeData, source_index: int) -> CompactAttributeData:
    return CompactAttributeData(
        np.asarray(data.weight_sum)[source_index],
        np.asarray(data.weighted_sum)[source_index],
        np.asarray(data.weighted_square_sum)[source_index],
        np.asarray(data.valid_count)[source_index],
        np.asarray(data.valid_mask)[source_index],
    )


def _npz_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())


def _with_current_compact_size(result, scene_index: int, path: Path):
    scenes = list(result.scenes)
    scenes[scene_index] = replace(scenes[scene_index], compact_uncompressed_size=_npz_size(path))
    return replace(result, scenes=tuple(scenes))


def test_production_shaped_fixture_round_trip_and_structure(golden_root: Path) -> None:
    result = _loaded(golden_root)
    assert result.result_id == "golden-p5a-v1"
    assert len(result.scenes) == 11
    assert len(result.attributes) == 10
    assert [item.attribute_id for item in result.attributes] == [row[0] for row in ATTRIBUTE_ROWS]
    assert all(len(scene.sources) == 2 for scene in result.scenes[:-1])
    assert len(result.scenes[-1].sources) == 3
    assert len(result.scenes[-1].comparisons) == 20
    assert result.scenes[0].detail_artifacts
    assert all(not scene.detail_artifacts for scene in result.scenes[1:])
    assert result.scenes[3].grids["luma_noise"].block_width == 40.0
    assert result.scenes[8].grids["luma_contrast"].block_width == 96.0
    compact = load_compact_scene(result, "scene_000000")
    assert compact.status is LoadStatus.SUCCESS
    assert compact.data is not None
    assert set(compact.data.attributes) == {item.attribute_id for item in result.attributes}


def test_recomposition_matches_tier1_authority_and_modes_differ(golden_root: Path) -> None:
    result = _loaded(golden_root)
    scene = result.scene("scene_000007")
    loaded = load_compact_scene(result, scene.scene_id)
    assert loaded.data is not None
    compact = loaded.data.attributes["luma_detail"]
    computed = compare_sources(
        result.attribute("luma_detail"), _source_data(compact, 0), _source_data(compact, 1)
    )
    official = next(item for item in scene.comparisons if item.attribute_id == "luma_detail")
    ratio = official.official[ComparisonMode.RATIO_OF_WEIGHTED_MEANS]
    grid = official.official[ComparisonMode.MEAN_OF_GRID_LOG_RATIOS]
    assert ratio.valid and grid.valid
    assert ratio.value == pytest.approx(computed["raw"].value, abs=1e-12)
    assert grid.value == pytest.approx(computed["grid"].value, abs=1e-12)
    assert ratio.value != pytest.approx(grid.value, abs=1e-5)


def test_weighted_mean_std_and_pairwise_intersection(golden_root: Path) -> None:
    result = _loaded(golden_root)
    loaded = load_compact_scene(result, "scene_000004")
    assert loaded.data is not None
    compact = loaded.data.attributes["luma_detail"]
    a = _source_data(compact, 0)
    b = _source_data(compact, 1)
    intersection = pairwise_valid_blocks(a, b)
    assert int(np.count_nonzero(intersection)) == intersection.size - 2
    mean, std = recompose_statistics(a, intersection)
    weights = np.asarray(a.weight_sum)[intersection]
    first = np.asarray(a.weighted_sum)[intersection]
    second = np.asarray(a.weighted_square_sum)[intersection]
    expected_mean = float(np.sum(first) / np.sum(weights))
    expected_std = math.sqrt(max(0.0, float(np.sum(second) / np.sum(weights)) - expected_mean**2))
    assert mean.value == pytest.approx(expected_mean)
    assert std.value == pytest.approx(expected_std)


def test_epsilon_orientation_noise_quality_and_identical_sources(golden_root: Path) -> None:
    result = _loaded(golden_root)
    near_zero = load_compact_scene(result, "scene_000002")
    assert near_zero.data is not None
    compact = near_zero.data.attributes["luma_noise"]
    comparison = compare_sources(
        result.attribute("luma_noise"), _source_data(compact, 0), _source_data(compact, 1)
    )
    assert comparison["raw"].value is not None and comparison["raw"].value < 0.0
    assert comparison["quality"].value == pytest.approx(-comparison["raw"].value)
    identical = load_compact_scene(result, "scene_000000")
    assert identical.data is not None
    compact = identical.data.attributes["colorfulness"]
    same = compare_sources(
        result.attribute("colorfulness"), _source_data(compact, 0), _source_data(compact, 1)
    )
    assert same["raw"].value == pytest.approx(0.0, abs=1e-12)
    assert same["quality"].value == pytest.approx(same["raw"].value)

    invalid_scene = result.scene("scene_000005")
    invalid = next(
        item for item in invalid_scene.comparisons if item.attribute_id == "edge_strength"
    )
    official = invalid.official[ComparisonMode.RATIO_OF_WEIGHTED_MEANS]
    assert (official.value, official.valid, official.invalid_reason) == (
        None,
        False,
        "no_valid_blocks",
    )


def test_signed_bias_preserves_negative_zero_positive(golden_root: Path) -> None:
    result = _loaded(golden_root)
    deltas: list[float] = []
    for scene_id in ("scene_000000", "scene_000001", "scene_000002"):
        loaded = load_compact_scene(result, scene_id)
        assert loaded.data is not None
        compact = loaded.data.attributes["luma_bias"]
        computed = compare_sources(
            result.attribute("luma_bias"), _source_data(compact, 0), _source_data(compact, 1)
        )
        assert computed["raw"].value is not None
        assert not computed["quality"].valid
        deltas.append(computed["raw"].value)
    assert deltas[0] < 0.0
    assert deltas[1] == pytest.approx(0.0, abs=1e-12)
    assert deltas[2] > 0.0


def test_zero_weight_no_valid_and_nonfinite_are_explicit_invalid() -> None:
    shape = (2, 2)
    zeros = np.zeros(shape, dtype=np.float64)
    counts = np.ones(shape, dtype=np.int32)
    masks = np.ones(shape, dtype=np.bool_)
    data = CompactAttributeData(zeros, zeros, zeros, counts, masks)
    mean, std = recompose_statistics(data)
    assert (mean.value, mean.valid, mean.invalid_reason) == (None, False, "zero_weight")
    assert not std.valid
    no_valid = CompactAttributeData(zeros, zeros, zeros, counts, np.zeros(shape, dtype=np.bool_))
    mean, _ = recompose_statistics(no_valid)
    assert mean.invalid_reason == "no_valid_blocks"
    nonfinite = CompactAttributeData(
        np.ones(shape), np.asarray([[np.inf, 1.0], [1.0, 1.0]]), np.ones(shape), counts, masks
    )
    mean, _ = recompose_statistics(nonfinite)
    assert mean.invalid_reason == "nonfinite_input"


def test_noninteger_affine_inverse_cell_and_discarded_border(golden_root: Path) -> None:
    result = _loaded(golden_root)
    scene = result.scene("scene_000003")
    geometry = scene.geometry
    source_points = np.asarray([[0.25, 0.75], [999.5, 699.25]], dtype=np.float64)
    analysis_points = source_to_analysis(geometry, source_points)
    assert np.allclose(analysis_to_source(geometry, analysis_points), source_points)
    grid = scene.grids["luma_noise"]
    analysis_polygon = analysis_cell_polygon(grid, 2, 3)
    source_polygon = source_cell_polygon(geometry, grid, 2, 3, 1000, 700)
    assert np.allclose(source_to_analysis(geometry, source_polygon), analysis_polygon)
    valid_x, valid_y, valid_width, valid_height = geometry.valid_rect
    assert grid.origin_x > valid_x and grid.origin_y > valid_y
    assert grid.origin_x + grid.columns * grid.block_width + grid.discarded_right == pytest.approx(
        valid_x + valid_width
    )
    assert grid.origin_y + grid.rows * grid.block_height + grid.discarded_bottom == pytest.approx(
        valid_y + valid_height
    )


@pytest.mark.parametrize(
    ("field", "value", "status"),
    [
        ("kind", "other", LoadStatus.INVALID),
        ("schema_version", 2, LoadStatus.UNSUPPORTED),
        ("schema_version", 0, LoadStatus.UNSUPPORTED),
        ("publication_state", "writing", LoadStatus.INVALID),
    ],
)
def test_exact_manifest_identity_and_publication(
    golden_root: Path, field: str, value: object, status: LoadStatus
) -> None:
    manifest = _manifest(golden_root)
    manifest[field] = value
    _write_manifest(golden_root, manifest)
    outcome = load_result(golden_root)
    assert outcome.status is status
    assert outcome.result is None


def test_dimension_mismatch_is_explicit_invalid_model(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["scenes"][0]["sources"][1]["width"] += 1
    _write_manifest(golden_root, manifest)
    outcome = load_result(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert outcome.reason is not None and "dimension_mismatch" in outcome.reason


@pytest.mark.parametrize(
    "reference",
    ["../outside.npz", "/outside.npz", "C:\\outside.npz", "\\\\host\\share\\x.npz"],
)
def test_traversal_and_absolute_artifacts_are_rejected(golden_root: Path, reference: str) -> None:
    manifest = _manifest(golden_root)
    manifest["summary_artifact"]["path"] = reference
    _write_manifest(golden_root, manifest)
    assert load_result(golden_root).status is LoadStatus.CORRUPT


def test_nul_artifact_is_rejected_before_path_access(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["summary_artifact"]["path"] = "summary.npz\x00ignored"
    _write_manifest(golden_root, manifest)
    outcome = load_result(golden_root)
    assert outcome.status is LoadStatus.CORRUPT
    assert outcome.reason is not None and "NUL" in outcome.reason


def test_resolved_symlink_or_reparse_escape_is_rejected(
    golden_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.npz"
    outside.write_bytes((golden_root / "summary.npz").read_bytes())
    link = golden_root / "escape.npz"
    link.write_bytes(b"placeholder")
    original_resolve = Path.resolve

    def resolve_like_reparse(path: Path, strict: bool = False) -> Path:
        if path.name == "escape.npz":
            return original_resolve(outside, strict=strict)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_like_reparse)
    manifest = _manifest(golden_root)
    manifest["summary_artifact"]["path"] = "escape.npz"
    _write_manifest(golden_root, manifest)
    assert load_result(golden_root).status is LoadStatus.CORRUPT


def test_missing_and_corrupt_compact_artifact_are_explicit(golden_root: Path) -> None:
    result = _loaded(golden_root)
    compact_path = golden_root / result.scenes[0].compact_artifact
    compact_path.unlink()
    missing = load_compact_scene(result, result.scenes[0].scene_id)
    assert missing.status is LoadStatus.CORRUPT
    compact_path.write_bytes(b"not-a-zip")
    corrupt = load_compact_scene(result, result.scenes[0].scene_id)
    assert corrupt.status is LoadStatus.CORRUPT


def test_object_array_is_rejected_without_pickle(golden_root: Path) -> None:
    result = _loaded(golden_root)
    scene = result.scenes[0]
    path = golden_root / scene.compact_artifact
    with np.load(path, allow_pickle=False) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    arrays["luma_noise__weight_sum"] = np.asarray([object()], dtype=object)
    np.savez(path, **arrays)
    result = _with_current_compact_size(result, 0, path)
    outcome = load_compact_scene(result, scene.scene_id)
    assert outcome.status is LoadStatus.CORRUPT
    assert outcome.reason is not None and "object/pickle" in outcome.reason


@pytest.mark.parametrize(
    "replacement",
    [
        np.zeros((1,), dtype=np.float64),
        np.zeros((2, 3, 4), dtype=np.float32),
        np.zeros((2, 99, 99), dtype=np.float64),
    ],
)
def test_malformed_rank_dtype_and_shape_rejected(
    golden_root: Path, replacement: np.ndarray[Any, Any]
) -> None:
    result = _loaded(golden_root)
    scene = result.scenes[0]
    path = golden_root / scene.compact_artifact
    with np.load(path, allow_pickle=False) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    arrays["luma_noise__weight_sum"] = replacement
    np.savez(path, **arrays)
    result = _with_current_compact_size(result, 0, path)
    outcome = load_compact_scene(result, scene.scene_id)
    assert outcome.status is LoadStatus.CORRUPT
    assert outcome.reason is not None and "dtype/rank/shape" in outcome.reason


def test_declared_and_actual_oversized_artifact_rejected_before_load(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["scenes"][0]["compact_artifact"]["uncompressed_size"] = SCENE_LIMIT + 1
    _write_manifest(golden_root, manifest)
    assert load_result(golden_root).status is LoadStatus.CORRUPT

    # The central directory exposes the actual uncompressed total before NumPy materializes it.
    result = _loaded(write_golden_result(golden_root.parent / "actual"))
    scene = result.scenes[0]
    path = result.root / scene.compact_artifact
    np.savez(path, oversized=np.zeros((SCENE_LIMIT // 8 + 1,), dtype=np.float64))
    outcome = load_compact_scene(result, scene.scene_id)
    assert outcome.status is LoadStatus.CORRUPT
    assert outcome.reason is not None and "uncompressed safety ceiling" in outcome.reason


def test_per_array_safety_limit_constant_is_stricter_than_scene_limit() -> None:
    assert ARRAY_LIMIT == 32 * 1024 * 1024
    assert SCENE_LIMIT == 64 * 1024 * 1024
    assert ARRAY_LIMIT < SCENE_LIMIT


def test_attribute_semantics_are_versioned_metadata(golden_root: Path) -> None:
    result = _loaded(golden_root)
    assert result.attribute("luma_noise").quality_direction is QualityDirection.LOWER_IS_BETTER
    assert result.attribute("luma_noise").value_kind is ValueKind.POWER
    assert result.attribute("luma_noise").stabilization_epsilon == 1e-9
    assert result.attribute("luma_bias").quality_direction is QualityDirection.NEUTRAL
    assert result.attribute("luma_bias").value_kind is ValueKind.SIGNED
