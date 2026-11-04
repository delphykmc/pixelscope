from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pixelscope.io.path_discovery import (
    RAW_LIKE_IMAGE_SUFFIXES,
    raw_profile_sidecar_for_path,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import required_file_size
from pixelscope.io.yuv_profile import YuvProfile

InputProfile = RawProfile | YuvProfile
CandidateStatus = Literal["eligible", "unchanged", "rejected"]


def interpretation_key(profile: InputProfile) -> str:
    """Mirror W08a's canonical native interpretation identity without a Qt import."""

    kind = "raw" if isinstance(profile, RawProfile) else "yuv"
    payload = profile.dict(exclude={"name"})
    encoded = json.dumps(
        {"kind": kind, "interpretation": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ExistingProfileBinding:
    document_id: str
    generation: int
    profile: InputProfile | None


@dataclass(frozen=True)
class FileRevision:
    """Advisory TOCTOU guard; not a content hash or verified source identity."""

    size: int
    mtime_ns: int
    device: int
    inode: int


@dataclass(frozen=True)
class ProfileBatchCandidate:
    path: Path
    profile: InputProfile
    interpretation: str
    document_id: str | None
    generation: int | None
    previous_interpretation: str | None
    previous_profile: InputProfile | None
    sidecar: Path | None
    sidecar_override: bool
    revision: FileRevision | None
    required_size: int
    status: CandidateStatus
    reason: str

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"


def _revision(path: Path) -> FileRevision:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Not a regular source file")
    return FileRevision(info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino)


def candidate_file_is_current(candidate: ProfileBatchCandidate) -> bool:
    """Recheck before each canonical commit; metadata is not a semantic guarantee."""

    if not candidate.eligible or candidate.revision is None:
        return False
    try:
        return _revision(candidate.path) == candidate.revision
    except (OSError, ValueError):
        return False


def preflight_input_profile_batch(
    paths: tuple[Path, ...],
    profile: InputProfile,
    *,
    existing: Mapping[Path, ExistingProfileBinding] | None = None,
    override_sidecars: bool = False,
    override_registered: bool = False,
    require_exact_raw_size: bool = False,
) -> tuple[ProfileBatchCandidate, ...]:
    """Validate each path independently; never resolve or overwrite sidecars.

    An explicit batch profile may supersede JSON/imgprops or a registered
    interpretation only when the caller enables the corresponding override.
    A size match does not establish packing/layout semantic correctness.
    """

    bindings = existing or {}
    key = interpretation_key(profile)
    required = (
        required_file_size(profile)
        if isinstance(profile, RawProfile)
        else profile.expected_file_size
    )
    unique: set[Path] = set()
    candidates: list[ProfileBatchCandidate] = []
    for supplied in paths:
        path = Path(supplied).absolute()
        if path in unique:
            continue
        unique.add(path)
        binding = bindings.get(path)
        prior = (
            interpretation_key(binding.profile)
            if binding is not None and binding.profile is not None
            else None
        )
        sidecar: Path | None = None
        revision: FileRevision | None = None
        status: CandidateStatus = "eligible"
        reason = "File size compatible; native interpretation not verified"
        if path.suffix.casefold() not in RAW_LIKE_IMAGE_SUFFIXES:
            status, reason = "rejected", "Unsupported RAW/YUV source extension"
        elif isinstance(profile, YuvProfile) and path.suffix.casefold() != ".yuv":
            status, reason = "rejected", "Native YUV profile requires a .yuv source"
        else:
            try:
                revision = _revision(path)
                sidecar = raw_profile_sidecar_for_path(path)
                if revision.size < required:
                    status, reason = (
                        "rejected",
                        (f"Truncated: {revision.size} bytes; needs at least {required}"),
                    )
                elif isinstance(profile, YuvProfile) and revision.size != required:
                    status, reason = (
                        "rejected",
                        (f"YUV requires exactly {required} bytes; got {revision.size}"),
                    )
                elif (
                    isinstance(profile, RawProfile)
                    and require_exact_raw_size
                    and revision.size != required
                ):
                    status, reason = (
                        "rejected",
                        (f"Exact RAW size setting requires {required} bytes; got {revision.size}"),
                    )
                elif isinstance(profile, RawProfile) and revision.size > required:
                    reason = (
                        f"RAW: {revision.size - required} trailing bytes ignored "
                        f"from offset {required}"
                    )
            except (OSError, ValueError) as exc:
                status, reason = "rejected", f"Unavailable source: {exc}"
        if status == "eligible":
            if prior == key:
                status, reason = "unchanged", "Already uses this native interpretation"
            elif binding is not None and not override_registered:
                status, reason = "rejected", "Registered interpretation requires explicit override"
            elif sidecar is not None and not override_sidecars:
                status, reason = (
                    "rejected",
                    (f"{sidecar.suffix} sidecar takes priority without explicit override"),
                )
        candidates.append(
            ProfileBatchCandidate(
                path=path,
                profile=profile.copy(deep=True),
                interpretation=key,
                document_id=binding.document_id if binding is not None else None,
                generation=binding.generation if binding is not None else None,
                previous_interpretation=prior,
                previous_profile=(
                    binding.profile.copy(deep=True)
                    if binding is not None and binding.profile is not None
                    else None
                ),
                sidecar=sidecar,
                sidecar_override=bool(
                    sidecar is not None and override_sidecars and status == "eligible"
                ),
                revision=revision,
                required_size=required,
                status=status,
                reason=reason,
            )
        )
    return tuple(candidates)
