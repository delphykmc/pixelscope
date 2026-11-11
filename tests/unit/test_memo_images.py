"""Frozen Memo crops preserve channel order and exact bounds without clipping."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_images import encode_roi_png


@pytest.mark.parametrize("channels", [1, 3, 4])
def test_png_preserves_exact_noncontiguous_roi_and_channels(channels):
    shape = (12, 18) if channels == 1 else (12, 18, channels)
    original = np.arange(np.prod(shape), dtype=np.uint8).reshape(shape)
    preview = original[::2, ::2]
    expected = preview[1:4, 2:6]
    data = encode_roi_png(preview, RoiBounds(2, 1, 4, 3))
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if channels == 3:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    elif channels == 4:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
    np.testing.assert_array_equal(decoded, expected)
    np.testing.assert_array_equal(preview, original[::2, ::2])


def test_roi_outside_bounds_is_rejected_instead_of_clipped():
    with pytest.raises(ValueError, match="in-bounds"):
        encode_roi_png(np.zeros((5, 6), dtype=np.uint8), RoiBounds(4, 3, 4, 4))


def test_native_values_cannot_be_silently_converted_to_preview():
    with pytest.raises(ValueError, match="8-bit"):
        encode_roi_png(np.full((5, 6), 1023, dtype=np.uint16), RoiBounds(0, 0, 2, 2))
