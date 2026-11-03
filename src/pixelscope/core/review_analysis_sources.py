"""Shared Qt-free source identity adapter for W02 analysis producers.

A source key is durable only once W09's canonical Review owner binds it. The
fallback UUID is session-local and never inferred from a path or display alias.
"""
from __future__ import annotations

import hashlib
import json

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis import AnalysisSourceV1


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
                    "width", "height", "stride_bytes", "offset_bytes",
                    "storage_format", "container_dtype", "endianness",
                    "bit_depth", "bit_alignment", "packed_bit_order",
                    "channel_layout", "bayer_pattern", "black_level", "white_level",
                )
            }
            if profile is not None else None
        ),
        "yuv_layout": getattr(frame, "layout", None),
        "subsampling": getattr(frame, "subsampling", None),
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
        sha256=(encoded_sha256 if isinstance(encoded_sha256, str)
                and len(encoded_sha256) == 64 else None),
        # Decode-time digest alone does not attest to current on-disk content.
        verification="unverified",
    )
