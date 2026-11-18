"""Encode frozen reference-space ROI previews for the single Memo save path."""
from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from pixelscope.core.roi import RoiBounds, roi_fits_shape


def encode_roi_png(preview: NDArray[np.uint8], roi: RoiBounds) -> bytes:
    if preview.dtype != np.uint8 or not roi_fits_shape(preview.shape, roi):
        raise ValueError("Memo requires an in-bounds ROI on an 8-bit preview")
    region = np.ascontiguousarray(preview[roi.y : roi.bottom, roi.x : roi.right])
    if region.ndim == 3 and region.shape[2] == 3:
        source = cv2.cvtColor(region, cv2.COLOR_RGB2BGR)
    elif region.ndim == 3 and region.shape[2] == 4:
        source = cv2.cvtColor(region, cv2.COLOR_RGBA2BGRA)
    elif region.ndim == 2:
        source = region
    else:
        raise ValueError("Memo PNG supports Gray, RGB and RGBA previews")
    ok, encoded = cv2.imencode(".png", source)
    if not ok:
        raise OSError("Memo PNG encoding failed")
    return encoded.tobytes()
