from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.image_viewer import ImageViewer, RoiViewBox
from pixelscope.ui.pixel_inspector import PixelInspector

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_viewer_pixel_and_ctrl_drag_roi(qtbot: object) -> None:
    viewer = ImageViewer()
    inspector = PixelInspector()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    qtbot.addWidget(inspector)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.arange(100, dtype=np.uint8).reshape(10, 10), "pixel")
    viewer.set_document(document)
    inspector.update_document(document, 0, 0)
    assert inspector.value_text() == "0"

    with qtbot.waitSignal(viewer.roi_changed):  # type: ignore[attr-defined]
        viewer._on_roi_dragged((QPointF(2.2, 3.1), QPointF(7.8, 8.0)), True)
    assert viewer.current_roi_bounds() == RoiBounds(2, 3, 6, 5)
    viewer.clear_roi()
    assert viewer.current_roi_bounds() is None

    with qtbot.waitSignal(viewer.line_changed):  # type: ignore[attr-defined]
        viewer._on_line_dragged((QPointF(1.2, 6.7), QPointF(8.8, 2.0)), True)
    assert viewer.line_selection == LineSelection(1, 6, 8)
    viewer.clear_line()
    assert viewer.line_selection is None


def test_rgb_channel_split_uses_three_automatic_views(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.zeros((6, 8, 4), dtype=np.uint8), "rgba.png")
    window.add_document(document)
    split_action = window.action_map["Split Channels"]
    split_action.trigger()
    assert window._layout_mode == "Multi View"
    split_documents = [viewer.document for viewer in window.multi_compare_view.viewers[:4]]
    assert [item.channel_layout for item in split_documents if item is not None] == [
        "CHANNEL_R",
        "CHANNEL_G",
        "CHANNEL_B",
    ]
    assert split_documents[3] is None
    window.close()


def test_plain_drag_is_pan_only_and_crosshair_recovers(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(
        ImageDocument.from_array(np.arange(100, dtype=np.uint8).reshape(10, 10), "drag")
    )
    viewer.set_interaction_mode("line")
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.NoModifier) is None
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.ShiftModifier) == "line"
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.AltModifier) is None
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.ControlModifier) == "roi"

    inside = viewer.view_box.mapViewToScene(QPointF(3.2, 4.2))
    outside = viewer.view_box.mapViewToScene(QPointF(-2.0, -2.0))
    viewer._on_scene_mouse_moved(inside)
    assert viewer._vertical_cursor.isVisible()
    assert viewer._horizontal_cursor.isVisible()
    viewer._on_scene_mouse_moved(outside)
    assert not viewer._vertical_cursor.isVisible()
    viewer._on_scene_mouse_moved(inside)
    assert viewer._vertical_cursor.isVisible()
    assert viewer._horizontal_cursor.isVisible()


def test_grid_slots_and_shared_roi(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((12, 16), index, dtype=np.uint16), f"{index}.png")
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_view_capacity(4)
    qtbot.wait(10)  # type: ignore[attr-defined]

    assert [viewer.document for viewer in window.multi_compare_view.viewers[:4]] == [
        *documents,
        None,
    ]
    fitted_range = window.multi_compare_view.viewers[0].view_box.viewRange()
    assert fitted_range[0][0] <= 0 and fitted_range[0][1] >= 16
    assert fitted_range[1][0] <= 0 and fitted_range[1][1] >= 12
    window._shared_roi_changed(RoiBounds(2, 3, 7, 6))
    assert all(
        viewer.current_roi_bounds() == RoiBounds(2, 3, 7, 6)
        for viewer in window.multi_compare_view.viewers[:3]
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 3
        and all(
            result.pixel_count == 42 for result in window.comparison_analysis_panel.last_results
        ),
        timeout=3000,
    )
    assert all(result.pixel_count == 42 for result in window.comparison_analysis_panel.last_results)
    third_plot = window.comparison_analysis_panel.plots[2]
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(third_plot)
    )[:2] == (2, 0)
    assert not window.comparison_analysis_panel.plots[3].isVisibleTo(
        window.comparison_analysis_panel
    )
    window.clear_roi()
    assert all(
        viewer.current_roi_bounds() is None for viewer in window.multi_compare_view.viewers[:3]
    )
    window.close()


def test_single_view_number_shortcuts_and_six_histogram_grid(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((4, 4), index, dtype=np.uint8),
            f"selected-{index + 1}.png",
        )
        for index in range(6)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 6,
        timeout=3000,
    )
    for index, plot in enumerate(window.comparison_analysis_panel.plots):
        position = window.comparison_analysis_panel.histogram_layout.getItemPosition(
            window.comparison_analysis_panel.histogram_layout.indexOf(plot)
        )
        assert position[:2] == (index, 0)

    window.set_layout_mode("Single View")
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    qtbot.keyClick(window.viewer, Qt.Key.Key_Right)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[1]
    qtbot.keyClick(window.viewer, Qt.Key.Key_Left)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[0]
    qtbot.keyClick(window.viewer, Qt.Key.Key_6)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[5]
    assert window.viewer.header.text() == "[6/6] selected-6.png"
    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[0]
    window.close()


def test_auto_grid_fine_navigation_crosses_seven_image_page_boundary(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((3, 3), index, dtype=np.uint8), f"{index}.png")
        for index in range(7)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_view_capacity(4)
    assert window._layout_mode == "Multi View"
    assert window._view_capacity == 6

    for document in documents[1:6]:
        window.next_image()
        assert window._page_start == 0
        assert window._active_document_id == document.document_id

    window.next_image()
    assert window._page_start == 6
    assert window.multi_compare_view.viewers[0].document is documents[6]
    assert all(viewer.document is None for viewer in window.multi_compare_view.viewers[1:6])

    window.next_image()
    assert window._page_start == 0
    assert window._active_document_id == documents[0].document_id
    window.previous_image()
    assert window._page_start == 6
    assert window._active_document_id == documents[6].document_id
    window.close()
