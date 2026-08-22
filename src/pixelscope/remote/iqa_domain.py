"""Qt-free domain models for published Remote IQA result artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ValueKind(str, Enum):
    POWER = "power"
    SIGNED = "signed"


class QualityDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


class ComparisonMode(str, Enum):
    RATIO_OF_WEIGHTED_MEANS = "ratio_of_weighted_means"
    MEAN_OF_GRID_LOG_RATIOS = "mean_of_grid_log_ratios"
    SIGNED_DELTA = "signed_delta"


class ComparisonOperator(str, Enum):
    # Schema-v1 historical/read-only names. Keep these for v1 compatibility.
    POWER_RATIO_A_OVER_B_DB = "power_ratio_a_over_b_db"
    SIGNED_A_MINUS_B = "signed_a_minus_b"
    # Schema-v2 canonical names. Operands are selected locally at runtime.
    POWER_RATIO_TARGET_OVER_REFERENCE_DB = "power_ratio_target_over_reference_db"
    SIGNED_TARGET_MINUS_REFERENCE = "signed_target_minus_reference"


class LoadStatus(str, Enum):
    SUCCESS = "success"
    INVALID = "invalid"
    CORRUPT = "corrupt"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ScalarStatistic:
    value: float | None
    valid: bool
    invalid_reason: str | None = None

    @classmethod
    def invalid(cls, reason: str) -> ScalarStatistic:
        return cls(value=None, valid=False, invalid_reason=reason)


@dataclass(frozen=True)
class AttributeSpec:
    attribute_id: str
    name: str
    value_kind: ValueKind
    comparison_operator: ComparisonOperator
    quality_direction: QualityDirection
    unit: str
    stabilization_epsilon: float | None
    weighting_provenance: str


@dataclass(frozen=True)
class Source:
    source_id: str
    relative_path: str
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class GridGeometry:
    rows: int
    columns: int
    block_width: float
    block_height: float
    origin_x: float
    origin_y: float
    discarded_right: float
    discarded_bottom: float


@dataclass(frozen=True)
class SceneGeometry:
    analysis_width: int
    analysis_height: int
    source_to_analysis: tuple[tuple[float, float, float], ...]
    valid_rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class Comparison:
    scene_id: str
    source_a_id: str
    source_b_id: str
    attribute_id: str
    official: dict[ComparisonMode, ScalarStatistic]


@dataclass(frozen=True)
class Scene:
    scene_id: str
    sources: tuple[Source, ...]
    geometry: SceneGeometry
    grids: dict[str, GridGeometry]
    compact_artifact: str
    compact_uncompressed_size: int
    detail_artifacts: tuple[str, ...]
    comparisons: tuple[Comparison, ...]


@dataclass(frozen=True)
class Result:
    root: Path
    result_id: str
    schema_version: int
    attributes: tuple[AttributeSpec, ...]
    scenes: tuple[Scene, ...]
    summary_artifact: str

    def attribute(self, attribute_id: str) -> AttributeSpec:
        return next(item for item in self.attributes if item.attribute_id == attribute_id)

    def scene(self, scene_id: str) -> Scene:
        return next(item for item in self.scenes if item.scene_id == scene_id)


@dataclass(frozen=True)
class ResultLoadOutcome:
    status: LoadStatus
    result: Result | None = None
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is LoadStatus.SUCCESS


@dataclass(frozen=True)
class CompactAttributeData:
    weight_sum: object
    weighted_sum: object
    weighted_square_sum: object
    valid_count: object
    valid_mask: object


@dataclass(frozen=True)
class CompactSceneData:
    scene_id: str
    source_ids: tuple[str, ...]
    attributes: dict[str, CompactAttributeData]


@dataclass(frozen=True)
class CompactLoadOutcome:
    status: LoadStatus
    data: CompactSceneData | None = None
    reason: str | None = None
