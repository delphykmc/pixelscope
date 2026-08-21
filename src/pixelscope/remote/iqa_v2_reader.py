"""Safe summary-first reader for immutable PixelScope Remote IQA schema-v2 results."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    LoadStatus,
    ScalarStatistic,
    ValueKind,
)
from pixelscope.remote.iqa_v2_domain import (
    DatasetSummaryV2,
    GridLoadOutcomeV2,
    GridSceneDataV2,
    MeasurementSummary,
    ResultV2,
    SceneV2,
    SourceMeasurementV2,
    Variant,
    VersionedResultLoadOutcome,
)
from pixelscope.remote.iqa_v2_manifest import integer, parse_complete_manifest
from pixelscope.remote.iqa_v2_math import (
    projection_matches,
    summary_from_accumulators,
    summary_from_grid,
)
from pixelscope.remote.iqa_v2_support import (
    CorruptV2,
    InvalidV2,
    UnsupportedV2,
    V2_ARCHIVE_ON_DISK_LIMIT,
    V2_ARRAY_LIMIT,
    V2_MANIFEST_LIMIT,
    V2_MAX_ATTRIBUTES,
    V2_MAX_DETAIL_ARTIFACTS,
    V2_MAX_GRID_CELLS,
    V2_MAX_SCENES,
    V2_MAX_SOURCE_BINDINGS,
    V2_MAX_VARIANTS,
    V2_NPZ_MEMBER_LIMIT,
    V2_NPY_MEMBER_SIZE_LIMIT,
    V2_SCENE_LIMIT,
    V2_SUMMARY_LIMIT,
    load_npz,
    read_manifest,
    safe_artifact,
)

__all__ = [
    "V2_ARCHIVE_ON_DISK_LIMIT",
    "V2_ARRAY_LIMIT",
    "V2_MANIFEST_LIMIT",
    "V2_MAX_ATTRIBUTES",
    "V2_MAX_DETAIL_ARTIFACTS",
    "V2_MAX_GRID_CELLS",
    "V2_MAX_SCENES",
    "V2_MAX_SOURCE_BINDINGS",
    "V2_MAX_VARIANTS",
    "V2_NPZ_MEMBER_LIMIT",
    "V2_NPY_MEMBER_SIZE_LIMIT",
    "V2_SCENE_LIMIT",
    "V2_SUMMARY_LIMIT",
    "load_grid_scene",
    "load_result_v2",
]


def load_result_v2(root: Path | str) -> VersionedResultLoadOutcome:
    result_root = Path(root)
    try:
        manifest = read_manifest(result_root)
        if manifest.get("kind") != "pixelscope-iqa-result":
            raise InvalidV2("manifest kind must be pixelscope-iqa-result")
        version = integer(manifest, "schema_version")
        if version != 2:
            raise UnsupportedV2(f"schema-v2 reader cannot read schema_version {version}")
        state = manifest.get("publication_state")
        if state == "partial":
            raise UnsupportedV2(
                "schema-v2 PARTIAL terminal details are reserved for P5-C; "
                "successful Scene representation remains version-compatible"
            )
        if state != "complete":
            raise InvalidV2("schema-v2 publication_state must be complete or partial")
        parsed = parse_complete_manifest(result_root, manifest)
        summary_path = safe_artifact(result_root, parsed.summary_artifact)
        arrays = _load_summary(
            summary_path,
            parsed.summary_uncompressed_size,
            len(parsed.scenes),
            len(parsed.variants),
            len(parsed.attributes),
        )
        _validate_summary_identity(arrays, parsed.scenes, parsed.variants, parsed.attributes)
        scenes = _populate_scene_summaries(parsed.scenes, parsed.attributes, arrays)
        dataset = _parse_dataset_summaries(
            scenes, parsed.variants, parsed.attributes, arrays
        )
        return VersionedResultLoadOutcome(
            LoadStatus.SUCCESS,
            result=ResultV2(
                root=result_root.resolve(),
                result_id=parsed.result_id,
                schema_version=2,
                variants=parsed.variants,
                attributes=parsed.attributes,
                scenes=scenes,
                dataset_summaries=dataset,
                summary_artifact=parsed.summary_artifact,
            ),
        )
    except UnsupportedV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.UNSUPPORTED, reason=str(exc))
    except InvalidV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.INVALID, reason=str(exc))
    except CorruptV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.CORRUPT, reason=str(exc))


def load_grid_scene(result: ResultV2, scene_id: str) -> GridLoadOutcomeV2:
    try:
        try:
            scene = result.scene(scene_id)
        except StopIteration as exc:
            raise InvalidV2(f"unknown scene_id {scene_id}") from exc
        source_count = len(scene.sources)
        expected: dict[str, tuple[np.dtype[Any], tuple[int, ...]]] = {
            "variant_ids": (np.dtype("<U128"), (source_count,)),
            "source_ids": (np.dtype("<U128"), (source_count,)),
            "measurement_context_id": (np.dtype("<U68"), (1,)),
        }
        for attribute in result.attributes:
            grid = scene.grid(attribute.attribute_id)
            shape = (source_count, grid.rows, grid.columns)
            prefix = f"{attribute.attribute_id}__"
            expected[prefix + "weight_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "weighted_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "weighted_square_sum"] = (np.dtype("float64"), shape)
            expected[prefix + "valid_count"] = (np.dtype("int32"), shape)
            expected[prefix + "valid_mask"] = (np.dtype("bool"), shape)
        arrays = load_npz(
            safe_artifact(result.root, scene.grid_artifact),
            total_limit=V2_SCENE_LIMIT,
            expected=expected,
            declared_size=scene.grid_uncompressed_size,
        )
        variants = tuple(item.variant_id for item in scene.sources)
        sources = tuple(item.source.source_id for item in scene.sources)
        if tuple(str(value) for value in arrays["variant_ids"].tolist()) != variants:
            raise CorruptV2("grid artifact variant identity/order mismatch")
        if tuple(str(value) for value in arrays["source_ids"].tolist()) != sources:
            raise CorruptV2("grid artifact source identity/order mismatch")
        if str(arrays["measurement_context_id"][0]) != scene.measurement_context_id:
            raise CorruptV2("grid artifact measurement_context_id mismatch")
        attributes: dict[str, CompactAttributeData] = {}
        for attribute in result.attributes:
            prefix = f"{attribute.attribute_id}__"
            data = CompactAttributeData(
                arrays[prefix + "weight_sum"],
                arrays[prefix + "weighted_sum"],
                arrays[prefix + "weighted_square_sum"],
                arrays[prefix + "valid_count"],
                arrays[prefix + "valid_mask"],
            )
            attributes[attribute.attribute_id] = data
            for index, measurement in enumerate(scene.sources):
                sliced = CompactAttributeData(
                    np.asarray(data.weight_sum)[index],
                    np.asarray(data.weighted_sum)[index],
                    np.asarray(data.weighted_square_sum)[index],
                    np.asarray(data.valid_count)[index],
                    np.asarray(data.valid_mask)[index],
                )
                try:
                    recomposed = summary_from_grid(sliced, attribute.value_kind)
                except ValueError as exc:
                    raise CorruptV2(
                        f"grid numerical safety failure for {scene.scene_id}/"
                        f"{measurement.variant_id}/{attribute.attribute_id}: {exc}"
                    ) from exc
                _assert_summary_matches_grid(
                    measurement.summary(attribute.attribute_id),
                    recomposed,
                    scene.scene_id,
                    measurement.variant_id,
                    attribute.attribute_id,
                )
        return GridLoadOutcomeV2(
            LoadStatus.SUCCESS,
            GridSceneDataV2(
                scene.scene_id,
                scene.measurement_context_id,
                variants,
                sources,
                attributes,
            ),
        )
    except InvalidV2 as exc:
        return GridLoadOutcomeV2(LoadStatus.INVALID, reason=str(exc))
    except CorruptV2 as exc:
        return GridLoadOutcomeV2(LoadStatus.CORRUPT, reason=str(exc))


def _load_summary(
    path: Path,
    declared_size: int,
    scene_count: int,
    variant_count: int,
    attribute_count: int,
) -> dict[str, np.ndarray[Any, Any]]:
    scene_shape = (scene_count, variant_count, attribute_count)
    dataset_shape = (variant_count, attribute_count)
    expected: dict[str, tuple[np.dtype[Any], tuple[int, ...]]] = {
        "scene_ids": (np.dtype("<U128"), (scene_count,)),
        "variant_ids": (np.dtype("<U128"), (variant_count,)),
        "attribute_ids": (np.dtype("<U64"), (attribute_count,)),
        "source_ids": (np.dtype("<U128"), (scene_count, variant_count)),
        "measurement_context_ids": (np.dtype("<U68"), (scene_count,)),
        "scene_weight_sum": (np.dtype("float64"), scene_shape),
        "scene_weighted_sum": (np.dtype("float64"), scene_shape),
        "scene_weighted_square_sum": (np.dtype("float64"), scene_shape),
        "scene_valid_count": (np.dtype("int64"), scene_shape),
        "scene_valid": (np.dtype("bool"), scene_shape),
        "scene_weighted_mean": (np.dtype("float64"), scene_shape),
        "scene_weighted_std": (np.dtype("float64"), scene_shape),
        "pooled_weight_sum": (np.dtype("float64"), dataset_shape),
        "pooled_weighted_sum": (np.dtype("float64"), dataset_shape),
        "pooled_weighted_square_sum": (np.dtype("float64"), dataset_shape),
        "pooled_valid_count": (np.dtype("int64"), dataset_shape),
        "pooled_valid": (np.dtype("bool"), dataset_shape),
        "pooled_weighted_mean": (np.dtype("float64"), dataset_shape),
        "pooled_weighted_std": (np.dtype("float64"), dataset_shape),
        "scene_mean": (np.dtype("float64"), dataset_shape),
        "scene_std": (np.dtype("float64"), dataset_shape),
        "scene_count": (np.dtype("int32"), dataset_shape),
        "equal_scene_valid": (np.dtype("bool"), dataset_shape),
    }
    return load_npz(
        path,
        total_limit=V2_SUMMARY_LIMIT,
        expected=expected,
        declared_size=declared_size,
    )


def _validate_summary_identity(
    arrays: dict[str, np.ndarray[Any, Any]],
    scenes: tuple[SceneV2, ...],
    variants: tuple[Variant, ...],
    attributes: tuple[AttributeSpec, ...],
) -> None:
    if tuple(str(value) for value in arrays["scene_ids"].tolist()) != tuple(
        scene.scene_id for scene in scenes
    ):
        raise CorruptV2("summary scene identity/order mismatch")
    if tuple(str(value) for value in arrays["variant_ids"].tolist()) != tuple(
        item.variant_id for item in variants
    ):
        raise CorruptV2("summary variant identity/order mismatch")
    if tuple(str(value) for value in arrays["attribute_ids"].tolist()) != tuple(
        item.attribute_id for item in attributes
    ):
        raise CorruptV2("summary attribute identity/order mismatch")
    if tuple(str(value) for value in arrays["measurement_context_ids"].tolist()) != tuple(
        scene.measurement_context_id for scene in scenes
    ):
        raise CorruptV2("summary measurement_context_id identity/order mismatch")
    expected_sources = tuple(
        tuple(measurement.source.source_id for measurement in scene.sources)
        for scene in scenes
    )
    actual_sources = tuple(
        tuple(str(value) for value in row) for row in arrays["source_ids"].tolist()
    )
    if actual_sources != expected_sources:
        raise CorruptV2("summary source identity/order mismatch")


def _populate_scene_summaries(
    scenes: tuple[SceneV2, ...],
    attributes: tuple[AttributeSpec, ...],
    arrays: dict[str, np.ndarray[Any, Any]],
) -> tuple[SceneV2, ...]:
    populated: list[SceneV2] = []
    for scene_index, scene in enumerate(scenes):
        sources: list[SourceMeasurementV2] = []
        for variant_index, source in enumerate(scene.sources):
            summaries = {
                attribute.attribute_id: _published_summary(
                    arrays,
                    (scene_index, variant_index, attribute_index),
                    attribute.value_kind,
                    "scene_",
                    f"{scene.scene_id}/{source.variant_id}/{attribute.attribute_id}",
                )
                for attribute_index, attribute in enumerate(attributes)
            }
            sources.append(replace(source, summaries=summaries))
        populated.append(replace(scene, sources=tuple(sources)))
    return tuple(populated)


def _parse_dataset_summaries(
    scenes: tuple[SceneV2, ...],
    variants: tuple[Variant, ...],
    attributes: tuple[AttributeSpec, ...],
    arrays: dict[str, np.ndarray[Any, Any]],
) -> dict[tuple[str, str], DatasetSummaryV2]:
    result: dict[tuple[str, str], DatasetSummaryV2] = {}
    for variant_index, variant in enumerate(variants):
        for attribute_index, attribute in enumerate(attributes):
            index = (variant_index, attribute_index)
            identity = f"dataset/{variant.variant_id}/{attribute.attribute_id}"
            pooled = _published_summary(
                arrays, index, attribute.value_kind, "pooled_", identity
            )
            scene_summaries = [
                scene.source_for_variant(variant.variant_id).summary(attribute.attribute_id)
                for scene in scenes
            ]
            contributing = [item for item in scene_summaries if item.valid]
            if not contributing:
                _validate_empty_dataset(arrays, index, pooled, identity)
                result[(variant.variant_id, attribute.attribute_id)] = DatasetSummaryV2(
                    pooled,
                    ScalarStatistic.invalid("no_valid_scenes"),
                    ScalarStatistic.invalid("no_valid_scenes"),
                    0,
                )
                continue
            _validate_pooled(pooled, contributing, identity)
            means = [
                float(item.weighted_mean)
                for item in contributing
                if item.weighted_mean is not None
            ]
            expected_mean = math.fsum(means) / len(means)
            expected_variance = (
                math.fsum((value - expected_mean) ** 2 for value in means) / len(means)
            )
            expected_std = math.sqrt(max(0.0, expected_variance))
            count = int(arrays["scene_count"][index])
            mean = float(arrays["scene_mean"][index])
            std = float(arrays["scene_std"][index])
            if not bool(arrays["equal_scene_valid"][index]) or count != len(means):
                raise CorruptV2(f"{identity} equal-Scene validity/count mismatch")
            if not projection_matches(mean, expected_mean) or not projection_matches(
                std, expected_std
            ):
                raise CorruptV2(f"{identity} equal-Scene projection mismatch")
            result[(variant.variant_id, attribute.attribute_id)] = DatasetSummaryV2(
                pooled, ScalarStatistic(mean, True), ScalarStatistic(std, True), count
            )
    return result


def _published_summary(
    arrays: dict[str, np.ndarray[Any, Any]],
    index: tuple[int, ...],
    value_kind: ValueKind,
    prefix: str,
    identity: str,
) -> MeasurementSummary:
    try:
        recomposed = summary_from_accumulators(
            weight_sum=float(arrays[prefix + "weight_sum"][index]),
            weighted_sum=float(arrays[prefix + "weighted_sum"][index]),
            weighted_square_sum=float(arrays[prefix + "weighted_square_sum"][index]),
            valid_count=int(arrays[prefix + "valid_count"][index]),
            valid=bool(arrays[prefix + "valid"][index]),
            value_kind=value_kind,
        )
    except ValueError as exc:
        raise CorruptV2(f"{identity} accumulator safety failure: {exc}") from exc
    mean = float(arrays[prefix + "weighted_mean"][index])
    std = float(arrays[prefix + "weighted_std"][index])
    if not recomposed.valid:
        if mean != 0.0 or std != 0.0:
            raise CorruptV2(f"{identity} invalid summary projections must be zero")
        return recomposed
    assert recomposed.weighted_mean is not None and recomposed.weighted_std is not None
    if not projection_matches(mean, recomposed.weighted_mean) or not projection_matches(
        std, recomposed.weighted_std
    ):
        raise CorruptV2(f"{identity} summary projection mismatch")
    return replace(recomposed, weighted_mean=mean, weighted_std=std)


def _validate_pooled(
    published: MeasurementSummary,
    contributing: list[MeasurementSummary],
    identity: str,
) -> None:
    if not published.valid:
        raise CorruptV2(f"{identity} pooled validity mismatch")
    expected_count = sum(item.valid_count for item in contributing)
    if published.valid_count != expected_count:
        raise CorruptV2(f"{identity} pooled valid_count mismatch")
    expected = (
        math.fsum(item.weight_sum for item in contributing),
        math.fsum(item.weighted_sum for item in contributing),
        math.fsum(item.weighted_square_sum for item in contributing),
    )
    actual = (published.weight_sum, published.weighted_sum, published.weighted_square_sum)
    for name, actual_value, expected_value in zip(
        ("weight_sum", "weighted_sum", "weighted_square_sum"),
        actual,
        expected,
        strict=True,
    ):
        if not projection_matches(actual_value, expected_value):
            raise CorruptV2(f"{identity} pooled {name} mismatch")


def _validate_empty_dataset(
    arrays: dict[str, np.ndarray[Any, Any]],
    index: tuple[int, int],
    pooled: MeasurementSummary,
    identity: str,
) -> None:
    if pooled.valid:
        raise CorruptV2(f"{identity} pooled validity mismatch")
    if bool(arrays["equal_scene_valid"][index]) or int(arrays["scene_count"][index]) != 0:
        raise CorruptV2(f"{identity} equal-Scene validity/count mismatch")
    if (
        float(arrays["scene_mean"][index]) != 0.0
        or float(arrays["scene_std"][index]) != 0.0
    ):
        raise CorruptV2(f"{identity} invalid equal-Scene projections must be zero")


def _assert_summary_matches_grid(
    published: MeasurementSummary,
    recomposed: MeasurementSummary,
    scene_id: str,
    variant_id: str,
    attribute_id: str,
) -> None:
    identity = f"{scene_id}/{variant_id}/{attribute_id}"
    if published.valid != recomposed.valid:
        raise CorruptV2(f"{identity} grid/summary validity mismatch")
    if published.valid_count != recomposed.valid_count:
        raise CorruptV2(f"{identity} grid/summary valid_count mismatch")
    if not published.valid:
        return
    for name in ("weight_sum", "weighted_sum", "weighted_square_sum"):
        if not projection_matches(
            float(getattr(published, name)), float(getattr(recomposed, name))
        ):
            raise CorruptV2(f"{identity} grid/summary {name} mismatch")
