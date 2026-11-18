"""8-bit preview-only ROI fidelity metric; no native source or Qt dependency."""
from __future__ import annotations

import math
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

_MAX_PNG_BYTES = 64 * 1024 * 1024
_MAX_PIXELS = 16 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _decode_png(payload: bytes) -> NDArray[np.uint8] | None:
    if (
        not isinstance(payload, bytes)
        or not 32 <= len(payload) <= _MAX_PNG_BYTES
        or payload[:8] != _PNG_SIGNATURE
        or payload[12:16] != b"IHDR"
    ):
        return None
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    if width <= 0 or height <= 0 or width * height > _MAX_PIXELS:
        return None
    try:
        decoded = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    except cv2.error:
        return None
    if (
        decoded is None
        or decoded.shape[:2] != (height, width)
        or decoded.dtype != np.uint8
        or decoded.ndim not in (2, 3)
        or (decoded.ndim == 3 and decoded.shape[2] != 3)
    ):
        return None
    # RGBA is deliberately not conflated with RGB; alpha-composite PSNR is undefined
    # without an explicit background and color-space contract.
    return cast(NDArray[np.uint8], decoded)


def psnr_8bit_png(reference: bytes, target: bytes) -> float | None:
    """PSNR of the decoded *stored* preview pixels, peak=255; unavailable -> None.

    OpenCV's L2SQR norm uses a bounded native implementation rather than allocating
    a full float64 difference cube. Channel ordering is identical for both PNGs;
    average squared error includes every sample in grayscale or three-channel BGR.
    No alignment, color-space conversion or external-file access occurs.
    """
    ref = _decode_png(reference)
    other = _decode_png(target)
    if ref is None or other is None or ref.shape != other.shape:
        return None
    try:
        error_sum = float(cv2.norm(ref, other, cv2.NORM_L2SQR))
    except cv2.error:
        return None
    if not math.isfinite(error_sum):
        return None
    if error_sum == 0:
        return math.inf
    mse = error_sum / ref.size
    return 10.0 * math.log10((255.0 * 255.0) / mse)
