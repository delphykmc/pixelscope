"""Schema-v2 PARTIAL domain and scene-outcome structural validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_manifest import bounded_list, bounded_string
from pixelscope.remote.iqa_v2_support import V2_MAX_ID_LENGTH, V2_MAX_SCENES, InvalidV2

MAX_SCENE_ERROR_CODE_LENGTH = 128
MAX_SCENE_ERROR_MESSAGE_LENGTH = 512
_OUTCOME_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass(frozen=True)
class SceneOutcomeV2:
    """One requested Scene's terminal outcome in original request order."""

    scene_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None


@dataclass(frozen=True)
class PartialResultV2(ResultV2):
    """A valid v2 PARTIAL result containing only fully published successful Scenes."""

    publication_state: str = "partial"
    scene_outcomes: tuple[SceneOutcomeV2, ...] = ()

    @property
    def requested_scene_count(self) -> int:
        return len(self.scene_outcomes)

    @property
    def successful_scene_count(self) -> int:
        return len(self.scenes)

    @property
    def unsuccessful_scene_outcomes(self) -> tuple[SceneOutcomeV2, ...]:
        return tuple(item for item in self.scene_outcomes if item.status != "succeeded")


def parse_scene_outcomes(data: dict[str, Any]) -> tuple[SceneOutcomeV2, ...]:
    """Parse bounded outcomes while preserving unknown future error-code strings."""

    raw_outcomes = bounded_list(data, "scene_outcomes", V2_MAX_SCENES)
    if len(raw_outcomes) < 2:
        raise InvalidV2("PARTIAL result requires success plus failed/cancelled Scene outcomes")
    outcomes: list[SceneOutcomeV2] = []
    for raw in raw_outcomes:
        if not isinstance(raw, dict):
            raise InvalidV2("scene_outcome must be an object")
        scene_id = bounded_string(raw, "scene_id", V2_MAX_ID_LENGTH)
        status = bounded_string(raw, "status", 16)
        if status not in _OUTCOME_STATUSES:
            raise InvalidV2(f"invalid scene_outcome status {status}")
        error = raw.get("error")
        if status == "succeeded":
            if error is not None:
                raise InvalidV2("successful scene_outcome must not contain error diagnostics")
            outcome = SceneOutcomeV2(scene_id, status)
        else:
            if not isinstance(error, dict):
                raise InvalidV2(f"{status} scene_outcome requires bounded error diagnostics")
            code = bounded_string(error, "code", MAX_SCENE_ERROR_CODE_LENGTH)
            message = bounded_string(error, "message", MAX_SCENE_ERROR_MESSAGE_LENGTH)
            retryable = error.get("retryable")
            if retryable is not None and not isinstance(retryable, bool):
                raise InvalidV2("scene_outcome error retryable must be boolean when supplied")
            outcome = SceneOutcomeV2(scene_id, status, code, message, retryable)
        outcomes.append(outcome)
    if len({item.scene_id for item in outcomes}) != len(outcomes):
        raise InvalidV2("scene_outcome scene_id values must be unique")
    return tuple(outcomes)
