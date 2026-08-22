from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelscope.remote.iqa_debug_fixture import DebugResultMode, write_debug_result_bundle
from pixelscope.remote.iqa_debug_replay import (
    DEBUG_REPLAY_FORMAT,
    ReplayValidationError,
    load_replay_record,
    parse_replay_record,
)
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_submission import JobState
from pixelscope.remote.iqa_v2_partial import PartialResultV2


def test_complete_debug_bundle_uses_logical_reference_and_canonical_v2_loader(
    tmp_path: Path,
) -> None:
    bundle = write_debug_result_bundle(
        tmp_path,
        "debug_iqa",
        "results/job_debug_complete",
        mode=DebugResultMode.COMPLETE,
        job_id="job_debug_complete",
    )

    replay = load_replay_record(bundle.replay_path)
    outcome = load_result(bundle.result_root)

    assert replay.state is JobState.SUCCEEDED
    assert replay.completed_scenes == replay.total_scenes == 3
    assert replay.result_reference.storage_root_id == "debug_iqa"
    assert replay.result_reference.relative_path == "results/job_debug_complete"
    assert replay.result_reference.publication_state == "complete"
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert not isinstance(outcome.result, PartialResultV2)
    replay_text = bundle.replay_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in replay_text
    assert "result_path" not in replay_text


@pytest.mark.parametrize(
    ("mode", "failed_status"),
    (
        (DebugResultMode.PARTIAL_FAILED, "failed"),
        (DebugResultMode.PARTIAL_CANCELLED, "cancelled"),
    ),
)
def test_partial_debug_bundle_preserves_three_successful_scenes(
    tmp_path: Path,
    mode: DebugResultMode,
    failed_status: str,
) -> None:
    bundle = write_debug_result_bundle(
        tmp_path,
        "debug_iqa",
        f"results/job_debug_{failed_status}",
        mode=mode,
        job_id=f"job_debug_{failed_status}",
    )

    replay = load_replay_record(bundle.replay_path)
    outcome = load_result(bundle.result_root)

    assert replay.state is JobState.PARTIAL
    assert replay.completed_scenes == 3
    assert replay.total_scenes == 4
    assert replay.result_reference.publication_state == "partial"
    assert outcome.status is LoadStatus.SUCCESS, outcome.reason
    assert isinstance(outcome.result, PartialResultV2)
    result = outcome.result
    assert result.successful_scene_count == 3
    assert result.requested_scene_count == 4
    assert len(result.unsuccessful_scene_outcomes) == 1
    assert result.unsuccessful_scene_outcomes[0].status == failed_status


def _valid_replay() -> dict[str, object]:
    return {
        "debug_format": DEBUG_REPLAY_FORMAT,
        "job_id": "job_debug_000001",
        "submission_kind": "folder_pair",
        "state": "succeeded",
        "completed_scenes": 3,
        "total_scenes": 3,
        "message": "synthetic debug result",
        "result_reference": {
            "job_id": "job_debug_000001",
            "storage_root_id": "debug_iqa",
            "relative_path": "results/job_debug_000001",
            "schema_version": 2,
            "publication_state": "complete",
        },
    }


@pytest.mark.parametrize(
    "mutate",
    (
        lambda payload: payload.update({"result_path": "C:/private/result"}),
        lambda payload: payload.update({"state": "queued"}),
        lambda payload: payload["result_reference"].update(  # type: ignore[union-attr]
            {"relative_path": "C:/private/result"}
        ),
        lambda payload: payload["result_reference"].update(  # type: ignore[union-attr]
            {"publication_state": "partial"}
        ),
        lambda payload: payload["result_reference"].update(  # type: ignore[union-attr]
            {"schema_version": 1}
        ),
    ),
)
def test_replay_contract_rejects_physical_paths_and_protocol_mismatch(
    mutate: object,
) -> None:
    payload = _valid_replay()
    mutate(payload)  # type: ignore[operator]

    with pytest.raises(ReplayValidationError):
        parse_replay_record(payload)


def test_replay_loader_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ReplayValidationError):
        load_replay_record(path)
