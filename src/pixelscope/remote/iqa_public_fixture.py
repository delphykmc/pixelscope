"""Company-neutral synthetic IQA fixtures for Client development and validation.

The fixture catalog targets the Client-owned public contract directly. It intentionally
contains no Remote-IQA transport, storage-root, authentication, or proprietary payload
knowledge and creates no Qt objects or thread pools.
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
    IqaJobProgress,
    IqaJobReference,
    IqaJobSnapshot,
    IqaJobState,
    IqaMeasurementSummary,
    IqaProviderError,
    IqaProviderErrorKind,
    IqaResult,
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
    IqaSpatialLoadOutcome,
    IqaSpatialSceneData,
    IqaSubmissionIntent,
    IqaVariant,
)


class IqaFixtureProfile(str, Enum):
    """Representative public Client workloads used at Issue #121 Checkpoint B."""

    MINIMAL = "minimal"
    NORMAL = "normal"
    LARGE = "large"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(frozen=True)
class IqaFixtureSpec:
    profile: IqaFixtureProfile
    attribute_count: int
    variant_count: int
    scene_count: int
    completeness: IqaResultCompleteness


FIXTURE_SPECS: dict[IqaFixtureProfile, IqaFixtureSpec] = {
    IqaFixtureProfile.MINIMAL: IqaFixtureSpec(
        IqaFixtureProfile.MINIMAL,
        attribute_count=2,
        variant_count=2,
        scene_count=3,
        completeness=IqaResultCompleteness.COMPLETE,
    ),
    IqaFixtureProfile.NORMAL: IqaFixtureSpec(
        IqaFixtureProfile.NORMAL,
        attribute_count=10,
        variant_count=3,
        scene_count=12,
        completeness=IqaResultCompleteness.COMPLETE,
    ),
    IqaFixtureProfile.LARGE: IqaFixtureSpec(
        IqaFixtureProfile.LARGE,
        attribute_count=32,
        variant_count=16,
        scene_count=128,
        completeness=IqaResultCompleteness.COMPLETE,
    ),
    IqaFixtureProfile.PARTIAL: IqaFixtureSpec(
        IqaFixtureProfile.PARTIAL,
        attribute_count=10,
        variant_count=3,
        scene_count=12,
        completeness=IqaResultCompleteness.PARTIAL,
    ),
    IqaFixtureProfile.FAILURE: IqaFixtureSpec(
        IqaFixtureProfile.FAILURE,
        attribute_count=2,
        variant_count=2,
        scene_count=3,
        completeness=IqaResultCompleteness.COMPLETE,
    ),
}


@dataclass(frozen=True)
class _FixtureShape:
    scene_ids: tuple[str, ...]
    variant_ids: tuple[str, ...]
    source_ids: dict[str, tuple[str, ...]]
    attribute_ids: tuple[str, ...]
    missing_measurements: frozenset[tuple[str, str, str]]


class _FixtureSpatialAccess:
    """Generate small spatial arrays on demand instead of retaining them in the fixture."""

    def __init__(self, shape: _FixtureShape) -> None:
        self._shape = shape

    def load_scene(self, scene_id: str) -> IqaSpatialLoadOutcome:
        try:
            scene_index = self._shape.scene_ids.index(scene_id)
        except ValueError:
            return IqaSpatialLoadOutcome(
                IqaAvailability.MISSING,
                diagnostics=(
                    IqaDiagnostic(
                        "fixture_scene_missing",
                        "Synthetic fixture does not publish this Scene.",
                        scene_id=scene_id,
                    ),
                ),
            )

        variant_count = len(self._shape.variant_ids)
        attributes: dict[str, CompactAttributeData] = {}
        partial = False
        for attribute_index, attribute_id in enumerate(self._shape.attribute_ids):
            weights = np.ones((variant_count, 1, 1), dtype=np.float64)
            weighted = np.zeros_like(weights)
            squared = np.zeros_like(weights)
            counts = np.ones((variant_count, 1, 1), dtype=np.int64)
            valid = np.ones((variant_count, 1, 1), dtype=np.bool_)
            for variant_index, variant_id in enumerate(self._shape.variant_ids):
                key = (scene_id, variant_id, attribute_id)
                if key in self._shape.missing_measurements:
                    weights[variant_index, 0, 0] = 0.0
                    counts[variant_index, 0, 0] = 0
                    valid[variant_index, 0, 0] = False
                    partial = True
                    continue
                value = _fixture_value(scene_index, variant_index, attribute_index)
                weighted[variant_index, 0, 0] = value
                squared[variant_index, 0, 0] = value * value
            attributes[attribute_id] = CompactAttributeData(
                weight_sum=weights,
                weighted_sum=weighted,
                weighted_square_sum=squared,
                valid_count=counts,
                valid_mask=valid,
            )

        return IqaSpatialLoadOutcome(
            IqaAvailability.PARTIAL if partial else IqaAvailability.AVAILABLE,
            IqaSpatialSceneData(
                scene_id=scene_id,
                variant_ids=self._shape.variant_ids,
                source_ids=self._shape.source_ids[scene_id],
                attributes=attributes,
            ),
        )


def build_fixture_result(
    root: Path,
    *,
    attribute_count: int,
    variant_count: int,
    scene_count: int,
    completeness: IqaResultCompleteness = IqaResultCompleteness.COMPLETE,
    result_id: str | None = None,
) -> IqaResult:
    """Build a normalized public result with deterministic, lazily generated grids.

    ``PARTIAL`` deliberately omits one Scene/variant/attribute measurement. This models
    the public Client semantics without claiming that today's durable schema-v2 encoding
    can serialize every arbitrary per-metric absence.
    """

    if attribute_count <= 0 or variant_count <= 0 or scene_count <= 0:
        raise ValueError("fixture cardinalities must be positive")

    attributes = tuple(_attribute(index) for index in range(attribute_count))
    variants = tuple(
        IqaVariant(f"variant_{index:03d}", f"Variant {index:02d}")
        for index in range(variant_count)
    )
    scene_ids = tuple(f"scene_{index:04d}" for index in range(scene_count))
    attribute_ids = tuple(item.attribute_id for item in attributes)
    variant_ids = tuple(item.variant_id for item in variants)
    fixture_result_id = result_id or f"synthetic-{attribute_count}-{variant_count}-{scene_count}"

    missing_measurements: frozenset[tuple[str, str, str]] = frozenset()
    diagnostics: tuple[IqaDiagnostic, ...] = ()
    if completeness is IqaResultCompleteness.PARTIAL:
        missing_key = (scene_ids[-1], variant_ids[-1], attribute_ids[-1])
        missing_measurements = frozenset({missing_key})
        diagnostics = (
            IqaDiagnostic(
                "fixture_metric_missing",
                "Synthetic fixture omits one measurement.",
                scene_id=missing_key[0],
                attribute_id=missing_key[2],
            ),
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
    grid = GridGeometry(
        rows=1,
        columns=1,
        block_width=64.0,
        block_height=64.0,
        origin_x=0.0,
        origin_y=0.0,
        discarded_right=0.0,
        discarded_bottom=0.0,
    )
    grids = {attribute_id: grid for attribute_id in attribute_ids}

    dataset_values: dict[tuple[str, str], list[float]] = {
        (variant_id, attribute_id): []
        for variant_id in variant_ids
        for attribute_id in attribute_ids
    }
    source_ids: dict[str, tuple[str, ...]] = {}
    scenes: list[IqaScene] = []
    for scene_index, scene_id in enumerate(scene_ids):
        scene_sources: list[IqaSceneSource] = []
        scene_source_ids: list[str] = []
        for variant_index, variant in enumerate(variants):
            source_id = f"source_{scene_index:04d}_{variant_index:03d}"
            scene_source_ids.append(source_id)
            summaries: dict[str, IqaMeasurementSummary] = {}
            for attribute_index, attribute in enumerate(attributes):
                measurement_key = (scene_id, variant.variant_id, attribute.attribute_id)
                if measurement_key in missing_measurements:
                    summaries[attribute.attribute_id] = IqaMeasurementSummary.missing(
                        "fixture_metric_not_published"
                    )
                    continue
                value = _fixture_value(scene_index, variant_index, attribute_index)
                summaries[attribute.attribute_id] = _summary(value)
                dataset_values[(variant.variant_id, attribute.attribute_id)].append(value)
            scene_sources.append(
                IqaSceneSource(
                    variant_id=variant.variant_id,
                    source=IqaSource(
                        source_id=source_id,
                        locator=IqaSourceLocator(
                            locator_id=f"fixture:{fixture_result_id}:{source_id}",
                            display_name=f"{scene_id}_{variant.variant_id}.png",
                        ),
                        sha256=f"{scene_index * variant_count + variant_index:064x}",
                        width=64,
                        height=64,
                    ),
                    geometry=geometry,
                    grids=dict(grids),
                    summaries=summaries,
                )
            )
        source_ids[scene_id] = tuple(scene_source_ids)
        scenes.append(IqaScene(scene_id=scene_id, sources=tuple(scene_sources)))

    dataset_summaries: dict[tuple[str, str], IqaDatasetSummary] = {}
    for variant in variants:
        for attribute in attributes:
            dataset_key = (variant.variant_id, attribute.attribute_id)
            values = dataset_values[dataset_key]
            if not values:
                pooled = IqaMeasurementSummary.missing("fixture_metric_not_published")
                scene_mean = ScalarStatistic.invalid("missing_data")
                scene_std = ScalarStatistic.invalid("missing_data")
            else:
                mean = float(sum(values) / len(values))
                availability = (
                    IqaAvailability.PARTIAL
                    if len(values) != scene_count
                    else IqaAvailability.AVAILABLE
                )
                pooled = _summary(mean, availability=availability, valid_count=len(values))
                scene_mean = ScalarStatistic(mean, True)
                variance = sum((value - mean) ** 2 for value in values) / len(values)
                scene_std = ScalarStatistic(float(variance**0.5), True)
            dataset_summaries[dataset_key] = IqaDatasetSummary(
                pooled=pooled,
                scene_mean=scene_mean,
                scene_std=scene_std,
                scene_count=len(values),
            )

    shape = _FixtureShape(
        scene_ids=scene_ids,
        variant_ids=variant_ids,
        source_ids=source_ids,
        attribute_ids=attribute_ids,
        missing_measurements=missing_measurements,
    )
    return IqaResult(
        root=root,
        result_id=fixture_result_id,
        schema_version=2,
        dataset=IqaDatasetMetadata(
            dataset_id=f"dataset-{fixture_result_id}",
            label="Synthetic IQA fixture",
        ),
        variants=variants,
        attributes=attributes,
        scenes=tuple(scenes),
        dataset_summaries=dataset_summaries,
        completeness=completeness,
        diagnostics=diagnostics,
        spatial_access=_FixtureSpatialAccess(shape),
    )


def build_profile_result(root: Path, profile: IqaFixtureProfile) -> IqaResult:
    """Build one catalog result profile; ``FAILURE`` is execution-only."""

    spec = FIXTURE_SPECS[profile]
    if profile is IqaFixtureProfile.FAILURE:
        raise ValueError("failure profile has no published result")
    return build_fixture_result(
        root,
        attribute_count=spec.attribute_count,
        variant_count=spec.variant_count,
        scene_count=spec.scene_count,
        completeness=spec.completeness,
        result_id=f"fixture-{profile.value}",
    )


class FixtureIqaProvider:
    """Deterministic in-process implementation of the public IQA ports.

    ``advance`` is an explicit test/development clock: reads never advance execution on
    their own, so callers can deterministically hold queued/running states. All mutable
    provider state is guarded so one instance is safe for overlapping public calls.
    """

    def __init__(
        self,
        root: Path,
        profile: IqaFixtureProfile = IqaFixtureProfile.NORMAL,
    ) -> None:
        self._root = root
        self._profile = profile
        self._lock = RLock()
        self._next_job = 1
        self._jobs: dict[str, IqaJobSnapshot] = {}
        self._result_references: dict[str, str] = {}
        self._result = (
            None if profile is IqaFixtureProfile.FAILURE else build_profile_result(root, profile)
        )

    @property
    def capabilities(self) -> IqaExecutionCapabilities:
        return IqaExecutionCapabilities(can_cancel=True)

    def submit(self, intent: IqaSubmissionIntent) -> IqaJobReference:
        del intent
        with self._lock:
            reference = IqaJobReference(f"fixture-job-{self._next_job:04d}")
            self._next_job += 1
            self._jobs[reference.job_id] = IqaJobSnapshot(
                reference,
                IqaJobState.QUEUED,
                IqaJobProgress(0, 2),
                "Synthetic IQA job is queued.",
            )
            return reference

    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot:
        with self._lock:
            return self._job(reference)

    def advance(self, reference: IqaJobReference) -> IqaJobSnapshot:
        """Advance QUEUED -> RUNNING -> terminal without sleeps or external resources."""

        with self._lock:
            current = self._job(reference)
            if current.state is IqaJobState.QUEUED:
                next_snapshot = IqaJobSnapshot(
                    reference,
                    IqaJobState.RUNNING,
                    IqaJobProgress(1, 2),
                    "Synthetic IQA job is running.",
                )
            elif current.state is IqaJobState.RUNNING:
                failed = self._profile is IqaFixtureProfile.FAILURE
                state = IqaJobState.FAILED if failed else IqaJobState.COMPLETED
                next_snapshot = IqaJobSnapshot(
                    reference,
                    state,
                    IqaJobProgress(2, 2),
                    (
                        "Synthetic IQA job failed."
                        if failed
                        else "Synthetic IQA job completed."
                    ),
                )
                if not failed:
                    self._result_references[reference.job_id] = (
                        f"fixture-result:{reference.job_id}"
                    )
            else:
                return current
            self._jobs[reference.job_id] = next_snapshot
            return next_snapshot

    def get_result_reference(self, reference: IqaJobReference) -> IqaResultReference:
        with self._lock:
            snapshot = self._job(reference)
            reference_id = self._result_references.get(reference.job_id)
            if snapshot.state is not IqaJobState.COMPLETED or reference_id is None:
                raise IqaProviderError(
                    IqaProviderErrorKind.OPERATION_FAILED,
                    "Synthetic IQA result is not available.",
                )
            return IqaResultReference(reference_id)

    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot:
        with self._lock:
            current = self._job(reference)
            if current.state.terminal:
                return current
            cancelled = IqaJobSnapshot(
                reference,
                IqaJobState.CANCELLED,
                current.progress,
                "Synthetic IQA job was cancelled.",
            )
            self._jobs[reference.job_id] = cancelled
            return cancelled

    def materialize(self, reference: IqaResultReference) -> IqaResultSourceOutcome:
        with self._lock:
            if (
                reference.reference_id not in self._result_references.values()
                or self._result is None
            ):
                return IqaResultSourceOutcome(
                    IqaAvailability.MISSING,
                    diagnostics=(
                        IqaDiagnostic(
                            "fixture_result_missing",
                            "Synthetic result is not available.",
                        ),
                    ),
                )
            availability = _result_availability(self._result.completeness)
            return IqaResultSourceOutcome(
                availability,
                IqaResultSource(self._root, self._result.completeness),
                self._result.diagnostics,
            )

    def open_result(self, source: IqaResultSource) -> IqaResultOpenOutcome:
        with self._lock:
            if self._result is None:
                return IqaResultOpenOutcome(
                    IqaAvailability.FAILED,
                    diagnostics=(
                        IqaDiagnostic(
                            "fixture_result_failed",
                            "Synthetic provider did not publish a result.",
                        ),
                    ),
                )
            if source.root != self._root:
                return IqaResultOpenOutcome(
                    IqaAvailability.MISSING,
                    diagnostics=(
                        IqaDiagnostic(
                            "fixture_result_missing",
                            "Synthetic result source is not known.",
                        ),
                    ),
                )
            return IqaResultOpenOutcome(
                _result_availability(self._result.completeness),
                self._result,
                self._result.diagnostics,
            )

    def resolve_source(self, locator: IqaSourceLocator) -> IqaSourceResolutionOutcome:
        del locator
        return IqaSourceResolutionOutcome(
            IqaAvailability.MISSING,
            diagnostics=(
                IqaDiagnostic(
                    "fixture_source_not_materialized",
                    "Synthetic fixture does not materialize original source files.",
                ),
            ),
        )

    def _job(self, reference: IqaJobReference) -> IqaJobSnapshot:
        try:
            return self._jobs[reference.job_id]
        except KeyError as exc:
            raise IqaProviderError(
                IqaProviderErrorKind.INVALID,
                "Unknown synthetic IQA job.",
            ) from exc


def _attribute(index: int) -> AttributeSpec:
    return AttributeSpec(
        attribute_id=f"attribute_{index:03d}",
        name=f"Attribute {index:02d}",
        value_kind=ValueKind.POWER,
        comparison_operator=ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB,
        quality_direction=(
            QualityDirection.HIGHER_IS_BETTER
            if index % 2 == 0
            else QualityDirection.LOWER_IS_BETTER
        ),
        unit="linear-power",
        stabilization_epsilon=1e-9,
        weighting_provenance="synthetic-unit-weight",
    )


def _fixture_value(scene_index: int, variant_index: int, attribute_index: int) -> float:
    return float(attribute_index + 1) + 0.1 * variant_index + 0.001 * scene_index


def _summary(
    value: float,
    *,
    availability: IqaAvailability = IqaAvailability.AVAILABLE,
    valid_count: int = 1,
) -> IqaMeasurementSummary:
    return IqaMeasurementSummary(
        availability=availability,
        weight_sum=float(valid_count),
        weighted_sum=value * valid_count,
        weighted_square_sum=value * value * valid_count,
        valid_count=valid_count,
        weighted_mean=value,
        weighted_std=0.0,
    )


def _result_availability(completeness: IqaResultCompleteness) -> IqaAvailability:
    return (
        IqaAvailability.PARTIAL
        if completeness is IqaResultCompleteness.PARTIAL
        else IqaAvailability.AVAILABLE
    )
