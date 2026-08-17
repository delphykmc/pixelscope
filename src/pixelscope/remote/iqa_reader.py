"""Safe reader for immutable PixelScope Remote IQA schema-v1 results."""

from __future__ import annotations

import json
import math
import zipfile
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any

import numpy as np
from numpy.lib import format as npy_format

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    CompactLoadOutcome,
    CompactSceneData,
    Comparison,
    ComparisonMode,
    GridGeometry,
    LoadStatus,
    QualityDirection,
    Result,
    ResultLoadOutcome,
    ScalarStatistic,
    Scene,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_geometry import source_to_analysis

MANIFEST_LIMIT = 4 * 1024 * 1024
SUMMARY_LIMIT = 64 * 1024 * 1024
SCENE_LIMIT = 64 * 1024 * 1024
ARRAY_LIMIT = 32 * 1024 * 1024


class _InvalidResult(ValueError):
    pass


class _CorruptResult(ValueError):
    pass


class _UnsupportedResult(ValueError):
    pass


def load_result(root: Path | str) -> ResultLoadOutcome:
    result_root = Path(root)
    try:
        manifest_path = result_root / "manifest.json"
        if not manifest_path.is_file():
            raise _CorruptResult("missing manifest.json publication marker")
        if manifest_path.stat().st_size > MANIFEST_LIMIT:
            raise _CorruptResult("manifest exceeds 4 MiB safety ceiling")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _CorruptResult(f"manifest is unreadable: {exc}") from exc
        if not isinstance(manifest, dict):
            raise _InvalidResult("manifest must be a JSON object")
        if manifest.get("kind") != "pixelscope-iqa-result":
            raise _InvalidResult("manifest kind must be pixelscope-iqa-result")
        version = _integer(manifest, "schema_version")
        if version > 1:
            raise _UnsupportedResult(f"unsupported result schema_version {version}")
        if version != 1:
            raise _UnsupportedResult(f"no compatibility path for schema_version {version}")
        if manifest.get("publication_state") != "complete":
            raise _InvalidResult("result publication_state is not complete")
        result = _parse_manifest(result_root, manifest)
        return ResultLoadOutcome(LoadStatus.SUCCESS, result=result)
    except _UnsupportedResult as exc:
        return ResultLoadOutcome(LoadStatus.UNSUPPORTED, reason=str(exc))
    except _InvalidResult as exc:
        return ResultLoadOutcome(LoadStatus.INVALID, reason=str(exc))
    except _CorruptResult as exc:
        return ResultLoadOutcome(LoadStatus.CORRUPT, reason=str(exc))


def load_compact_scene(result: Result, scene_id: str) -> CompactLoadOutcome:
    try:
        scene = result.scene(scene_id)
        path = _safe_artifact(result.root, scene.compact_artifact)
        expected: dict[str, tuple[np.dtype[Any], tuple[int, ...]]] = {}
        shape_prefix = (len(scene.sources),)
        for attribute in result.attributes:
            grid = scene.grids[attribute.attribute_id]
            shape = shape_prefix + (grid.rows, grid.columns)
            prefix = f"{attribute.attribute_id}__"
            expected[prefix + "weight_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "weighted_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "weighted_square_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "valid_count"] = (np.dtype("int32"), shape)
            expected[prefix + "valid_mask"] = (np.dtype("bool"), shape)
        arrays = _load_npz(path, SCENE_LIMIT, expected, scene.compact_uncompressed_size)
        attributes = {
            attribute.attribute_id: CompactAttributeData(
                weight_sum=arrays[f"{attribute.attribute_id}__weight_sum"],
                weighted_sum=arrays[f"{attribute.attribute_id}__weighted_sum"],
                weighted_square_sum=arrays[f"{attribute.attribute_id}__weighted_square_sum"],
                valid_count=arrays[f"{attribute.attribute_id}__valid_count"],
                valid_mask=arrays[f"{attribute.attribute_id}__valid_mask"],
            )
            for attribute in result.attributes
        }
        return CompactLoadOutcome(
            LoadStatus.SUCCESS,
            data=CompactSceneData(
                scene_id=scene.scene_id,
                source_ids=tuple(source.source_id for source in scene.sources),
                attributes=attributes,
            ),
        )
    except (KeyError, StopIteration):
        return CompactLoadOutcome(LoadStatus.INVALID, reason=f"unknown scene_id {scene_id}")
    except _InvalidResult as exc:
        return CompactLoadOutcome(LoadStatus.INVALID, reason=str(exc))
    except _CorruptResult as exc:
        return CompactLoadOutcome(LoadStatus.CORRUPT, reason=str(exc))


def _parse_manifest(root: Path, data: dict[str, Any]) -> Result:
    result_id = _string(data, "result_id")
    attributes_data = _list(data, "attributes")
    scenes_data = _list(data, "scenes")
    if not attributes_data or not scenes_data:
        raise _InvalidResult("result requires attributes and scenes")
    attributes = tuple(_parse_attribute(item) for item in attributes_data)
    attribute_ids = tuple(item.attribute_id for item in attributes)
    if len(set(attribute_ids)) != len(attribute_ids):
        raise _InvalidResult("attribute_id values must be unique")
    summary_ref = _artifact_ref(data, "summary_artifact", SUMMARY_LIMIT)
    summary_path = _safe_artifact(root, summary_ref[0])
    comparison_count = sum(
        len(_list(scene, "comparison_pairs")) for scene in scenes_data if isinstance(scene, dict)
    )
    expected_summary = {
        "comparison_keys": (np.dtype("<U256"), (comparison_count,)),
        "attribute_ids": (np.dtype("<U64"), (len(attributes),)),
        "values": (np.dtype("float64"), (comparison_count, len(attributes), 3)),
        "valid": (np.dtype("bool"), (comparison_count, len(attributes), 3)),
        "invalid_reasons": (np.dtype("<U64"), (comparison_count, len(attributes), 3)),
    }
    summary = _load_npz(summary_path, SUMMARY_LIMIT, expected_summary, summary_ref[1])
    if tuple(summary["attribute_ids"].tolist()) != attribute_ids:
        raise _InvalidResult("summary attribute identity/order mismatch")
    scenes: list[Scene] = []
    source_ids: set[str] = set()
    comparison_index = 0
    for scene_data in scenes_data:
        if not isinstance(scene_data, dict):
            raise _InvalidResult("scene must be an object")
        scene, comparison_index = _parse_scene(
            root,
            scene_data,
            attributes,
            summary,
            comparison_index,
            source_ids,
        )
        scenes.append(scene)
    scene_ids = [scene.scene_id for scene in scenes]
    if len(set(scene_ids)) != len(scene_ids):
        raise _InvalidResult("scene_id values must be unique")
    return Result(
        root=root.resolve(),
        result_id=result_id,
        schema_version=1,
        attributes=attributes,
        scenes=tuple(scenes),
        summary_artifact=summary_ref[0],
    )


def _parse_attribute(data: Any) -> AttributeSpec:
    if not isinstance(data, dict):
        raise _InvalidResult("attribute must be an object")
    try:
        value_kind = ValueKind(_string(data, "value_kind"))
        direction = QualityDirection(_string(data, "quality_direction"))
    except ValueError as exc:
        raise _InvalidResult(f"invalid attribute enum: {exc}") from exc
    epsilon_raw = data.get("stabilization_epsilon")
    epsilon = None if epsilon_raw is None else _finite_float(epsilon_raw, "stabilization_epsilon")
    if value_kind is ValueKind.POWER and (epsilon is None or epsilon < 0.0):
        raise _InvalidResult("power attribute requires non-negative finite epsilon")
    if value_kind is ValueKind.SIGNED and direction is not QualityDirection.NEUTRAL:
        raise _InvalidResult("signed attribute must have neutral quality direction")
    return AttributeSpec(
        attribute_id=_string(data, "attribute_id"),
        name=_string(data, "name"),
        value_kind=value_kind,
        quality_direction=direction,
        unit=_string(data, "unit"),
        stabilization_epsilon=epsilon,
        weighting_provenance=_string(data, "weighting_provenance"),
    )


def _parse_scene(
    root: Path,
    data: dict[str, Any],
    attributes: tuple[AttributeSpec, ...],
    summary: dict[str, np.ndarray[Any, Any]],
    comparison_index: int,
    all_source_ids: set[str],
) -> tuple[Scene, int]:
    scene_id = _string(data, "scene_id")
    source_items = _list(data, "sources")
    if len(source_items) < 2:
        raise _InvalidResult("scene requires at least two ordered sources")
    sources = tuple(_parse_source(item) for item in source_items)
    local_ids = [source.source_id for source in sources]
    if len(set(local_ids)) != len(local_ids) or any(item in all_source_ids for item in local_ids):
        raise _InvalidResult("source_id must be unique inside the result")
    all_source_ids.update(local_ids)
    dimensions = {(source.width, source.height) for source in sources}
    if len(dimensions) != 1:
        raise _InvalidResult(f"scene {scene_id} has dimension_mismatch")
    geometry = _parse_geometry(data.get("geometry"))
    source_to_analysis(geometry, np.asarray([[0.0, 0.0]], dtype=np.float64))
    grids_data = data.get("grids")
    if not isinstance(grids_data, dict):
        raise _InvalidResult("scene grids must be an object")
    grids = {
        attribute.attribute_id: _parse_grid(grids_data, attribute.attribute_id, geometry)
        for attribute in attributes
    }
    compact_ref = _artifact_ref(data, "compact_artifact", SCENE_LIMIT)
    _safe_artifact(root, compact_ref[0])
    detail_refs = data.get("detail_artifacts", [])
    if not isinstance(detail_refs, list) or not all(isinstance(item, str) for item in detail_refs):
        raise _InvalidResult("detail_artifacts must be an array of paths")
    for reference in detail_refs:
        _safe_artifact(root, reference)
    comparisons: list[Comparison] = []
    for pair in _list(data, "comparison_pairs"):
        if not isinstance(pair, dict):
            raise _InvalidResult("comparison pair must be an object")
        source_a = _string(pair, "source_a_id")
        source_b = _string(pair, "source_b_id")
        if source_a == source_b or source_a not in local_ids or source_b not in local_ids:
            raise _InvalidResult("comparison operands must be distinct Scene source IDs")
        expected_key = f"{scene_id}|{source_a}|{source_b}"
        if str(summary["comparison_keys"][comparison_index]) != expected_key:
            raise _InvalidResult("summary comparison identity/order mismatch")
        for attribute_offset, attribute in enumerate(attributes):
            official: dict[ComparisonMode, ScalarStatistic] = {}
            modes = (
                ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
                ComparisonMode.MEAN_OF_GRID_LOG_RATIOS,
                ComparisonMode.SIGNED_DELTA,
            )
            for mode_index, mode in enumerate(modes):
                valid = bool(summary["valid"][comparison_index, attribute_offset, mode_index])
                value = float(summary["values"][comparison_index, attribute_offset, mode_index])
                reason = str(
                    summary["invalid_reasons"][comparison_index, attribute_offset, mode_index]
                )
                if valid:
                    if not math.isfinite(value):
                        raise _InvalidResult("valid summary value must be finite")
                    official[mode] = ScalarStatistic(value, True)
                else:
                    official[mode] = ScalarStatistic.invalid(reason or "missing_data")
            comparisons.append(
                Comparison(scene_id, source_a, source_b, attribute.attribute_id, official)
            )
        comparison_index += 1
    return (
        Scene(
            scene_id=scene_id,
            sources=sources,
            geometry=geometry,
            grids=grids,
            compact_artifact=compact_ref[0],
            compact_uncompressed_size=compact_ref[1],
            detail_artifacts=tuple(detail_refs),
            comparisons=tuple(comparisons),
        ),
        comparison_index,
    )


def _parse_source(data: Any) -> Source:
    if not isinstance(data, dict):
        raise _InvalidResult("source must be an object")
    sha256 = _string(data, "sha256")
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise _InvalidResult("source sha256 must be 64 lowercase hexadecimal characters")
    width = _positive_integer(data, "width")
    height = _positive_integer(data, "height")
    return Source(_string(data, "source_id"), _string(data, "relative_path"), sha256, width, height)


def _parse_geometry(data: Any) -> SceneGeometry:
    if not isinstance(data, dict):
        raise _InvalidResult("geometry must be an object")
    affine = data.get("source_to_analysis")
    if not isinstance(affine, list) or len(affine) != 3:
        raise _InvalidResult("source_to_analysis must have three rows")
    try:
        matrix = tuple(tuple(_finite_float(value, "affine") for value in row) for row in affine)
    except TypeError as exc:
        raise _InvalidResult("source_to_analysis rows must be arrays") from exc
    if any(len(row) != 3 for row in matrix):
        raise _InvalidResult("source_to_analysis must be 3x3")
    valid = data.get("valid_rect")
    if not isinstance(valid, list) or len(valid) != 4:
        raise _InvalidResult("valid_rect must have four values")
    valid_rect = tuple(_finite_float(value, "valid_rect") for value in valid)
    if valid_rect[2] <= 0 or valid_rect[3] <= 0:
        raise _InvalidResult("valid_rect dimensions must be positive")
    typed_matrix = (
        (matrix[0][0], matrix[0][1], matrix[0][2]),
        (matrix[1][0], matrix[1][1], matrix[1][2]),
        (matrix[2][0], matrix[2][1], matrix[2][2]),
    )
    geometry = SceneGeometry(
        analysis_width=_positive_integer(data, "analysis_width"),
        analysis_height=_positive_integer(data, "analysis_height"),
        source_to_analysis=typed_matrix,
        valid_rect=(valid_rect[0], valid_rect[1], valid_rect[2], valid_rect[3]),
    )
    try:
        source_to_analysis(geometry, np.asarray([[0.0, 0.0]], dtype=np.float64))
    except ValueError as exc:
        raise _InvalidResult(str(exc)) from exc
    return geometry


def _parse_grid(grids: dict[str, Any], attribute_id: str, geometry: SceneGeometry) -> GridGeometry:
    data = grids.get(attribute_id)
    if not isinstance(data, dict):
        raise _InvalidResult(f"missing grid for attribute {attribute_id}")
    grid = GridGeometry(
        rows=_positive_integer(data, "rows"),
        columns=_positive_integer(data, "columns"),
        block_width=_positive_float(data, "block_width"),
        block_height=_positive_float(data, "block_height"),
        origin_x=_finite_float(data.get("origin_x"), "origin_x"),
        origin_y=_finite_float(data.get("origin_y"), "origin_y"),
        discarded_right=_nonnegative_float(data, "discarded_right"),
        discarded_bottom=_nonnegative_float(data, "discarded_bottom"),
    )
    valid_x, valid_y, valid_width, valid_height = geometry.valid_rect
    right = grid.origin_x + grid.columns * grid.block_width
    bottom = grid.origin_y + grid.rows * grid.block_height
    tolerance = 1e-9
    if (
        grid.origin_x < valid_x - tolerance
        or grid.origin_y < valid_y - tolerance
        or right > valid_x + valid_width + tolerance
        or bottom > valid_y + valid_height + tolerance
    ):
        raise _InvalidResult(f"grid {attribute_id} is not contained by valid_rect")
    expected_right = valid_x + valid_width - right
    expected_bottom = valid_y + valid_height - bottom
    if not math.isclose(
        expected_right, grid.discarded_right, abs_tol=tolerance
    ) or not math.isclose(expected_bottom, grid.discarded_bottom, abs_tol=tolerance):
        raise _InvalidResult(f"grid {attribute_id} discarded border metadata mismatch")
    return grid


def _artifact_ref(data: dict[str, Any], key: str, limit: int) -> tuple[str, int]:
    item = data.get(key)
    if not isinstance(item, dict):
        raise _InvalidResult(f"{key} must be an artifact object")
    path = _string(item, "path")
    declared = _positive_integer(item, "uncompressed_size")
    if declared > limit:
        raise _CorruptResult(f"{key} declared size exceeds safety ceiling")
    return path, declared


def _safe_artifact(root: Path, reference: str) -> Path:
    if "\x00" in reference:
        raise _CorruptResult("artifact path contains NUL")
    windows = PureWindowsPath(reference)
    path = Path(reference)
    if path.is_absolute() or windows.is_absolute() or windows.drive or ".." in path.parts:
        raise _CorruptResult("artifact path must be a relative path beneath result root")
    try:
        resolved_root = root.resolve(strict=True)
        resolved = (root / path).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _CorruptResult(f"artifact is missing or escapes result root: {reference}") from exc
    if not resolved.is_file():
        raise _CorruptResult(f"artifact is not a regular file: {reference}")
    return resolved


def _load_npz(
    path: Path,
    total_limit: int,
    expected: dict[str, tuple[np.dtype[Any], tuple[int, ...]]],
    declared_size: int | None = None,
) -> dict[str, np.ndarray[Any, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            actual_total = sum(info.file_size for info in infos)
            if actual_total > total_limit:
                raise _CorruptResult(f"artifact {path.name} exceeds uncompressed safety ceiling")
            if declared_size is not None and actual_total != declared_size:
                raise _CorruptResult(f"artifact {path.name} declared/actual size mismatch")
            names = {info.filename for info in infos}
            expected_names = {f"{key}.npy" for key in expected}
            if names != expected_names:
                raise _CorruptResult(f"artifact {path.name} has unexpected array members")
            for key, (expected_dtype, expected_shape) in expected.items():
                info = archive.getinfo(f"{key}.npy")
                with archive.open(info) as stream:
                    version = npy_format.read_magic(stream)  # type: ignore[no-untyped-call]
                    header_reader: Callable[..., tuple[tuple[int, ...], bool, np.dtype[Any]]]
                    if version == (1, 0):
                        header_reader = npy_format.read_array_header_1_0
                    elif version in {(2, 0), (3, 0)}:
                        header_reader = npy_format.read_array_header_2_0
                    else:
                        raise _CorruptResult(f"unsupported NPY version {version}")
                    shape, _fortran, dtype = header_reader(stream)  # type: ignore[no-untyped-call]
                if dtype.hasobject:
                    raise _CorruptResult(f"object/pickle array rejected: {key}")
                if dtype != expected_dtype or shape != expected_shape:
                    raise _CorruptResult(f"array {key} dtype/rank/shape mismatch: {dtype} {shape}")
                array_bytes = int(dtype.itemsize * math.prod(shape))
                if array_bytes > ARRAY_LIMIT or info.file_size > ARRAY_LIMIT:
                    raise _CorruptResult(f"array {key} exceeds safety ceiling")
        with np.load(path, allow_pickle=False) as loaded:
            return {key: np.asarray(loaded[key]) for key in expected}
    except _CorruptResult:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, EOFError) as exc:
        raise _CorruptResult(f"artifact {path.name} is corrupt: {exc}") from exc


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise _InvalidResult(f"{key} must be a non-empty string")
    return value


def _list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise _InvalidResult(f"{key} must be an array")
    return value


def _integer(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise _InvalidResult(f"{key} must be an integer")
    return value


def _positive_integer(data: dict[str, Any], key: str) -> int:
    value = _integer(data, key)
    if value <= 0:
        raise _InvalidResult(f"{key} must be positive")
    return value


def _finite_float(value: Any, name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise _InvalidResult(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise _InvalidResult(f"{name} must be finite")
    return result


def _positive_float(data: dict[str, Any], key: str) -> float:
    value = _finite_float(data.get(key), key)
    if value <= 0.0:
        raise _InvalidResult(f"{key} must be positive")
    return value


def _nonnegative_float(data: dict[str, Any], key: str) -> float:
    value = _finite_float(data.get(key), key)
    if value < 0.0:
        raise _InvalidResult(f"{key} must be non-negative")
    return value
