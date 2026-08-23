from __future__ import annotations

import pytest

from pixelscope.remote.iqa_client import IqaClientError, IqaClientErrorKind, IqaJobClient
from pixelscope.remote.iqa_compatibility_probe import run_iqa_compatibility_probe
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
    PortableSourceRequest,
    SceneRequest,
)


class _ScriptedClient(IqaJobClient):
    def __init__(self, states: list[JobState]) -> None:
        self.states = list(states)
        self.create_calls = 0
        self.status_calls = 0
        self.result_calls = 0
        self.cancel_calls = 0

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        self.create_calls += 1
        return IqaJobCreated("job-1", JobState.QUEUED)

    def get_status(self, job_id: str) -> IqaJobStatus:
        self.status_calls += 1
        state = self.states.pop(0)
        completed = 1 if state in {JobState.EXTRACTING, JobState.SUCCEEDED} else 0
        return IqaJobStatus(job_id, state, completed, 1)

    def get_result(self, job_id: str) -> IqaResultReference:
        self.result_calls += 1
        return IqaResultReference(job_id, "shared", "results/job-1", 2, "complete")

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        self.cancel_calls += 1
        return IqaJobStatus(job_id, JobState.CANCELLED, 0, 1)


def _request(scene_count: int = 1) -> IqaJobRequest:
    scenes = []
    for index in range(scene_count):
        source_a = PortableSourceRequest(
            "shared",
            f"a/{index:06d}.png",
            "a" * 64,
            1920,
            1080,
        )
        source_b = PortableSourceRequest(
            "shared",
            f"b/{index:06d}.png",
            "b" * 64,
            1920,
            1080,
        )
        scenes.append(
            SceneRequest(
                f"scene_{index:06d}",
                (("A", source_a), ("B", source_b)),
            )
        )
    return IqaJobRequest("folder_pair", ("A", "B"), tuple(scenes))


def test_probe_uses_single_create_serial_status_and_terminal_result() -> None:
    client = _ScriptedClient([JobState.PREPARING, JobState.EXTRACTING, JobState.SUCCEEDED])

    trace = run_iqa_compatibility_probe(client, _request())

    assert client.create_calls == 1
    assert client.status_calls == 3
    assert client.result_calls == 1
    assert client.cancel_calls == 0
    assert trace.state_sequence == ("queued", "preparing", "extracting", "succeeded")
    assert trace.terminal_state == "succeeded"
    assert trace.result_schema_version == 2
    assert trace.result_publication_state == "complete"
    assert trace.result_storage_root_id == "shared"
    assert trace.result_relative_path == "results/job-1"
    assert trace.error_kind is None


def test_probe_cancel_is_single_bounded_operation() -> None:
    client = _ScriptedClient([JobState.PREPARING, JobState.EXTRACTING])

    trace = run_iqa_compatibility_probe(
        client,
        _request(),
        cancel_after_status_requests=1,
    )

    assert client.create_calls == 1
    assert client.status_calls == 1
    assert client.cancel_calls == 1
    assert client.result_calls == 0
    assert trace.terminal_state == "cancelled"


def test_probe_records_classified_transport_error_without_retrying_create() -> None:
    class FailingClient(_ScriptedClient):
        def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
            self.create_calls += 1
            raise IqaClientError(IqaClientErrorKind.TIMEOUT, "private endpoint detail")

    client = FailingClient([])

    trace = run_iqa_compatibility_probe(client, _request())

    assert client.create_calls == 1
    assert trace.error_kind == "timeout"
    assert trace.error_message == "timeout"
    assert "private" not in (trace.error_message or "")


@pytest.mark.parametrize("scene_count", [1, 10, 50, 150, 300])
def test_large_request_workloads_preserve_order_without_binary_fixture(scene_count: int) -> None:
    request = _request(scene_count)
    payload = request.to_json()

    scenes = payload["scenes"]
    assert isinstance(scenes, list)
    assert len(scenes) == scene_count
    assert scenes[0]["scene_id"] == "scene_000000"
    assert scenes[-1]["scene_id"] == f"scene_{scene_count - 1:06d}"
    assert all(
        [source["variant_id"] for source in scene["sources"]] == ["A", "B"]
        for scene in scenes
    )
