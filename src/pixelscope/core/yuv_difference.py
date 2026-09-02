from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.diff_engine import (
    DifferenceCompatibility,
    DifferenceFamily,
    difference_compatibility as legacy_difference_compatibility,
)
from pixelscope.core.image_document import ImageDocument

YUV_LAYOUTS = ("YUV444", "YUV422", "YUV420")
YUV_DIFFERENCE_CHANNELS = ("Y", "U", "V")


def is_yuv_document(document: ImageDocument) -> bool:
    """Return whether a document declares one of the native WP-C1 YUV layouts."""

    return document.channel_layout in YUV_LAYOUTS


def difference_compatibility(a: ImageDocument, b: ImageDocument) -> DifferenceCompatibility:
    """Extend the established Difference compatibility contract with native YUV.

    Existing RGB/Gray/Bayer pairs are delegated unchanged to ``diff_engine``. Native
    YUV is intentionally same-subsampling and 8-bit only for WP-C2; no preview RGB,
    normalization, or chroma resampling participates in this decision.
    """

    yuv_a = is_yuv_document(a)
    yuv_b = is_yuv_document(b)
    if not yuv_a and not yuv_b:
        return legacy_difference_compatibility(a, b)

    if a.source is None or b.source is None:
        return DifferenceCompatibility(
            compatible=False,
            family=None,
            domain=None,
            reason_code="source-unavailable",
            detail="Both images must be loaded before comparison.",
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )
    if a.shape[:2] != b.shape[:2]:
        return DifferenceCompatibility(
            compatible=False,
            family=None,
            domain=None,
            reason_code="size-mismatch",
            detail=f"Image dimensions do not match: {a.shape[:2]} vs {b.shape[:2]}.",
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )
    if yuv_a != yuv_b:
        return DifferenceCompatibility(
            compatible=False,
            family=None,
            domain=None,
            reason_code="layout-mismatch",
            detail=(
                "Difference image families do not match: YUV vs non-YUV. "
                "YUV Difference requires two native YUV images."
            ),
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )

    family: DifferenceFamily = "YUV"
    frame_a = a.yuv_frame
    frame_b = b.yuv_frame
    if frame_a is None or frame_b is None:
        return DifferenceCompatibility(
            compatible=False,
            family=family,
            domain=None,
            reason_code="unsupported-layout",
            detail="Native YUV Difference requires authoritative Y/U/V planes for both images.",
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )
    if frame_a.layout != a.channel_layout or frame_b.layout != b.channel_layout:
        return DifferenceCompatibility(
            compatible=False,
            family=family,
            domain=None,
            reason_code="unsupported-layout",
            detail="YUV document layout does not match its native plane metadata.",
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )
    if frame_a.layout != frame_b.layout:
        return DifferenceCompatibility(
            compatible=False,
            family=family,
            domain=None,
            reason_code="layout-mismatch",
            detail=(
                "YUV subsampling does not match: "
                f"{frame_a.layout} vs {frame_b.layout}. "
                "WP-C2 supports same-subsampling YUV Difference only."
            ),
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )
    if a.bit_depth != 8 or b.bit_depth != 8:
        return DifferenceCompatibility(
            compatible=False,
            family=family,
            domain=None,
            reason_code="unsupported-layout",
            detail="WP-C2 supports native 8-bit YUV Difference only.",
            effective_bit_depth_a=a.bit_depth,
            effective_bit_depth_b=b.bit_depth,
            data_range=None,
        )

    return DifferenceCompatibility(
        compatible=True,
        family=family,
        domain="native",
        reason_code="ok",
        detail="Compatible native YUV Difference pair.",
        effective_bit_depth_a=8,
        effective_bit_depth_b=8,
        data_range=255.0,
    )


def native_yuv_plane(document: ImageDocument, channel: str) -> NDArray[np.uint8]:
    """Return one authoritative native plane without chroma replication."""

    frame = document.yuv_frame
    if frame is None or not is_yuv_document(document):
        raise ValueError("document is not an authoritative native YUV image")
    if channel == "Y":
        return frame.y
    if channel == "U":
        return frame.u
    if channel == "V":
        return frame.v
    raise ValueError(f"unsupported YUV Difference channel: {channel}")
