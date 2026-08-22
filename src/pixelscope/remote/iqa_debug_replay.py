"""Strict debug-only transport replay record for Remote IQA terminal jobs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pixelscope.remote.iqa_storage import StorageResolutionError, validate_relative_path
from pixelscope.remote.iqa_submission import IqaResultReference, JobState, MAX_SCENES

DEBUG_REPLAY_FORMAT = "pixelscope-iqa-replay-v1"
MAX_REPLAY_BYTES = 64 * 1024
MAX_REPLAY_MESSAGE_LENGTH = 512
_STORAGE_ROOT_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
_SUBMISSION_KINDS = frozenset({"current_pair", "folder_pair"})
_TERMINAL_RESULT_STATES = frozenset({JobState.SUCCEEDED, JobState.PARTIAL})
_TOP_LEVEL_KEYS = frozenset(
    {
        "debug_format",
        "job_id",
        "submission_kind",
        "state",
        "completed_scenes",
        "total_scenes",
        "message",
        "result_reference",
    }
)
_RESULT_REFERENCE_KEYS = frozenset(
    {
        "job_id",
        "storage_root_id",
        "relative_path",
        "schema_version",
        "publication_state",
    }
)


class ReplayValidationError(ValueError):
    """A debug replay JSON document violates the bounded replay contract."""


@dataclass(frozen=True)
class IqaReplayRecord:
    """One logical terminal-job replay record; never contains a physical result path."""

    job_id: str
    submission_kind: str
    state: JobState
    completed_scenes: int
    total_scenes: int
    message: str | None
    result_reference: IqaResultReference

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "debug_format": DEBUG_REPLAY_FORMAT,
            "job_id": self.job_id,
            "submission_kind": self.submission_kind,
            "state": self.state.value,
            "completed_scenes": self.completed_scenes,
            "total_scenes": self.total_scenes,
            "result_reference": {
                "job_id": self.result_reference.job_id,
                "storage_root_id": self.result_reference.storage_root_id,
                "relative_path": self.result_reference.relative_path,
                "schema_version": self.result_reference.schema_version,
                "publication_state": self.result_reference.publication_state,
            },
        }
        if self.message is not None:
            payload["message"] = self.message
        return payload


def load_replay_record(path: Path | str) -> IqaReplayRecord:
    """Read one bounded UTF-8 replay document and validate its logical identity."""

    replay_path = Path(path)
    if not replay_path.is_file() or replay_path.is_symlink():
        raise ReplayValidationError("replay JSON must be a regular file")
    try:
        size = replay_path.stat().st_size
    except OSError as exc:
        raise ReplayValidationError("replay JSON metadata is unavailable") from exc
    if size > MAX_REPLAY_BYTES:
        raise ReplayValidationError("replay JSON exceeds the 64 KiB safety limit")
    try:
        text = replay_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayValidationError("replay JSON is unreadable or malformed") from exc
    return parse_replay_record(data)


def parse_replay_record(data: object) -> IqaReplayRecord:
    """Validate a replay object without accepting arbitrary local result paths."""

    if not isinstance(data, dict):
        raise ReplayValidationError("replay JSON root must be an object")
    _reject_unknown(data, _TOP_LEVEL_KEYS, "replay")
    if _required_string(data, "debug_format", 64) != DEBUG_REPLAY_FORMAT:
        raise ReplayValidationError(f"debug_format must be {DEBUG_REPLAY_FORMAT}")

    job_id = _job_id(_required_string(data, "job_id", 128))
    submission_kind = _required_string(data, "submission_kind", 32)
    if submission_kind not in _SUBMISSION_KINDS:
        raise ReplayValidationError("submission_kind must be current_pair or folder_pair")

    state_text = _required_string(data, "state", 32)
    try:
        state = JobState(state_text)
    except ValueError as exc:
        raise ReplayValidationError(f"unknown replay state: {state_text}") from exc
    if state not in _TERMINAL_RESULT_STATES:
        raise ReplayValidationError("replay state must be succeeded or partial")

    completed = _required_nonnegative_int(data, "completed_scenes")
    total = _required_nonnegative_int(data, "total_scenes")
    if total < 1 or total > MAX_SCENES or completed > total:
        raise ReplayValidationError("replay Scene progress is outside the P5-C safety bounds")
    if state is JobState.SUCCEEDED and completed != total:
        raise ReplayValidationError("succeeded replay must report all Scenes completed")
    if state is JobState.PARTIAL and not (0 < completed < total):
        raise ReplayValidationError("partial replay must report success plus unavailable Scenes")

    message = _optional_string(data, "message", MAX_REPLAY_MESSAGE_LENGTH)
    raw_reference = data.get("result_reference")
    if not isinstance(raw_reference, dict):
        raise ReplayValidationError("result_reference must be an object")
    _reject_unknown(raw_reference, _RESULT_REFERENCE_KEYS, "result_reference")
    returned_job_id = _job_id(_required_string(raw_reference, "job_id", 128))
    if returned_job_id != job_id:
        raise ReplayValidationError("result_reference job_id must match replay job_id")

    storage_root_id = _required_string(raw_reference, "storage_root_id", 64)
    if _STORAGE_ROOT_ID_RE.fullmatch(storage_root_id) is None:
        raise ReplayValidationError("result_reference storage_root_id is invalid")
    relative_path = _required_string(raw_reference, "relative_path", 2048)
    try:
        validate_relative_path(relative_path)
    except StorageResolutionError as exc:
        raise ReplayValidationError(str(exc)) from exc

    schema_version = _required_nonnegative_int(raw_reference, "schema_version")
    if schema_version != 2:
        raise ReplayValidationError("debug replay result_reference must use schema_version 2")
    publication_state = _required_string(raw_reference, "publication_state", 16)
    expected_publication = "complete" if state is JobState.SUCCEEDED else "partial"
    if publication_state != expected_publication:
        raise ReplayValidationError("terminal state/result publication mismatch")

    return IqaReplayRecord(
        job_id,
        submission_kind,
        state,
        completed,
        total,
        message,
        IqaResultReference(
            job_id,
            storage_root_id,
            relative_path,
            schema_version,
            publication_state,
        ),
    )


def _reject_unknown(data: dict[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ReplayValidationError(f"{context} contains unsupported field: {unknown[0]}")


def _job_id(value: str) -> str:
    if any(char in value for char in "/\\\x00"):
        raise ReplayValidationError("job_id contains an invalid path character")
    return value


def _required_string(data: dict[str, Any], key: str, maximum: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise ReplayValidationError(f"{key} is missing or invalid")
    if value != value.strip():
        raise ReplayValidationError(f"{key} must not contain surrounding whitespace")
    return value


def _optional_string(data: dict[str, Any], key: str, maximum: int) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise ReplayValidationError(f"{key} is invalid")
    clean = " ".join(value.split())
    return clean or None


def _required_nonnegative_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReplayValidationError(f"{key} must be a non-negative integer")
    return value
