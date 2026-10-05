from __future__ import annotations

import json
import struct
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.remote.iqa_domain import ComparisonMode, LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_public_adapter import (
    P5IqaExecutionAdapter,
    P5IqaReferenceRegistry,
    P5IqaResultAccessAdapter,
    normalize_result_v2,
)
from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaExecutionPort,
    IqaJobReference,
    IqaJobState,
    IqaMeasurementSummary,
    IqaResultAccessPort,
    IqaResultCompleteness,
    IqaResultReference,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    JobState,
)
from pixelscope.remote.iqa_submission import IqaResultReference as P5ResultReference
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.remote.iqa_v2_reader import load_result_v2


class _FakeJobClient(IqaJobClient):
    def __init__(self) -> None:
        self.created_request: IqaJobRequest | None = None

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        self.created_request = request
        return IqaJobCreated("job-public", JobState.QUEUED)

    def get_status(self, job_id: str) -> IqaJobStatus:
        return IqaJobStatus(job_id, JobState.EXTRACTING, 1, 3, "running")

    def get_result(self, job_id: str) -> P5ResultReference:
        return P5ResultReference(job_id, "shared", "results/job-public", 2, "complete")

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        return IqaJobStatus(job_id, JobState.CANCELLED, 1, 3, "cancelled")


def _png(path: Path, width: int = 8, height: int = 6) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    )


def _settings(root: Path) -> RemoteIqaSettings:
    return RemoteIqaSettings(
        "https://provider.invalid",
        (RemoteIqaStorageRoot("shared", str(root)),),
        "shared",
    )


def _intent(a: Path, b: Path) -> IqaSubmissionIntent:
    return IqaSubmissionIntent(
        "current_pair",
        (IqaVariant("A", "A"), IqaVariant("B", "B")),
        (
            IqaSubmissionScene(
                "scene_000000",
                (
                    IqaSubmissionSource("A", a),
                    IqaSubmissionSource("B", b),
                ),
            ),
        ),
    )


def _loaded_v2(root: Path) -> ResultV2:
    outcome = load_result_v2(root)
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, ResultV2)
    return outcome.result


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def test_public_ports_expose_semantics_without_transport_or_storage_topology(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    a = shared / "a.png"
    b = shared / "b.png"
    _png(a)
    _png(b)
    registry = P5IqaReferenceRegistry()
    client = _FakeJobClient()
    adapter = P5IqaExecutionAdapter(client, _settings(shared), registry)

    assert isinstance(adapter, IqaExecutionPort)
    assert [item.name for item in fields(IqaResultReference)] == ["reference_id"]
    assert [item.name for item in fields(IqaSubmissionSource)] == ["variant_id", "local_path"]

    job = adapter.submit(_intent(a, b))
    assert job == IqaJobReference("job-public")
    assert client.created_request is not None
    assert adapter.get_status(job).state is IqaJobState.RUNNING
    assert adapter.get_status(job).progress.completed == 1
    assert adapter.get_result_reference(job) == IqaResultReference("job-public")
    assert adapter.cancel(job).state is IqaJobState.CANCELLED


def test_p5_result_adapter_materializes_and_normalizes_for_existing_client_model(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    result_root = write_golden_result_v2(shared / "results" / "job-public")
    legacy = _loaded_v2(result_root)
    registry = P5IqaReferenceRegistry()
    public_reference = registry.register_result(
        P5ResultReference("job-public", "shared", "results/job-public", 2, "complete")
    )
    adapter = P5IqaResultAccessAdapter(_settings(shared), registry)

    assert isinstance(adapter, IqaResultAccessPort)
    materialized = adapter.materialize(public_reference)
    assert materialized.succeeded
    assert materialized.source is not None
    opened = adapter.open_result(materialized.source)
    assert opened.succeeded
    assert opened.result is not None
    public = opened.result
    assert public.completeness is IqaResultCompleteness.COMPLETE
    assert public.dataset.dataset_id == legacy.result_id
    assert not hasattr(public.scenes[0].sources[0].source, "storage_root_id")
    assert "/" not in public.scenes[0].sources[0].source.relative_path

    legacy_model = IqaExplorerModel(legacy)
    public_model = IqaExplorerModel(public)
    attribute_id = legacy.attributes[0].attribute_id
    variant_id = legacy.variants[0].variant_id
    assert public_model.absolute_dataset_stat(
        variant_id,
        attribute_id,
    ) == legacy_model.absolute_dataset_stat(variant_id, attribute_id)

    reference_id = legacy.variants[0].variant_id
    target_id = legacy.variants[1].variant_id
    public_relative = public_model.prepare_reference(reference_id)
    legacy_relative = legacy_model.prepare_reference(reference_id)
    assert public_relative.relative_dataset_stat(
        attribute_id,
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        reference_id,
        target_id,
    ) == legacy_relative.relative_dataset_stat(
        attribute_id,
        ComparisonMode.RATIO_OF_WEIGHTED_MEANS,
        reference_id,
        target_id,
    )


def test_normalized_result_keeps_spatial_access_lazy_and_failure_explicit(
    tmp_path: Path,
) -> None:
    root = write_golden_result_v2(tmp_path / "lazy")
    legacy = _loaded_v2(root)
    public = normalize_result_v2(legacy)
    manifest = _manifest(root)
    first_scene_id = legacy.scenes[0].scene_id
    grid_path = root / manifest["scenes"][0]["grid_artifact"]["path"]
    grid_path.unlink()

    model = IqaExplorerModel(public)
    attribute_id = legacy.attributes[0].attribute_id
    variant_id = legacy.variants[0].variant_id
    assert model.absolute_dataset_stat(variant_id, attribute_id).valid

    spatial = public.load_spatial(first_scene_id)
    assert spatial.availability is IqaAvailability.FAILED
    assert not spatial.succeeded
    assert spatial.diagnostics[0].scene_id == first_scene_id
    with pytest.raises(ValueError, match=first_scene_id):
        model.prepare_reference(variant_id)


def test_partial_and_missing_states_are_explicit_in_public_domain(tmp_path: Path) -> None:
    root = write_golden_result_v2(tmp_path / "partial", scene_count=4)
    manifest = _manifest(root)
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {"scene_id": scene["scene_id"], "status": "succeeded"} for scene in manifest["scenes"]
    ] + [
        {
            "scene_id": "scene_000004",
            "status": "failed",
            "error": {
                "code": "provider.scene_failed",
                "message": "Scene was not published",
                "retryable": True,
            },
        }
    ]
    _write_manifest(root, manifest)
    outcome = load_result_v2(root)
    assert isinstance(outcome.result, PartialResultV2)

    public = normalize_result_v2(outcome.result)
    assert public.completeness is IqaResultCompleteness.PARTIAL
    assert public.diagnostics[0].scene_id == "scene_000004"
    assert public.diagnostics[0].code == "provider.scene_failed"
    missing = IqaMeasurementSummary.missing("metric_not_published")
    assert missing.availability is IqaAvailability.MISSING
    assert not missing.valid
    assert missing.reason == "metric_not_published"
