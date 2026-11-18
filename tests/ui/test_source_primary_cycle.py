from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QTransform
from PySide6.QtWidgets import QApplication, QLineEdit

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.image_viewer import ImageViewer

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object, count: int) -> tuple[MainWindow, list[ImageDocument]]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(
            np.full((240, 320), index + 1, dtype=np.uint8), f"cycle-{index}.png"
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    return window, documents


def _visible_source_ids(window: MainWindow) -> list[str]:
    return [
        viewer.document.document_id
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None and viewer.document.channel_layout != "DIFFERENCE"
    ]


def _image_view_oracle(viewer: ImageViewer) -> tuple[tuple[float, float], tuple[float, float]]:
    """Independent mapping for this test's untransformed 320x240 Gray inputs.

    Integer mapFromScene endpoints have at most one physical-pixel rounding
    error over a 2048-native-pixel baseline. No production zoom helper is used.
    """
    image = viewer.image_item
    graphics = viewer._graphics
    origin = graphics.mapFromScene(image.mapToScene(QPointF(0.5, 0.5)))
    px = graphics.mapFromScene(image.mapToScene(QPointF(2048.5, 0.5)))
    py = graphics.mapFromScene(image.mapToScene(QPointF(0.5, 2048.5)))
    dpr = graphics.viewport().devicePixelRatioF()
    scale = ((px.x() - origin.x()) * dpr / 2048, (py.y() - origin.y()) * dpr / 2048)
    box = viewer.view_box
    center = image.mapFromScene(box.mapToScene(QPointF(box.width() / 2, box.height() / 2)))
    return scale, (center.x(), center.y())


@pytest.mark.parametrize("count", (2, 3, 4, 5, 6))
def test_t_rotates_last_source_to_primary_without_image_upload(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    window, documents = _window(qtbot, count)
    selected_ids = [document.document_id for document in documents]
    window.set_layout_mode("Multi View")
    before_order = _visible_source_ids(window)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window.multi_compare_view._layout_refit_active
        and all(
            not v._geometry_timer.isActive() for v in window.multi_compare_view.occupied_viewers
        )
    )
    before_views = {
        viewer.document.document_id: (
            viewer.measure_physical_zoom().percent,
            [sum(axis) / 2 for axis in viewer.view_box.viewRange()],
            _image_view_oracle(viewer),
        )
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    }
    uploads: list[str] = []
    original_upload = ImageViewer._upload_preview

    def recording_upload(self: ImageViewer, preview: object, document: ImageDocument) -> None:
        uploads.append(document.document_id)
        original_upload(self, preview, document)

    monkeypatch.setattr(ImageViewer, "_upload_preview", recording_upload)
    for _ in range(count):
        expected = [before_order[-1], *before_order[:-1]]
        window.cycle_primary_source()
        assert _visible_source_ids(window) == expected
        assert window._focus_document_id == expected[0]
        assert [document.document_id for document in window.selected_documents] == selected_ids
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: not window.multi_compare_view._layout_refit_active
            and all(
                not v._geometry_timer.isActive() for v in window.multi_compare_view.occupied_viewers
            )
        )
        # Integer tile-width redistribution changes visible endpoints at the
        # same physical scale. Check each retained source's scale and center,
        # rather than comparing endpoints from different viewport dimensions.
        for viewer in window.multi_compare_view.occupied_viewers:
            assert viewer.document is not None
            percent, center, (oracle_scale, oracle_center) = before_views[
                viewer.document.document_id
            ]
            measurement = viewer.measure_physical_zoom()
            assert measurement.valid and percent is not None
            assert measurement.percent == pytest.approx(percent, rel=0.005)
            assert [sum(axis) / 2 for axis in viewer.view_box.viewRange()] == pytest.approx(
                center, abs=1e-8, rel=0
            )
            actual_scale, actual_center = _image_view_oracle(viewer)
            assert actual_scale == pytest.approx(
                oracle_scale, abs=2 * viewer._graphics.viewport().devicePixelRatioF() / 2048, rel=0
            )
            assert actual_center == pytest.approx(oracle_center, abs=1e-8, rel=0)
        before_order = expected
    assert uploads == []
    assert before_order == selected_ids
    window.close()


@pytest.mark.parametrize("distortion", ["translate", "scale"])
def test_primary_oracle_detects_image_transform_errors(qtbot, distortion) -> None:
    window, _ = _window(qtbot, 2)
    viewer = window.multi_compare_view.occupied_viewers[0]
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    before_scale, before_center = _image_view_oracle(viewer)
    position, transform = viewer.image_item.pos(), viewer.image_item.transform()
    try:
        if distortion == "translate":
            viewer.image_item.setPos(position + QPointF(7, 5))
            _, center = _image_view_oracle(viewer)
            assert center == pytest.approx((before_center[0] - 7, before_center[1] - 5))
        else:
            viewer.image_item.setTransform(QTransform().scale(1.1, 1.1))
            scale, _ = _image_view_oracle(viewer)
            assert scale == pytest.approx(tuple(s * 1.1 for s in before_scale), abs=2 / 2048, rel=0)
    finally:
        viewer.image_item.setPos(position)
        viewer.image_item.setTransform(transform)
        window.close()


def test_t_rotates_in_single_view_without_displaying_diff(
    qtbot: object,
) -> None:
    window, documents = _window(qtbot, 3)
    window.set_layout_mode("Single View")
    expected = [documents[2], documents[1], documents[0], documents[2]]
    for source in expected:
        window.cycle_primary_source()
        assert window.viewer.document is source
        assert window._focus_document_id == source.document_id
    window.close()


def test_t_uses_only_current_page_and_skips_derived_order_entries(qtbot: object) -> None:
    window, documents = _window(qtbot, 7)
    window.set_layout_mode("Multi View")
    # A leftover derived/display-only ID must never become a source target.
    window._multi_display_order.append("generated-difference")
    window.cycle_primary_source()
    assert window._focus_document_id == documents[5].document_id
    assert window._page_start == 0
    assert documents[6].document_id not in _visible_source_ids(window)
    window.close()


@pytest.mark.parametrize("scope", ["viewer", "document_list"])
def test_t_shortcut_is_scoped_to_viewer_and_files(qtbot: object, scope: str) -> None:
    window, documents = _window(qtbot, 2)
    window.activateWindow()
    window.set_layout_mode("Single View")
    target = getattr(window, scope)
    target.setFocus()
    qtbot.keyClick(target, Qt.Key.Key_T)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[1]
    window.close()


def test_t_leaves_editor_and_modified_key_input_alone(qtbot: object) -> None:
    window, documents = _window(qtbot, 2)
    window.set_layout_mode("Single View")
    editor = QLineEdit(window)
    editor.show()
    window.activateWindow()
    editor.setFocus()
    qtbot.keyClicks(editor, "t")  # type: ignore[attr-defined]
    assert editor.text() == "t"
    assert window.viewer.document is documents[0]
    window.viewer.setFocus()
    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier
    )
    assert window.viewer.document is documents[0]
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_T, Qt.KeyboardModifier.NoModifier, "t", True)
    QApplication.sendEvent(window.viewer, event)
    assert window.viewer.document is documents[0]
    window.close()


def test_cycle_does_nothing_for_one_source_or_split_channels(qtbot: object) -> None:
    window, documents = _window(qtbot, 1)
    window.cycle_primary_source()
    assert window.viewer.document is documents[0]
    window.close()

    window, documents = _window(qtbot, 2)
    window._channel_split_active = True
    before = list(window._multi_display_order)
    window.cycle_primary_source()
    assert window._multi_display_order == before
    window.close()


def test_b_no_longer_overlays_source_images(qtbot: object) -> None:
    window, _documents = _window(qtbot, 2)
    viewer = window.multi_compare_view.occupied_viewers[0]
    before_document = viewer.document
    before_image = np.array(viewer.image_item.image, copy=True)
    window.activateWindow()
    viewer.setFocus()
    qtbot.keyClick(viewer, Qt.Key.Key_B)  # type: ignore[attr-defined]
    assert viewer.document is before_document
    assert np.array_equal(viewer.image_item.image, before_image)
    assert not hasattr(window.quick_compare_controller, "_blink_snapshot")
    window.close()
