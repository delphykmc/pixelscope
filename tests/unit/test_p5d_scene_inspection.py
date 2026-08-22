from __future__ import annotations

import json
import math
import struct
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    ComparisonOperator,
    CompactAttributeData,
    GridGeometry,
    LoadStatus,
    QualityDirection,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_geometry import source_cell_polygon, source_point_to_grid_cell
from pixelscope.remote.iqa_scene_inspection import (
    inspect_unavailable_reason,
    probe_image_dimensions,
    verify_scene_sources,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_spatial import (
    SpatialMode,
    derive_spatial_scene,
    hit_test_spatial_cell,
    spatial_cell_detail,
)
from pixelscope.remote.iqa_storage import sha256_file
from pixelscope.remote.iqa_v2_domain import (
    GridSceneDataV2,
    MeasurementContextProvenance,
    ResultV2,
    SceneV2,
    SourceMeasurementV2,
    Variant,
    build_measurement_context_id,
)
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_reader import load_result_v2


def _specs() -> tuple[AttributeSpec, AttributeSpec]:
    return (
        AttributeSpec(
            "power",
            "Power",
            ValueKind.POWER,
            ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB,
            QualityDirection.LOWER_IS_BETTER,
            "arb",
            0.1,
            "fixture-power",
        ),
        AttributeSpec(
            "signed",
            "Signed",
            ValueKind.SIGNED,
            ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE,
            QualityDirection.NEUTRAL,
            "delta",
            None,
            "fixture-signed",
        ),
    )


def _scene_result(
    *,
    storage_root_id: str | None = "fixture-root",
    variant_count: int = 2,
) -> ResultV2:
    geometry = SceneGeometry(
        analysis_width=8,
        analysis_height=6,
        source_to_analysis=((0.5, 0.0, 0.25), (0.0, 0.5, 0.5), (0.0, 0.0, 1.0)),
        valid_rect=(1.0, 1.0, 6.0, 4.0),
    )
    grid = GridGeometry(
        rows=2,
        columns=2,
        block_width=2.0,
        block_height=1.25,
        origin_x=1.5,
        origin_y=1.25,
        discarded_right=1.5,
        discarded_bottom=1.25,
    )
    specs = _specs()
    variants = tuple(Variant(f"v{index}", f"Variant {index}") for index in range(variant_count))
    measurements = tuple(
        SourceMeasurementV2(
            variant_id=variant.variant_id,
            source=Source(
                source_id=f"source-{index}",
                relative_path=f"scene/source-{index}.bmp",
                sha256=f"{index + 1:064x}",
                width=16,
                height=12,
                storage_root_id=storage_root_id,
            ),
            geometry=geometry,
            grids={"power": grid, "signed": grid},
            summaries={},
        )
        for index, variant in enumerate(variants)
    )
    scene = SceneV2(
        scene_id="scene-1",
        measurement_context_id="mc2:" + "0" * 64,
        context_provenance=MeasurementContextProvenance("rep", "pre", "model", "weight", "geom"),
        sources=measurements,
        grid_artifact="scenes/scene-1/grid.npz",
        grid_uncompressed_size=1,
        detail_artifacts=(),
    )
    return ResultV2(
        root=Path("."),
        result_id="p5d-fixture",
        schema_version=2,
        variants=variants,
        attributes=specs,
        scenes=(scene,),
        dataset_summaries={},
        summary_artifact="summary.npz",
    )


def _compact_cube(means: np.ndarray, valid: np.ndarray) -> CompactAttributeData:
    weights = np.asarray(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[2.0, 1.0], [4.0, 5.0]],
        ],
        dtype=np.float64,
    )
    return CompactAttributeData(
        weight_sum=weights,
        weighted_sum=weights * means,
        weighted_square_sum=weights * means * means,
        valid_count=np.where(valid, 3, 0).astype(np.int32),
        valid_mask=valid,
    )


def _grid_data(result: ResultV2) -> GridSceneDataV2:
    power_means = np.asarray(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[2.0, 1.0], [6.0, 4.0]],
        ],
        dtype=np.float64,
    )
    signed_means = np.asarray(
        [
            [[-1.0, 2.0], [4.0, -3.0]],
            [[1.0, 1.0], [7.0, -1.0]],
        ],
        dtype=np.float64,
    )
    valid = np.ones((2, 2, 2), dtype=np.bool_)
    valid[1, 1, 1] = False
    scene = result.scene("scene-1")
    return GridSceneDataV2(
        scene_id=scene.scene_id,
        measurement_context_id=scene.measurement_context_id,
        variant_ids=tuple(item.variant_id for item in scene.sources),
        source_ids=tuple(item.source.source_id for item in scene.sources),
        attributes={
            "power": _compact_cube(power_means, valid),
            "signed": _compact_cube(signed_means, valid),
        },
    )


def test_old_v2_without_storage_root_still_opens_but_inspect_does_not_guess(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "golden")
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    result = outcome.result
    assert result.scenes[0].sources[0].source.storage_root_id is None
    assert inspect_unavailable_reason(result, result.scenes[0].scene_id, RemoteIqaSettings()) == (
        "Published source location is unavailable"
    )


def test_additive_storage_root_locator_round_trips_without_context_change(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "golden")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_contexts = [scene["measurement_context_id"] for scene in manifest["scenes"]]
    for scene in manifest["scenes"]:
        for source in scene["sources"]:
            source["storage_root_id"] = "fixture-root"
    manifest_path.write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")

    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    assert all(
        measurement.source.storage_root_id == "fixture-root"
        for scene in outcome.result.scenes
        for measurement in scene.sources
    )
    assert [scene.measurement_context_id for scene in outcome.result.scenes] == original_contexts


def test_storage_root_is_not_part_of_measurement_context_fingerprint() -> None:
    result = _scene_result(storage_root_id=None)
    scene = result.scenes[0]
    before = build_measurement_context_id(
        scene.scene_id,
        scene.sources,
        result.attributes,
        scene.context_provenance,
    )
    relocated = tuple(
        replace(item, source=replace(item.source, storage_root_id="another-root"))
        for item in scene.sources
    )
    after = build_measurement_context_id(
        scene.scene_id,
        relocated,
        result.attributes,
        scene.context_provenance,
    )
    assert before == after


def test_more_than_six_variants_are_not_silently_truncated() -> None:
    result = _scene_result(variant_count=7)
    assert inspect_unavailable_reason(result, "scene-1", RemoteIqaSettings()) == (
        "Native Inspect supports at most 6 Scene variants"
    )


def test_missing_root_mapping_is_explicit() -> None:
    result = _scene_result(storage_root_id="missing-root")
    assert inspect_unavailable_reason(result, "scene-1", RemoteIqaSettings()) == (
        "Source root is not configured"
    )


def test_absolute_spatial_values_are_s1_over_w_and_invalid_cells_remain_invalid() -> None:
    result = _scene_result()
    field = derive_spatial_scene(result, "scene-1", _grid_data(result), "power")
    assert field.mode is SpatialMode.ABSOLUTE
    assert field.reference_variant_id is None
    np.testing.assert_allclose(field.variant("v0").values, [[1.0, 2.0], [3.0, 4.0]])
    assert not field.variant("v1").valid_mask[1, 1]
    assert np.isnan(field.variant("v1").values[1, 1])


def test_relative_power_cells_use_canonical_raw_target_reference_db() -> None:
    result = _scene_result()
    field = derive_spatial_scene(result, "scene-1", _grid_data(result), "power", "v0")
    expected = 10.0 * math.log10((2.0 + 0.1) / (1.0 + 0.1))
    assert field.mode is SpatialMode.RELATIVE
    assert field.variant("v1").values[0, 0] == pytest.approx(expected)
    assert field.variant("v0").values[0, 0] == pytest.approx(0.0)
    assert not field.variant("v1").valid_mask[1, 1]
    assert field.scale_min == pytest.approx(-field.scale_max)


def test_signed_relative_cells_are_raw_target_minus_reference() -> None:
    result = _scene_result()
    field = derive_spatial_scene(result, "scene-1", _grid_data(result), "signed", "v0")
    np.testing.assert_allclose(
        field.variant("v1").values[0],
        np.asarray([2.0, -1.0]),
    )
    assert field.scale_min == pytest.approx(-field.scale_max)


def test_nonzero_origin_noninteger_affine_drawing_and_hit_testing_identify_same_cell() -> None:
    result = _scene_result()
    scene = result.scene("scene-1")
    grid = scene.grid("power")
    polygon = source_cell_polygon(scene.geometry, grid, 0, 0, 16, 12)
    np.testing.assert_allclose(
        polygon,
        np.asarray([[2.5, 1.5], [6.5, 1.5], [6.5, 4.0], [2.5, 4.0]]),
    )
    assert source_point_to_grid_cell(scene.geometry, grid, 3.0, 2.0) == (0, 0)
    assert source_point_to_grid_cell(scene.geometry, grid, 7.0, 2.0) == (0, 1)
    # analysis x=6.5 is inside valid_rect but in the published discarded-right border.
    assert source_point_to_grid_cell(scene.geometry, grid, 12.5, 2.0) is None

    field = derive_spatial_scene(result, "scene-1", _grid_data(result), "power")
    assert hit_test_spatial_cell(field, "v0", 3.0, 2.0) == (0, 0)


def test_block_detail_preserves_published_sufficient_statistics_and_relative_pair_state() -> None:
    result = _scene_result()
    grid_data = _grid_data(result)
    field = derive_spatial_scene(result, "scene-1", grid_data, "power", "v0")
    detail = spatial_cell_detail(result, field, "v1", 0, 0)
    assert detail.valid
    assert detail.weight_sum == pytest.approx(2.0)
    assert detail.weighted_sum == pytest.approx(4.0)
    assert detail.weighted_square_sum == pytest.approx(8.0)
    assert detail.valid_count == 3
    assert detail.cell_mean == pytest.approx(2.0)
    assert detail.reference_variant_id == "v0"
    assert detail.reference_cell_mean == pytest.approx(1.0)
    assert detail.pair_valid is True
    assert detail.relative_value is not None

    invalid = spatial_cell_detail(result, field, "v1", 1, 1)
    assert not invalid.valid
    assert invalid.pair_valid is False
    assert invalid.relative_value is None


def _write_bmp(path: Path, width: int, height: int, fill: int = 0) -> None:
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_size = row_size * height
    file_size = 54 + pixel_size
    header = bytearray()
    header.extend(b"BM")
    header.extend(struct.pack("<IHHI", file_size, 0, 0, 54))
    header.extend(struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0, pixel_size, 0, 0, 0, 0))
    pixels = bytes([fill & 0xFF]) * pixel_size
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + pixels)


def test_lightweight_probe_reads_bmp_dimensions_without_decode(tmp_path: Path) -> None:
    path = tmp_path / "source.bmp"
    _write_bmp(path, 13, 7)
    assert probe_image_dimensions(path) == (13, 7)


@pytest.mark.skipif(sys.platform != "win32", reason="Remote IQA client roots are Windows/UNC paths")
def test_scene_verification_is_all_or_nothing_and_reports_identity_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "root"
    first = root / "scene" / "source-0.bmp"
    second = root / "scene" / "source-1.bmp"
    _write_bmp(first, 16, 12, 10)
    _write_bmp(second, 16, 12, 20)
    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("fixture-root", str(root)),),
    )
    result = _scene_result()
    scene = result.scene("scene-1")
    sources = []
    for measurement, path in zip(scene.sources, (first, second), strict=True):
        sources.append(
            replace(
                measurement,
                source=replace(
                    measurement.source,
                    sha256=sha256_file(path),
                    width=16,
                    height=12,
                ),
            )
        )
    result = replace(result, scenes=(replace(scene, sources=tuple(sources)),))

    success = verify_scene_sources(result, "scene-1", settings)
    assert success.succeeded
    assert [item.variant_id for item in success.sources] == ["v0", "v1"]

    changed = replace(
        result,
        scenes=(
            replace(
                result.scene("scene-1"),
                sources=(
                    result.scene("scene-1").sources[0],
                    replace(
                        result.scene("scene-1").sources[1],
                        source=replace(
                            result.scene("scene-1").sources[1].source,
                            sha256="f" * 64,
                        ),
                    ),
                ),
            ),
        ),
    )
    failed = verify_scene_sources(changed, "scene-1", settings)
    assert not failed.succeeded
    assert failed.sources == ()
    assert failed.reason == "Source hash changed"
    assert failed.failed_source_id == "source-1"


@pytest.mark.skipif(sys.platform != "win32", reason="Remote IQA client roots are Windows/UNC paths")
def test_scene_verification_dimension_and_missing_file_fail_before_any_payload(tmp_path: Path) -> None:
    root = tmp_path / "root"
    first = root / "scene" / "source-0.bmp"
    second = root / "scene" / "source-1.bmp"
    _write_bmp(first, 16, 12)
    _write_bmp(second, 15, 12)
    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("fixture-root", str(root)),),
    )
    result = _scene_result()
    scene = result.scene("scene-1")
    measurements = tuple(
        replace(
            measurement,
            source=replace(measurement.source, sha256=sha256_file(path)),
        )
        for measurement, path in zip(scene.sources, (first, second), strict=True)
    )
    result = replace(result, scenes=(replace(scene, sources=measurements),))
    dimensions = verify_scene_sources(result, "scene-1", settings)
    assert dimensions.sources == ()
    assert dimensions.reason == "Source dimensions changed"

    second.unlink()
    missing = verify_scene_sources(result, "scene-1", settings)
    assert missing.sources == ()
    assert missing.reason == "Source is unavailable"
