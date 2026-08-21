"""Deterministic production-shaped Remote IQA schema-v2 fixture writer."""

from __future__ import annotations

import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonOperator,
    GridGeometry,
    QualityDirection,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_v2_domain import (
    MeasurementContextProvenance,
    SourceMeasurementV2,
    build_measurement_context_id,
)

V2_ATTRIBUTE_ROWS = (
    (
        "luma_noise",
        "Luma noise",
        "power",
        "lower_is_better",
        "linear-power",
        1e-9,
        "soft-flat-gate-v3",
    ),
    (
        "luma_detail",
        "Luma detail",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "hard-texture-gate-v2",
    ),
    (
        "chroma_noise",
        "Chroma noise",
        "power",
        "lower_is_better",
        "linear-power",
        1e-9,
        "soft-flat-gate-v3",
    ),
    (
        "chroma_detail",
        "Chroma detail",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "hard-texture-gate-v2",
    ),
    (
        "edge_strength",
        "Edge strength",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "soft-pidinet-edge-v1",
    ),
    (
        "luma_contrast",
        "Luma contrast",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "unit-weight",
    ),
    (
        "luma_bias",
        "Luma bias",
        "signed",
        "neutral",
        "normalized-code",
        None,
        "unit-weight",
    ),
    (
        "chroma_contrast",
        "Chroma contrast",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "unit-weight",
    ),
    (
        "chroma_bias",
        "Chroma bias",
        "signed",
        "neutral",
        "normalized-code",
        None,
        "unit-weight",
    ),
    (
        "colorfulness",
        "Colorfulness",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "unit-weight",
    ),
)

V2_VARIANTS = (
    ("baseline", "Baseline"),
    ("candidate_fast", "Candidate Fast"),
    ("candidate_quality", "Candidate Quality"),
)


def write_golden_result_v2(root: Path, scene_count: int = 4) -> Path:
    """Write a deterministic N-way schema-v2 fixture and publish manifest last."""
    if scene_count < 3 or scene_count > 12:
        raise ValueError("schema-v2 golden fixture scene_count must be between 3 and 12")
    root.mkdir(parents=True, exist_ok=True)
    scenes_root = root / "scenes"
    detail_root = root / "detail"
    scenes_root.mkdir(exist_ok=True)
    detail_root.mkdir(exist_ok=True)
    specs = tuple(_attribute_spec(row) for row in V2_ATTRIBUTE_ROWS)
    attributes = [_attribute_manifest(row) for row in V2_ATTRIBUTE_ROWS]
    variants = [
        {"variant_id": variant_id, "label": label}
        for variant_id, label in V2_VARIANTS
    ]
    variant_count = len(variants)
    attribute_count = len(specs)

    scene_weight = np.zeros(
        (scene_count, variant_count, attribute_count), dtype=np.float64
    )
    scene_weighted = np.zeros_like(scene_weight)
    scene_squared = np.zeros_like(scene_weight)
    scene_count_values = np.zeros(
        (scene_count, variant_count, attribute_count), dtype=np.int64
    )
    scene_valid = np.zeros(
        (scene_count, variant_count, attribute_count), dtype=np.bool_
    )
    scene_mean = np.zeros_like(scene_weight)
    scene_std = np.zeros_like(scene_weight)
    source_ids = np.empty((scene_count, variant_count), dtype="<U128")
    context_ids = np.empty((scene_count,), dtype="<U68")
    scenes: list[dict[str, Any]] = []

    for scene_index in range(scene_count):
        scene_id = f"scene_{scene_index:06d}"
        geometry = _geometry(scene_index)
        grids = {
            spec.attribute_id: _grid(scene_index, attribute_index, geometry)
            for attribute_index, spec in enumerate(specs)
        }
        measurements: list[SourceMeasurementV2] = []
        source_manifests: list[dict[str, Any]] = []
        arrays: dict[str, np.ndarray[Any, Any]] = {}
        for variant_index, (variant_id, _label) in enumerate(V2_VARIANTS):
            source = _source(scene_index, variant_index)
            source_ids[scene_index, variant_index] = source.source_id
            measurement = SourceMeasurementV2(
                variant_id=variant_id,
                source=source,
                geometry=geometry,
                grids=dict(grids),
                summaries={},
            )
            measurements.append(measurement)
            source_manifests.append(_source_manifest(measurement))
        provenance = MeasurementContextProvenance(
            representative_id=f"representative-policy-v1:scene-{scene_index % 2}",
            preprocessing_id="rgb-analysis-profile-v2",
            model_id="pixelscope-iqa-model-suite-v2",
            weighting_id="scene-context-gating-v2",
            geometry_id="analysis-grid-profile-v2",
        )
        context_id = build_measurement_context_id(
            scene_id, measurements, specs, provenance
        )
        context_ids[scene_index] = context_id

        for attribute_index, spec in enumerate(specs):
            grid = grids[spec.attribute_id]
            compact = _compact_arrays(
                scene_index,
                variant_count,
                attribute_index,
                spec,
                grid.rows,
                grid.columns,
            )
            prefix = f"{spec.attribute_id}__"
            arrays[prefix + "weight_sum"] = np.asarray(compact.weight_sum)
            arrays[prefix + "weighted_sum"] = np.asarray(compact.weighted_sum)
            arrays[prefix + "weighted_square_sum"] = np.asarray(
                compact.weighted_square_sum
            )
            arrays[prefix + "valid_count"] = np.asarray(compact.valid_count)
            arrays[prefix + "valid_mask"] = np.asarray(compact.valid_mask)
            for variant_index in range(variant_count):
                summary = _fixture_summary(_slice(compact, variant_index))
                if summary is None:
                    continue
                weight, weighted, squared, count, mean, std = summary
                index = (scene_index, variant_index, attribute_index)
                scene_weight[index] = weight
                scene_weighted[index] = weighted
                scene_squared[index] = squared
                scene_count_values[index] = count
                scene_valid[index] = True
                scene_mean[index] = mean
                scene_std[index] = std

        arrays["variant_ids"] = np.asarray(
            [row[0] for row in V2_VARIANTS], dtype="<U128"
        )
        arrays["source_ids"] = source_ids[scene_index].copy()
        arrays["measurement_context_id"] = np.asarray([context_id], dtype="<U68")
        grid_path = scenes_root / f"{scene_id}.npz"
        np.savez(grid_path, **arrays)
        detail_artifacts: list[str] = []
        if scene_index == 0:
            detail_path = detail_root / "scene_000000_edge.npy"
            np.save(detail_path, np.arange(20, dtype=np.float32).reshape(4, 5))
            detail_artifacts.append("detail/scene_000000_edge.npy")
        scenes.append(
            {
                "scene_id": scene_id,
                "measurement_context_id": context_id,
                "context_provenance": {
                    "representative_id": provenance.representative_id,
                    "preprocessing_id": provenance.preprocessing_id,
                    "model_id": provenance.model_id,
                    "weighting_id": provenance.weighting_id,
                    "geometry_id": provenance.geometry_id,
                },
                "sources": source_manifests,
                "grid_artifact": {
                    "path": f"scenes/{scene_id}.npz",
                    "uncompressed_size": _npz_uncompressed_size(grid_path),
                },
                "detail_artifacts": detail_artifacts,
            }
        )

    pooled_weight = np.zeros((variant_count, attribute_count), dtype=np.float64)
    pooled_weighted = np.zeros_like(pooled_weight)
    pooled_squared = np.zeros_like(pooled_weight)
    pooled_count = np.zeros((variant_count, attribute_count), dtype=np.int64)
    pooled_valid = np.zeros((variant_count, attribute_count), dtype=np.bool_)
    pooled_mean = np.zeros_like(pooled_weight)
    pooled_std = np.zeros_like(pooled_weight)
    equal_mean = np.zeros_like(pooled_weight)
    equal_std = np.zeros_like(pooled_weight)
    equal_count = np.zeros((variant_count, attribute_count), dtype=np.int32)
    equal_valid = np.zeros((variant_count, attribute_count), dtype=np.bool_)

    for variant_index in range(variant_count):
        for attribute_index in range(attribute_count):
            mask = scene_valid[:, variant_index, attribute_index]
            if not np.any(mask):
                continue
            weights = scene_weight[:, variant_index, attribute_index][mask]
            first = scene_weighted[:, variant_index, attribute_index][mask]
            second = scene_squared[:, variant_index, attribute_index][mask]
            counts = scene_count_values[:, variant_index, attribute_index][mask]
            weight = math.fsum(float(value) for value in weights.tolist())
            weighted = math.fsum(float(value) for value in first.tolist())
            squared = math.fsum(float(value) for value in second.tolist())
            count = sum(int(value) for value in counts.tolist())
            mean = weighted / weight
            std = _std(weight, weighted, squared)
            index = (variant_index, attribute_index)
            pooled_weight[index] = weight
            pooled_weighted[index] = weighted
            pooled_squared[index] = squared
            pooled_count[index] = count
            pooled_valid[index] = True
            pooled_mean[index] = mean
            pooled_std[index] = std
            means = [
                float(value)
                for value in scene_mean[
                    :, variant_index, attribute_index
                ][mask].tolist()
            ]
            mean_of_scenes = math.fsum(means) / len(means)
            variance = (
                math.fsum((value - mean_of_scenes) ** 2 for value in means)
                / len(means)
            )
            equal_mean[index] = mean_of_scenes
            equal_std[index] = math.sqrt(max(0.0, variance))
            equal_count[index] = len(means)
            equal_valid[index] = True

    summary_path = root / "summary.npz"
    np.savez(
        summary_path,
        scene_ids=np.asarray([scene["scene_id"] for scene in scenes], dtype="<U128"),
        variant_ids=np.asarray([row[0] for row in V2_VARIANTS], dtype="<U128"),
        attribute_ids=np.asarray(
            [spec.attribute_id for spec in specs], dtype="<U64"
        ),
        source_ids=source_ids,
        measurement_context_ids=context_ids,
        scene_weight_sum=scene_weight,
        scene_weighted_sum=scene_weighted,
        scene_weighted_square_sum=scene_squared,
        scene_valid_count=scene_count_values,
        scene_valid=scene_valid,
        scene_weighted_mean=scene_mean,
        scene_weighted_std=scene_std,
        pooled_weight_sum=pooled_weight,
        pooled_weighted_sum=pooled_weighted,
        pooled_weighted_square_sum=pooled_squared,
        pooled_valid_count=pooled_count,
        pooled_valid=pooled_valid,
        pooled_weighted_mean=pooled_mean,
        pooled_weighted_std=pooled_std,
        scene_mean=equal_mean,
        scene_std=equal_std,
        scene_count=equal_count,
        equal_scene_valid=equal_valid,
    )
    manifest = {
        "kind": "pixelscope-iqa-result",
        "schema_version": 2,
        "publication_state": "complete",
        "result_id": "golden-p5a2-v2",
        "variants": variants,
        "attributes": attributes,
        "summary_artifact": {
            "path": "summary.npz",
            "uncompressed_size": _npz_uncompressed_size(summary_path),
        },
        "scenes": scenes,
    }
    part = root / "manifest.json.part"
    part.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    part.replace(root / "manifest.json")
    return root


def _attribute_manifest(
    row: tuple[str, str, str, str, str, float | None, str],
) -> dict[str, Any]:
    attribute_id, name, kind, direction, unit, epsilon, weighting = row
    return {
        "attribute_id": attribute_id,
        "name": name,
        "value_kind": kind,
        "comparison_operator": (
            "power_ratio_target_over_reference_db"
            if kind == "power"
            else "signed_target_minus_reference"
        ),
        "quality_direction": direction,
        "unit": unit,
        "stabilization_epsilon": epsilon,
        "weighting_provenance": weighting,
    }


def _attribute_spec(
    row: tuple[str, str, str, str, str, float | None, str],
) -> AttributeSpec:
    attribute_id, name, kind, direction, unit, epsilon, weighting = row
    return AttributeSpec(
        attribute_id=attribute_id,
        name=name,
        value_kind=ValueKind(kind),
        comparison_operator=(
            ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB
            if kind == "power"
            else ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE
        ),
        quality_direction=QualityDirection(direction),
        unit=unit,
        stabilization_epsilon=epsilon,
        weighting_provenance=weighting,
    )


def _source(scene_index: int, variant_index: int) -> Source:
    variant_id = V2_VARIANTS[variant_index][0]
    identity = f"v2-source-content-{scene_index}-{variant_index}"
    return Source(
        source_id=f"source_{scene_index:06d}_{variant_id}",
        relative_path=f"dataset/{variant_id}/{scene_index:06d}.png",
        sha256=hashlib.sha256(identity.encode("ascii")).hexdigest(),
        width=1000,
        height=700,
    )


def _source_manifest(measurement: SourceMeasurementV2) -> dict[str, Any]:
    source = measurement.source
    geometry = measurement.geometry
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
            "source_to_analysis": [list(row) for row in geometry.source_to_analysis],
            "valid_rect": list(geometry.valid_rect),
        },
        "grids": {
            attribute_id: {
                "rows": grid.rows,
                "columns": grid.columns,
                "block_width": grid.block_width,
                "block_height": grid.block_height,
                "origin_x": grid.origin_x,
                "origin_y": grid.origin_y,
                "discarded_right": grid.discarded_right,
                "discarded_bottom": grid.discarded_bottom,
            }
            for attribute_id, grid in measurement.grids.items()
        },
    }


def _geometry(scene_index: int) -> SceneGeometry:
    offset = scene_index * 0.125
    return SceneGeometry(
        analysis_width=641,
        analysis_height=361,
        source_to_analysis=(
            (0.625, 0.0, 3.25 + offset),
            (0.0, 0.5, 2.75),
            (0.0, 0.0, 1.0),
        ),
        valid_rect=(11.5 + offset, 7.25, 611.75 - offset, 337.5),
    )


def _grid(
    scene_index: int, attribute_index: int, geometry: SceneGeometry
) -> GridGeometry:
    if attribute_index < 5:
        block_width, block_height, rows, columns = (32.0, 32.0, 3, 4)
    else:
        block_width, block_height, rows, columns = (128.0, 128.0, 2, 3)
    valid_x, valid_y, valid_width, valid_height = geometry.valid_rect
    origin_x = valid_x + 5.5 + (0.25 if scene_index == 2 else 0.0)
    origin_y = valid_y + 3.25
    return GridGeometry(
        rows=rows,
        columns=columns,
        block_width=block_width,
        block_height=block_height,
        origin_x=origin_x,
        origin_y=origin_y,
        discarded_right=valid_x + valid_width - (origin_x + columns * block_width),
        discarded_bottom=valid_y + valid_height - (origin_y + rows * block_height),
    )


def _compact_arrays(
    scene_index: int,
    variant_count: int,
    attribute_index: int,
    spec: AttributeSpec,
    rows: int,
    columns: int,
) -> CompactAttributeData:
    shape = (variant_count, rows, columns)
    weight = np.empty(shape, dtype=np.float64)
    weighted = np.empty(shape, dtype=np.float64)
    squared = np.empty(shape, dtype=np.float64)
    count = np.full(shape, 12, dtype=np.int32)
    valid = np.ones(shape, dtype=np.bool_)
    for variant_index in range(variant_count):
        for row in range(rows):
            for column in range(columns):
                cell_index = row * columns + column
                cell_weight = float(1 + ((cell_index + variant_index) % 4))
                if spec.value_kind is ValueKind.SIGNED:
                    mean = -0.04 + attribute_index * 0.004 + scene_index * 0.012
                    mean += (
                        (-0.025, 0.0, 0.035)[variant_index]
                        + cell_index * 0.0015
                    )
                else:
                    mean = 0.035 + attribute_index * 0.012 + scene_index * 0.004
                    mean *= 1.0 + cell_index * 0.025
                    mean *= (1.0, 1.18, 0.88)[variant_index]
                    if (
                        scene_index == 1
                        and attribute_index == 0
                        and variant_index == 2
                    ):
                        mean = 0.0
                weight[variant_index, row, column] = cell_weight
                weighted[variant_index, row, column] = cell_weight * mean
                squared[variant_index, row, column] = cell_weight * (
                    mean * mean + 0.0004
                )
    if scene_index == 0 and attribute_index == 1:
        valid[0, 0, 0] = False
        valid[1, 0, 1] = False
        valid[2, 0, 2] = False
    if scene_index == 2 and attribute_index == 4:
        valid[2, :, :] = False
    if scene_index == 3 and attribute_index == 8:
        valid[0, 1, 1] = False
        valid[1, 0, 2] = False
    return CompactAttributeData(weight, weighted, squared, count, valid)


def _slice(data: CompactAttributeData, index: int) -> CompactAttributeData:
    return CompactAttributeData(
        np.asarray(data.weight_sum)[index],
        np.asarray(data.weighted_sum)[index],
        np.asarray(data.weighted_square_sum)[index],
        np.asarray(data.valid_count)[index],
        np.asarray(data.valid_mask)[index],
    )


def _fixture_summary(
    data: CompactAttributeData,
) -> tuple[float, float, float, int, float, float] | None:
    mask = np.asarray(data.valid_mask, dtype=np.bool_)
    if not np.any(mask):
        return None
    weight = [float(value) for value in np.asarray(data.weight_sum)[mask].tolist()]
    weighted = [
        float(value) for value in np.asarray(data.weighted_sum)[mask].tolist()
    ]
    squared = [
        float(value)
        for value in np.asarray(data.weighted_square_sum)[mask].tolist()
    ]
    counts = [int(value) for value in np.asarray(data.valid_count)[mask].tolist()]
    total_weight = math.fsum(weight)
    total_weighted = math.fsum(weighted)
    total_squared = math.fsum(squared)
    total_count = sum(counts)
    mean = total_weighted / total_weight
    return (
        total_weight,
        total_weighted,
        total_squared,
        total_count,
        mean,
        _std(total_weight, total_weighted, total_squared),
    )


def _std(weight: float, weighted: float, squared: float) -> float:
    mean = weighted / weight
    variance = squared / weight - mean * mean
    scale = max(
        abs(squared / weight),
        abs(mean * mean),
        float(np.finfo(np.float64).tiny),
    )
    tolerance = 64.0 * float(np.finfo(np.float64).eps) * scale
    if variance < -tolerance:
        raise ValueError("fixture generated inconsistent moments")
    return math.sqrt(max(0.0, variance))


def _npz_uncompressed_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())