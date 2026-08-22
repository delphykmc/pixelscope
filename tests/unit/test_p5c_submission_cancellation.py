from __future__ import annotations

import struct
from pathlib import Path
from threading import Event

import httpx
import pytest

from pixelscope.core.cancellation import CooperativeCancellation, cancellation_scope
from pixelscope.remote.iqa_client import (
    HttpIqaJobClient,
    IqaClientError,
    IqaClientErrorKind,
    IqaCreateOutcomeUnknown,
)
from pixelscope.remote.iqa_mock_transport import MockIqaService, MockJobScript, MockJobStep
from pixelscope.remote.iqa_storage import sha256_file
from pixelscope.remote.iqa_submission import (
    IqaJobRequest,
    JobState,
    PortableSourceRequest,
    SceneRequest,
    pair_folders,
)


def _request() -> IqaJobRequest:
    source_a = PortableSourceRequest("shared", "set/a.png", "a" * 64, 8, 6)
    source_b = PortableSourceRequest("shared", "set/b.png", "b" * 64, 8, 6)
    return IqaJobRequest(
        "current_pair",
        ("A", "B"),
        (SceneRequest("scene_000000", (("A", source_a), ("B", source_b))),),
    )


def _png(path: Path) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 8, 6)
    )


def test_cancelled_scope_interrupts_hash_before_more_io(tmp_path: Path) -> None:
    source = tmp_path / "large.bin"
    source.write_bytes(b"pixelscope" * 100_000)
    event = Event()
    event.set()

    with cancellation_scope(event), pytest.raises(CooperativeCancellation):
        sha256_file(source)


def test_cancelled_scope_interrupts_folder_preflight(tmp_path: Path) -> None:
    folder_a = tmp_path / "A"
    folder_b = tmp_path / "B"
    folder_a.mkdir()
    folder_b.mkdir()
    _png(folder_a / "a.png")
    _png(folder_b / "b.png")
    event = Event()
    event.set()

    with cancellation_scope(event), pytest.raises(CooperativeCancellation):
        pair_folders(folder_a, folder_b)


def test_cancelled_scope_blocks_create_before_post() -> None:
    service = MockIqaService((MockJobScript((MockJobStep(JobState.QUEUED),)),))
    client = HttpIqaJobClient("https://mock.invalid", transport=service.transport())
    event = Event()
    event.set()

    with cancellation_scope(event), pytest.raises(CooperativeCancellation):
        client.create_job(_request())

    assert service.request_counts[("POST", "/v1/iqa/jobs")] == 0


def test_create_5xx_is_explicit_unknown_and_never_retried() -> None:
    service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.QUEUED),),
                create_status_code=503,
            ),
        )
    )
    client = HttpIqaJobClient("https://mock.invalid", transport=service.transport())

    with pytest.raises(IqaCreateOutcomeUnknown) as raised:
        client.create_job(_request())

    assert raised.value.kind is IqaClientErrorKind.HTTP
    assert raised.value.status_code == 503
    assert "do not blindly resubmit" in str(raised.value)
    assert service.request_counts[("POST", "/v1/iqa/jobs")] == 1


def test_create_4xx_remains_known_http_rejection() -> None:
    service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.QUEUED),),
                create_status_code=400,
            ),
        )
    )
    client = HttpIqaJobClient("https://mock.invalid", transport=service.transport())

    with pytest.raises(IqaClientError) as raised:
        client.create_job(_request())

    assert not isinstance(raised.value, IqaCreateOutcomeUnknown)
    assert raised.value.kind is IqaClientErrorKind.HTTP
    assert raised.value.status_code == 400
    assert service.request_counts[("POST", "/v1/iqa/jobs")] == 1


def test_create_success_with_unusable_job_id_is_explicit_unknown() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            request=request,
            json={"job_id": "bad/id", "state": "queued"},
        )

    client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(IqaCreateOutcomeUnknown) as raised:
        client.create_job(_request())

    assert raised.value.kind is IqaClientErrorKind.PROTOCOL
    assert calls == 1
