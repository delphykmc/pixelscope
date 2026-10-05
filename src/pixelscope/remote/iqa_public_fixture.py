"""Deterministic company-neutral IQA fixtures for public Client development.

These fixtures exercise the Slice 2 public IQA contract directly. They intentionally
contain no transport, server, storage-root, authentication, or proprietary payload
semantics and do not create Qt objects or thread pools.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock

import numpy as np

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    CompactAttributeData,
    ComparisonOperator,
    GridGeometry,
    QualityDirection,
    ScalarStatistic,
    SceneGeometry,
    ValueKind,
)
from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaDatasetMetadata,
    IqaDatasetSummary,
    IqaDiagnostic,
    IqaExecutionCapabilities,
    IqaExecutionPort,
    IqaJobProgress,
    IqaJobReference,
    IqaJobSnapshot,
    IqaJobState,
    IqaMeasurementSummary,
    IqaProviderError,
    IqaProviderErrorKind,
    IqaResolvedSource,
    IqaResult,
    IqaResultAccessPort,
    IqaResultCompleteness,
    IqaResultOpenOutcome,
    IqaResultReference,
    IqaResultSource,
    IqaResultSourceOutcome,
    IqaScene,
    IqaSceneSource,
    IqaSource,
    IqaSourceLocator,
    IqaSourceResolutionOutcome,
    IqaSpatialAccess,
    IqaSpatialLoadOutcome,
    IqaSpatialSceneData,
    IqaSubmissionIntent,
    IqaVariant,
)


class SyntheticIqaProfile(str, Enum):
    MINIMAL = "minimal"
    NORMAL = "normal"
    LARGE = "large"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(frozen=True)
class SyntheticIqaProfileSpec:
    attribute_count: int
    variant_count: int
    scene_count: int
    completeness: IqaResultCompleteness = IqaResultCompleteness.COMPLETE
    terminal_state: IqaJobState = IqaJobState.COMPLETED
    missing_measurement: bool = False


SYNTHETIC_IQA_PROFILES: dict[SyntheticIqaProfile, SyntheticIqaProfileSpec] = {
    SyntheticIqaProfile.MINIMAL: SyntheticIqaProfileSpec(2, 2, 3),
    SyntheticIqaProfile.NORMAL: SyntheticIqaProfileSpec(10, 3, 12),
    SyntheticIqaProfile.LARGE: SyntheticIqaProfileSpec(32, 16, 128),
    SyntheticIqaProfile.PARTIAL: SyntheticIqaProfileSpec(
        10,
        3,
        12,
        completeness=IqaResultCompleteness.PARTIAL,
        missing_measurement=True,
    ),
    SyntheticIqaProfile.FAILURE: SyntheticIqaProfileSpec(
        2,
        2,
        3,
        terminal_state=IqaJobState.FAILED,
    ),
}


class _SyntheticSpatialAccess(IqaSpatialAccess):
    def __init__(
        self,
        scene_ids: tuple[str, ...],
        variants: tuple[IqaVariant, ...],
        attributes: tuple[AttributeSpec, ...],
        grids: dict[str, GridGeometry],
    ) -> None:
        self._scene_ids = frozenset(scene_ids)
        self._variants = variants
        self._attributes = attributes
        self._grids = grids
        self.load_count = 0
        self._lock = RLock()

    def load_scene(self, scene_id: str) -> IqaSpatialLoadOutcome:
        with self._lock:
            self.load_count += 1
        if scene_id not in self._scene_ids:
            return IqaSpatialLoadOutcome(
                IqaAvailability.MISSING,
                diagnostics=(
                    IqaDiagnostic(
                        "synthetic_scene_missing",
                        "Synthetic Scene is not available.",
                        scene_id,
                    ),
                ),
            )
        variant_ids = tuple(item.variant_id for item in self._variants)
        source_ids = tuple(f"{scene_id}:{variant_id}" for variant_id in variant_ids)
        arrays: dict[str, CompactAttributeData] = {}
        for attribute_index, attribute in enumerate(self._attributes):
            grid = self._grids[attribute.attribute_id]
            shape = (len(variant_ids), grid.rows, grid.columns)
            base = float(attribute_index + 1)
            weight = np.ones(shape, dtype=np.float64)
            weighted = np.empty(shape, dtype=np.float64)
            for variant_index in range(len(variant_ids)):
                weighted[variant_index].fill(base + 0.1 * variant_index)
            arrays[attribute.attribute_id] = CompactAttributeData(
                weight_sum=weight,
                weighted_sum=weighted,
                weighted_square_sum=weighted * weighted,
                valid_count=np.ones(shape, dtype=np.int64),
                valid_mask=np.ones(shape, dtype=np.bool_),
            )
        return IqaSpatialLoadOutcome(
            IqaAvailability.AVAILABLE,
            IqaSpatialSceneData(scene_id, variant_ids, source_ids, arrays),
        )


def _attribute(index: int) -> AttributeSpec:
    signed = index % 5 == 4
    return AttributeSpec(
        attribute_id=f"attribute_{index:03d}",
        name=f"Attribute {index:02d}",
        value_kind=ValueKind.SIGNED if signed else ValueKind.POWER,
        comparison_operator=(
            ComparisonOperator.SIGNED_TARGET_MINUS_REFERENCE
            if signed
            else ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB
        ),
        quality_direction=(
            QualityDirection.NEUTRAL
            if signed
            else (
                QualityDirection.LOWER_IS_BETTER
                if index % 2 == 0
                else QualityDirection.HIGHER_IS_BETTER
            )
        ),
        unit="normalized-code" if signed else "linear-power",
        stabilization_epsilon=None if signed else 1e-9,
        weighting_provenance="synthetic-unit-weight",
    )


def _summary(value: float) -> IqaMeasurementSummary:
    return IqaMeasurementSummary(
        IqaAvailability.AVAILABLE,
        weight_sum=1.0,
        weighted_sum=value,
        weighted_square_sum=value * value,
        valid_count=1,
        weighted_mean=value,
        weighted_std=0.0,
    )


def _dataset_summary(value: float, scene_count: int) -> IqaDatasetSummary:
    return IqaDatasetSummary(
        pooled=_summary(value),
        scene_mean=ScalarStatistic(value, True),
        scene_std=ScalarStatistic(0.0, True),
        scene_count=scene_count,
    )


def build_synthetic_iqa_result(
    root: Path,
    profile: SyntheticIqaProfile | str = SyntheticIqaProfile.NORMAL,
) -> IqaResult | None:
    """Build one deterministic normalized public result.

    ``failure`` models an execution that publishes no result, so this function returns
    ``None`` for that profile by design.
    """

    selected = SyntheticIqaProfile(profile)
    spec = SYNTHETIC_IQA_PROFILES[selected]
    if spec.terminal_state is IqaJobState.FAILED:
        return None

    root.mkdir(parents=True, exist_ok=True)
    attributes = tuple(_attribute(index) for index in range(spec.attribute_count))
    variants = tuple(
        IqaVariant(f"variant_{index:03d}", f"Variant {index:02d}")
        for index in range(spec.variant_count)
    )
    geometry = SceneGeometry(
        analysis_width=64,
        analysis_height=64,
        source_to_analysis=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        valid_rect=(0.0, 0.0, 64.0, 64.0),
    )
    grids = {
        attribute.attribute_id: GridGeometry(
            rows=2,
            columns=2,
            block_width=32.0,
            block_height=32.0,
            origin_x=0.0,
            origin_y=0.0,
            discarded_right=0.0,
            discarded_bottom=0.0,
        )
        for attribute in attributes
    }

    scenes: list[IqaScene] = []
    dataset_values: dict[tuple[str, str], list[float]] = {
        (variant.variant_id, attribute.attribute_id): []
        for variant in variants
        for attribute in attributes
    }
    for scene_index in range(spec.scene_count):
        scene_id = f"scene_{scene_index:04d}"
        sources: list[IqaSceneSource] = []
        for variant_index, variant in enumerate(variants):
            source_id = f"{scene_id}:{variant.variant_id}"
            source_path = root / "sources" / f"{scene_id}_{variant.variant_id}.bin"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(source_id.encode("ascii"))
            summaries: dict[str, IqaMeasurementSummary] = {}
            for attribute_index, attribute in enumerate(attributes):
                value = (
                    float(attribute_index + 1)
                    + 0.1 * variant_index
                    + 0.001 * scene_index
                )
                missing = (
                    spec.missing_measurement
                    and scene_index == spec.scene_count - 1
                    and variant_index == spec.variant_count - 1
                    and attribute_index == spec.attribute_count - 1
                )
                summaries[attribute.attribute_id] = (
                    IqaMeasurementSummary.missing("synthetic_missing_measurement")
                    if missing
                    else _summary(value)
                )
                if not missing:
                    dataset_values[(variant.variant_id, attribute.attribute_id)].append(value)
            sources.append(
                IqaSceneSource(
                    variant.variant_id,
                    IqaSource(
                        source_id,
                        IqaSourceLocator(source_id, source_path.name),
                        f"{scene_index * spec.variant_count + variant_index:064x}",
                        64,
                        64,
                    ),
                    geometry,
                    dict(grids),
                    summaries,
                )
            )
        scenes.append(IqaScene(scene_id, tuple(sources)))

    dataset_summaries: dict[tuple[str, str], IqaDatasetSummary] = {}
    for key, values in dataset_values.items():
        mean = sum(values) / len(values) if values else 0.0
        dataset_summaries[key] = _dataset_summary(mean, len(values))

    diagnostics: tuple[IqaDiagnostic, ...] = ()
    if spec.completeness is IqaResultCompleteness.PARTIAL:
        diagnostics = (
            IqaDiagnostic(
                "synthetic_partial_result",
                "Synthetic result intentionally contains one missing measurement.",
                scenes[-1].scene_id,
                attributes[-1].attribute_id,
            ),
        )
    spatial = _SyntheticSpatialAccess(
        tuple(scene.scene_id for scene in scenes),
        variants,
        attributes,
        grids,
    )
    return IqaResult(
        root=root,
        result_id=f"synthetic-{selected.value}",
        schema_version=2,
        dataset=IqaDatasetMetadata(
            f"synthetic-{selected.value}",
            f"Synthetic {selected.value}",
        ),
        variants=variants,
        attributes=attributes,
        scenes=tuple(scenes),
        dataset_summaries=dataset_summaries,
        completeness=spec.completeness,
        diagnostics=diagnostics,
        spatial_access=spatial,
    )


class FixtureIqaProvider(IqaExecutionPort, IqaResultAccessPort):
    """Deterministic in-process provider for external Client development and tests."""

    def __init__(self, root: Path, profile: SyntheticIqaProfile | str) -> None:
        self.profile = SyntheticIqaProfile(profile)
        self.spec = SYNTHETIC_IQA_PROFILES[self.profile]
        self._root = root
        self._result = build_synthetic_iqa_result(root, self.profile)
        self._job: IqaJobReference | None = None
        self._poll_count = 0
        self._cancelled = False
        self._lock = RLock()
        self._sources: dict[str, Path] = {}
        if self._result is not None:
            for scene in self._result.scenes:
                for item in scene.sources:
                    locator = item.source.locator
                    self._sources[locator.locator_id] = (
                        root / "sources" / str(locator.display_name)
                    )

    @property
    def capabilities(self) -> IqaExecutionCapabilities:
        return IqaExecutionCapabilities(can_cancel=True)

    def submit(self, intent: IqaSubmissionIntent) -> IqaJobReference:
        del intent
        with self._lock:
            self._job = IqaJobReference(f"fixture-{self.profile.value}")
            self._poll_count = 0
            self._cancelled = False
            return self._job

    def _require_job(self, reference: IqaJobReference) -> None:
        if self._job != reference:
            raise IqaProviderError(
                IqaProviderErrorKind.INVALID,
                "Unknown synthetic IQA job.",
            )

    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot:
        with self._lock:
            self._require_job(reference)
            if self._cancelled:
                return IqaJobSnapshot(
                    reference,
                    IqaJobState.CANCELLED,
                    message="IQA job was cancelled.",
                )
            if self._poll_count == 0:
                self._poll_count += 1
                return IqaJobSnapshot(
                    reference,
                    IqaJobState.QUEUED,
                    IqaJobProgress(0, 1),
                )
            if self._poll_count == 1:
                self._poll_count += 1
                return IqaJobSnapshot(
                    reference,
                    IqaJobState.RUNNING,
                    IqaJobProgress(0, 1),
                )
            state = self.spec.terminal_state
            return IqaJobSnapshot(
                reference,
                state,
                IqaJobProgress(1, 1),
                "IQA job completed."
                if state is IqaJobState.COMPLETED
                else "IQA job failed.",
            )

    def get_result_reference(self, reference: IqaJobReference) -> IqaResultReference:
        with self._lock:
            self._require_job(reference)
            if self._cancelled or self.spec.terminal_state is not IqaJobState.COMPLETED:
                raise IqaProviderError(
                    IqaProviderErrorKind.OPERATION_FAILED,
                    "Synthetic IQA job did not publish a result.",
                )
            return IqaResultReference(reference.job_id)

    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot:
        with self._lock:
            self._require_job(reference)
            self._cancelled = True
            return IqaJobSnapshot(
                reference,
                IqaJobState.CANCELLED,
                message="IQA job was cancelled.",
            )

    def materialize(self, reference: IqaResultReference) -> IqaResultSourceOutcome:
        with self._lock:
            unavailable = (
                self._result is None
                or self._job is None
                or reference.reference_id != self._job.job_id
            )
            if unavailable:
                return IqaResultSourceOutcome(
                    IqaAvailability.MISSING,
                    diagnostics=(
                        IqaDiagnostic(
                            "synthetic_result_missing",
                            "Synthetic result is not available.",
                        ),
                    ),
                )
            availability = (
                IqaAvailability.PARTIAL
                if self._result.completeness is IqaResultCompleteness.PARTIAL
                else IqaAvailability.AVAILABLE
            )
            return IqaResultSourceOutcome(
                availability,
                IqaResultSource(self._root, self._result.completeness),
            )

    def open_result(self, source: IqaResultSource) -> IqaResultOpenOutcome:
        with self._lock:
            if self._result is None or source.root != self._root:
                return IqaResultOpenOutcome(
                    IqaAvailability.MISSING,
                    diagnostics=(
                        IqaDiagnostic(
                            "synthetic_result_missing",
                            "Synthetic result is not available.",
                        ),
                    ),
                )
            availability = (
                IqaAvailability.PARTIAL
                if self._result.completeness is IqaResultCompleteness.PARTIAL
                else IqaAvailability.AVAILABLE
            )
            return IqaResultOpenOutcome(
                availability,
                self._result,
                self._result.diagnostics,
            )

    def resolve_source(self, locator: IqaSourceLocator) -> IqaSourceResolutionOutcome:
        with self._lock:
            path = self._sources.get(locator.locator_id)
        if path is None or not path.exists():
            return IqaSourceResolutionOutcome(
                IqaAvailability.MISSING,
                diagnostics=(
                    IqaDiagnostic(
                        "synthetic_source_missing",
                        "Synthetic source is not available.",
                    ),
                ),
            )
        return IqaSourceResolutionOutcome(
            IqaAvailability.AVAILABLE,
            IqaResolvedSource(path),
        )
