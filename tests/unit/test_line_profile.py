from __future__ import annotations

import numpy as np

from pixelscope.core.line_profile import (
    LineSelection,
    clamp_line,
    horizontal_line_profile,
    selected_line_profile,
)
from pixelscope.core.roi import RoiBounds


def test_horizontal_line_profile_uses_roi_center() -> None:
    image = np.arange(30, dtype=np.uint16).reshape(5, 6)
    result = horizontal_line_profile(image, RoiBounds(1, 1, 4, 3))
    assert result.x_start == 1
    assert result.y == 2
    assert result.values[0].tolist() == [13.0, 14.0, 15.0, 16.0]


def test_rgb_line_profile_preserves_channels() -> None:
    image = np.zeros((2, 3, 3), dtype=np.uint8)
    image[:, :, 0] = (1, 2, 3)
    image[:, :, 1] = (4, 5, 6)
    result = horizontal_line_profile(image)
    assert result.channel_names == ("R", "G", "B")
    assert result.values[0].tolist() == [1.0, 2.0, 3.0]
    assert result.values[1].tolist() == [4.0, 5.0, 6.0]


def test_selected_line_profile_includes_endpoints_and_drag_direction() -> None:
    image = np.arange(20, dtype=np.uint16).reshape(2, 10)
    forward = selected_line_profile(image, LineSelection(2, 1, 6))
    reverse = selected_line_profile(image, LineSelection(6, 1, 0))
    assert forward.values[0].tolist() == [12.0, 13.0, 14.0, 15.0, 16.0]
    assert reverse.values[0].tolist() == [
        16.0,
        15.0,
        14.0,
        13.0,
        12.0,
        11.0,
        10.0,
    ]


def test_line_selection_clamps_to_common_image_coordinates() -> None:
    assert clamp_line((4, 5), -3, 10, 9) == LineSelection(0, 3, 4)
