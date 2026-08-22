"""Qt-free Remote IQA request, preflight, folder pairing, and job-domain authority."""

from __future__ import annotations

import struct
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO

from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import ResolvedSource, resolve_or_stage_source

SUPPORTED_REMOTE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp"})
VARIANT_IDS = ("A", "B")
MAX_SCENES = 512


class PreflightError(ValueError):
    """Client-known input error that must block remote submission."""


class JobState(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    EXTRACTING = "extracting"
    AGGREGATING = "aggregating"
    WRITING = "writing"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            JobState.SUCCEEDED,
            JobState.PARTIAL,
            JobState.FAILED,
            JobState.CANCELLED,
        }


@dataclass(frozen=True)
class ImageProbe:
    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class FolderPairEntry:
    scene_id: str
    source_a: ImageProbe
    source_b: ImageProbe


@dataclass(frozen=True)
class PortableSourceRequest:
    storage_root_id: str
    relative_path: str
    sha256: str
    width: int
    height: int

    def to_json(self) -> dict[str, object]:
        return {
            "storage_root_id": self.storage_root_id,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class SceneRequest:
    scene_id: str
    sources: tuple[tuple[str, PortableSourceRequest], ...]

    def to_json(self) -> dict[str, object]:
        return {
            "scene_id": self.scene_id,
            "sources": [
                {"variant_id": variant_id, **source.to_json()}
                for variant_id, source in self.sources
            ],
        }


@dataclass(frozen=True)
class IqaJobRequest:
    submission_kind: str
    variants: tuple[str, ...]
    scenes: tuple[SceneRequest, ...]

    def __post_init__(self) -> None:
        if self.variants != VARIANT_IDS:
            raise ValueError("initial P5-C requests must use ordered variants A/B")
        if not self.scenes or len(self.scenes) > MAX_SCENES:
            raise ValueError("request must contain 1..512 Scenes")
        expected = tuple(f"scene_{index:06d}" for index in range(len(self.scenes)))
        if tuple(item.scene_id for item in self.scenes) != expected:
            raise ValueError("Scene IDs/order must be deterministic scene_000000 sequence")
        for scene in self.scenes:
            if tuple(item[0] for item in scene.sources) != self.variants:
                raise ValueError("each Scene must contain sources in exact variant order")

    def to_json(self) -> dict[str, object]:
        return {
            "submission_kind": self.submission_kind,
            "variants": [{"variant_id": item} for item in self.variants],
            "scenes": [scene.to_json() for scene in self.scenes],
        }


@dataclass(frozen=True)
class IqaJobCreated:
    job_id: str
    state: JobState


@dataclass(frozen=True)
class IqaJobStatus:
    job_id: str
    state: JobState
    completed_scenes: int | None = None
    total_scenes: int | None = None
    message: str | None = None

    @property
    def cancellable(self) -> bool:
        return not self.state.terminal


@dataclass(frozen=True)
class IqaResultReference:
    job_id: str
    storage_root_id: str
    relative_path: str
    schema_version: int
    publication_state: str


def is_remote_eligible_path(path: Path | str) -> bool:
    return Path(path).suffix.casefold() in SUPPORTED_REMOTE_SUFFIXES


def probe_image(path: Path | str) -> ImageProbe:
    """Read only format headers/markers required for original dimensions."""

    image_path = Path(path)
    if not image_path.is_file() or image_path.is_symlink():
        raise PreflightError(f"missing source: {image_path.name}")
    suffix = image_path.suffix.casefold()
    if suffix not in SUPPORTED_REMOTE_SUFFIXES:
        if suffix == ".raw":
            raise PreflightError("RAW is not eligible for Remote IQA")
        raise PreflightError(f"unsupported Remote IQA input: {image_path.name}")
    try:
        with image_path.open("rb") as stream:
            if suffix == ".png":
                width, height = _probe_png(stream)
            elif suffix == ".bmp":
                width, height = _probe_bmp(stream)
            else:
                width, height = _probe_jpeg(stream)
    except OSError as exc:
        raise PreflightError(f"unreadable image: {image_path.name}") from exc
    if width <= 0 or height <= 0:
        raise PreflightError(f"invalid image dimensions: {image_path.name}")
    return ImageProbe(image_path, width, height)


def pair_current_paths(
    path_a: Path | str,
    path_b: Path | str,
) -> tuple[FolderPairEntry, ...]:
    a = probe_image(path_a)
    b = probe_image(path_b)
    _require_same_dimensions(a, b, "Current Pair")
    return (FolderPairEntry("scene_000000", a, b),)


def pair_folders(
    folder_a: Path | str,
    folder_b: Path | str,
) -> tuple[FolderPairEntry, ...]:
    """Apply the durable P5 lexical two-folder Pair algorithm."""

    a_paths = _folder_eligible_paths(Path(folder_a))
    b_paths = _folder_eligible_paths(Path(folder_b))
    if len(a_paths) != len(b_paths):
        raise PreflightError(
            f"Folder Pair count mismatch: A={len(a_paths)}, B={len(b_paths)}"
        )
    if not a_paths:
        raise PreflightError("Folder Pair contains no eligible images")
    if len(a_paths) > MAX_SCENES:
        raise PreflightError(f"Folder Pair exceeds {MAX_SCENES} Scene safety limit")
    entries: list[FolderPairEntry] = []
    for index, (path_a, path_b) in enumerate(zip(a_paths, b_paths, strict=True)):
        probe_a = probe_image(path_a)
        probe_b = probe_image(path_b)
        scene_id = f"scene_{index:06d}"
        _require_same_dimensions(probe_a, probe_b, scene_id)
        entries.append(FolderPairEntry(scene_id, probe_a, probe_b))
    return tuple(entries)


def build_request(
    entries: tuple[FolderPairEntry, ...],
    settings: RemoteIqaSettings,
    *,
    submission_kind: str,
) -> IqaJobRequest:
    """Resolve/hash/stage sequentially and build the explicit ordered Scene manifest."""

    if not settings.server_base_url:
        raise PreflightError("Remote IQA server URL is not configured")
    if not settings.storage_roots:
        raise PreflightError("Remote IQA storage roots are not configured")
    cache: dict[Path, ResolvedSource] = {}
    scenes: list[SceneRequest] = []
    for entry in entries:
        pair: list[tuple[str, PortableSourceRequest]] = []
        for variant_id, probe in (("A", entry.source_a), ("B", entry.source_b)):
            key = probe.path.resolve(strict=False)
            resolved = cache.get(key)
            if resolved is None:
                try:
                    resolved = resolve_or_stage_source(probe.path, settings)
                except ValueError as exc:
                    raise PreflightError(str(exc)) from exc
                cache[key] = resolved
            pair.append(
                (
                    variant_id,
                    PortableSourceRequest(
                        resolved.logical_path.storage_root_id,
                        resolved.logical_path.relative_path,
                        resolved.sha256,
                        probe.width,
                        probe.height,
                    ),
                )
            )
        scenes.append(SceneRequest(entry.scene_id, tuple(pair)))
    return IqaJobRequest(submission_kind, VARIANT_IDS, tuple(scenes))


def _folder_eligible_paths(folder: Path) -> tuple[Path, ...]:
    if not folder.is_dir():
        raise PreflightError(f"folder is unavailable: {folder}")
    candidates: list[tuple[str, str, Path]] = []
    try:
        for item in folder.iterdir():
            if item.is_symlink() or not item.is_file():
                continue
            if item.suffix.casefold() not in SUPPORTED_REMOTE_SUFFIXES:
                continue
            normalized = unicodedata.normalize("NFC", item.name)
            candidates.append((normalized.casefold(), normalized, item))
    except OSError as exc:
        raise PreflightError(f"unable to enumerate folder: {folder}") from exc
    candidates.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in candidates)


def _require_same_dimensions(a: ImageProbe, b: ImageProbe, context: str) -> None:
    if (a.width, a.height) != (b.width, b.height):
        raise PreflightError(
            f"{context} dimension mismatch: "
            f"A={a.width}x{a.height}, B={b.width}x{b.height}"
        )


def _probe_png(stream: BinaryIO) -> tuple[int, int]:
    header = stream.read(24)
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise PreflightError("unreadable PNG header")
    return struct.unpack(">II", header[16:24])


def _probe_bmp(stream: BinaryIO) -> tuple[int, int]:
    header = stream.read(26)
    if len(header) != 26 or header[:2] != b"BM":
        raise PreflightError("unreadable BMP header")
    dib_size = struct.unpack("<I", header[14:18])[0]
    if dib_size == 12:
        width, height = struct.unpack("<HH", header[18:22])
    elif dib_size >= 40:
        width, height = struct.unpack("<ii", header[18:26])
        height = abs(height)
    else:
        raise PreflightError("unsupported BMP header")
    return int(width), int(height)


def _probe_jpeg(stream: BinaryIO) -> tuple[int, int]:
    if stream.read(2) != b"\xff\xd8":
        raise PreflightError("unreadable JPEG header")
    sof_markers = {
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
    scanned = 2
    while scanned < 16 * 1024 * 1024:
        byte = stream.read(1)
        scanned += 1
        if not byte:
            break
        if byte != b"\xff":
            continue
        while True:
            marker_byte = stream.read(1)
            scanned += 1
            if not marker_byte:
                raise PreflightError("truncated JPEG marker")
            if marker_byte != b"\xff":
                break
        marker = marker_byte[0]
        if marker in {0x00, 0x01} or 0xD0 <= marker <= 0xD9:
            continue
        raw_length = stream.read(2)
        scanned += 2
        if len(raw_length) != 2:
            raise PreflightError("truncated JPEG segment")
        length = struct.unpack(">H", raw_length)[0]
        if length < 2:
            raise PreflightError("invalid JPEG segment length")
        if marker in sof_markers:
            payload = stream.read(5)
            if len(payload) != 5:
                raise PreflightError("truncated JPEG SOF")
            height, width = struct.unpack(">HH", payload[1:5])
            return int(width), int(height)
        stream.seek(length - 2, 1)
        scanned += length - 2
    raise PreflightError("JPEG dimensions were not found")
