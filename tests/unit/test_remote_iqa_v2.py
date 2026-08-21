from __future__ import annotations

import io
import json
import math
import struct
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonMode,
    ComparisonOperator,
    GridGeometry,
    LoadStatus,
    QualityDirection,
    ScalarStatistic,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_fixture import write_golden_result
from pixelscope.remote.iqa_result_reader import load_result as load_versioned_result
from pixelscope.remote.iqa_v2_domain import (
    MeasurementContextProvenance,
    ResultV2,
    SourceMeasurementV2,
    build_measurement_context_id,
)
from pixelscope.remote.iqa_v2_fixture import (
    V2_ATTRIBUTE_ROWS,
    V2_VARIANTS,
    write_golden_result_v2,
)
from pixelscope.remote.iqa_v2_manifest import parse_complete_manifest
from pixelscope.remote.iqa_v2_math import (
    compare_v2_sources,
    projection_matches,
    reduce_relative_scene_values,
    summary_from_grid,
)
from pixelscope.remote.iqa_v2_reader import load_grid_scene, load_result_v2
from pixelscope.remote.iqa_v2_support import (
    CorruptV2,
    InvalidV2,
    load_npz,
    validate_artifact_reference,
)

ArrayMap = dict[str, np.ndarray[Any, Any]]


@pytest.fixture()
def golden_root(tmp_path: Path) -> Path:
    return write_golden_result_v2(tmp_path / "golden-v2")


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(
        json.dumps(manifest, allow_nan=False), encoding="utf-8"
    )


def _npz_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())


def _rewrite_npz(path: Path, mutate: Callable[[ArrayMap], None]) -> None:
    with np.load(path, allow_pickle=False) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    mutate(arrays)
    np.savez(path, **arrays)


def _loaded(root: Path) -> ResultV2:
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


def _spec(
    *,
    kind: ValueKind = ValueKind.POWER,
    direction: QualityDirection = QualityDirection.HIGHER_IS_BETTER,
    epsilon: float | None = 0.0,
) -> AttributeSpec:
    operator = (
        ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB
        if kind is ValueKind.POWER
        else ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE
    )
    return AttributeSpec(
        "test",
        "Test",
        kind,
        operator,
        direction,
        "unit",
        epsilon,
        "test-weighting",
    )


def _compact(
    means: list[float],
    *,
    weights: list[float] | None = None,
    valid: list[bool] | None = None,
) -> CompactAttributeData:
    weight = np.asarray(weights or [1.0] * len(means), dtype=np.float64)
    values = np.asarray(means, dtype=np.float64)
    mask = np.asarray(valid or [True] * len(means), dtype=np.bool_)
    return CompactAttributeData(
        weight,
        weight * values,
        weight * values * values,
        np.ones(len(means), dtype=np.int32),
        mask,
    )


def _stat(value: float) -> ScalarStatistic:
    return ScalarStatistic(value, True)


def test_v2_fixture_round_trip_freezes_n_way_identity_and_operator_names(
    golden_root: Path,
) -> None:
    result = _loaded(golden_root)
    assert result.result_id == "golden-p5a2-v2"
    assert [item.variant_id for item in result.variants] == [
        row[0] for row in V2_VARIANTS
    ]
    assert [item.label for item in result.variants] == [row[1] for row in V2_VARIANTS]
    assert [item.attribute_id for item in result.attributes] == [
        row[0] for row in V2_ATTRIBUTE_ROWS
    ]
    assert len(result.scenes) == 4
    assert all(len(scene.sources) == 3 for scene in result.scenes)
    assert all(
        attribute.comparison_operator
        is ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB
        for attribute in result.attributes
        if attribute.value_kind is ValueKind.POWER
    )
    assert all(
        attribute.comparison_operator
        is ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE
        for attribute in result.attributes
        if attribute.value_kind is ValueKind.SIGNED
    )


def test_context_fingerprint_is_deterministic_golden(golden_root: Path) -> None:
    result = _loaded(golden_root)
    scene = result.scene("scene_000000")
    assert scene.measurement_context_id == (
        "mc2:83e0933c0ff0f28c4ebbef7f2c7477563bb60e4313f68ac3d6e367304c212a99"
    )
    assert scene.measurement_context_id == build_measurement_context_id(
        scene.scene_id,
        scene.sources,
        result.attributes,
        scene.context_provenance,
    )


def test_summary_first_open_does_not_require_scene_or_detail_files(
    golden_root: Path,
) -> None:
    manifest = _manifest(golden_root)
    scene_path = golden_root / manifest["scenes"][0]["grid_artifact"]["path"]
    detail_path = golden_root / manifest["scenes"][0]["detail_artifacts"][0]
    scene_path.unlink()
    detail_path.unlink()

    result = _loaded(golden_root)
    grid = load_grid_scene(result, "scene_000000")
    assert grid.status is LoadStatus.CORRUPT
    assert grid.data is None


def test_grid_load_preserves_n_way_variant_source_identity(golden_root: Path) -> None:
    result = _loaded(golden_root)
    outcome = load_grid_scene(result, "scene_000000")
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert outcome.data is not None
    assert outcome.data.variant_ids == tuple(row[0] for row in V2_VARIANTS)
    scene = result.scene("scene_000000")
    expected_sources = tuple(item.source.source_id for item in scene.sources)
    assert outcome.data.source_ids == expected_sources
    baseline = outcome.data.attribute_for_variant("baseline", "luma_noise")
    quality = outcome.data.attribute_for_variant("candidate_quality", "luma_noise")
    assert np.asarray(baseline.valid_mask).shape == np.asarray(quality.valid_mask).shape


def test_scene_recomposition_is_sum_s1_over_sum_w_not_equal_grid_mean() -> None:
    data = _compact([1.0, 3.0], weights=[1.0, 3.0])
    summary = summary_from_grid(data, ValueKind.POWER)
    assert summary.weight_sum == pytest.approx(4.0)
    assert summary.weighted_sum == pytest.approx(10.0)
    assert summary.weighted_square_sum == pytest.approx(28.0)
    assert summary.weighted_mean == pytest.approx(2.5)
    assert summary.weighted_mean != pytest.approx(2.0)
    assert summary.weighted_std == pytest.approx(math.sqrt(0.75))


def test_fixture_dataset_pooled_and_equal_scene_means_are_distinct(
    golden_root: Path,
) -> None:
    result = _loaded(golden_root)
    summary = result.dataset_summary("baseline", "luma_noise")
    assert summary.pooled.valid
    assert summary.pooled.weighted_mean is not None
    assert summary.scene_mean.valid
    assert summary.scene_mean.value is not None
    scene_summaries = [
        scene.source_for_variant("baseline").summary("luma_noise")
        for scene in result.scenes
    ]
    expected_pooled = math.fsum(
        item.weighted_sum for item in scene_summaries
    ) / math.fsum(item.weight_sum for item in scene_summaries)
    expected_equal = math.fsum(
        float(item.weighted_mean)
        for item in scene_summaries
        if item.weighted_mean is not None
    ) / len(scene_summaries)
    assert summary.pooled.weighted_mean == pytest.approx(expected_pooled)
    assert summary.scene_mean.value == pytest.approx(expected_equal)
    assert not math.isclose(
        expected_pooled,
        expected_equal,
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def test_power_modes_diverge_and_quality_direction_is_centralized() -> None:
    target = _compact([1.0, 9.0], weights=[9.0, 1.0])
    reference = _compact([1.0, 1.0])
    spec = _spec(direction=QualityDirection.LOWER_IS_BETTER)

    result = compare_v2_sources(spec, target, reference)
    aggregate = result[ComparisonMode.RATIO_OF_WEIGHTED_MEANS]
    grid = result[ComparisonMode.MEAN_OF_GRID_LOG_RATIOS]
    assert aggregate.raw.value == pytest.approx(2.5527250510330606)
    assert grid.raw.value == pytest.approx(4.771212547196624)
    assert aggregate.quality.value == pytest.approx(-2.5527250510330606)
    assert grid.quality.value == pytest.approx(-4.771212547196624)

    reverse = compare_v2_sources(spec, reference, target)
    for mode in (
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
    ):
        assert reverse[mode].raw.value == pytest.approx(-result[mode].raw.value)
        assert reverse[mode].quality.value == pytest.approx(-result[mode].quality.value)


def test_higher_is_better_quality_matches_raw_for_both_power_modes() -> None:
    result = compare_v2_sources(
        _spec(direction=QualityDirection.HIGHER_IS_BETTER),
        _compact([2.0, 4.0]),
        _compact([1.0, 1.0]),
    )
    for statistic in result.values():
        assert statistic.raw.valid and statistic.quality.valid
        assert statistic.quality.value == pytest.approx(statistic.raw.value)


def test_signed_delta_is_target_minus_reference_and_quality_is_not_applicable() -> None:
    spec = _spec(
        kind=ValueKind.SIGNED,
        direction=QualityDirection.NEUTRAL,
        epsilon=None,
    )
    target = _compact([-1.0, 3.0], weights=[1.0, 3.0])
    reference = _compact([0.0, 1.0], weights=[1.0, 3.0])
    forward = compare_v2_sources(spec, target, reference)[ComparisonMode.SIGNED_DELTA]
    reverse = compare_v2_sources(spec, reference, target)[ComparisonMode.SIGNED_DELTA]
    assert forward.raw.value == pytest.approx(1.25)
    assert reverse.raw.value == pytest.approx(-1.25)
    assert not forward.quality.valid
    assert forward.quality.invalid_reason == "neutral_attribute"


def test_pair_valid_intersection_controls_relative_comparison() -> None:
    target = _compact([1.0, 100.0, 5.0], valid=[True, False, True])
    reference = _compact([1.0, 2.0, 10.0], valid=[True, True, False])
    result = compare_v2_sources(_spec(), target, reference)
    for statistic in result.values():
        assert statistic.raw.value == pytest.approx(0.0)


def test_relative_dataset_reduction_is_equal_scene_arithmetic_mean() -> None:
    values = [
        _stat(1.0),
        _stat(3.0),
        ScalarStatistic.invalid("no_valid_blocks"),
    ]
    reduced = reduce_relative_scene_values(values)
    assert reduced.valid
    assert reduced.value == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("target", "reference", "epsilon", "reason"),
    [
        ([-1.0], [1.0], 0.0, "negative_power"),
        ([float("inf")], [1.0], 0.0, "nonfinite_input"),
        ([0.0], [0.0], 0.0, "undefined_ratio"),
    ],
)
def test_power_comparison_rejects_invalid_domains(
    target: list[float],
    reference: list[float],
    epsilon: float,
    reason: str,
) -> None:
    result = compare_v2_sources(
        _spec(epsilon=epsilon), _compact(target), _compact(reference)
    )
    assert all(not item.raw.valid for item in result.values())
    assert any(item.raw.invalid_reason == reason for item in result.values())


def test_positive_epsilon_stabilizes_zero_power_ratio() -> None:
    result = compare_v2_sources(
        _spec(epsilon=1e-9), _compact([0.0]), _compact([0.0])
    )
    for item in result.values():
        assert item.raw.valid
        assert item.raw.value == pytest.approx(0.0)


def test_projection_tolerance_has_deterministic_boundary() -> None:
    expected = 100.0
    inside = expected + 0.5 * max(1e-12, 1e-9 * expected)
    outside = expected + 2.0 * max(1e-12, 1e-9 * expected)
    assert projection_matches(inside, expected)
    assert not projection_matches(outside, expected)


def test_summary_projection_mismatch_is_corrupt(golden_root: Path) -> None:
    summary_path = golden_root / "summary.npz"

    def mutate(arrays: ArrayMap) -> None:
        arrays["scene_weighted_mean"] = arrays["scene_weighted_mean"].copy()
        arrays["scene_weighted_mean"][0, 0, 0] += 0.01

    _rewrite_npz(summary_path, mutate)
    manifest = _manifest(golden_root)
    manifest["summary_artifact"]["uncompressed_size"] = _npz_size(summary_path)
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.CORRUPT
    assert "projection mismatch" in (outcome.reason or "")


def test_measurement_context_tampering_is_invalid(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["scenes"][0]["measurement_context_id"] = "mc2:" + "0" * 64
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "fingerprint mismatch" in (outcome.reason or "")


def test_complete_result_rejects_missing_variant_binding(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["scenes"][0]["sources"].pop()
    _write_manifest(golden_root, manifest)
    assert load_result_v2(golden_root).status is LoadStatus.INVALID


def test_complete_result_rejects_cross_variant_geometry_mismatch(
    golden_root: Path,
) -> None:
    manifest = _manifest(golden_root)
    affine = manifest["scenes"][0]["sources"][1]["geometry"]["source_to_analysis"]
    affine[0][2] += 0.001
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "geometry mismatch" in (outcome.reason or "")


def test_complete_result_rejects_cross_variant_grid_mismatch(
    golden_root: Path,
) -> None:
    manifest = _manifest(golden_root)
    grid = manifest["scenes"][0]["sources"][1]["grids"]["luma_noise"]
    grid["origin_x"] += 0.25
    grid["discarded_right"] -= 0.25
    _write_manifest(golden_root, manifest)
    outcome = load_result_v2(golden_root)
    assert outcome.status is LoadStatus.INVALID
    assert "grid geometry mismatch" in (outcome.reason or "")


def _minimal_manifest(
    root: Path,
    *,
    reuse_across_scenes: bool = False,
    source_metadata_mismatch: bool = False,
    duplicate_inside_scene: bool = False,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.npz").write_bytes(b"x")
    spec = _spec(epsilon=1e-9)
    geometry = SceneGeometry(
        analysis_width=64,
        analysis_height=64,
        source_to_analysis=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        valid_rect=(0.0, 0.0, 64.0, 64.0),
    )
    grid = GridGeometry(2, 2, 16.0, 16.0, 0.0, 0.0, 32.0, 32.0)
    provenance = MeasurementContextProvenance(
        "rep", "pre", "model", "weight", "geom"
    )
    shared = Source("shared", "dataset/shared.png", "1" * 64, 100, 100)

    def source(scene_index: int, variant_index: int) -> Source:
        if duplicate_inside_scene and scene_index == 0:
            return shared
        if reuse_across_scenes and variant_index == 0:
            if scene_index == 1 and source_metadata_mismatch:
                return Source(
                    "shared",
                    "dataset/changed.png",
                    "2" * 64,
                    100,
                    100,
                )
            return shared
        return Source(
            f"s{scene_index}-v{variant_index}",
            f"dataset/s{scene_index}-v{variant_index}.png",
            str(3 + scene_index * 2 + variant_index) * 64,
            100,
            100,
        )

    scenes: list[dict[str, Any]] = []
    for scene_index in range(2):
        scene_id = f"scene-{scene_index}"
        measurements = tuple(
            SourceMeasurementV2(
                variant_id=f"v{variant_index}",
                source=source(scene_index, variant_index),
                geometry=geometry,
                grids={"test": grid},
                summaries={},
            )
            for variant_index in range(2)
        )
        context_id = build_measurement_context_id(
            scene_id, measurements, (spec,), provenance
        )
        scenes.append(
            {
                "scene_id": scene_id,
                "measurement_context_id": context_id,
                "context_provenance": {
                    "representative_id": "rep",
                    "preprocessing_id": "pre",
                    "model_id": "model",
                    "weighting_id": "weight",
                    "geometry_id": "geom",
                },
                "sources": [
                    _measurement_manifest(item) for item in measurements
                ],
                "grid_artifact": {
                    "path": f"scenes/{scene_id}.npz",
                    "uncompressed_size": 1,
                },
                "detail_artifacts": [],
            }
        )
    return {
        "kind": "pixelscope-iqa-result",
        "schema_version": 2,
        "publication_state": "complete",
        "result_id": "minimal",
        "variants": [
            {"variant_id": "v0", "label": "Same Label"},
            {"variant_id": "v1", "label": "Same Label"},
        ],
        "attributes": [
            {
                "attribute_id": "test",
                "name": "Test",
                "value_kind": "power",
                "comparison_operator": "power_ratio_target_over_reference_db",
                "quality_direction": "higher_is_better",
                "unit": "unit",
                "stabilization_epsilon": 1e-9,
                "weighting_provenance": "test-weighting",
            }
        ],
        "summary_artifact": {
            "path": "summary.npz",
            "uncompressed_size": 1,
        },
        "scenes": scenes,
    }


def _measurement_manifest(measurement: SourceMeasurementV2) -> dict[str, Any]:
    source = measurement.source
    geometry = measurement.geometry
    grid = measurement.grids["test"]
    return {
        "variant_id": measurement.variant_id,
        "source_id": source.source_id,
        "relative_path": source.relative_path,
        "sha256": source.sha256,
        "width": source.width,
        "height": source.height,
        "geometry": {
            "analysis_width": geometry.analysis_width,
            "analysis_height": geometry.analysis_height,
            "source_to_analysis": [
                list(row) for row in geometry.source_to_analysis
            ],
            "valid_rect": list(geometry.valid_rect),
        },
        "grids": {
            "test": {
                "rows": grid.rows,
                "columns": grid.columns,
                "block_width": grid.block_width,
                "block_height": grid.block_height,
                "origin_x": grid.origin_x,
                "origin_y": grid.origin_y,
                "discarded_right": grid.discarded_right,
                "discarded_bottom": grid.discarded_bottom,
            }
        },
    }


def test_source_id_may_recur_across_measurement_contexts_with_same_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reuse"
    manifest = _minimal_manifest(root, reuse_across_scenes=True)
    parsed = parse_complete_manifest(root, manifest)
    assert parsed.scenes[0].sources[0].source.source_id == "shared"
    assert parsed.scenes[1].sources[0].source.source_id == "shared"
    assert (
        parsed.scenes[0].measurement_context_id
        != parsed.scenes[1].measurement_context_id
    )


def test_source_id_reuse_requires_identical_immutable_metadata(tmp_path: Path) -> None:
    root = tmp_path / "reuse-mismatch"
    manifest = _minimal_manifest(
        root,
        reuse_across_scenes=True,
        source_metadata_mismatch=True,
    )
    with pytest.raises(InvalidV2, match="immutable metadata mismatch"):
        parse_complete_manifest(root, manifest)


def test_duplicate_source_binding_inside_one_scene_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "same-scene-duplicate"
    manifest = _minimal_manifest(root, duplicate_inside_scene=True)
    with pytest.raises(InvalidV2, match="duplicate source_id"):
        parse_complete_manifest(root, manifest)


def test_display_labels_are_not_variant_identity(tmp_path: Path) -> None:
    root = tmp_path / "duplicate-label"
    manifest = _minimal_manifest(root)
    parsed = parse_complete_manifest(root, manifest)
    assert parsed.variants[0].label == parsed.variants[1].label
    assert parsed.variants[0].variant_id != parsed.variants[1].variant_id


def test_v2_rejects_legacy_a_b_operator_names(tmp_path: Path) -> None:
    root = tmp_path / "legacy-op"
    manifest = _minimal_manifest(root)
    manifest["attributes"][0]["comparison_operator"] = "power_ratio_a_over_b_db"
    with pytest.raises(InvalidV2, match="target_over_reference"):
        parse_complete_manifest(root, manifest)


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.npz",
        "..\\outside.npz",
        "/absolute/outside.npz",
        "C:\\outside.npz",
        "\\\\server\\share\\outside.npz",
    ],
)
def test_artifact_reference_rejects_posix_and_windows_escape(reference: str) -> None:
    with pytest.raises(CorruptV2):
        validate_artifact_reference(reference)


def test_artifact_reference_accepts_relative_result_path() -> None:
    assert validate_artifact_reference("scenes/scene_000000.npz") == Path(
        "scenes", "scene_000000.npz"
    )


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=True)
    return stream.getvalue()


def test_npz_duplicate_members_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.npz"
    payload = _npy_bytes(np.asarray([1.0], dtype=np.float64))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("x.npy", payload)
        archive.writestr("x.npy", payload)
    with pytest.raises(CorruptV2, match="duplicate members"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_object_array_is_rejected_before_materialization(tmp_path: Path) -> None:
    path = tmp_path / "object.npz"
    np.savez(path, x=np.asarray([{"unsafe": True}], dtype=object))
    with pytest.raises(CorruptV2, match="object/pickle"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("O"), (1,))},
        )


def test_npz_wrong_dtype_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dtype.npz"
    np.savez(path, x=np.asarray([1.0], dtype=np.float32))
    with pytest.raises(CorruptV2, match="dtype/rank/shape mismatch"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_unsupported_compression_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bzip2.npz"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_BZIP2) as archive:
        archive.writestr(
            "x.npy",
            _npy_bytes(np.asarray([1.0], dtype=np.float64)),
        )
    with pytest.raises(CorruptV2, match="unsupported member compression"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_encrypted_flag_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "encrypted-flag.npz"
    np.savez(path, x=np.asarray([1.0], dtype=np.float64))
    payload = bytearray(path.read_bytes())
    local = payload.find(b"PK\x03\x04")
    central = payload.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    local_flags = struct.unpack_from("<H", payload, local + 6)[0] | 0x1
    central_flags = struct.unpack_from("<H", payload, central + 8)[0] | 0x1
    struct.pack_into("<H", payload, local + 6, local_flags)
    struct.pack_into("<H", payload, central + 8, central_flags)
    path.write_bytes(payload)
    with pytest.raises(CorruptV2, match="encrypted members"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
        )


def test_npz_member_and_array_safety_ceilings_are_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pixelscope.remote import iqa_v2_support as support

    path = tmp_path / "limits.npz"
    np.savez(
        path,
        x=np.asarray([1.0], dtype=np.float64),
        y=np.asarray([2.0], dtype=np.float64),
    )
    expected = {
        "x": (np.dtype("float64"), (1,)),
        "y": (np.dtype("float64"), (1,)),
    }
    monkeypatch.setattr(support, "V2_NPZ_MEMBER_LIMIT", 1)
    with pytest.raises(CorruptV2, match="too many members"):
        load_npz(path, total_limit=1024 * 1024, expected=expected)
    monkeypatch.setattr(support, "V2_NPZ_MEMBER_LIMIT", 192)
    monkeypatch.setattr(support, "V2_ARRAY_LIMIT", 1)
    with pytest.raises(CorruptV2, match="array x exceeds safety ceiling"):
        load_npz(path, total_limit=1024 * 1024, expected=expected)


def test_npz_declared_size_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "declared.npz"
    np.savez(path, x=np.asarray([1.0], dtype=np.float64))
    with pytest.raises(CorruptV2, match="declared/actual size mismatch"):
        load_npz(
            path,
            total_limit=1024 * 1024,
            expected={"x": (np.dtype("float64"), (1,))},
            declared_size=1,
        )


def test_grid_numerical_corruption_is_detected_lazily(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    grid_path = golden_root / manifest["scenes"][0]["grid_artifact"]["path"]

    def mutate(arrays: ArrayMap) -> None:
        arrays["luma_noise__weight_sum"] = arrays[
            "luma_noise__weight_sum"
        ].copy()
        arrays["luma_noise__weight_sum"][0, 0, 0] = -1.0

    _rewrite_npz(grid_path, mutate)
    grid_ref = manifest["scenes"][0]["grid_artifact"]
    grid_ref["uncompressed_size"] = _npz_size(grid_path)
    _write_manifest(golden_root, manifest)
    result = _loaded(golden_root)
    outcome = load_grid_scene(result, "scene_000000")
    assert outcome.status is LoadStatus.CORRUPT
    assert "numerical safety failure" in (outcome.reason or "")


def test_partial_v2_is_explicitly_unsupported_for_stage2(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["publication_state"] = "partial"
    _write_manifest(golden_root, manifest)
    outcome = load_versioned_result(golden_root)
    assert outcome.status is LoadStatus.UNSUPPORTED
    assert "PARTIAL" in (outcome.reason or "")


def test_future_schema_version_is_unsupported(golden_root: Path) -> None:
    manifest = _manifest(golden_root)
    manifest["schema_version"] = 3
    _write_manifest(golden_root, manifest)
    outcome = load_versioned_result(golden_root)
    assert outcome.status is LoadStatus.UNSUPPORTED


def test_real_schema_v1_fixture_uses_read_only_dispatch_without_upgrade(
    tmp_path: Path,
) -> None:
    root = write_golden_result(tmp_path / "golden-v1")
    outcome = load_versioned_result(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert outcome.result is not None
    assert outcome.result.schema_version == 1
    assert not isinstance(outcome.result, ResultV2)
