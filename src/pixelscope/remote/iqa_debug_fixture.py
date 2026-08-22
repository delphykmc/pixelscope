"""Deterministic schema-v2 result bundles for the P5-C debug replay harness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from pixelscope.remote.iqa_debug_replay import IqaReplayRecord, parse_replay_record
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_storage import StorageResolutionError, validate_relative_path
from pixelscope.remote.iqa_submission import IqaResultReference, JobState
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2

SUCCESSFUL_DEBUG_SCENES = 3


class DebugResultMode(str, Enum):
    COMPLETE = "complete"
    PARTIAL_FAILED = "partial-failed"
    PARTIAL_CANCELLED = "partial-cancelled"


@dataclass(frozen=True)
class DebugResultBundle:
    result_root: Path
    replay_path: Path
    replay: IqaReplayRecord


def write_debug_result_bundle(
    storage_root: Path | str,
    storage_root_id: str,
    relative_path: str,
    *,
    mode: DebugResultMode,
    job_id: str,
    submission_kind: str = "folder_pair",
    replay_path: Path | str | None = None,
) -> DebugResultBundle:
    """Write a canonical v2 result plus a logical replay record without physical paths."""

    root = Path(storage_root)
    if not root.is_dir():
        raise ValueError("debug storage root must already exist and be a directory")
    try:
        validate_relative_path(relative_path)
    except StorageResolutionError as exc:
        raise ValueError(str(exc)) from exc

    state, publication_state, completed, total, message = _mode_state(mode)
    replay = parse_replay_record(
        IqaReplayRecord(
            job_id=job_id,
            submission_kind=submission_kind,
            state=state,
            completed_scenes=completed,
            total_scenes=total,
            message=message,
            result_reference=IqaResultReference(
                job_id,
                storage_root_id,
                relative_path,
                2,
                publication_state,
            ),
        ).to_json()
    )

    result_root = root.joinpath(*PurePosixPath(relative_path).parts)
    try:
        result_root.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("debug result path escapes the supplied storage root") from exc
    if result_root.exists():
        raise ValueError("debug result target already exists")

    output_replay = (
        Path(replay_path)
        if replay_path is not None
        else root / "debug-replay" / f"{job_id}.json"
    )
    if output_replay.exists():
        raise ValueError("debug replay JSON target already exists")

    write_golden_result_v2(result_root, scene_count=SUCCESSFUL_DEBUG_SCENES)
    manifest_path = result_root / "manifest.json"
    manifest = _read_manifest(manifest_path)
    manifest["result_id"] = job_id
    if mode is not DebugResultMode.COMPLETE:
        failed_status = (
            "failed" if mode is DebugResultMode.PARTIAL_FAILED else "cancelled"
        )
        manifest["publication_state"] = publication_state
        manifest["scene_outcomes"] = [
            {"scene_id": scene["scene_id"], "status": "succeeded"}
            for scene in manifest["scenes"]
        ] + [
            {
                "scene_id": f"scene_{SUCCESSFUL_DEBUG_SCENES:06d}",
                "status": failed_status,
                "error": {
                    "code": f"debug.synthetic_{failed_status}",
                    "message": f"synthetic {failed_status} Scene for P5-C replay",
                    "retryable": failed_status == "failed",
                },
            }
        ]

    _publish_json(manifest_path, manifest)
    outcome = load_result(result_root)
    if outcome.status is not LoadStatus.SUCCESS:
        raise RuntimeError(
            f"generated schema-v2 debug result failed canonical validation: {outcome.reason}"
        )

    output_replay.parent.mkdir(parents=True, exist_ok=True)
    _publish_json(output_replay, replay.to_json())
    return DebugResultBundle(result_root, output_replay, replay)


def _mode_state(mode: DebugResultMode) -> tuple[JobState, str, int, int, str]:
    if mode is DebugResultMode.COMPLETE:
        return (
            JobState.SUCCEEDED,
            "complete",
            SUCCESSFUL_DEBUG_SCENES,
            SUCCESSFUL_DEBUG_SCENES,
            "synthetic complete debug result",
        )
    failed_status = "failed" if mode is DebugResultMode.PARTIAL_FAILED else "cancelled"
    return (
        JobState.PARTIAL,
        "partial",
        SUCCESSFUL_DEBUG_SCENES,
        SUCCESSFUL_DEBUG_SCENES + 1,
        f"synthetic partial debug result ({failed_status})",
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("generated schema-v2 manifest is not an object")
    return data


def _publish_json(path: Path, data: object) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    part.replace(path)
