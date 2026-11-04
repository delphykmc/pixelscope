"""Shared Qt-free source identity adapter for W02 analysis producers.

A source key is durable only once W09's canonical Review owner binds it. The
fallback UUID is session-local and never inferred from a path or display alias.
"""
from __future__ import annotations

import hashlib
import json

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis import AnalysisSourceV1
from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1


def native_interpretation(document: ImageDocument) -> AnalysisNativeInterpretationV1:
    """Build a path-free, typed description of the *native* numeric meaning."""
    profile = document.raw_profile
    frame = document.yuv_frame
    sampling = document.spatial_sampling
    black_level = getattr(profile, "black_level", None)
    levels = (
        (black_level,)
        if isinstance(black_level, int) and not isinstance(black_level, bool)
        else tuple(black_level)
        if isinstance(black_level, tuple | list)
        else None
    )
    cfa_pattern = getattr(profile, "bayer_pattern", None)
    return AnalysisNativeInterpretationV1(
        sampling_semantics=sampling.sampling_semantics if sampling is not None else "direct",
        sample_step_xy=(
            (sampling.column_step, sampling.row_step) if sampling is not None else (1, 1)
        ),
        sample_phase_xy=(
            (sampling.column_phase, sampling.row_phase) if sampling is not None else (0, 0)
        ),
        sample_channel=document.sample_channel,
        cfa_pattern=cfa_pattern,
        # The CFA pattern is anchored at source reference origin by the RAW
        # decoder; ROI parity is conveyed separately by token.roi_ref.
        cfa_phase_xy=(0, 0) if cfa_pattern is not None else None,
        raw_storage_format=getattr(profile, "storage_format", None),
        raw_container_dtype=getattr(profile, "container_dtype", None),
        raw_row_stride_bytes=getattr(profile, "stride_bytes", None),
        raw_byte_offset=getattr(profile, "offset_bytes", None),
        raw_endianness=getattr(profile, "endianness", None),
        raw_bit_alignment=getattr(profile, "bit_alignment", None),
        raw_packed_bit_order=getattr(profile, "packed_bit_order", None),
        raw_black_levels=levels,
        raw_white_level=getattr(profile, "white_level", None),
        yuv_layout=frame.layout if frame is not None else None,
        yuv_chroma_step_xy=frame.chroma_scale if frame is not None else None,
        yuv_plane_shapes=(
            tuple((int(plane.shape[0]), int(plane.shape[1])) for plane in frame.planes)
            if frame is not None
            else None
        ),
    )


def native_profile_signature(document: ImageDocument) -> str:
    profile = document.raw_profile
    frame = document.yuv_frame
    fields = {
        "layout": document.channel_layout,
        "dtype": str(document.original_dtype),
        "bit_depth": document.bit_depth,
        "native_shape": list(document.shape),
        "reference_shape": list(document.reference_shape),
        "raw_interpretation": (
            {
                name: getattr(profile, name)
                for name in (
                    "width",
                    "height",
                    "stride_bytes",
                    "offset_bytes",
                    "storage_format",
                    "container_dtype",
                    "endianness",
                    "bit_depth",
                    "bit_alignment",
                    "packed_bit_order",
                    "channel_layout",
                    "bayer_pattern",
                    "black_level",
                    "white_level",
                )
            }
            if profile is not None
            else None
        ),
        "yuv_layout": getattr(frame, "layout", None),
        "subsampling": getattr(frame, "subsampling", None),
        "native_interpretation": native_interpretation(document).to_portable(),
    }
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def snapshot_source(document: ImageDocument, source_key: str) -> AnalysisSourceV1:
    if document.source is None:
        raise ValueError("unloaded source cannot be captured")
    encoded_sha256 = document.encoded_source_sha256
    return AnalysisSourceV1(
        source_key=source_key,
        document_id=document.document_id,
        generation=document.generation,
        native_shape=tuple(int(v) for v in document.shape),
        reference_shape=(int(document.reference_shape[0]), int(document.reference_shape[1])),
        native_dtype=str(document.original_dtype),
        channel_layout=document.channel_layout,
        effective_bits=document.bit_depth,
        profile_signature=native_profile_signature(document),
        native_interpretation=native_interpretation(document),
        sha256=(
            encoded_sha256
            if isinstance(encoded_sha256, str) and len(encoded_sha256) == 64
            else None
        ),
        # Decode-time digest alone does not attest to current on-disk content.
        verification="unverified",
    )
