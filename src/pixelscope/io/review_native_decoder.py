"""W09b production RAW/YUV verification: decode the W09a candidate descriptor.

Never infer a profile from a saved Review, filename or cached preview. The
caller supplies a separately approved, validated native input profile; this
adapter consumes the *same open candidate descriptor* as W09a's SHA replay.
The existing RAW unpacking/MIPI reader kernels and W02 source identity builder
are reused so no independent interpretation/signature dialect is introduced.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis_sources import snapshot_source
from pixelscope.core.review_record import ReviewNativeSignatureV1, canonical_json
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import (
    _decode_mipi_raw10,
    _decode_mipi_raw12,
    _decode_mipi_raw14,
    _decode_packed_stream,
    _packed_rows,
    _read_unpacked,
    required_file_size,
)
from pixelscope.io.review_repository import (
    CandidateDecodeProbeV1,
    CandidateNativeDecoderV1,
)
from pixelscope.io.yuv_profile import YuvProfile

# Deliberately below a full-resolution unbounded image allocation. Excessively
# large candidates remain candidate_unverified, never silently trusted.
MAX_NATIVE_VERIFY_BYTES = 128 * 1024 * 1024


class UnsupportedNativeCandidate(ValueError):
    """Unsupported or incompatible approved profile/source combination."""


def native_sample_sha256(document: ImageDocument) -> str:
    """Content digest of native samples (including all YUV planes), not preview.

    A candidate fingerprint is not enough to prove that a previously loaded
    ImageDocument still represents the same bytes. W09b capture uses this
    native digest as a second independent equality check after W09a SHA/
    interpretation verification, off the GUI thread.
    """
    arrays = (
        document.yuv_frame.planes
        if document.yuv_frame is not None
        else (document.source,)
    )
    if not arrays or any(plane is None for plane in arrays):
        raise UnsupportedNativeCandidate("unloaded native samples")
    hasher = hashlib.sha256()
    hasher.update(document.channel_layout.encode("utf-8"))
    for array in arrays:
        if array is None:
            raise UnsupportedNativeCandidate("unloaded native plane")
        contiguous = np.ascontiguousarray(array)
        hasher.update(str(contiguous.shape).encode("ascii"))
        hasher.update(str(contiguous.dtype).encode("ascii"))
        hasher.update(contiguous.tobytes(order="C"))
    return hasher.hexdigest()


def _raw_samples(data: bytes, profile: RawProfile) -> NDArray[np.generic]:
    """Reuse the production RAW kernels, but source bytes come only from probe."""
    required = required_file_size(profile)
    if len(data) < required:
        raise UnsupportedNativeCandidate("RAW footprint shorter than approved profile")
    source = np.frombuffer(data, dtype=np.uint8)
    if profile.storage_format == "unpacked":
        return _read_unpacked(source, profile)
    rows = _packed_rows(source, profile)
    if profile.storage_format == "packed_stream":
        return _decode_packed_stream(rows, profile)
    if profile.storage_format == "mipi_raw10":
        return _decode_mipi_raw10(rows)
    if profile.storage_format == "mipi_raw12":
        return _decode_mipi_raw12(rows)
    if profile.storage_format == "mipi_raw14":
        return _decode_mipi_raw14(rows)
    raise UnsupportedNativeCandidate("unsupported native RAW packing")


def _yuv_frame(data: bytes, profile: YuvProfile) -> NativeYuvFrame:
    """Reproduce production Y-first / interleaved-UV native plane geometry."""
    if len(data) != profile.expected_file_size:
        raise UnsupportedNativeCandidate("YUV byte count does not match profile")
    source = np.frombuffer(data, dtype=np.uint8)
    luma_count = profile.width * profile.height
    y = source[:luma_count].reshape(profile.height, profile.width)
    x_step = 1 if profile.channel_layout == "YUV444" else 2
    y_step = 2 if profile.channel_layout == "YUV420" else 1
    chroma_rows = profile.height // y_step
    chroma_cols = profile.width // x_step
    uv = source[luma_count:].reshape(chroma_rows, chroma_cols * 2)
    return NativeYuvFrame(y, uv[:, 0::2], uv[:, 1::2], profile.channel_layout)


@dataclass(frozen=True)
class ProductionNativeCandidateDecoder(CandidateNativeDecoderV1):
    """An explicit UI-authorized profile bound to W09a's candidate stream.

    The selected profile is frozen by Pydantic deep-copy at construction. The
    separately reviewed W09a verifier checks SHA, full replay, file revision,
    saved signature equality and per-source relocation consent. Here decoding
    only uses bytes from the candidate probe, never historical Review fields.
    """

    profile: RawProfile | YuvProfile
    max_decode_bytes: int = MAX_NATIVE_VERIFY_BYTES
    native_sample_digest: str | None = field(init=False, default=None, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, RawProfile | YuvProfile):
            raise UnsupportedNativeCandidate("explicit RAW/YUV profile required")
        if (
            not isinstance(self.max_decode_bytes, int)
            or isinstance(self.max_decode_bytes, bool)
            or self.max_decode_bytes <= 0
        ):
            raise UnsupportedNativeCandidate("invalid bounded decode budget")
        object.__setattr__(self, "profile", self.profile.copy(deep=True))

    def decode_signature(self, probe: CandidateDecodeProbeV1) -> ReviewNativeSignatureV1:
        object.__setattr__(self, "native_sample_digest", None)
        profile = self.profile
        expected = (
            required_file_size(profile)
            if isinstance(profile, RawProfile)
            else profile.expected_file_size
        )
        file_size = probe.revision[2]
        if file_size > self.max_decode_bytes or expected > self.max_decode_bytes:
            raise UnsupportedNativeCandidate("candidate exceeds native decode budget")
        if file_size < expected or (isinstance(profile, YuvProfile) and file_size != expected):
            raise UnsupportedNativeCandidate("candidate byte footprint differs from profile")
        # One descriptor from open through SHA, native decoding and W09a replay;
        # never open probe.path or use raw_reader.read_raw(path) here.
        probe.seek(0)
        data = probe.read(file_size + 1)
        if len(data) != file_size:
            raise UnsupportedNativeCandidate("candidate changed during native read")
        try:
            if isinstance(profile, RawProfile):
                array = _raw_samples(data, profile)
                if array.shape != (profile.height, profile.width):
                    raise UnsupportedNativeCandidate("decoded RAW dimensions differ")
                document = ImageDocument(
                    source_path=Path(probe.path),
                    display_name="candidate",
                    source=array,
                    channel_layout=profile.channel_layout,
                    bit_depth=profile.bit_depth,
                    raw_profile=profile,
                )
            else:
                frame = _yuv_frame(data, profile)
                document = ImageDocument(
                    source_path=Path(probe.path),
                    display_name="candidate",
                    source=frame.y,
                    channel_layout=frame.layout,
                    bit_depth=profile.bit_depth,
                    yuv_frame=frame,
                    raw_profile=profile,
                )
            # The same W02 producer used for live analysis. Do not construct
            # signature from the saved Review DTO or preview-cache metadata.
            source = snapshot_source(document, str(uuid4()))
            object.__setattr__(self, "native_sample_digest", native_sample_sha256(document))
            return ReviewNativeSignatureV1(
                profile_signature=source.profile_signature,
                native_shape=source.native_shape,
                reference_shape=source.reference_shape,
                native_dtype=source.native_dtype,
                channel_layout=source.channel_layout,
                effective_bits=source.effective_bits,
                native_interpretation_json=canonical_json(
                    source.native_interpretation.to_portable(), limit=16_384
                ),
            )
        except (ValueError, TypeError, OverflowError, MemoryError) as exc:
            raise UnsupportedNativeCandidate(f"unsupported native interpretation: {exc}") from exc
