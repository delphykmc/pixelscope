from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _yuv_document(name: str, *, u_delta: int = 0) -> ImageDocument:
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    u = np.array([[40, 50], [60, 70]], dtype=np.uint8)
    v = np.array([[180, 190], [200, 210]], dtype=np.uint8)
    if u_delta:
        u = (u.astype(np.uint16) + u_delta).astype(np.uint8)
    return ImageDocument.from_yuv(
        NativeYuvFrame(y=y, u=u, v=v, layout="YUV420"),
        name,
    )


def _bayer_document(name: str, *, delta: int = 0) -> ImageDocument:
    source = np.zeros((4, 4), dtype=np.uint16)
    source[0::2, 0::2] = 100
    if delta:
        source[0::2, 0::2] = source[0::2, 0::2] + np.uint16(delta)
    profile = RawProfile(
        name=name,
        width=4,
        height=4,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=1023,
    )
    return ImageDocument.from_array(
        source,
        name,
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
        prepared_preview=render_bayer_preview(source, "RGGB", 0, 10),
    )


def test_yuv420_u_difference_preserves_reference_extent_and_lookup(qtbot: object) -> None:
    window = _window(qtbot)
    first = _yuv_document("a.yuv")
    second = _yuv_document("b.yuv", u_delta=7)
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    panel = window.difference_panel
    panel.channel.setCurrentText("U")

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=3000,
    )

    difference = window._difference_document
    assert difference is not None
    assert difference.source is not None
    assert difference.source.shape == (2, 2)
    assert difference.reference_shape == (4, 4)
    assert difference.spatial_sampling is not None
    assert difference.spatial_sampling.semantics == "cell_footprint"
    assert difference.spatial_sampling.presentation_rect == (0.0, 0.0, 4.0, 4.0)
    assert difference.sample_channel == "U"

    left_lookup = difference.sample_lookup_at_reference(1, 0)
    right_lookup = difference.sample_lookup_at_reference(2, 0)
    assert left_lookup is not None
    assert right_lookup is not None
    assert (left_lookup.sample_xy, left_lookup.value) == ((0, 0), 7)
    assert (right_lookup.sample_xy, right_lookup.value) == ((1, 0), 7)
    assert window._reference_value_at(difference, 1, 0) == 7
    assert window._reference_value_at(difference, 2, 0) == 7

    window.close()


def test_bayer_channel_difference_uses_point_lattice_lookup(qtbot: object) -> None:
    window = _window(qtbot)
    first = _bayer_document("a.raw")
    second = _bayer_document("b.raw", delta=5)
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    panel = window.difference_panel
    panel.channel.setCurrentText("R")

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=3000,
    )

    difference = window._difference_document
    assert difference is not None
    assert difference.source is not None
    assert difference.source.shape == (2, 2)
    assert difference.reference_shape == (4, 4)
    assert difference.spatial_sampling is not None
    assert difference.spatial_sampling.semantics == "point_lattice"
    assert difference.sample_channel == "R"

    matching = difference.sample_lookup_at_reference(0, 0)
    skipped = difference.sample_lookup_at_reference(1, 0)
    next_matching = difference.sample_lookup_at_reference(2, 0)
    assert matching is not None
    assert skipped is not None
    assert skipped.sample_xy is None
    assert skipped.value is None
    assert next_matching is not None
    assert (matching.sample_xy, matching.value) == ((0, 0), 5)
    assert (next_matching.sample_xy, next_matching.value) == ((1, 0), 5)
    assert window._reference_value_at(difference, 1, 0) is None

    window.close()
