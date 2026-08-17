"""Deterministic production-shaped Remote IQA v1 golden fixture writer."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    QualityDirection,
    ValueKind,
)
from pixelscope.remote.iqa_math import compare_sources

ATTRIBUTE_ROWS = (
    ("luma_noise", "Luma noise", "power", "lower_is_better", "linear-power", 1e-9, "flat-gate-v3"),
    (
        "luma_detail",
        "Luma detail",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "texture-gate-v2",
    ),
    (
        "chroma_noise",
        "Chroma noise",
        "power",
        "lower_is_better",
        "linear-power",
        1e-9,
        "flat-gate-v3",
    ),
    (
        "chroma_detail",
        "Chroma detail",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "texture-gate-v2",
    ),
    (
        "edge_strength",
        "Edge strength",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "pidinet-edge-v1",
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
    ("luma_bias", "Luma bias", "signed", "neutral", "normalized-code", None, "unit-weight"),
    (
        "chroma_contrast",
        "Chroma contrast",
        "power",
        "higher_is_better",
        "linear-power",
        1e-9,
        "unit-weight",
    ),
    ("chroma_bias", "Chroma bias", "signed", "neutral", "normalized-code", None, "unit-weight"),
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


def write_golden_result(root: Path, scene_count: int = 11) -> Path:
    """Write a deterministic fixture, publishing ``manifest.json`` last."""
    if scene_count < 10 or scene_count > 12:
        raise ValueError("golden fixture scene_count must be between 10 and 12")
    root.mkdir(parents=True, exist_ok=True)
    scenes_root = root / "scenes"
    details_root = root / "details"
    scenes_root.mkdir(exist_ok=True)
    details_root.mkdir(exist_ok=True)
    attributes = [_attribute_manifest(row) for row in ATTRIBUTE_ROWS]
    specs = tuple(_attribute_spec(row) for row in ATTRIBUTE_ROWS)
    scenes: list[dict[str, Any]] = []
    comparison_keys: list[str] = []
    summary_values: list[list[list[float]]] = []
    summary_valid: list[list[list[bool]]] = []
    summary_reasons: list[list[list[str]]] = []

    for scene_index in range(scene_count):
        scene_id = f"scene_{scene_index:06d}"
        source_count = 3 if scene_index == scene_count - 1 else 2
        sources = [
            _source_manifest(scene_index, source_index) for source_index in range(source_count)
        ]
        geometry = _geometry_manifest()
        grids = {
            spec.attribute_id: _grid_manifest(scene_index, attribute_index, geometry)
            for attribute_index, spec in enumerate(specs)
        }
        arrays: dict[str, np.ndarray[Any, Any]] = {}
        compact_by_attribute: dict[str, CompactAttributeData] = {}
        for attribute_index, spec in enumerate(specs):
            grid = grids[spec.attribute_id]
            compact = _compact_arrays(
                scene_index,
                source_count,
                attribute_index,
                spec,
                int(grid["rows"]),
                int(grid["columns"]),
            )
            compact_by_attribute[spec.attribute_id] = compact
            prefix = f"{spec.attribute_id}__"
            arrays[prefix + "weight_sum"] = np.asarray(compact.weight_sum)
            arrays[prefix + "weighted_sum"] = np.asarray(compact.weighted_sum)
            arrays[prefix + "weighted_square_sum"] = np.asarray(compact.weighted_square_sum)
            arrays[prefix + "valid_count"] = np.asarray(compact.valid_count)
            arrays[prefix + "valid_mask"] = np.asarray(compact.valid_mask)
        compact_path = scenes_root / f"{scene_id}.npz"
        np.savez(compact_path, **arrays)
        pairs = [{"source_a_id": sources[0]["source_id"], "source_b_id": sources[1]["source_id"]}]
        if source_count == 3:
            pairs.append(
                {"source_a_id": sources[0]["source_id"], "source_b_id": sources[2]["source_id"]}
            )
        for pair in pairs:
            source_a_index = next(
                index
                for index, source in enumerate(sources)
                if source["source_id"] == pair["source_a_id"]
            )
            source_b_index = next(
                index
                for index, source in enumerate(sources)
                if source["source_id"] == pair["source_b_id"]
            )
            comparison_keys.append(f"{scene_id}|{pair['source_a_id']}|{pair['source_b_id']}")
            pair_values: list[list[float]] = []
            pair_valid: list[list[bool]] = []
            pair_reasons: list[list[str]] = []
            for spec in specs:
                compact = compact_by_attribute[spec.attribute_id]
                a = _source_data(compact, source_a_index)
                b = _source_data(compact, source_b_index)
                computed = compare_sources(spec, a, b)
                if spec.value_kind is ValueKind.POWER:
                    stats = [computed["raw"], computed["grid"], computed["quality"]]
                    # The third summary slot is reserved for signed_delta and is invalid here.
                    stats[2] = type(computed["raw"]).invalid("not_applicable")
                else:
                    invalid = type(computed["raw"]).invalid("not_applicable")
                    stats = [invalid, invalid, computed["raw"]]
                pair_values.append(
                    [stat.value if stat.value is not None else 0.0 for stat in stats]
                )
                pair_valid.append([stat.valid for stat in stats])
                pair_reasons.append([stat.invalid_reason or "" for stat in stats])
            summary_values.append(pair_values)
            summary_valid.append(pair_valid)
            summary_reasons.append(pair_reasons)
        detail_artifacts: list[str] = []
        if scene_index == 0:
            detail_path = details_root / "scene_000000_edge.npy"
            np.save(detail_path, np.arange(20, dtype=np.float32).reshape(4, 5))
            detail_artifacts.append("details/scene_000000_edge.npy")
        compact_relative = f"scenes/{scene_id}.npz"
        scenes.append(
            {
                "scene_id": scene_id,
                "sources": sources,
                "geometry": geometry,
                "grids": grids,
                "compact_artifact": {
                    "path": compact_relative,
                    "uncompressed_size": _npz_uncompressed_size(compact_path),
                },
                "detail_artifacts": detail_artifacts,
                "comparison_pairs": pairs,
            }
        )

    summary_path = root / "summary.npz"
    np.savez(
        summary_path,
        comparison_keys=np.asarray(comparison_keys, dtype="<U256"),
        attribute_ids=np.asarray([spec.attribute_id for spec in specs], dtype="<U64"),
        values=np.asarray(summary_values, dtype=np.float64),
        valid=np.asarray(summary_valid, dtype=np.bool_),
        invalid_reasons=np.asarray(summary_reasons, dtype="<U64"),
    )
    manifest = {
        "kind": "pixelscope-iqa-result",
        "schema_version": 1,
        "publication_state": "complete",
        "result_id": "golden-p5a-v1",
        "attributes": attributes,
        "summary_artifact": {
            "path": "summary.npz",
            "uncompressed_size": _npz_uncompressed_size(summary_path),
        },
        "scenes": scenes,
    }
    (root / "manifest.json.part").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (root / "manifest.json.part").replace(root / "manifest.json")
    return root


def _attribute_manifest(row: tuple[str, str, str, str, str, float | None, str]) -> dict[str, Any]:
    attribute_id, name, kind, direction, unit, epsilon, weighting = row
    return {
        "attribute_id": attribute_id,
        "name": name,
        "value_kind": kind,
        "quality_direction": direction,
        "unit": unit,
        "stabilization_epsilon": epsilon,
        "weighting_provenance": weighting,
    }


def _attribute_spec(row: tuple[str, str, str, str, str, float | None, str]) -> AttributeSpec:
    attribute_id, name, kind, direction, unit, epsilon, weighting = row
    return AttributeSpec(
        attribute_id,
        name,
        ValueKind(kind),
        QualityDirection(direction),
        unit,
        epsilon,
        weighting,
    )


def _source_manifest(scene_index: int, source_index: int) -> dict[str, Any]:
    identity = f"golden-source-{scene_index}-{source_index}"
    return {
        "source_id": f"source_{scene_index:06d}_{source_index}",
        "relative_path": f"dataset/source_{source_index}/{scene_index:06d}.png",
        "sha256": hashlib.sha256(identity.encode("ascii")).hexdigest(),
        "width": 1000,
        "height": 700,
    }


def _geometry_manifest() -> dict[str, Any]:
    return {
        "analysis_width": 641,
        "analysis_height": 361,
        "source_to_analysis": [[0.625, 0.0, 3.25], [0.0, 0.5, 2.75], [0.0, 0.0, 1.0]],
        "valid_rect": [11.5, 7.25, 611.75, 337.5],
    }


def _grid_manifest(
    scene_index: int, attribute_index: int, geometry: dict[str, Any]
) -> dict[str, Any]:
    if attribute_index < 5:
        block_width, block_height = (40.0, 24.0) if scene_index == 3 else (32.0, 32.0)
        rows, columns = 3, 4
    else:
        block_width, block_height = (96.0, 80.0) if scene_index == 8 else (128.0, 128.0)
        rows, columns = 2, 3
    valid_x, valid_y, valid_width, valid_height = geometry["valid_rect"]
    origin_x = valid_x + 5.5
    origin_y = valid_y + 3.25
    return {
        "rows": rows,
        "columns": columns,
        "block_width": block_width,
        "block_height": block_height,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "discarded_right": valid_x + valid_width - (origin_x + columns * block_width),
        "discarded_bottom": valid_y + valid_height - (origin_y + rows * block_height),
    }


def _compact_arrays(
    scene_index: int,
    source_count: int,
    attribute_index: int,
    spec: AttributeSpec,
    rows: int,
    columns: int,
) -> CompactAttributeData:
    shape = (source_count, rows, columns)
    weight = np.empty(shape, dtype=np.float64)
    weighted = np.empty(shape, dtype=np.float64)
    squared = np.empty(shape, dtype=np.float64)
    count = np.full(shape, 16, dtype=np.int32)
    valid = np.ones(shape, dtype=np.bool_)
    for source_index in range(source_count):
        for row in range(rows):
            for column in range(columns):
                cell_index = row * columns + column
                cell_weight = float(1 + (cell_index % 4))
                if spec.value_kind is ValueKind.SIGNED:
                    sign_pattern = (-0.06, 0.0, 0.08)[scene_index % 3]
                    mean = 0.2 + attribute_index * 0.01 + cell_index * 0.002
                    if source_index == 0:
                        mean += sign_pattern
                else:
                    mean = 0.04 + attribute_index * 0.015 + scene_index * 0.004
                    mean *= 1.0 + cell_index * 0.035
                    if scene_index == 0:
                        source_factor = 1.0
                    elif source_index == 0:
                        source_factor = 4.0 if scene_index == 7 else 1.0 + 0.04 * scene_index
                    else:
                        source_factor = 1.0 - 0.015 * scene_index + 0.012 * cell_index
                    mean *= source_factor
                    if scene_index == 2 and attribute_index == 0:
                        mean = 0.0 if source_index == 0 else 1e-12 * (cell_index + 1)
                weight[source_index, row, column] = cell_weight
                weighted[source_index, row, column] = cell_weight * mean
                squared[source_index, row, column] = cell_weight * (mean * mean + 0.0004)
    if scene_index == 4 and attribute_index == 1:
        valid[0, 0, 0] = False
        valid[1, 0, 1] = False
    if scene_index == 5 and attribute_index == 4:
        valid[:] = False
    if scene_index == 6 and attribute_index == 5:
        weight[:, 0, 0] = 0.0
        weighted[:, 0, 0] = 0.0
        squared[:, 0, 0] = 0.0
    return CompactAttributeData(weight, weighted, squared, count, valid)


def _source_data(data: CompactAttributeData, source_index: int) -> CompactAttributeData:
    return CompactAttributeData(
        np.asarray(data.weight_sum)[source_index],
        np.asarray(data.weighted_sum)[source_index],
        np.asarray(data.weighted_square_sum)[source_index],
        np.asarray(data.valid_count)[source_index],
        np.asarray(data.valid_mask)[source_index],
    )


def _npz_uncompressed_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())
