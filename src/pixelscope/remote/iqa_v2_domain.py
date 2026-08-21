"""Qt-free executable domain for Remote IQA schema v2."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    GridGeometry,
    LoadStatus,
    Result,
    ScalarStatistic,
    SceneGeometry,
    Source,
)

MEASUREMENT_CONTEXT_PREFIX = "mc2:"


@dataclass(frozen=True)
class Variant:
    variant_id: str
    label: str


@dataclass(frozen=True)
class MeasurementContextProvenance:
    representative_id: str
    preprocessing_id: str
    model_id: str
    weighting_id: str
    geometry_id: str


@dataclass(frozen=True)
class MeasurementSummary:
    weight_sum: float
    weighted_sum: float
    weighted_square_sum: float
    valid_count: int
    valid: bool
    weighted_mean: float | None
    weighted_std: float | None

    @classmethod
    def invalid(cls) -> MeasurementSummary:
        return cls(0.0, 0.0, 0.0, 0, False, None, None)


@dataclass(frozen=True)
class DatasetSummaryV2:
    pooled: MeasurementSummary
    scene_mean: ScalarStatistic
    scene_std: ScalarStatistic
    scene_count: int


@dataclass(frozen=True)
class RelativeStatisticV2:
    """One local target/reference statistic in engineering and quality orientation."""

    raw: ScalarStatistic
    quality: ScalarStatistic


@dataclass(frozen=True)
class SourceMeasurementV2:
    variant_id: str
    source: Source
    geometry: SceneGeometry
    grids: dict[str, GridGeometry]
    summaries: dict[str, MeasurementSummary]

    def summary(self, attribute_id: str) -> MeasurementSummary:
        return self.summaries[attribute_id]


@dataclass(frozen=True)
class SceneV2:
    scene_id: str
    measurement_context_id: str
    context_provenance: MeasurementContextProvenance
    sources: tuple[SourceMeasurementV2, ...]
    grid_artifact: str
    grid_uncompressed_size: int
    detail_artifacts: tuple[str, ...]

    def source_for_variant(self, variant_id: str) -> SourceMeasurementV2:
        return next(item for item in self.sources if item.variant_id == variant_id)

    @property
    def geometry(self) -> SceneGeometry:
        return self.sources[0].geometry

    def grid(self, attribute_id: str) -> GridGeometry:
        return self.sources[0].grids[attribute_id]


@dataclass(frozen=True)
class ResultV2:
    root: Path
    result_id: str
    schema_version: int
    variants: tuple[Variant, ...]
    attributes: tuple[AttributeSpec, ...]
    scenes: tuple[SceneV2, ...]
    dataset_summaries: dict[tuple[str, str], DatasetSummaryV2]
    summary_artifact: str

    def variant(self, variant_id: str) -> Variant:
        return next(item for item in self.variants if item.variant_id == variant_id)

    def attribute(self, attribute_id: str) -> AttributeSpec:
        return next(item for item in self.attributes if item.attribute_id == attribute_id)

    def scene(self, scene_id: str) -> SceneV2:
        return next(item for item in self.scenes if item.scene_id == scene_id)

    def dataset_summary(self, variant_id: str, attribute_id: str) -> DatasetSummaryV2:
        return self.dataset_summaries[(variant_id, attribute_id)]


@dataclass(frozen=True)
class GridSceneDataV2:
    scene_id: str
    measurement_context_id: str
    variant_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    attributes: dict[str, CompactAttributeData]

    def attribute_for_variant(self, variant_id: str, attribute_id: str) -> CompactAttributeData:
        index = self.variant_ids.index(variant_id)
        data = self.attributes[attribute_id]
        return CompactAttributeData(
            weight_sum=np.asarray(data.weight_sum)[index],
            weighted_sum=np.asarray(data.weighted_sum)[index],
            weighted_square_sum=np.asarray(data.weighted_square_sum)[index],
            valid_count=np.asarray(data.valid_count)[index],
            valid_mask=np.asarray(data.valid_mask)[index],
        )


@dataclass(frozen=True)
class GridLoadOutcomeV2:
    status: LoadStatus
    data: GridSceneDataV2 | None = None
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is LoadStatus.SUCCESS


@dataclass(frozen=True)
class VersionedResultLoadOutcome:
    status: LoadStatus
    result: Result | ResultV2 | None = None
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is LoadStatus.SUCCESS


def build_measurement_context_id(
    scene_id: str,
    sources: Sequence[SourceMeasurementV2],
    attributes: Sequence[AttributeSpec],
    provenance: MeasurementContextProvenance,
) -> str:
    """Build the reproducible schema-v2 Scene measurement-context fingerprint."""
    attribute_rows = []
    for attribute in attributes:
        attribute_rows.append(
            {
                "attribute_id": attribute.attribute_id,
                "value_kind": attribute.value_kind.value,
                "weighting_provenance": attribute.weighting_provenance,
            }
        )
    source_rows = []
    for measurement in sources:
        geometry = measurement.geometry
        grid_rows = []
        for attribute in attributes:
            grid = measurement.grids[attribute.attribute_id]
            grid_rows.append(
                {
                    "attribute_id": attribute.attribute_id,
                    "rows": grid.rows,
                    "columns": grid.columns,
                    "block_width": _float_token(grid.block_width),
                    "block_height": _float_token(grid.block_height),
                    "origin_x": _float_token(grid.origin_x),
                    "origin_y": _float_token(grid.origin_y),
                    "discarded_right": _float_token(grid.discarded_right),
                    "discarded_bottom": _float_token(grid.discarded_bottom),
                }
            )
        source_rows.append(
            {
                "variant_id": measurement.variant_id,
                "source_id": measurement.source.source_id,
                "sha256": measurement.source.sha256,
                "width": measurement.source.width,
                "height": measurement.source.height,
                "geometry": {
                    "analysis_width": geometry.analysis_width,
                    "analysis_height": geometry.analysis_height,
                    "source_to_analysis": [
                        [_float_token(value) for value in row]
                        for row in geometry.source_to_analysis
                    ],
                    "valid_rect": [_float_token(value) for value in geometry.valid_rect],
                },
                "grids": grid_rows,
            }
        )
    payload = {
        "schema": "pixelscope-iqa-measurement-context-v2",
        "scene_id": scene_id,
        "sources": source_rows,
        "attributes": attribute_rows,
        "provenance": {
            "representative_id": provenance.representative_id,
            "preprocessing_id": provenance.preprocessing_id,
            "model_id": provenance.model_id,
            "weighting_id": provenance.weighting_id,
            "geometry_id": provenance.geometry_id,
        },
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return MEASUREMENT_CONTEXT_PREFIX + hashlib.sha256(canonical).hexdigest()


def _float_token(value: float) -> str:
    return float(value).hex()