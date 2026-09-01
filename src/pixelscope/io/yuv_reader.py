from __future__ import annotations

from pathlib import Path

import numpy as np

from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.yuv_profile import YuvProfile


class YuvReadError(ValueError):
    """Raised when a source does not match the explicit WP-C1 YUV profile."""


def required_yuv_file_size(profile: YuvProfile) -> int:
    return profile.expected_file_size


def read_yuv(path: str | Path, profile: YuvProfile) -> NativeYuvFrame:
    """Decode Y first + UV-interleaved tightly packed storage into native plane views."""

    source_path = Path(path)
    expected = required_yuv_file_size(profile)
    try:
        actual = source_path.stat().st_size
    except OSError as exc:
        raise YuvReadError(f"cannot read YUV source: {exc}") from exc
    if actual != expected:
        raise YuvReadError(
            f"YUV file size does not match profile: expected {expected} bytes, got {actual}"
        )

    payload = np.fromfile(source_path, dtype=np.uint8)
    luma_count = profile.width * profile.height
    y = payload[:luma_count].reshape(profile.height, profile.width)
    scale_x = 1 if profile.channel_layout == "YUV444" else 2
    scale_y = 2 if profile.channel_layout == "YUV420" else 1
    chroma_height = profile.height // scale_y
    chroma_width = profile.width // scale_x
    uv = payload[luma_count:].reshape(chroma_height, chroma_width * 2)
    # U/V remain strided views into the interleaved file payload; no full-resolution
    # chroma replication or independent plane copy is introduced as analysis authority.
    u = uv[:, 0::2]
    v = uv[:, 1::2]
    return NativeYuvFrame(y=y, u=u, v=v, layout=profile.channel_layout)
