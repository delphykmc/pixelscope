from __future__ import annotations

import hashlib
import os
import struct
from contextlib import suppress
from pathlib import Path

import pytest

from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaClientError
from pixelscope.remote.iqa_mock_transport import (
    MockIqaService,
    MockJobScript,
    MockJobStep,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_storage import (
    StorageResolutionError,
    resolve_result_reference,
    sha256_file,
    stage_source,
    validate_relative_path,
)
from pixelscope.remote.iqa_submission import (
    IqaJobRequest,
    JobState,
    PortableSourceRequest,
    PreflightError,
    SceneRequest,
    pair_current_paths,
    pair_folders,
    probe_image,
)


def _png(path: Path, width: int, height: int) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )


def _request() -> IqaJobRequest:
    source_a = PortableSourceRequest(
        "shared",
        "set/a.png",
        "a" * 64,
        640,
        480,
    )
    source_b = PortableSourceRequest(
        "shared",
        "set/b.png",
        "b" * 64,
        640,
        480,
    )
    return IqaJobRequest(
        "current_pair",
        ("A", "B"),
        (SceneRequest("scene_000000", (("A", source_a), ("B", source_b))),),
    )


def _result_ref(state: str = "complete") -> dict[str, object]:
    return {
        "storage_root_id": "shared",
        "relative_path": "results/job_000001",
        "schema_version": 2,
        "publication_state": state,
    }


def test_remote_settings_validate_portable_ids_drive_unc_and_staging_membership() -> None:
    drive = RemoteIqaStorageRoot("drive.root", "C:/images")
    unc = RemoteIqaStorageRoot("unc-root", r"\\server\iqa")
    settings = RemoteIqaSettings(
        "https://iqa.example.test",
        (drive, unc),
        "unc-root",
    )
    assert settings.submission_configured
    assert settings.root("drive.root") == drive

    with pytest.raises(ValueError):
        RemoteIqaStorageRoot("bad/root", "C:/images")
    with pytest.raises(ValueError):
        RemoteIqaStorageRoot("relative", "images")
    with pytest.raises(ValueError):
        RemoteIqaSettings(storage_roots=(drive, drive))
    with pytest.raises(ValueError):
        RemoteIqaSettings(storage_roots=(drive,), staging_root_id="missing")
    with pytest.raises(ValueError):
        RemoteIqaSettings(server_base_url="https://user:secret@example.test")


def test_portable_relative_path_rejects_traversal_and_absolute_forms() -> None:
    validate_relative_path("dataset/scene.png")
    for value in (
        "../escape",
        "dataset/../escape",
        "/absolute",
        "C:/absolute",
        r"a\b",
    ):
        with pytest.raises(StorageResolutionError):
            validate_relative_path(value)


def test_streaming_sha_and_staging_are_atomic_and_content_addressed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "outside" / "sample.bin"
    source.parent.mkdir()
    payload = b"pixel-scope" * 100_000
    source.write_bytes(payload)
    staging = tmp_path / "share"
    staging.mkdir()

    expected = hashlib.sha256(payload).hexdigest()
    assert sha256_file(source, chunk_size=31) == expected

    first = stage_source(source, staging, "stage")
    second = stage_source(source, staging, "stage")

    expected_final = staging / "staging" / expected / source.name
    assert first.local_path == second.local_path == expected_final
    assert first.sha256 == second.sha256 == expected
    assert expected_final.read_bytes() == payload
    assert not expected_final.with_name(expected_final.name + ".part").exists()


def test_existing_staged_target_is_reused_only_after_identity_verification(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"identity")
    staging = tmp_path / "share"
    staging.mkdir()
    staged = stage_source(source, staging, "stage")
    staged.local_path.write_bytes(b"tampered")

    with pytest.raises(StorageResolutionError, match="identity verification"):
        stage_source(source, staging, "stage")


def test_header_only_preflight_and_current_pair_dimension_contract(
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.PNG"
    b = tmp_path / "b.jpeg"
    raw = tmp_path / "raw.RAW"
    _png(a, 640, 480)
    # JPEG SOI + SOF0 length/precision/height/width is enough for the bounded marker probe.
    b.write_bytes(
        b"\xff\xd8\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", 480, 640)
        + b"\x03"
        + b"\x00" * 9
    )
    raw.write_bytes(b"raw")

    assert probe_image(a).width == 640
    assert pair_current_paths(a, b)[0].scene_id == "scene_000000"
    with pytest.raises(PreflightError, match="RAW"):
        probe_image(raw)

    mismatch = tmp_path / "mismatch.png"
    _png(mismatch, 641, 480)
    with pytest.raises(PreflightError, match="dimension mismatch"):
        pair_current_paths(a, mismatch)


def test_folder_pair_is_immediate_regular_non_symlink_nfc_lexical_and_full(
    tmp_path: Path,
) -> None:
    folder_a = tmp_path / "A"
    folder_b = tmp_path / "B"
    folder_a.mkdir()
    folder_b.mkdir()
    for name in ("B.png", "a.PNG", ".hidden.bmp"):
        _png(folder_a / name, 8, 6)
    for name in ("2.png", "1.PNG", ".zero.bmp"):
        _png(folder_b / name, 8, 6)
    (folder_a / "nested").mkdir()
    _png(folder_a / "nested" / "ignored.png", 8, 6)
    (folder_a / "ignored.raw").write_bytes(b"raw")
    with suppress(OSError):
        (folder_a / "link.png").symlink_to(folder_a / "a.PNG")

    paired = pair_folders(folder_a, folder_b)

    assert [item.scene_id for item in paired] == [
        "scene_000000",
        "scene_000001",
        "scene_000002",
    ]
    assert [item.source_a.path.name for item in paired] == [
        ".hidden.bmp",
        "a.PNG",
        "B.png",
    ]
    assert [item.source_b.path.name for item in paired] == [
        ".zero.bmp",
        "1.PNG",
        "2.png",
    ]


def test_folder_pair_count_and_dimension_errors_block_before_request(
    tmp_path: Path,
) -> None:
    folder_a = tmp_path / "A"
    folder_b = tmp_path / "B"
    folder_a.mkdir()
    folder_b.mkdir()
    _png(folder_a / "a.png", 8, 6)
    with pytest.raises(PreflightError, match="count mismatch"):
        pair_folders(folder_a, folder_b)

    _png(folder_b / "a.png", 9, 6)
    with pytest.raises(PreflightError, match="dimension mismatch"):
        pair_folders(folder_a, folder_b)


def test_request_json_freezes_explicit_variant_scene_order_and_portable_identity() -> None:
    payload = _request().to_json()
    assert payload == {
        "submission_kind": "current_pair",
        "variants": [{"variant_id": "A"}, {"variant_id": "B"}],
        "scenes": [
            {
                "scene_id": "scene_000000",
                "sources": [
                    {
                        "variant_id": "A",
                        "storage_root_id": "shared",
                        "relative_path": "set/a.png",
                        "sha256": "a" * 64,
                        "width": 640,
                        "height": 480,
                    },
                    {
                        "variant_id": "B",
                        "storage_root_id": "shared",
                        "relative_path": "set/b.png",
                        "sha256": "b" * 64,
                        "width": 640,
                        "height": 480,
                    },
                ],
            }
        ],
    }
    serialized = repr(payload)
    assert "C:/" not in serialized and "\\\\server" not in serialized


def test_http_client_uses_iqa_endpoints_and_scripted_progress_to_complete() -> None:
    service = MockIqaService(
        (
            MockJobScript(
                (
                    MockJobStep(JobState.QUEUED, 0, 1),
                    MockJobStep(JobState.EXTRACTING, 0, 1),
                    MockJobStep(JobState.SUCCEEDED, 1, 1),
                ),
                _result_ref(),
            ),
        )
    )
    client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=service.transport(),
    )

    created = client.create_job(_request())
    first = client.get_status(created.job_id)
    second = client.get_status(created.job_id)
    terminal = client.get_status(created.job_id)
    result = client.get_result(created.job_id)

    assert created.state is JobState.QUEUED
    assert [first.state, second.state, terminal.state] == [
        JobState.QUEUED,
        JobState.EXTRACTING,
        JobState.SUCCEEDED,
    ]
    assert result.publication_state == "complete"
    assert service.request_counts[("POST", "/v1/iqa/jobs")] == 1
    assert service.created_requests == [_request().to_json()]


def test_create_job_failure_is_not_retried() -> None:
    service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.QUEUED),),
                create_status_code=503,
            ),
        )
    )
    client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=service.transport(),
    )

    with pytest.raises(IqaClientError):
        client.create_job(_request())

    assert service.request_counts[("POST", "/v1/iqa/jobs")] == 1


def test_cancel_races_preserve_server_terminal_decision_and_partial_result() -> None:
    partial_service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.EXTRACTING, 1, 2),),
                _result_ref("partial"),
            ),
        )
    )
    partial_client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=partial_service.transport(),
    )
    job = partial_client.create_job(_request())
    cancelled = partial_client.cancel_job(job.job_id)
    assert cancelled.state is JobState.PARTIAL
    assert partial_client.get_result(job.job_id).publication_state == "partial"

    complete_service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.SUCCEEDED, 2, 2),),
                _result_ref(),
            ),
        )
    )
    complete_client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=complete_service.transport(),
    )
    complete_job = complete_client.create_job(_request())
    assert complete_client.cancel_job(complete_job.job_id).state is JobState.SUCCEEDED


def test_malformed_status_is_protocol_error() -> None:
    service = MockIqaService(
        (
            MockJobScript(
                (MockJobStep(JobState.QUEUED),),
                malformed_status=True,
            ),
        )
    )
    client = HttpIqaJobClient(
        "https://mock.invalid",
        transport=service.transport(),
    )
    job = client.create_job(_request())
    with pytest.raises(IqaClientError):
        client.get_status(job.job_id)


@pytest.mark.skipif(
    os.name != "nt",
    reason="client storage mappings intentionally require drive/UNC paths",
)
def test_logical_result_reference_resolves_only_through_current_mapping(
    tmp_path: Path,
) -> None:
    result = tmp_path / "results" / "job"
    result.mkdir(parents=True)
    root = RemoteIqaStorageRoot("shared", str(tmp_path))
    settings = RemoteIqaSettings(storage_roots=(root,))

    assert resolve_result_reference("shared", "results/job", settings) == result
    with pytest.raises(StorageResolutionError, match="not configured"):
        resolve_result_reference("missing", "results/job", settings)
