"""Qt-free public IQA Client contract for execution and published-result access.

The types in this module are owned by the IQA Client. Enterprise implementations may
implement these ports, but transport, storage topology, authentication, proprietary
payloads, and Qt/thread ownership are intentionally outside this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    GridGeometry,
    ScalarStatistic,
    SceneGeometry,
)


class IqaJobState(str, Enum):
    """Client-visible execution states independent of backend pipeline phases."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {IqaJobState.COMPLETED, IqaJobState.FAILED, IqaJobState.CANCELLED}


class IqaAvailability(str, Enum):
    """Explicit availability for result/artifact/data access."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    MISSING = "missing"
    FAILED = "failed"


class IqaResultCompleteness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True)
class IqaDiagnostic:
    code: str
    message: str
    scene_id: str | None = None
    attribute_id: str | None = None


@dataclass(frozen=True)
class IqaVariant:
    variant_id: str
    label: str


@dataclass(frozen=True)
class IqaSubmissionSource:
    """One Client-local input. Enterprise staging/location is provider-owned."""

    variant_id: str
    local_path: Path


@dataclass(frozen=True)
class IqaSubmissionScene:
    scene_id: str
    sources: tuple[IqaSubmissionSource, ...]


@dataclass(frozen=True)
class IqaSubmissionIntent:
    """Company-neutral Client intent, not a serialized enterprise request."""

    submission_kind: str
    variants: tuple[IqaVariant, ...]
    scenes: tuple[IqaSubmissionScene, ...]

    def __post_init__(self) -> None:
        if not self.submission_kind:
            raise ValueError("submission_kind must be non-empty")
        if not self.variants:
            raise ValueError("submission must contain at least one variant")
        variant_ids = tuple(item.variant_id for item in self.variants)
        if any(not item for item in variant_ids) or len(set(variant_ids)) != len(variant_ids):
            raise ValueError("variant IDs must be non-empty and unique")
        if not self.scenes:
            raise ValueError("submission must contain at least one Scene")
        scene_ids = tuple(item.scene_id for item in self.scenes)
        if any(not item for item in scene_ids) or len(set(scene_ids)) != len(scene_ids):
            raise ValueError("Scene IDs must be non-empty and unique")
        for scene in self.scenes:
            if tuple(item.variant_id for item in scene.sources) != variant_ids:
                raise ValueError("each Scene must contain sources in declared variant order")


@dataclass(frozen=True)
class IqaExecutionCapabilities:
    can_cancel: bool = False


@dataclass(frozen=True)
class IqaJobReference:
    job_id: str


@dataclass(frozen=True)
class IqaJobProgress:
    completed: int | None = None
    total: int | None = None

    def __post_init__(self) -> None:
        if self.completed is not None and self.completed < 0:
            raise ValueError("completed progress must be non-negative")
        if self.total is not None and self.total < 0:
            raise ValueError("total progress must be non-negative")
        if self.completed is not None and self.total is not None and self.completed > self.total:
            raise ValueError("completed progress cannot exceed total")


@dataclass(frozen=True)
class IqaJobSnapshot:
    reference: IqaJobReference
    state: IqaJobState
    progress: IqaJobProgress = IqaJobProgress()
    message: str | None = None


@dataclass(frozen=True)
class IqaResultReference:
    """Opaque stable reference; no storage topology is encoded in the public API."""

    reference_id: str


@runtime_checkable
class IqaExecutionPort(Protocol):
    """Synchronous Qt-free control plane scheduled by the Client's existing workers."""

    @property
    def capabilities(self) -> IqaExecutionCapabilities: ...

    def submit(self, intent: IqaSubmissionIntent) -> IqaJobReference: ...

    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot: ...

    def get_result_reference(self, reference: IqaJobReference) -> IqaResultReference: ...

    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot: ...


@dataclass(frozen=True)
class IqaDatasetMetadata:
    dataset_id: str
    label: str


@dataclass(frozen=True)
class IqaMeasurementSummary:
    """One explicit scalar/per-Scene measurement summary."""

    availability: IqaAvailability
    weight_sum: float = 0.0
    weighted_sum: float = 0.0
    weighted_square_sum: float = 0.0
    valid_count: int = 0
    weighted_mean: float | None = None
    weighted_std: float | None = None
    reason: str | None = None

    @property
    def valid(self) -> bool:
        return (
            self.availability in {IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL}
            and self.weighted_mean is not None
        )

    @classmethod
    def missing(cls, reason: str = "missing_data") -> IqaMeasurementSummary:
        return cls(IqaAvailability.MISSING, reason=reason)

    @classmethod
    def failed(cls, reason: str) -> IqaMeasurementSummary:
        return cls(IqaAvailability.FAILED, reason=reason)


@dataclass(frozen=True)
class IqaDatasetSummary:
    pooled: IqaMeasurementSummary
    scene_mean: ScalarStatistic
    scene_std: ScalarStatistic
    scene_count: int


@dataclass(frozen=True)
class IqaSourceLocator:
    """Opaque resolver key plus an optional company-neutral display hint."""

    locator_id: str
    display_name: str | None = None


@dataclass(frozen=True)
class IqaSource:
    source_id: str
    locator: IqaSourceLocator
    sha256: str
    width: int
    height: int

    @property
    def relative_path(self) -> str:
        """Compatibility display text; never an enterprise physical path."""

        return self.locator.display_name or self.locator.locator_id


@dataclass(frozen=True)
class IqaSceneSource:
    variant_id: str
    source: IqaSource
    geometry: SceneGeometry
    grids: dict[str, GridGeometry]
    summaries: dict[str, IqaMeasurementSummary]

    def summary(self, attribute_id: str) -> IqaMeasurementSummary:
        return self.summaries[attribute_id]


@dataclass(frozen=True)
class IqaScene:
    scene_id: str
    sources: tuple[IqaSceneSource, ...]

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("Scene must contain at least one source")

    def source_for_variant(self, variant_id: str) -> IqaSceneSource:
        return next(item for item in self.sources if item.variant_id == variant_id)

    @property
    def geometry(self) -> SceneGeometry:
        return self.sources[0].geometry

    def grid(self, attribute_id: str) -> GridGeometry:
        return self.sources[0].grids[attribute_id]


@dataclass(frozen=True)
class IqaSpatialSceneData:
    scene_id: str
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
class IqaSpatialLoadOutcome:
    availability: IqaAvailability
    data: IqaSpatialSceneData | None = None
    diagnostics: tuple[IqaDiagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.availability in {IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL}
            and self.data is not None
        )


@runtime_checkable
class IqaSpatialAccess(Protocol):
    def load_scene(self, scene_id: str) -> IqaSpatialLoadOutcome: ...


@dataclass(frozen=True)
class IqaResult:
    """Client-owned normalized IQA result with lazy spatial access."""

    root: Path
    result_id: str
    schema_version: int
    dataset: IqaDatasetMetadata
    variants: tuple[IqaVariant, ...]
    attributes: tuple[AttributeSpec, ...]
    scenes: tuple[IqaScene, ...]
    dataset_summaries: dict[tuple[str, str], IqaDatasetSummary]
    completeness: IqaResultCompleteness
    diagnostics: tuple[IqaDiagnostic, ...]
    spatial_access: IqaSpatialAccess

    def variant(self, variant_id: str) -> IqaVariant:
        return next(item for item in self.variants if item.variant_id == variant_id)

    def attribute(self, attribute_id: str) -> AttributeSpec:
        return next(item for item in self.attributes if item.attribute_id == attribute_id)

    def scene(self, scene_id: str) -> IqaScene:
        return next(item for item in self.scenes if item.scene_id == scene_id)

    def dataset_summary(self, variant_id: str, attribute_id: str) -> IqaDatasetSummary:
        return self.dataset_summaries[(variant_id, attribute_id)]

    def load_spatial(self, scene_id: str) -> IqaSpatialLoadOutcome:
        return self.spatial_access.load_scene(scene_id)


@dataclass(frozen=True)
class IqaResultSource:
    root: Path
    completeness: IqaResultCompleteness = IqaResultCompleteness.COMPLETE


@dataclass(frozen=True)
class IqaResultSourceOutcome:
    availability: IqaAvailability
    source: IqaResultSource | None = None
    diagnostics: tuple[IqaDiagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.availability in {IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL}
            and self.source is not None
        )


@dataclass(frozen=True)
class IqaResultOpenOutcome:
    availability: IqaAvailability
    result: IqaResult | None = None
    diagnostics: tuple[IqaDiagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.availability in {IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL}
            and self.result is not None
        )


@dataclass(frozen=True)
class IqaResolvedSource:
    local_path: Path


@runtime_checkable
class IqaResultAccessPort(Protocol):
    """Qt-free artifact/result/source access, independent of the execution lifetime."""

    def materialize(self, reference: IqaResultReference) -> IqaResultSourceOutcome: ...

    def open_result(self, source: IqaResultSource) -> IqaResultOpenOutcome: ...

    def resolve_source(self, locator: IqaSourceLocator) -> IqaResolvedSource | None: ...
