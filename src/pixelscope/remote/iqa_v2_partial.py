"""Executable schema-v2 PARTIAL result support owned by P5-C."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_v2_domain import ResultV2, VersionedResultLoadOutcome
from pixelscope.remote.iqa_v2_manifest import bounded_list, bounded_string, integer, parse_complete_manifest
from pixelscope.remote.iqa_v2_reader import (
    _load_summary,
    _parse_dataset_summaries,
    _populate_scene_summaries,
    _validate_summary_identity,
)
from pixelscope.remote.iqa_v2_support import (
    V2_MAX_ID_LENGTH,
    V2_MAX_SCENES,
    CorruptV2,
    InvalidV2,
    UnsupportedV2,
    read_manifest,
    safe_artifact,
)

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


def load_partial_result_v2(root: Path | str) -> VersionedResultLoadOutcome:
    """Load a v2 PARTIAL publication without weakening complete Scene invariants."""

    result_root = Path(root)
    try:
        manifest = read_manifest(result_root)
        if manifest.get("kind") != "pixelscope-iqa-result":
            raise InvalidV2("manifest kind must be pixelscope-iqa-result")
        version = integer(manifest, "schema_version")
        if version != 2:
            raise UnsupportedV2(f"schema-v2 PARTIAL reader cannot read schema_version {version}")
        if manifest.get("publication_state") != "partial":
            raise InvalidV2("PARTIAL reader requires publication_state=partial")

        outcomes = _parse_scene_outcomes(manifest)
        parsed = parse_complete_manifest(result_root, manifest)
        successful_ids = tuple(item.scene_id for item in outcomes if item.status == "succeeded")
        scene_ids = tuple(scene.scene_id for scene in parsed.scenes)
        if successful_ids != scene_ids:
            raise InvalidV2(
                "successful scene_outcomes must correspond exactly to scenes[] in request order"
            )
        if not successful_ids:
            raise InvalidV2("PARTIAL result requires at least one successful Scene")
        if len(successful_ids) == len(outcomes):
            raise InvalidV2("PARTIAL result requires at least one failed or cancelled Scene")

        summary_path = safe_artifact(result_root, parsed.summary_artifact)
        arrays = _load_summary(
            summary_path,
            parsed.summary_uncompressed_size,
            len(parsed.scenes),
            len(parsed.variants),
            len(parsed.attributes),
        )
        _validate_summary_identity(arrays, parsed.scenes, parsed.variants, parsed.attributes)
        scenes = _populate_scene_summaries(parsed.scenes, parsed.attributes, arrays)
        dataset = _parse_dataset_summaries(scenes, parsed.variants, parsed.attributes, arrays)
        return VersionedResultLoadOutcome(
            LoadStatus.SUCCESS,
            result=PartialResultV2(
                root=result_root.resolve(),
                result_id=parsed.result_id,
                schema_version=2,
                variants=parsed.variants,
                attributes=parsed.attributes,
                scenes=scenes,
                dataset_summaries=dataset,
                summary_artifact=parsed.summary_artifact,
                scene_outcomes=outcomes,
            ),
        )
    except UnsupportedV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.UNSUPPORTED, reason=str(exc))
    except InvalidV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.INVALID, reason=str(exc))
    except CorruptV2 as exc:
        return VersionedResultLoadOutcome(LoadStatus.CORRUPT, reason=str(exc))


def _parse_scene_outcomes(data: dict[str, Any]) -> tuple[SceneOutcomeV2, ...]:
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
