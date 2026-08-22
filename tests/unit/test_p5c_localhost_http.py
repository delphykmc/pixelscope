from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pixelscope.remote.iqa_client import (
    HttpIqaJobClient,
    IqaClientError,
    IqaClientErrorKind,
)
from pixelscope.remote.iqa_localhost_server import (
    LocalhostIqaServer,
    LocalhostIqaServerConfig,
)
from pixelscope.remote.iqa_submission import (
    IqaJobRequest,
    JobState,
    PortableSourceRequest,
    SceneRequest,
)


def _request(scene_count: int = 1) -> IqaJobRequest:
    scenes = []
    for index in range(scene_count):
        source_a = PortableSourceRequest(
            "debug_iqa",
            f"set/a_{index}.png",
            "a" * 64,
            640,
            480,
        )
        source_b = PortableSourceRequest(
            "debug_iqa",
            f"set/b_{index}.png",
            "b" * 64,
            640,
            480,
        )
        scenes.append(
            SceneRequest(
                f"scene_{index:06d}",
                (("A", source_a), ("B", source_b)),
            )
        )
    return IqaJobRequest("folder_pair", ("A", "B"), tuple(scenes))


def test_localhost_server_exercises_real_http_and_captures_create_request(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "last_request.json"
    config = LocalhostIqaServerConfig(
        scenario="normal",
        storage_root_id="debug_iqa",
        result_relative_path="results/debug-complete",
        last_request_path=capture,
    )
    with LocalhostIqaServer(config) as server:
        client = HttpIqaJobClient(server.base_url, timeout_seconds=2.0)
        created = client.create_job(_request())
        first = client.get_status(created.job_id)
        terminal = client.get_status(created.job_id)
        result = client.get_result(created.job_id)
        client.close()

    assert created.state is JobState.QUEUED
    assert first.state is JobState.EXTRACTING
    assert terminal.state is JobState.SUCCEEDED
    assert result.storage_root_id == "debug_iqa"
    assert result.relative_path == "results/debug-complete"
    assert json.loads(capture.read_text(encoding="utf-8")) == _request().to_json()


def test_localhost_transient_result_failure_is_http_error_then_recovers() -> None:
    config = LocalhostIqaServerConfig(
        scenario="result-500-once",
        result_relative_path="results/debug-complete",
    )
    with LocalhostIqaServer(config) as server:
        client = HttpIqaJobClient(server.base_url, timeout_seconds=2.0)
        created = client.create_job(_request())
        client.get_status(created.job_id)
        terminal = client.get_status(created.job_id)
        assert terminal.state is JobState.SUCCEEDED

        with pytest.raises(IqaClientError) as exc_info:
            client.get_result(created.job_id)
        assert exc_info.value.kind is IqaClientErrorKind.HTTP

        result = client.get_result(created.job_id)
        client.close()

    assert result.publication_state == "complete"


def test_localhost_malformed_json_is_protocol_error() -> None:
    config = LocalhostIqaServerConfig(scenario="malformed-json")
    with LocalhostIqaServer(config) as server:
        client = HttpIqaJobClient(server.base_url, timeout_seconds=2.0)
        created = client.create_job(_request())
        with pytest.raises(IqaClientError) as exc_info:
            client.get_status(created.job_id)
        client.close()

    assert exc_info.value.kind is IqaClientErrorKind.PROTOCOL


def test_client_classifies_connection_timeout_and_configuration_errors() -> None:
    def connect_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = HttpIqaJobClient(
        "http://127.0.0.1:8765",
        transport=httpx.MockTransport(connect_failure),
    )
    with pytest.raises(IqaClientError) as connect_info:
        client.create_job(_request())
    client.close()
    assert connect_info.value.kind is IqaClientErrorKind.CONNECT

    def timeout_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("scripted timeout", request=request)

    client = HttpIqaJobClient(
        "http://127.0.0.1:8765",
        transport=httpx.MockTransport(timeout_failure),
    )
    with pytest.raises(IqaClientError) as timeout_info:
        client.create_job(_request())
    client.close()
    assert timeout_info.value.kind is IqaClientErrorKind.TIMEOUT

    with pytest.raises(IqaClientError) as config_info:
        HttpIqaJobClient("not-a-server-url")
    assert config_info.value.kind is IqaClientErrorKind.CONFIG


@pytest.mark.parametrize("scenario", ("wrong-job-id", "wrong-schema"))
def test_localhost_identity_and_schema_faults_are_protocol_errors(scenario: str) -> None:
    config = LocalhostIqaServerConfig(scenario=scenario)
    with LocalhostIqaServer(config) as server:
        client = HttpIqaJobClient(server.base_url, timeout_seconds=2.0)
        created = client.create_job(_request())
        if scenario == "wrong-job-id":
            with pytest.raises(IqaClientError) as exc_info:
                client.get_status(created.job_id)
        else:
            client.get_status(created.job_id)
            client.get_status(created.job_id)
            with pytest.raises(IqaClientError) as exc_info:
                client.get_result(created.job_id)
        client.close()

    assert exc_info.value.kind is IqaClientErrorKind.PROTOCOL
