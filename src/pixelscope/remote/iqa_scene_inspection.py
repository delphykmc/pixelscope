"""Qt-free source resolution and identity verification for IQA Scene inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.image_reader import ImageReadError, read_image
from pixelscope.io.path_discovery import ORDINARY_IMAGE_SUFFIXES
from pixelscope.remote.iqa_domain import Source
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import (
    ResolvedSource,
    StorageResolutionError,
    resolve_existing_source,
    validate_relative_path,
)
from pixelscope.remote.iqa_submission import PreflightError, probe_image
from pixelscope.remote.iqa_v2_domain import ResultV2


@dataclass(frozen=True)
class VerifiedSceneSource:
    """One published v2 source bound to the exact decoded ordinary-image bytes."""

    variant_id: str
    source: Source
    local_path: Path
    decoded_document: ImageDocument


@dataclass(frozen=True)
class SceneVerificationOutcome:
    """All-or-nothing native-source verification result for one IQA Scene."""

    scene_id: str
    sources: tuple[VerifiedSceneSource, ...] = ()
    reason: str | None = None
    failed_source_id: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.reason is None


def inspect_unavailable_reason(
    result: object,
    scene_id: str,
    settings: RemoteIqaSettings,
) -> str | None:
    """Return a compact passive reason when native Scene Inspect cannot start."""

    if not isinstance(result, ResultV2):
        return "Native Inspect requires a schema-v2 result"
    try:
        scene = result.scene(scene_id)
    except StopIteration:
        return "Scene is unavailable"
    count = len(scene.sources)
    if count < 1:
        return "Scene has no published sources"
    if count > 6:
        return "Native Inspect supports at most 6 Scene variants"
    seen_locators: dict[tuple[str, str], str] = {}
    for measurement in scene.sources:
        source = measurement.source
        if source.storage_root_id is None:
            return "Published source location is unavailable"
        if settings.root(source.storage_root_id) is None:
            return "Source root is not configured"
        locator = (source.storage_root_id, source.relative_path)
        existing_source_id = seen_locators.get(locator)
        if existing_source_id is not None and existing_source_id != source.source_id:
            return "Distinct source identities share one native source path"
        seen_locators[locator] = source.source_id
    return None


def verify_scene_sources(
    result: ResultV2,
    scene_id: str,
    settings: RemoteIqaSettings,
) -> SceneVerificationOutcome:
    """Resolve/decode every required source before returning any mutation payload."""

    cancellation_checkpoint()
    reason = inspect_unavailable_reason(result, scene_id, settings)
    if reason is not None:
        return SceneVerificationOutcome(scene_id=scene_id, reason=reason)
    scene = result.scene(scene_id)
    verified: list[VerifiedSceneSource] = []
    decoded_by_path: dict[Path, tuple[str, ImageDocument]] = {}
    for measurement in scene.sources:
        cancellation_checkpoint()
        source = measurement.source
        try:
            resolved = _resolve_published_source(source, settings)
            local_path = resolved.local_path
            canonical = local_path.resolve(strict=True)
            cached = decoded_by_path.get(canonical)
            if cached is not None:
                cached_source_id, decoded = cached
                if cached_source_id != source.source_id:
                    return SceneVerificationOutcome(
                        scene_id=scene_id,
                        reason="Distinct source identities share one native source path",
                        failed_source_id=source.source_id,
                    )
            else:
                width, height = probe_image_dimensions(local_path)
                if (width, height) != (source.width, source.height):
                    return SceneVerificationOutcome(
                        scene_id=scene_id,
                        reason="Source dimensions changed",
                        failed_source_id=source.source_id,
                    )
                cancellation_checkpoint()
                decoded = read_image(local_path)
                if decoded.shape[:2] != (source.height, source.width):
                    return SceneVerificationOutcome(
                        scene_id=scene_id,
                        reason="Decoded source dimensions changed",
                        failed_source_id=source.source_id,
                    )
                if decoded.encoded_source_sha256 != source.sha256:
                    return SceneVerificationOutcome(
                        scene_id=scene_id,
                        reason="Source hash changed",
                        failed_source_id=source.source_id,
                    )
                decoded_by_path[canonical] = (source.source_id, decoded)
        except (StorageResolutionError, PreflightError, ImageReadError, OSError, ValueError):
            return SceneVerificationOutcome(
                scene_id=scene_id,
                reason="Source is unavailable",
                failed_source_id=source.source_id,
            )
        verified.append(
            VerifiedSceneSource(
                variant_id=measurement.variant_id,
                source=source,
                local_path=local_path,
                decoded_document=decoded,
            )
        )
    cancellation_checkpoint()
    return SceneVerificationOutcome(scene_id=scene_id, sources=tuple(verified))


def _resolve_published_source(
    source: Source,
    settings: RemoteIqaSettings,
) -> ResolvedSource:
    root_id = source.storage_root_id
    if root_id is None:
        raise StorageResolutionError("published source location is unavailable")
    root = settings.root(root_id)
    if root is None:
        raise StorageResolutionError("source root is not configured")
    validate_relative_path(source.relative_path)
    relative = PurePosixPath(source.relative_path)
    candidate = Path(root.client_path).joinpath(*relative.parts)
    resolved = resolve_existing_source(candidate, settings)
    if resolved is None:
        raise StorageResolutionError("source is outside its published root")
    if (
        resolved.logical_path.storage_root_id != root_id
        or resolved.logical_path.relative_path != source.relative_path
    ):
        raise StorageResolutionError("published logical source locator does not match")
    if resolved.local_path.suffix.lower() not in ORDINARY_IMAGE_SUFFIXES:
        raise StorageResolutionError("published source type is not supported for native Inspect")
    return resolved


def probe_image_dimensions(path: Path) -> tuple[int, int]:
    """Reuse the P5-C ordinary-image header probe so submission/Inspect accept the same files."""

    probe = probe_image(path)
    return probe.width, probe.height
