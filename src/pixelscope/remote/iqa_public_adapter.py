"""Compatibility adapters from the existing P5 implementation to the public IQA seam.

This module is intentionally transitional. It may know current P5 settings, storage,
and job-domain types so those details do not cross the Client-owned public contract.
It does not alter current production composition or lifecycle ownership.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.remote.iqa_domain import LoadStatus, Source
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
    IqaResolvedSource,
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
    IqaSpatialLoadOutcome,
    IqaSpatialSceneData,
    IqaSubmissionIntent,
    IqaVariant,
)
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import (
    StorageResolutionError,
    resolve_existing_source,
    resolve_result_reference,
    validate_relative_path,
)
from pixelscope.remote.iqa_submission import (
    FolderPairEntry,
    IqaJobRequest,
    IqaJobStatus,
    JobState,
    build_request,
    probe_image,
)
from pixelscope.remote.iqa_submission import IqaResultReference as P5ResultReference
from pixelscope.remote.iqa_v2_domain import MeasurementSummary, ResultV2
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.remote.iqa_v2_reader import load_grid_scene


class P5IqaReferenceRegistry:
    """Keep current P5 storage/source locators behind opaque public references."""

    def __init__(self) -> None:
        self._results: dict[str, P5ResultReference] = {}
        self._sources: dict[str, Source] = {}

    def register_result(self, reference: P5ResultReference) -> IqaResultReference:
        self._results[reference.job_id] = reference
        return IqaResultReference(reference.job_id)

    def result(self, reference: IqaResultReference) -> P5ResultReference | None:
        return self._results.get(reference.reference_id)

    def register_source(self, locator: IqaSourceLocator, source: Source) -> None:
        self._sources[locator.locator_id] = source

    def source(self, locator: IqaSourceLocator) -> Source | None:
        return self._sources.get(locator.locator_id)


class P5IqaExecutionAdapter:
    """Expose current P5 job execution through the company-neutral control plane."""

    def __init__(
        self,
        client: IqaJobClient,
        settings: RemoteIqaSettings,
        registry: P5IqaReferenceRegistry,
    ) -> None:
        self._client = client
        self._settings = settings
        self._registry = registry

    @property
    def capabilities(self) -> IqaExecutionCapabilities:
        return IqaExecutionCapabilities(can_cancel=True)

    def submit(self, intent: IqaSubmissionIntent) -> IqaJobReference:
        request = _legacy_request(intent, self._settings)
        created = self._client.create_job(request)
        return IqaJobReference(created.job_id)

    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot:
        return _public_job_snapshot(self._client.get_status(reference.job_id))

    def get_result_reference(self, reference: IqaJobReference) -> IqaResultReference:
        legacy = self._client.get_result(reference.job_id)
        return self._registry.register_result(legacy)

    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot:
        return _public_job_snapshot(self._client.cancel_job(reference.job_id))


class P5IqaResultAccessAdapter:
    """Resolve/open current P5 publications without exposing storage-root semantics."""

    def __init__(
        self,
        settings: RemoteIqaSettings,
        registry: P5IqaReferenceRegistry,
    ) -> None:
        self._settings = settings
        self._registry = registry

    def materialize(self, reference: IqaResultReference) -> IqaResultSourceOutcome:
        legacy = self._registry.result(reference)
        if legacy is None:
            diagnostic = IqaDiagnostic(
                "unknown_result_reference",
                "Result reference is not known to this provider instance.",
            )
            return IqaResultSourceOutcome(IqaAvailability.MISSING, diagnostics=(diagnostic,))
        try:
            root = resolve_result_reference(
                legacy.storage_root_id,
                legacy.relative_path,
                self._settings,
            )
        except (StorageResolutionError, OSError, ValueError) as exc:
            diagnostic = IqaDiagnostic("result_materialization_failed", str(exc))
            return IqaResultSourceOutcome(IqaAvailability.FAILED, diagnostics=(diagnostic,))
        completeness = (
            IqaResultCompleteness.PARTIAL
            if legacy.publication_state == "partial"
            else IqaResultCompleteness.COMPLETE
        )
        availability = (
            IqaAvailability.PARTIAL
            if completeness is IqaResultCompleteness.PARTIAL
            else IqaAvailability.AVAILABLE
        )
        return IqaResultSourceOutcome(
            availability,
            source=IqaResultSource(root, completeness),
        )

    def open_result(self, source: IqaResultSource) -> IqaResultOpenOutcome:
        if not source.root.exists():
            diagnostic = IqaDiagnostic(
                "result_source_missing",
                "Result source is not available locally.",
            )
            return IqaResultOpenOutcome(IqaAvailability.MISSING, diagnostics=(diagnostic,))
        outcome = load_result(source.root)
        if outcome.status is not LoadStatus.SUCCESS or outcome.result is None:
            diagnostic = IqaDiagnostic(
                "result_open_failed",
                outcome.reason or f"unable to open IQA result ({outcome.status.value})",
            )
            return IqaResultOpenOutcome(IqaAvailability.FAILED, diagnostics=(diagnostic,))
        if not isinstance(outcome.result, ResultV2):
            diagnostic = IqaDiagnostic(
                "unsupported_public_result",
                "The public Slice 2 seam currently normalizes schema-v2 results only.",
            )
            return IqaResultOpenOutcome(IqaAvailability.FAILED, diagnostics=(diagnostic,))
        normalized = normalize_result_v2(
            outcome.result,
            registry=self._registry,
            completeness=source.completeness,
        )
        availability = (
            IqaAvailability.PARTIAL
            if normalized.completeness is IqaResultCompleteness.PARTIAL
            else IqaAvailability.AVAILABLE
        )
        return IqaResultOpenOutcome(
            availability,
            result=normalized,
            diagnostics=normalized.diagnostics,
        )

    def resolve_source(self, locator: IqaSourceLocator) -> IqaResolvedSource | None:
        source = self._registry.source(locator)
        if source is None or source.storage_root_id is None:
            return None
        root = self._settings.root(source.storage_root_id)
        if root is None:
            return None
        try:
            validate_relative_path(source.relative_path)
            candidate = Path(root.client_path).joinpath(*PurePosixPath(source.relative_path).parts)
            resolved = resolve_existing_source(candidate, self._settings)
        except (StorageResolutionError, OSError, ValueError):
            return None
        if resolved is None:
            return None
        if (
            resolved.logical_path.storage_root_id != source.storage_root_id
            or resolved.logical_path.relative_path != source.relative_path
        ):
            return None
        return IqaResolvedSource(resolved.local_path)


class _P5SpatialAccess:
    """Lazy bridge: no grid artifact is opened until the Client asks for one Scene."""

    def __init__(
        self,
        result: ResultV2,
        completeness: IqaResultCompleteness,
    ) -> None:
        self._result = result
        self._completeness = completeness

    def load_scene(self, scene_id: str) -> IqaSpatialLoadOutcome:
        if scene_id not in {scene.scene_id for scene in self._result.scenes}:
            availability = (
                IqaAvailability.MISSING
                if self._completeness is IqaResultCompleteness.PARTIAL
                else IqaAvailability.FAILED
            )
            diagnostic = IqaDiagnostic(
                "spatial_scene_not_published"
                if availability is IqaAvailability.MISSING
                else "spatial_scene_unknown",
                "Scene spatial data was not published."
                if availability is IqaAvailability.MISSING
                else "Scene is not part of this result.",
                scene_id=scene_id,
            )
            return IqaSpatialLoadOutcome(availability, diagnostics=(diagnostic,))

        outcome = load_grid_scene(self._result, scene_id)
        if not outcome.succeeded or outcome.data is None:
            diagnostic = IqaDiagnostic(
                "spatial_data_failed",
                outcome.reason or "Scene spatial data could not be loaded.",
                scene_id=scene_id,
            )
            return IqaSpatialLoadOutcome(IqaAvailability.FAILED, diagnostics=(diagnostic,))
        data = outcome.data
        return IqaSpatialLoadOutcome(
            IqaAvailability.AVAILABLE,
            data=IqaSpatialSceneData(
                scene_id=data.scene_id,
                variant_ids=data.variant_ids,
                source_ids=data.source_ids,
                attributes=data.attributes,
            ),
        )


def normalize_result_v2(
    result: ResultV2,
    *,
    registry: P5IqaReferenceRegistry | None = None,
    completeness: IqaResultCompleteness | None = None,
) -> IqaResult:
    """Project the existing schema-v2 result into the Client-owned public domain."""

    detected_completeness = (
        IqaResultCompleteness.PARTIAL
        if isinstance(result, PartialResultV2)
        else IqaResultCompleteness.COMPLETE
    )
    selected_completeness = completeness or detected_completeness
    if detected_completeness is IqaResultCompleteness.PARTIAL:
        selected_completeness = IqaResultCompleteness.PARTIAL

    diagnostics = _partial_diagnostics(result)
    scenes: list[IqaScene] = []
    for scene in result.scenes:
        public_sources: list[IqaSceneSource] = []
        for measurement in scene.sources:
            source = measurement.source
            locator = IqaSourceLocator(
                locator_id=f"{result.result_id}:{source.source_id}",
                display_name=PurePosixPath(source.relative_path).name,
            )
            if registry is not None:
                registry.register_source(locator, source)
            public_source = IqaSource(
                source_id=source.source_id,
                locator=locator,
                sha256=source.sha256,
                width=source.width,
                height=source.height,
            )
            public_sources.append(
                IqaSceneSource(
                    variant_id=measurement.variant_id,
                    source=public_source,
                    geometry=measurement.geometry,
                    grids=dict(measurement.grids),
                    summaries={
                        attribute_id: _public_measurement(summary)
                        for attribute_id, summary in measurement.summaries.items()
                    },
                )
            )
        scenes.append(IqaScene(scene.scene_id, tuple(public_sources)))

    dataset_summaries = {
        key: IqaDatasetSummary(
            pooled=_public_measurement(summary.pooled),
            scene_mean=summary.scene_mean,
            scene_std=summary.scene_std,
            scene_count=summary.scene_count,
        )
        for key, summary in result.dataset_summaries.items()
    }
    return IqaResult(
        root=result.root,
        result_id=result.result_id,
        schema_version=result.schema_version,
        dataset=IqaDatasetMetadata(result.result_id, result.root.name),
        variants=tuple(IqaVariant(item.variant_id, item.label) for item in result.variants),
        attributes=result.attributes,
        scenes=tuple(scenes),
        dataset_summaries=dataset_summaries,
        completeness=selected_completeness,
        diagnostics=diagnostics,
        spatial_access=_P5SpatialAccess(result, selected_completeness),
    )


def _legacy_request(
    intent: IqaSubmissionIntent,
    settings: RemoteIqaSettings,
) -> IqaJobRequest:
    variant_ids = tuple(item.variant_id for item in intent.variants)
    if variant_ids != ("A", "B"):
        raise ValueError(
            "the transitional P5 adapter supports the existing ordered A/B inputs only"
        )
    entries: list[FolderPairEntry] = []
    for scene in intent.scenes:
        paths = {item.variant_id: item.local_path for item in scene.sources}
        entries.append(
            FolderPairEntry(
                scene.scene_id,
                probe_image(paths["A"]),
                probe_image(paths["B"]),
            )
        )
    return build_request(tuple(entries), settings, submission_kind=intent.submission_kind)


def _public_job_snapshot(status: IqaJobStatus) -> IqaJobSnapshot:
    return IqaJobSnapshot(
        reference=IqaJobReference(status.job_id),
        state=_public_job_state(status.state),
        progress=IqaJobProgress(status.completed_scenes, status.total_scenes),
        message=status.message,
    )


def _public_job_state(state: JobState) -> IqaJobState:
    if state is JobState.QUEUED:
        return IqaJobState.QUEUED
    if state in {
        JobState.PREPARING,
        JobState.EXTRACTING,
        JobState.AGGREGATING,
        JobState.WRITING,
    }:
        return IqaJobState.RUNNING
    if state in {JobState.SUCCEEDED, JobState.PARTIAL}:
        return IqaJobState.COMPLETED
    if state is JobState.CANCELLED:
        return IqaJobState.CANCELLED
    return IqaJobState.FAILED


def _public_measurement(summary: MeasurementSummary) -> IqaMeasurementSummary:
    if not summary.valid or summary.weighted_mean is None:
        return IqaMeasurementSummary.missing()
    return IqaMeasurementSummary(
        availability=IqaAvailability.AVAILABLE,
        weight_sum=summary.weight_sum,
        weighted_sum=summary.weighted_sum,
        weighted_square_sum=summary.weighted_square_sum,
        valid_count=summary.valid_count,
        weighted_mean=summary.weighted_mean,
        weighted_std=summary.weighted_std,
    )


def _partial_diagnostics(result: ResultV2) -> tuple[IqaDiagnostic, ...]:
    if not isinstance(result, PartialResultV2):
        return ()
    diagnostics: list[IqaDiagnostic] = []
    for outcome in result.unsuccessful_scene_outcomes:
        diagnostics.append(
            IqaDiagnostic(
                code=outcome.error_code or f"scene_{outcome.status}",
                message=outcome.error_message or f"Scene {outcome.status}",
                scene_id=outcome.scene_id,
            )
        )
    return tuple(diagnostics)
