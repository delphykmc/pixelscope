from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.iqa_submission import _current_pair_image_contract


def _rgb(
    name: str,
    *,
    height: int = 4,
    width: int = 6,
    dtype: type[np.generic] = np.uint8,
) -> ImageDocument:
    return ImageDocument.from_array(
        np.zeros((height, width, 3), dtype=dtype),
        name,
    )


def test_current_pair_contract_accepts_matching_rgb8_images() -> None:
    eligible, status = _current_pair_image_contract(
        [_rgb("a.png"), _rgb("b.png")]
    )

    assert eligible
    assert status == "OK · RGB8 · 6×4"


def test_current_pair_contract_rejects_non_rgb_images() -> None:
    gray = ImageDocument.from_array(
        np.zeros((4, 6), dtype=np.uint8),
        "gray.png",
    )

    eligible, status = _current_pair_image_contract([_rgb("a.png"), gray])

    assert not eligible
    assert status == "IQA requires RGB images"


def test_current_pair_contract_rejects_size_mismatch() -> None:
    eligible, status = _current_pair_image_contract(
        [_rgb("a.png"), _rgb("b.png", width=7)]
    )

    assert not eligible
    assert status == "image size mismatch"


def test_current_pair_contract_rejects_mixed_rgb8_rgb16() -> None:
    eligible, status = _current_pair_image_contract(
        [_rgb("a.png", dtype=np.uint8), _rgb("b.png", dtype=np.uint16)]
    )

    assert not eligible
    assert status == "IQA requires 8-bit RGB images"


def test_current_pair_contract_rejects_matching_rgb16_images() -> None:
    eligible, status = _current_pair_image_contract(
        [_rgb("a.png", dtype=np.uint16), _rgb("b.png", dtype=np.uint16)]
    )

    assert not eligible
    assert status == "IQA requires 8-bit RGB images"
