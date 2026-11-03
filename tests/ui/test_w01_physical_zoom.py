"""W01 physical zoom tests: independent Qt mapFromScene oracle, not only labels.

Hardware screen capture, per-monitor OS DPI, and pixel-center screenshots remain
owner-side manual acceptance; synthetic DPR never substitutes for those tests.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.spatial_sampling import SpatialSampling
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.multi_compare_view import MultiCompareView

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _checkerboard(rows: int = 64, columns: int = 64) -> ImageDocument:
    y, x = np.indices((rows, columns))
    checker = ((x + y) % 2 * 255).astype(np.uint8)
    checker[rows // 2, columns // 2] = 127  # impulse/pixel-center witness
    return ImageDocument.from_array(checker, "checker.png")


def _qt_oracle_scale(viewer: ImageViewer) -> tuple[float, float]:
    """Independent Qt QGraphicsView integer viewport mapping over 512 pixels.

    Production uses the ImageItem's prescribed reference→local transform and
    QGraphicsView.viewportTransform at three subpixel points. This independent
    route uses the GraphicsView.mapFromScene API, so its endpoint rounding is
    explicitly amortized across a 512-reference-pixel baseline.
    """
    rect = viewer._presentation_rect(viewer.document)  # type: ignore[arg-type]
    local_bounds = viewer.image_item.boundingRect()

    def native_local(x: float, y: float) -> QPointF:
        return QPointF(
            local_bounds.left() + x * local_bounds.width() / rect.width(),
            local_bounds.top() + y * local_bounds.height() / rect.height(),
        )

    graphics = viewer._graphics
    p0 = graphics.mapFromScene(viewer.image_item.mapToScene(native_local(0.5, 0.5)))
    px = graphics.mapFromScene(viewer.image_item.mapToScene(native_local(512.5, 0.5)))
    py = graphics.mapFromScene(viewer.image_item.mapToScene(native_local(0.5, 512.5)))
    dpr = viewer._device_pixel_ratio()
    return (px.x() - p0.x()) * dpr / 512, (py.y() - p0.y()) * dpr / 512


@pytest.mark.parametrize("percent", [100.0, 200.0, 400.0])
def test_small_checkerboard_has_real_exact_scale_and_no_image_clamp(
    qtbot: object, percent: float
) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.resize(780, 540)
    viewer.set_document(_checkerboard(8, 8))
    viewer.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    result = viewer.set_physical_zoom(percent)
    assert result.achieved, result
    assert viewer.zoom_percent == pytest.approx(percent, rel=0.005)
    assert viewer.header.zoom.text() == f"{percent:.0f}%"
    if percent == 100:
        ranges = viewer.view_box.viewRange()
        assert ranges[0][1] - ranges[0][0] > 8
        assert ranges[1][1] - ranges[1][0] > 8
    oracle_x, oracle_y = _qt_oracle_scale(viewer)
    assert oracle_x == pytest.approx(percent / 100.0, rel=0.005)
    assert oracle_y == pytest.approx(percent / 100.0, rel=0.005)


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 1.75, 2.0])
def test_synthetic_fractional_dpr_recalibrates_reference_scale(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, dpr: float
) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.resize(703, 509)
    viewer.set_document(_checkerboard())
    viewer.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    monkeypatch.setattr(viewer, "_device_pixel_ratio", lambda: dpr)

    result = viewer.set_physical_zoom(100.0)
    assert result.achieved, result
    assert result.measurement.dpr == dpr
    assert viewer.zoom_percent == pytest.approx(100, rel=0.005)
    oracle_x, oracle_y = _qt_oracle_scale(viewer)
    assert oracle_x == pytest.approx(1.0, rel=0.005)
    assert oracle_y == pytest.approx(1.0, rel=0.005)


def test_item_transform_changes_actual_zoom_and_invalidates_distorted_label(
    qtbot: object,
) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.resize(700, 500)
    viewer.set_document(_checkerboard())
    viewer.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert viewer.set_physical_zoom(100).achieved
    original = viewer.image_item.transform()
    viewer.image_item.setTransform(QTransform().scale(1.1, 1.1))
    assert viewer.zoom_percent == pytest.approx(110.0, rel=0.005)
    viewer.image_item.setTransform(QTransform().scale(1.1, 1.0))
    assert viewer.zoom_percent is None
    assert not viewer.measure_physical_zoom().valid
    viewer.image_item.setTransform(QTransform().scale(-1.0, 1.0))
    assert viewer.zoom_percent is None
    viewer.image_item.setTransform(original)


def test_subsampled_plane_uses_reference_pixels_not_native_sample_cells(
    qtbot: object,
) -> None:
    sampling = SpatialSampling.cell_footprint((8, 8), (4, 4), row_step=2, column_step=2)
    document = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "YUV420-U-reference-grid",
        spatial_sampling=sampling,
    )
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.resize(760, 540)
    viewer.set_document(document)
    viewer.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert viewer.set_physical_zoom(100).achieved
    assert viewer.measure_physical_zoom().percent == pytest.approx(100.0, rel=0.005)
    assert viewer.image_item.mapRectToParent(viewer.image_item.boundingRect()).width() == 8


@pytest.mark.parametrize("count", [1, 2, 4, 6])
def test_multi_tiles_have_same_actual_physical_zoom_with_uneven_layout(
    qtbot: object, count: int
) -> None:
    multi = MultiCompareView()
    qtbot.addWidget(multi)  # type: ignore[attr-defined]
    multi.resize(1203, 699)
    multi.set_capacity(2 if count == 1 else count)
    documents = [
        ImageDocument.from_array(
            np.full((64, 96, 3), index, dtype=np.uint8), f"{index}.png"
        )
        for index in range(count)
    ]
    multi.set_documents(documents, 0, count, None, None)
    multi.show()
    qtbot.wait(30)  # type: ignore[attr-defined]
    multi.zoom_100_percent()

    for viewer in multi.visible_viewers[:count]:
        measurement = viewer.measure_physical_zoom()
        assert measurement.valid
        assert measurement.percent == pytest.approx(100, rel=0.005)


def test_unsynchronized_zoom_does_not_change_other_tile_on_pan(
    qtbot: object,
) -> None:
    multi = MultiCompareView()
    qtbot.addWidget(multi)  # type: ignore[attr-defined]
    multi.resize(1051, 601)
    multi.set_documents([_checkerboard(), _checkerboard()], 0, 2, None, None)
    multi.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    multi.set_sync_enabled(False)
    multi.zoom_100_percent()
    first, second = multi.visible_viewers
    second_before = second.view_box.viewRange()
    first.view_box.translateBy(x=20, y=12)
    assert second.view_box.viewRange() == second_before
    assert first.measure_physical_zoom().percent == pytest.approx(100, rel=0.005)
    assert second.measure_physical_zoom().percent == pytest.approx(100, rel=0.005)
