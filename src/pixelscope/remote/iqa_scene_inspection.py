"""Qt-free source resolution and identity verification for IQA Scene inspection."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.io.path_discovery import ORDINARY_IMAGE_SUFFIXES
from pixelscope.remote.iqa_domain import Source
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import (
    StorageResolutionError,
    resolve_existing_source,
    sha256_file,
    validate_relative_path,
)
from pixelscope.remote.iqa_v2_domain import ResultV2

_JPEG_SOF_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)
_JPEG_STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD9)})
_MAX_JPEG_PROBE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class VerifiedSceneSource:
    """One published v2 source proven to match the current machine mapping."""

    variant_id: str
    source: Source
    local_path: Path


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
    seen_paths: set[tuple[str, str]] = set()
    for measurement in scene.sources:
        source = measurement.source
        if source.storage_root_id is None:
            return "Published source location is unavailable"
        if settings.root(source.storage_root_id) is None:
            return "Source root is not configured"
        locator = (source.storage_root_id, source.relative_path)
        if locator in seen_paths:
            return "Scene variants resolve to the same native source"
        seen_paths.add(locator)
    return None


def verify_scene_sources(
    result: ResultV2,
    scene_id: str,
    settings: RemoteIqaSettings,
) -> SceneVerificationOutcome:
    """Resolve and verify every required source before returning any mutation payload."""

    cancellation_checkpoint()
    reason = inspect_unavailable_reason(result, scene_id, settings)
    if reason is not None:
        return SceneVerificationOutcome(scene_id=scene_id, reason=reason)
    scene = result.scene(scene_id)
    verified: list[VerifiedSceneSource] = []
    resolved_paths: set[Path] = set()
    for measurement in scene.sources:
        cancellation_checkpoint()
        source = measurement.source
        try:
            local_path = _resolve_published_source(source, settings)
            canonical = local_path.resolve(strict=True)
            if canonical in resolved_paths:
                return SceneVerificationOutcome(
                    scene_id=scene_id,
                    reason="Scene variants resolve to the same native source",
                    failed_source_id=source.source_id,
                )
            resolved_paths.add(canonical)
            width, height = probe_image_dimensions(local_path)
            if (width, height) != (source.width, source.height):
                return SceneVerificationOutcome(
                    scene_id=scene_id,
                    reason="Source dimensions changed",
                    failed_source_id=source.source_id,
                )
            cancellation_checkpoint()
            if sha256_file(local_path) != source.sha256:
                return SceneVerificationOutcome(
                    scene_id=scene_id,
                    reason="Source hash changed",
                    failed_source_id=source.source_id,
                )
        except StorageResolutionError:
            return SceneVerificationOutcome(
                scene_id=scene_id,
                reason="Source is unavailable",
                failed_source_id=source.source_id,
            )
        except (OSError, ValueError):
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
            )
        )
    cancellation_checkpoint()
    return SceneVerificationOutcome(scene_id=scene_id, sources=tuple(verified))


def _resolve_published_source(source: Source, settings: RemoteIqaSettings) -> Path:
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
    return resolved.local_path


def probe_image_dimensions(path: Path) -> tuple[int, int]:
    """Read only bounded image header data; source bytes are never retained."""

    suffix = path.suffix.lower()
    if suffix == ".png":
        return _probe_png(path)
    if suffix == ".bmp":
        return _probe_bmp(path)
    if suffix in {".jpg", ".jpeg"}:
        return _probe_jpeg(path)
    raise ValueError("unsupported native IQA source type")


def _probe_png(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise ValueError("invalid PNG dimensions")
    return width, height


def _probe_bmp(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(26)
    if len(header) < 26 or header[:2] != b"BM":
        raise ValueError("invalid BMP header")
    dib_size = struct.unpack("<I", header[14:18])[0]
    if dib_size < 40:
        raise ValueError("unsupported BMP DIB header")
    width, height = struct.unpack("<ii", header[18:26])
    if width <= 0 or height == 0:
        raise ValueError("invalid BMP dimensions")
    return width, abs(height)


def _probe_jpeg(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        if stream.read(2) != b"\xff\xd8":
            raise ValueError("invalid JPEG header")
        scanned = 2
        while scanned < _MAX_JPEG_PROBE_BYTES:
            marker_prefix = stream.read(1)
            scanned += 1
            if not marker_prefix:
                break
            if marker_prefix != b"\xff":
                continue
            marker_byte = stream.read(1)
            scanned += 1
            while marker_byte == b"\xff":
                marker_byte = stream.read(1)
                scanned += 1
            if not marker_byte:
                break
            marker = marker_byte[0]
            if marker in _JPEG_STANDALONE_MARKERS:
                continue
            length_bytes = stream.read(2)
            scanned += 2
            if len(length_bytes) != 2:
                break
            segment_length = struct.unpack(">H", length_bytes)[0]
            if segment_length < 2:
                raise ValueError("invalid JPEG segment")
            payload_length = segment_length - 2
            if marker in _JPEG_SOF_MARKERS:
                payload = stream.read(min(payload_length, 5))
                scanned += len(payload)
                if len(payload) < 5:
                    break
                height, width = struct.unpack(">HH", payload[1:5])
                if width <= 0 or height <= 0:
                    raise ValueError("invalid JPEG dimensions")
                return width, height
            stream.seek(payload_length, 1)
            scanned += payload_length
    raise ValueError("JPEG dimensions were not found in bounded header data")
