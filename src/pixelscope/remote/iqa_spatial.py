"""Qt-free per-cell spatial derivation for schema-v2 IQA Scene inspection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from pixelscope.remote.iqa_domain import (
    CompactAttributeData,
    GridGeometry,
    SceneGeometry,
    ValueKind,
)
from pixelscope.remote.iqa_geometry import source_cell_polygon, source_point_to_grid_cell
from pixelscope.remote.iqa_v2_domain import GridSceneDataV2, ResultV2
from pixelscope.remote.iqa_v2_math import power_log_ratio


class SpatialMode(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass(frozen=True)
class SpatialVariantField:
    variant_id: str
    source_id: str
    values: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    cell_means: NDArray[np.float64]
    data: CompactAttributeData


@dataclass(frozen=True)
class SpatialSceneField:
    scene_id: str
    attribute_id: str
    unit: str
    mode: SpatialMode
    reference_variant_id: str | None
    geometry: SceneGeometry
    grid: GridGeometry
    variants: tuple[SpatialVariantField, ...]
    scale_min: float
    scale_max: float

    def variant(self, variant_id: str) -> SpatialVariantField:
        return next(item for item in self.variants if item.variant_id == variant_id)


@dataclass(frozen=True)
class SpatialCellDetail:
    scene_id: str
    attribute_id: str
    variant_id: str
    source_id: str
    row: int
    column: int
    valid: bool
    weight_sum: float
    weighted_sum: float
    weighted_square_sum: float
    valid_count: int
    cell_mean: float | None
    relative_value: float | None
    reference_variant_id: str | None
    reference_source_id: str | None
    pair_valid: bool | None
    reference_cell_mean: float | None
    analysis_bounds: tuple[float, float, float, float]
    source_polygon: tuple[tuple[float, float], ...]


def derive_spatial_scene(
    result: ResultV2,
    scene_id: str,
    grid_data: GridSceneDataV2,
    attribute_id: str,
    reference_variant_id: str | None = None,
) -> SpatialSceneField:
    """Derive the raw per-cell field underlying the scalar schema-v2 reductions."""

    scene = result.scene(scene_id)
    spec = result.attribute(attribute_id)
    if grid_data.scene_id != scene_id:
        raise ValueError("loaded grid Scene does not match the requested Scene")
    if grid_data.measurement_context_id != scene.measurement_context_id:
        raise ValueError("loaded grid measurement context does not match the Scene")
    expected_variants = tuple(item.variant_id for item in scene.sources)
    expected_sources = tuple(item.source.source_id for item in scene.sources)
    if grid_data.variant_ids != expected_variants or grid_data.source_ids != expected_sources:
        raise ValueError("loaded grid source identity/order does not match the Scene")
    if reference_variant_id is not None and reference_variant_id not in expected_variants:
        raise ValueError("reference variant is not present in the Scene")

    source_data: dict[str, CompactAttributeData] = {}
    source_means: dict[str, NDArray[np.float64]] = {}
    source_valid: dict[str, NDArray[np.bool_]] = {}
    for variant_id in expected_variants:
        data = grid_data.attribute_for_variant(variant_id, attribute_id)
        means, valid = _cell_means(data, spec.value_kind)
        source_data[variant_id] = data
        source_means[variant_id] = means
        source_valid[variant_id] = valid

    fields: list[SpatialVariantField] = []
    if reference_variant_id is None:
        for measurement in scene.sources:
            variant_id = measurement.variant_id
            fields.append(
                SpatialVariantField(
                    variant_id=variant_id,
                    source_id=measurement.source.source_id,
                    values=source_means[variant_id].copy(),
                    valid_mask=source_valid[variant_id].copy(),
                    cell_means=source_means[variant_id],
                    data=source_data[variant_id],
                )
            )
        mode = SpatialMode.ABSOLUTE
    else:
        reference_means = source_means[reference_variant_id]
        reference_valid = source_valid[reference_variant_id]
        epsilon = spec.stabilization_epsilon
        if spec.value_kind is ValueKind.POWER and (
            epsilon is None or not math.isfinite(epsilon) or epsilon < 0.0
        ):
            raise ValueError("power attribute requires valid stabilization epsilon")
        for measurement in scene.sources:
            variant_id = measurement.variant_id
            target_means = source_means[variant_id]
            pair_valid = source_valid[variant_id] & reference_valid
            values = np.full(target_means.shape, np.nan, dtype=np.float64)
            if spec.value_kind is ValueKind.SIGNED:
                values[pair_valid] = target_means[pair_valid] - reference_means[pair_valid]
                pair_valid &= np.isfinite(values)
            else:
                assert epsilon is not None
                for row, column in np.argwhere(pair_valid):
                    statistic = power_log_ratio(
                        float(target_means[row, column]),
                        float(reference_means[row, column]),
                        epsilon,
                    )
                    if statistic.valid and statistic.value is not None:
                        values[row, column] = statistic.value
                    else:
                        pair_valid[row, column] = False
            fields.append(
                SpatialVariantField(
                    variant_id=variant_id,
                    source_id=measurement.source.source_id,
                    values=values,
                    valid_mask=pair_valid,
                    cell_means=target_means,
                    data=source_data[variant_id],
                )
            )
        mode = SpatialMode.RELATIVE

    scale_min, scale_max = _shared_scale(fields, spec.value_kind, mode)
    relative_power = mode is SpatialMode.RELATIVE and spec.value_kind is ValueKind.POWER
    return SpatialSceneField(
        scene_id=scene_id,
        attribute_id=attribute_id,
        unit="dB" if relative_power else spec.unit,
        mode=mode,
        reference_variant_id=reference_variant_id,
        geometry=scene.geometry,
        grid=scene.grid(attribute_id),
        variants=tuple(fields),
        scale_min=scale_min,
        scale_max=scale_max,
    )


def spatial_cell_detail(
    result: ResultV2,
    field: SpatialSceneField,
    variant_id: str,
    row: int,
    column: int,
) -> SpatialCellDetail:
    """Return bounded published sufficient-statistic detail for one displayed cell."""

    scene = result.scene(field.scene_id)
    measurement = scene.source_for_variant(variant_id)
    variant = field.variant(variant_id)
    if not (0 <= row < field.grid.rows and 0 <= column < field.grid.columns):
        raise IndexError("spatial cell outside declared grid")
    data = variant.data
    weight = float(np.asarray(data.weight_sum)[row, column])
    weighted = float(np.asarray(data.weighted_sum)[row, column])
    squared = float(np.asarray(data.weighted_square_sum)[row, column])
    count = int(np.asarray(data.valid_count)[row, column])
    source_valid = bool(np.asarray(data.valid_mask, dtype=np.bool_)[row, column])
    cell_mean = float(variant.cell_means[row, column]) if source_valid else None
    display_valid = bool(variant.valid_mask[row, column])
    relative_value = float(variant.values[row, column]) if display_valid else None

    reference_variant_id = field.reference_variant_id
    reference_source_id: str | None = None
    reference_cell_mean: float | None = None
    pair_valid: bool | None = None
    if reference_variant_id is not None:
        reference = field.variant(reference_variant_id)
        reference_source_id = reference.source_id
        reference_source_valid = bool(
            np.asarray(reference.data.valid_mask, dtype=np.bool_)[row, column]
        )
        if reference_source_valid:
            reference_cell_mean = float(reference.cell_means[row, column])
        pair_valid = display_valid

    polygon = source_cell_polygon(
        field.geometry,
        field.grid,
        row,
        column,
        measurement.source.width,
        measurement.source.height,
    )
    left = field.grid.origin_x + column * field.grid.block_width
    top = field.grid.origin_y + row * field.grid.block_height
    return SpatialCellDetail(
        scene_id=field.scene_id,
        attribute_id=field.attribute_id,
        variant_id=variant_id,
        source_id=variant.source_id,
        row=row,
        column=column,
        valid=source_valid,
        weight_sum=weight,
        weighted_sum=weighted,
        weighted_square_sum=squared,
        valid_count=count,
        cell_mean=cell_mean,
        relative_value=relative_value,
        reference_variant_id=reference_variant_id,
        reference_source_id=reference_source_id,
        pair_valid=pair_valid,
        reference_cell_mean=reference_cell_mean,
        analysis_bounds=(left, top, field.grid.block_width, field.grid.block_height),
        source_polygon=tuple((float(x), float(y)) for x, y in polygon.tolist()),
    )


def hit_test_spatial_cell(
    field: SpatialSceneField,
    variant_id: str,
    source_x: float,
    source_y: float,
) -> tuple[int, int] | None:
    """Return the geometric grid cell even when the published cell is invalid.

    Overlay drawing filters invalid/pair-invalid cells, while the inspector still
    needs the same geometric hit test so it can report that a published cell is
    invalid rather than pretending that no grid cell exists.
    """

    field.variant(variant_id)
    return source_point_to_grid_cell(
        field.geometry,
        field.grid,
        source_x,
        source_y,
    )


def source_polygons_for_variant(
    result: ResultV2,
    field: SpatialSceneField,
    variant_id: str,
) -> tuple[tuple[int, int, tuple[tuple[float, float], ...]], ...]:
    """Return vector source polygons for valid cells; no full-resolution bitmap is created."""

    measurement = result.scene(field.scene_id).source_for_variant(variant_id)
    variant = field.variant(variant_id)
    polygons: list[tuple[int, int, tuple[tuple[float, float], ...]]] = []
    for row, column in np.argwhere(variant.valid_mask):
        polygon = source_cell_polygon(
            field.geometry,
            field.grid,
            int(row),
            int(column),
            measurement.source.width,
            measurement.source.height,
        )
        if polygon.shape[0] >= 3:
            polygons.append(
                (
                    int(row),
                    int(column),
                    tuple((float(x), float(y)) for x, y in polygon.tolist()),
                )
            )
    return tuple(polygons)


def _cell_means(
    data: CompactAttributeData,
    value_kind: ValueKind,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    weight = np.asarray(data.weight_sum, dtype=np.float64)
    weighted = np.asarray(data.weighted_sum, dtype=np.float64)
    squared = np.asarray(data.weighted_square_sum, dtype=np.float64)
    count = np.asarray(data.valid_count)
    valid = np.asarray(data.valid_mask, dtype=np.bool_).copy()
    if not (weight.shape == weighted.shape == squared.shape == count.shape == valid.shape):
        raise ValueError("grid sufficient-statistic shapes must match")
    if weight.ndim != 2:
        raise ValueError("spatial IQA grid must be two-dimensional")
    invalid_published = valid & (
        ~np.isfinite(weight)
        | ~np.isfinite(weighted)
        | ~np.isfinite(squared)
        | (weight <= 0.0)
        | (count <= 0)
        | (squared < 0.0)
    )
    if np.any(invalid_published):
        raise ValueError("published valid grid cell has invalid sufficient statistics")
    if value_kind is ValueKind.POWER and np.any(valid & (weighted < 0.0)):
        raise ValueError("published power grid contains negative weighted sum")
    means = np.full(weight.shape, np.nan, dtype=np.float64)
    means[valid] = weighted[valid] / weight[valid]
    if np.any(valid & ~np.isfinite(means)):
        raise ValueError("published valid grid cell has non-finite mean")
    if value_kind is ValueKind.POWER and np.any(valid & (means < 0.0)):
        raise ValueError("published power grid contains negative mean")
    return means, valid


def _shared_scale(
    fields: list[SpatialVariantField],
    value_kind: ValueKind,
    mode: SpatialMode,
) -> tuple[float, float]:
    finite: list[float] = []
    for field in fields:
        values = field.values[field.valid_mask]
        finite.extend(float(value) for value in values[np.isfinite(values)].tolist())
    if not finite:
        return -1.0, 1.0
    minimum = min(finite)
    maximum = max(finite)
    center_zero = mode is SpatialMode.RELATIVE or value_kind is ValueKind.SIGNED
    if center_zero:
        extent = max(abs(minimum), abs(maximum), float(np.finfo(np.float64).eps))
        return -extent, extent
    if math.isclose(minimum, maximum):
        padding = max(abs(minimum) * 0.05, 1e-12)
        return minimum - padding, maximum + padding
    return minimum, maximum
