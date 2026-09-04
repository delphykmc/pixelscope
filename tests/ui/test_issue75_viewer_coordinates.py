from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF

from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.core.spatial_sampling import SpatialSampling
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.multi_compare_view import MultiCompareView

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _mapped_document() -> ImageDocument:
    sampling = SpatialSampling.cell_footprint((6, 8), (3, 4), row_step=2, column_step=2)
    return ImageDocument.from_array(
        np.arange(12, dtype=np.uint8).reshape(3, 4),
        "mapped",
        spatial_sampling=sampling,
    )


def test_mapped_preview_uses_reference_rect_and_fit_extent(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    document = _mapped_document()
    viewer.set_document(document)

    rect = viewer.image_item.mapRectToParent(viewer.image_item.boundingRect())
    assert rect.width() == pytest.approx(8.0)
    assert rect.height() == pytest.approx(6.0)
    viewer.fit_image()
    x_range, y_range = viewer.view_box.viewRange()
    assert x_range[0] <= 0 and x_range[1] >= 8
    assert y_range[0] <= 0 and y_range[1] >= 6


def test_mapped_roi_and_line_are_clamped_in_reference_space(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(_mapped_document())

    viewer.set_roi_bounds(RoiBounds(0, 0, 8, 6))
    assert viewer.current_roi_bounds() == RoiBounds(0, 0, 8, 6)
    viewer.set_line_selection(LineSelection(0, 0, 99, 99))
    assert viewer.line_selection == LineSelection(0, 0, 7, 0)


def test_cursor_emits_reference_coordinate_when_lookup_has_no_sample(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(_mapped_document())
    emitted: list[tuple[int, int, object]] = []
    viewer.cursor_moved.connect(lambda x, y, value: emitted.append((x, y, value)))

    point = viewer.view_box.mapViewToScene(QPointF(7.2, 5.8))
    viewer._on_scene_mouse_moved(point)
    assert emitted[-1][:2] == (7, 5)
    assert emitted[-1][2] == 11

    point = viewer.view_box.mapViewToScene(QPointF(1.2, 1.2))
    viewer._on_scene_mouse_moved(point)
    assert emitted[-1][:2] == (1, 1)
    assert emitted[-1][2] == 0


@pytest.mark.parametrize(("layout", "native_shape"), [("YUV422", (4, 2)), ("YUV420", (2, 2))])
def test_yuv_split_keeps_native_preview_and_full_reference_rect(
    layout: str, native_shape: tuple[int, int], qtbot: object
) -> None:
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    u = np.arange(np.prod(native_shape), dtype=np.uint8).reshape(native_shape)
    v = (u + 40).astype(np.uint8)
    source_document = ImageDocument.from_yuv(NativeYuvFrame(y, u, v, layout), "native.yuv")
    _y_view, u_view, _v_view = split_document_channels(source_document)
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(u_view)

    assert u_view.preview is not None
    assert u_view.preview.shape[:2] == native_shape
    assert u_view.reference_shape == (4, 4)
    assert u_view.preview.shape[:2] != u_view.reference_shape
    rect = viewer.image_item.mapRectToParent(viewer.image_item.boundingRect())
    assert rect.width() == pytest.approx(4.0)
    assert rect.height() == pytest.approx(4.0)
    lookup = u_view.sample_lookup_at_reference(3, 3)
    assert lookup is not None and lookup.value == int(u[-1, -1])


def test_multi_view_sync_uses_reference_ranges_for_mapped_and_full_resolution(
    qtbot: object,
) -> None:
    multi = MultiCompareView()
    qtbot.addWidget(multi)  # type: ignore[attr-defined]
    mapped = _mapped_document()
    full = ImageDocument.from_array(np.arange(48, dtype=np.uint8).reshape(6, 8), "full")
    multi.set_documents([full, mapped], 0, 2, None, None)
    first, second = multi.visible_viewers
    first.view_box.setRange(xRange=(1, 5), yRange=(1, 4), padding=0)
    qtbot.wait(10)  # type: ignore[attr-defined]
    assert second.view_box.viewRange()[0] == pytest.approx([1.0, 5.0], abs=0.03)
    assert second.view_box.viewRange()[1] == pytest.approx([1.0, 4.0], abs=0.03)

    point = second.view_box.mapViewToScene(QPointF(7.2, 5.8))
    second._on_scene_mouse_moved(point)
    assert first._vertical_cursor.isVisible()
    assert first._horizontal_cursor.isVisible()
    assert first._vertical_cursor.value() == pytest.approx(7.5)
    multi.zoom_100_percent()
    assert multi.visible_viewers[0].view_box.viewRange()[0][1] >= 8.0


def test_mapped_to_identity_transition_resets_image_item_rect(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    mapped = _mapped_document()
    identity = ImageDocument.from_array(mapped.source.copy(), "identity")  # type: ignore[union-attr]
    viewer.set_document(mapped)
    mapped_rect = viewer.image_item.mapRectToParent(viewer.image_item.boundingRect())
    assert mapped_rect.width() == pytest.approx(8)
    viewer.set_document(identity, fit=False)
    rect = viewer.image_item.mapRectToParent(viewer.image_item.boundingRect())
    assert rect.width() == pytest.approx(4)
    assert rect.height() == pytest.approx(3)


def test_bayer_point_lattice_rect_and_invalid_site_cursor_are_reference_space(
    qtbot: object,
) -> None:
    source = np.arange(5 * 7, dtype=np.uint16).reshape(5, 7)
    profile = RawProfile(
        name="raw",
        width=7,
        height=5,
        stride_bytes=14,
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
    document = ImageDocument.from_array(
        source,
        "raw",
        channel_layout="BAYER",
        raw_profile=profile,
        prepared_preview=render_bayer_preview(source, "RGGB", 0, 10),
    )
    red = next(view for view in split_document_channels(document) if view.sample_channel == "R")
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(red)
    assert red.source is not None and red.preview is not None
    assert red.preview.shape[:2] == red.source.shape[:2]
    assert red.preview.shape[:2] != red.reference_shape
    rect = viewer.image_item.mapRectToParent(viewer.image_item.boundingRect())
    assert rect.x() == pytest.approx(-0.5)
    assert rect.y() == pytest.approx(-0.5)
    assert rect.width() == pytest.approx(8.0)
    assert rect.height() == pytest.approx(6.0)

    emitted: list[tuple[int, int, object]] = []
    viewer.cursor_moved.connect(lambda x, y, value: emitted.append((x, y, value)))
    point = viewer.view_box.mapViewToScene(QPointF(1.2, 0.2))
    viewer._on_scene_mouse_moved(point)
    assert emitted[-1] == (1, 0, None)
    assert viewer._vertical_cursor.isVisible()
