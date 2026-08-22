"""Manifest parser and complete-result structural invariants for IQA schema v2."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    ComparisonOperator,
    GridGeometry,
    QualityDirection,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_geometry import source_to_analysis
from pixelscope.remote.iqa_v2_domain import (
    MeasurementContextProvenance,
    SceneV2,
    SourceMeasurementV2,
    Variant,
    build_measurement_context_id,
)
from pixelscope.remote.iqa_v2_support import (
    V2_MAX_ARTIFACT_PATH_LENGTH,
    V2_MAX_ATTRIBUTES,
    V2_MAX_DETAIL_ARTIFACTS,
    V2_MAX_GRID_CELLS,
    V2_MAX_ID_LENGTH,
    V2_MAX_LABEL_LENGTH,
    V2_MAX_PROVENANCE_LENGTH,
    V2_MAX_SCENES,
    V2_MAX_SOURCE_BINDINGS,
    V2_MAX_SOURCE_PATH_LENGTH,
    V2_MAX_VARIANTS,
    V2_SCENE_LIMIT,
    V2_SUMMARY_LIMIT,
    CorruptV2,
    InvalidV2,
    safe_artifact,
    validate_artifact_reference,
)

_ATTRIBUTE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_CONTEXT_ID_PATTERN = re.compile(r"^mc2:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ParsedManifestV2:
    result_id: str
    variants: tuple[Variant, ...]
    attributes: tuple[AttributeSpec, ...]
    scenes: tuple[SceneV2, ...]
    summary_artifact: str
    summary_uncompressed_size: int


def parse_complete_manifest(root: Path, data: dict[str, Any]) -> ParsedManifestV2:
    result_id = bounded_string(data, "result_id", V2_MAX_ID_LENGTH)
    variants_data = bounded_list(data, "variants", V2_MAX_VARIANTS)
    attributes_data = bounded_list(data, "attributes", V2_MAX_ATTRIBUTES)
    scenes_data = bounded_list(data, "scenes", V2_MAX_SCENES)
    if len(variants_data) < 2:
        raise InvalidV2("schema-v2 complete result requires at least two variants")
    if not attributes_data or not scenes_data:
        raise InvalidV2("schema-v2 result requires attributes and scenes")
    variants = tuple(_parse_variant(item) for item in variants_data)
    if len({item.variant_id for item in variants}) != len(variants):
        raise InvalidV2("variant_id values must be unique")
    attributes = tuple(_parse_attribute(item) for item in attributes_data)
    if len({item.attribute_id for item in attributes}) != len(attributes):
        raise InvalidV2("attribute_id values must be unique")
    summary_path, summary_size = artifact_ref(
        data, "summary_artifact", V2_SUMMARY_LIMIT
    )
    safe_artifact(root, summary_path)
    scenes: list[SceneV2] = []
    source_registry: dict[str, Source] = {}
    total_sources = 0
    for item in scenes_data:
        if not isinstance(item, dict):
            raise InvalidV2("scene must be an object")
        scene = _parse_scene(
            root,
            item,
            variants,
            attributes,
            source_registry,
        )
        total_sources += len(scene.sources)
        if total_sources > V2_MAX_SOURCE_BINDINGS:
            raise InvalidV2("result exceeds schema-v2 source-binding safety ceiling")
        scenes.append(scene)
    if len({scene.scene_id for scene in scenes}) != len(scenes):
        raise InvalidV2("scene_id values must be unique")
    return ParsedManifestV2(
        result_id=result_id,
        variants=variants,
        attributes=attributes,
        scenes=tuple(scenes),
        summary_artifact=summary_path,
        summary_uncompressed_size=summary_size,
    )


def _parse_variant(data: Any) -> Variant:
    if not isinstance(data, dict):
        raise InvalidV2("variant must be an object")
    return Variant(
        variant_id=bounded_string(data, "variant_id", V2_MAX_ID_LENGTH),
        label=bounded_string(data, "label", V2_MAX_LABEL_LENGTH),
    )


def _parse_attribute(data: Any) -> AttributeSpec:
    if not isinstance(data, dict):
        raise InvalidV2("attribute must be an object")
    attribute_id = bounded_string(data, "attribute_id", 64)
    if _ATTRIBUTE_ID_PATTERN.fullmatch(attribute_id) is None:
        raise InvalidV2("attribute_id must be lowercase ASCII snake_case")
    try:
        value_kind = ValueKind(bounded_string(data, "value_kind", 32))
        operator = ComparisonOperator(
            bounded_string(data, "comparison_operator", 64)
        )
        direction = QualityDirection(
            bounded_string(data, "quality_direction", 32)
        )
    except ValueError as exc:
        raise InvalidV2(f"invalid attribute enum: {exc}") from exc
    raw_epsilon = data.get("stabilization_epsilon")
    epsilon = (
        None
        if raw_epsilon is None
        else finite_float(raw_epsilon, "stabilization_epsilon")
    )
    if value_kind is ValueKind.POWER and (epsilon is None or epsilon < 0.0):
        raise InvalidV2("power attribute requires non-negative finite epsilon")
    if value_kind is ValueKind.SIGNED and epsilon is not None:
        raise InvalidV2("signed attribute stabilization_epsilon must be null")
    if value_kind is ValueKind.SIGNED and direction is not QualityDirection.NEUTRAL:
        raise InvalidV2("signed attribute must have neutral quality direction")
    if (
        value_kind is ValueKind.POWER
        and operator
        is not ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB
    ):
        raise InvalidV2(
            "power attribute requires power_ratio_target_over_reference_db operator"
        )
    if (
        value_kind is ValueKind.SIGNED
        and operator is not ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE
    ):
        raise InvalidV2(
            "signed attribute requires signed_target_minus_reference operator"
        )
    return AttributeSpec(
        attribute_id=attribute_id,
        name=bounded_string(data, "name", V2_MAX_LABEL_LENGTH),
        value_kind=value_kind,
        comparison_operator=operator,
        quality_direction=direction,
        unit=bounded_string(data, "unit", 128),
        stabilization_epsilon=epsilon,
        weighting_provenance=bounded_string(
            data,
            "weighting_provenance",
            V2_MAX_PROVENANCE_LENGTH,
        ),
    )


def _parse_scene(
    root: Path,
    data: dict[str, Any],
    variants: tuple[Variant, ...],
    attributes: tuple[AttributeSpec, ...],
    source_registry: dict[str, Source],
) -> SceneV2:
    scene_id = bounded_string(data, "scene_id", V2_MAX_ID_LENGTH)
    context_id = bounded_string(data, "measurement_context_id", 68)
    if _CONTEXT_ID_PATTERN.fullmatch(context_id) is None:
        raise InvalidV2("measurement_context_id must be mc2:<64 lowercase hex>")
    provenance = _parse_context_provenance(data.get("context_provenance"))
    source_items = bounded_list(data, "sources", V2_MAX_VARIANTS)
    if len(source_items) != len(variants):
        raise InvalidV2(
            f"complete Scene {scene_id} must bind exactly one source per variant"
        )
    sources = tuple(
        _parse_source_measurement(item, attributes) for item in source_items
    )
    expected_variants = tuple(item.variant_id for item in variants)
    if tuple(item.variant_id for item in sources) != expected_variants:
        raise InvalidV2(
            f"complete Scene {scene_id} source order/bindings must exactly match "
            "top-level variants"
        )
    for measurement in sources:
        source = measurement.source
        registered = source_registry.get(source.source_id)
        if registered is None:
            source_registry[source.source_id] = source
        elif registered != source:
            raise InvalidV2(
                f"source_id {source.source_id} immutable metadata mismatch across bindings"
            )
    if len({(item.source.width, item.source.height) for item in sources}) != 1:
        raise InvalidV2(f"Scene {scene_id} has dimension_mismatch")
    first = sources[0]
    for item in sources[1:]:
        if item.geometry != first.geometry:
            raise InvalidV2(
                f"Scene {scene_id} has source-to-analysis geometry mismatch"
            )
        for attribute in attributes:
            if item.grids[attribute.attribute_id] != first.grids[attribute.attribute_id]:
                raise InvalidV2(
                    f"Scene {scene_id} attribute {attribute.attribute_id} "
                    "has grid geometry mismatch"
                )
    if context_id != build_measurement_context_id(
        scene_id,
        sources,
        attributes,
        provenance,
    ):
        raise InvalidV2(
            f"Scene {scene_id} measurement_context_id fingerprint mismatch"
        )
    grid_path, grid_size = artifact_ref(data, "grid_artifact", V2_SCENE_LIMIT)
    # Ordinary result open validates deferred artifact path syntax only. Existence,
    # containment after symlink resolution, and NPZ contents are checked on demand.
    validate_artifact_reference(grid_path)
    details = data.get("detail_artifacts", [])
    if not isinstance(details, list) or len(details) > V2_MAX_DETAIL_ARTIFACTS:
        raise InvalidV2("detail_artifacts must be a bounded array")
    detail_paths: list[str] = []
    for value in details:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > V2_MAX_ARTIFACT_PATH_LENGTH
        ):
            raise InvalidV2("detail_artifact path is invalid")
        validate_artifact_reference(value)
        detail_paths.append(value)
    return SceneV2(
        scene_id=scene_id,
        measurement_context_id=context_id,
        context_provenance=provenance,
        sources=sources,
        grid_artifact=grid_path,
        grid_uncompressed_size=grid_size,
        detail_artifacts=tuple(detail_paths),
    )


def _parse_source_measurement(
    data: Any,
    attributes: tuple[AttributeSpec, ...],
) -> SourceMeasurementV2:
    if not isinstance(data, dict):
        raise InvalidV2("Scene source binding must be an object")
    sha256 = bounded_string(data, "sha256", 64)
    if len(sha256) != 64 or any(
        char not in "0123456789abcdef" for char in sha256
    ):
        raise InvalidV2(
            "source sha256 must be 64 lowercase hexadecimal characters"
        )
    source = Source(
        source_id=bounded_string(data, "source_id", V2_MAX_ID_LENGTH),
        relative_path=bounded_string(
            data,
            "relative_path",
            V2_MAX_SOURCE_PATH_LENGTH,
        ),
        sha256=sha256,
        width=positive_integer(data, "width"),
        height=positive_integer(data, "height"),
    )
    geometry = _parse_geometry(data.get("geometry"))
    grids_data = data.get("grids")
    if not isinstance(grids_data, dict):
        raise InvalidV2("source grids must be an object")
    expected = {attribute.attribute_id for attribute in attributes}
    if set(grids_data) != expected:
        raise InvalidV2(
            "source grids must contain exactly the declared attribute IDs"
        )
    grids = {
        attribute.attribute_id: _parse_grid(
            grids_data[attribute.attribute_id],
            attribute.attribute_id,
            geometry,
        )
        for attribute in attributes
    }
    return SourceMeasurementV2(
        variant_id=bounded_string(data, "variant_id", V2_MAX_ID_LENGTH),
        source=source,
        geometry=geometry,
        grids=grids,
        summaries={},
    )


def _parse_context_provenance(data: Any) -> MeasurementContextProvenance:
    if not isinstance(data, dict):
        raise InvalidV2("context_provenance must be an object")
    expected = {
        "representative_id",
        "preprocessing_id",
        "model_id",
        "weighting_id",
        "geometry_id",
    }
    if set(data) != expected:
        raise InvalidV2(
            "context_provenance must contain the exact schema-v2 provenance keys"
        )
    return MeasurementContextProvenance(
        representative_id=bounded_string(
            data,
            "representative_id",
            V2_MAX_PROVENANCE_LENGTH,
        ),
        preprocessing_id=bounded_string(
            data,
            "preprocessing_id",
            V2_MAX_PROVENANCE_LENGTH,
        ),
        model_id=bounded_string(
            data,
            "model_id",
            V2_MAX_PROVENANCE_LENGTH,
        ),
        weighting_id=bounded_string(
            data,
            "weighting_id",
            V2_MAX_PROVENANCE_LENGTH,
        ),
        geometry_id=bounded_string(
            data,
            "geometry_id",
            V2_MAX_PROVENANCE_LENGTH,
        ),
    )


def _parse_geometry(data: Any) -> SceneGeometry:
    if not isinstance(data, dict):
        raise InvalidV2("geometry must be an object")
    affine = data.get("source_to_analysis")
    if not isinstance(affine, list) or len(affine) != 3:
        raise InvalidV2("source_to_analysis must be a 3x3 array")
    matrix_rows: list[tuple[float, float, float]] = []
    for row in affine:
        if not isinstance(row, list) or len(row) != 3:
            raise InvalidV2("source_to_analysis must be 3x3")
        matrix_rows.append(
            (
                finite_float(row[0], "source_to_analysis"),
                finite_float(row[1], "source_to_analysis"),
                finite_float(row[2], "source_to_analysis"),
            )
        )
    matrix = tuple(matrix_rows)
    raw_rect = data.get("valid_rect")
    if not isinstance(raw_rect, list) or len(raw_rect) != 4:
        raise InvalidV2("valid_rect must have four values")
    valid = tuple(finite_float(value, "valid_rect") for value in raw_rect)
    if valid[2] <= 0.0 or valid[3] <= 0.0:
        raise InvalidV2("valid_rect dimensions must be positive")
    geometry = SceneGeometry(
        analysis_width=positive_integer(data, "analysis_width"),
        analysis_height=positive_integer(data, "analysis_height"),
        source_to_analysis=matrix,
        valid_rect=(valid[0], valid[1], valid[2], valid[3]),
    )
    x, y, width, height = geometry.valid_rect
    if (
        x < 0.0
        or y < 0.0
        or x + width > geometry.analysis_width
        or y + height > geometry.analysis_height
    ):
        raise InvalidV2("valid_rect must be contained by the analysis image")
    try:
        source_to_analysis(
            geometry,
            np.asarray([[0.0, 0.0]], dtype=np.float64),
        )
    except ValueError as exc:
        raise InvalidV2(str(exc)) from exc
    return geometry


def _parse_grid(
    data: Any,
    attribute_id: str,
    geometry: SceneGeometry,
) -> GridGeometry:
    if not isinstance(data, dict):
        raise InvalidV2(f"grid {attribute_id} must be an object")
    grid = GridGeometry(
        rows=positive_integer(data, "rows"),
        columns=positive_integer(data, "columns"),
        block_width=positive_float(data, "block_width"),
        block_height=positive_float(data, "block_height"),
        origin_x=finite_float(data.get("origin_x"), "origin_x"),
        origin_y=finite_float(data.get("origin_y"), "origin_y"),
        discarded_right=nonnegative_float(data, "discarded_right"),
        discarded_bottom=nonnegative_float(data, "discarded_bottom"),
    )
    if grid.rows * grid.columns > V2_MAX_GRID_CELLS:
        raise InvalidV2(
            f"grid {attribute_id} exceeds schema-v2 cell safety ceiling"
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
        raise InvalidV2(f"grid {attribute_id} is not contained by valid_rect")
    expected_right = valid_x + valid_width - right
    expected_bottom = valid_y + valid_height - bottom
    if not math.isclose(
        expected_right,
        grid.discarded_right,
        abs_tol=tolerance,
    ) or not math.isclose(
        expected_bottom,
        grid.discarded_bottom,
        abs_tol=tolerance,
    ):
        raise InvalidV2(
            f"grid {attribute_id} discarded border metadata mismatch"
        )
    return grid


def artifact_ref(
    data: dict[str, Any],
    key: str,
    limit: int,
) -> tuple[str, int]:
    item = data.get(key)
    if not isinstance(item, dict):
        raise InvalidV2(f"{key} must be an artifact object")
    path = bounded_string(item, "path", V2_MAX_ARTIFACT_PATH_LENGTH)
    declared = positive_integer(item, "uncompressed_size")
    if declared > limit:
        raise CorruptV2(
            f"{key} declared size exceeds schema-v2 safety ceiling"
        )
    return path, declared


def bounded_string(
    data: dict[str, Any],
    key: str,
    maximum: int,
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise InvalidV2(f"{key} must be a non-empty string")
    if len(value) > maximum:
        raise InvalidV2(f"{key} exceeds schema-v2 string safety ceiling")
    return value


def bounded_list(
    data: dict[str, Any],
    key: str,
    maximum: int,
) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise InvalidV2(f"{key} must be an array")
    if len(value) > maximum:
        raise InvalidV2(f"{key} exceeds schema-v2 list safety ceiling")
    return value


def integer(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidV2(f"{key} must be an integer")
    return value


def positive_integer(data: dict[str, Any], key: str) -> int:
    value = integer(data, key)
    if value <= 0:
        raise InvalidV2(f"{key} must be positive")
    return value


def finite_float(value: Any, name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise InvalidV2(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise InvalidV2(f"{name} must be finite")
    return result


def positive_float(data: dict[str, Any], key: str) -> float:
    value = finite_float(data.get(key), key)
    if value <= 0.0:
        raise InvalidV2(f"{key} must be positive")
    return value


def nonnegative_float(data: dict[str, Any], key: str) -> float:
    value = finite_float(data.get(key), key)
    if value < 0.0:
        raise InvalidV2(f"{key} must be non-negative")
    return value
