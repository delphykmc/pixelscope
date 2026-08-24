from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeySequence, QPalette
from PySide6.QtWidgets import QAbstractItemView, QApplication

from pixelscope.app.application import create_application
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.image_viewer import ImageViewer

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_application_and_selection_driven_main_window(qtbot: object) -> None:
    assert isinstance(create_application([]), QApplication)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.arange(16, dtype=np.uint16).reshape(4, 4), "a")
    window.add_document(document)

    assert window.current_document is document
    assert window.viewer.document is document
    assert window.main_splitter.widget(0).minimumWidth() == 320
    assert window.document_list.selectionMode() == (
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    assert window.files_label.text() == "Files"
    assert window.analysis_tabs.count() == 2
    assert window.analysis_tabs.tabText(0) == "Statistics"
    assert window.analysis_tabs.tabText(1) == "Difference"
    assert window.bottom_tabs.count() == 2
    assert window.bottom_tabs.tabText(0) == "Histogram"
    assert window.bottom_tabs.tabText(1) == "Line Profile"
    toolbar_text = {action.text() for action in window.main_toolbar.actions()}
    assert not {"Open Image", "Open Folder", "Open RAW"}.intersection(toolbar_text)
    assert {
        "Fit Image",
        "100% Zoom",
        "Zoom In",
        "Zoom Out",
        "Diff",
        "Plots",
        "Export",
    }.issubset(toolbar_text)
    assert not {"Cursor", "ROI", "Set A", "Set B", "Swap A/B"}.intersection(toolbar_text)
    assert window.bottom_dock.isHidden()
    assert window.main_toolbar.objectName() == "mainToolbar"
    assert [action.text() for action in window.menuBar().actions()] == [
        "&File",
        "&Edit",
        "&Selection",
        "&View",
        "&Help",
    ]
    assert "Select A" not in window.action_map
    assert "Compare A/B" not in window.action_map
    assert "Compare Two Folders..." not in window.action_map
    shortcut_keys = {shortcut.key() for shortcut in window._selection_shortcuts}
    assert QKeySequence(Qt.Key.Key_PageUp) in shortcut_keys
    assert QKeySequence(Qt.Key.Key_PageDown) in shortcut_keys
    assert window.action_map["100% Zoom"].shortcut() == QKeySequence("Ctrl+0")
    view_action = next(action for action in window.menuBar().actions() if action.text() == "&View")
    view_menu = view_action.menu()
    assert view_menu is not None
    assert not any("Difference" in action.text() for action in view_menu.actions())
    assert window.action_map["Previous Selected Image"].shortcut().isEmpty()
    assert window.action_map["Next Selected Image"].shortcut().isEmpty()
    assert QKeySequence(Qt.Key.Key_Left) in shortcut_keys
    assert QKeySequence(Qt.Key.Key_Right) in shortcut_keys
    window.close()


def test_layout_tool_and_file_state_models(qtbot: object, tmp_path: Path) -> None:
    assert isinstance(create_application([]), QApplication)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((4, 5, 3), index, dtype=np.uint8),
            f"state-{index + 1}.png",
            source_path=tmp_path / f"state-{index + 1}.png",
        )
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([documents[0].document_id])

    layout_model = window.layout_selector.model()
    enabled = {
        window.layout_selector.itemText(index): layout_model.item(index).isEnabled()
        for index in range(window.layout_selector.count())
    }
    assert enabled == {
        "Auto": True,
        "Single View": True,
        "Multi View": True,
    }
    window._select_document_ids([document.document_id for document in documents[:2]])
    assert window._effective_layout(2) == ("Side by Side", 2)
    window._select_document_ids([document.document_id for document in documents])
    assert window._effective_layout(3) == ("Focus + 2", 4)
    window.set_layout_mode("Single View")
    assert window._effective_layout(3) == ("Single", 1)
    window.set_layout_mode("Multi View")
    assert window._effective_layout(3) == ("Focus + 2", 4)

    plots_action = next(
        action for action in window.main_toolbar.actions() if action.text() == "Plots"
    )
    plots_action.trigger()
    assert not window.bottom_dock.isHidden()
    assert window.bottom_tabs.currentIndex() == 0
    window._show_plot_tab(1)
    assert window.bottom_tabs.currentIndex() == 1
    plots_action.trigger()
    assert window.bottom_dock.isHidden()

    group = window.document_list.topLevelItem(0)
    child = group.child(0)
    assert group.font(0).bold()
    assert not group.icon(0).isNull()
    assert not child.icon(0).isNull()
    assert window.document_list.columnCount() == 2
    assert child.text(1) == "PNG"
    assert group.child(1).foreground(0).color().name() == "#e7e9ec"
    assert window.palette().color(QPalette.ColorRole.HighlightedText).name() == "#101316"
    window._select_document_ids([document.document_id for document in documents[:2]])
    window.compare_selection()
    assert [group.child(index).text(1) for index in range(3)] == [
        "PNG",
        "PNG",
        "PNG",
    ]
    assert group.child(0).font(0).bold()
    window.close()


def test_pending_document_keeps_previous_pixels_until_replacement_is_ready(
    qtbot: object, tmp_path: Path
) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    previous = ImageDocument.from_array(np.full((8, 9), 17, dtype=np.uint8), "previous.png")
    pending = ImageDocument.pending_document(tmp_path / "next.png")
    replacement = ImageDocument.from_array(
        np.full((8, 9), 31, dtype=np.uint8),
        "next.png",
        source_path=pending.source_path,
    )
    viewer.set_document(previous)
    previous_pixels = np.asarray(viewer.image_item.image).copy()
    viewer.set_document(pending, fit=False)
    assert viewer.document is previous
    assert viewer._loading_item.isVisible()
    assert np.array_equal(viewer.image_item.image, previous_pixels)
    viewer.set_document(replacement, fit=False)
    assert viewer.document is replacement
    assert not viewer._loading_item.isVisible()
    assert np.all(viewer.image_item.image == 31)


def test_single_to_multi_after_three_folder_selection_displays_all_images(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    selected_ids: list[str] = []
    for folder_index in range(5):
        folder = tmp_path / f"folder-{folder_index}"
        folder.mkdir()
        path = folder / "frame.png"
        assert cv2.imwrite(str(path), np.full((12, 16, 3), 30 + folder_index, dtype=np.uint8))
        window.register_folders([folder])
        selected_ids.append(window._document_id_by_path[window._path_key(path)])

    window.set_layout_mode("Single View")
    window._select_document_ids(selected_ids[:3])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.preview is not None for document in window.selected_documents),
        timeout=3000,
    )
    window.set_layout_mode("Multi View")
    window.resize(1200, 800)
    window.show()
    qtbot.wait(200)  # type: ignore[attr-defined]
    assert window.central_stack.currentWidget() is window.multi_compare_view
    occupied = window.multi_compare_view.occupied_viewers
    assert {viewer.document.document_id for viewer in occupied if viewer.document} == set(
        selected_ids[:3]
    )
    assert all(viewer.image_item.image is not None for viewer in occupied)

    for count in (4, 5):
        window._select_document_ids(selected_ids[:count])
        qtbot.wait(200)  # type: ignore[attr-defined]
        occupied = window.multi_compare_view.occupied_viewers
        assert len(occupied) == count
        for viewer in occupied:
            assert viewer.document is not None
            assert viewer.image_item.image is not None
            assert viewer.document.preview is not None
            height, width = viewer.document.preview.shape[:2]
            x_range, y_range = viewer.view_box.viewRange()
            assert x_range[0] <= width / 2.0 <= x_range[1]
            assert y_range[0] <= height / 2.0 <= y_range[1]
    window.close()


def test_reloaded_same_document_preview_is_uploaded_after_pending_clear(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.full((5, 7), 9, dtype=np.uint8), "reload.png")
    preview = document.preview
    assert preview is not None
    viewer.set_document(document)
    document.preview = None
    document.loading_state = "pending"
    viewer.set_document(document)
    assert viewer.image_item.image is None
    document.preview = preview
    document.loading_state = "ready"
    viewer.set_document(document, fit=False)
    assert viewer._displayed_preview is preview
    assert np.array_equal(viewer.image_item.image, preview)


def test_multi_view_primary_survives_arrow_key_active_navigation(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((20, 30, 3), index, dtype=np.uint8),
            f"image-{index + 1}.png",
            source_path=tmp_path / "set" / f"image-{index + 1}.png",
        )
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[2])
    assert window._focus_document_id == documents[2].document_id
    assert window.multi_compare_view.viewers[0].document is documents[2]
    assert window.multi_compare_view.viewers[0].header.badge.text() == "3"

    window.show()
    window.activateWindow()
    qtbot.wait(20)  # type: ignore[attr-defined]
    window.multi_compare_view.zoom_100_percent()
    zoom = window.multi_compare_view.viewers[0].zoom_percent
    window.multi_compare_view.viewers[0].setFocus()
    qtbot.keyClick(
        window.multi_compare_view.viewers[0],
        Qt.Key.Key_Right,
    )  # type: ignore[attr-defined]

    assert window._focus_document_id == documents[2].document_id
    assert window._active_document_id == documents[3].document_id
    assert window.multi_compare_view.viewers[0].document is documents[2]
    assert window.multi_compare_view.viewers[0].header.badge.text() == "3"
    assert window.multi_compare_view.viewers[0].zoom_percent == pytest.approx(zoom, rel=0.01)

    window.set_layout_mode("Single View")
    assert window.viewer.document is documents[3]
    assert window.viewer.header.badge.isHidden()
    assert window.viewer.header.navigation_layout.count() == 4
    assert "set / image-4.png" in window.viewer.header.name.text()
    window.close()


def test_reselecting_multi_view_is_noop_and_reference_order_pushes(
    qtbot: object, monkeypatch: object
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 10, 3), index, dtype=np.uint8), f"order-{index + 1}.png"
        )
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[2])
    window._set_focus_document(documents[3])
    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        documents[3],
        documents[2],
        documents[0],
        documents[1],
    ]

    def fail_render(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("same layout selection rebuilt the workspace")

    monkeypatch.setattr(window, "_render_selection", fail_render)  # type: ignore[attr-defined]
    window.set_layout_mode("Multi View")
    window.close()


def test_multi_selection_compare_toggle_stats_and_difference(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    a = ImageDocument.from_array(np.zeros((8, 8, 3), dtype=np.uint8), "a.png")
    b = ImageDocument.from_array(np.full((8, 8, 3), 20, dtype=np.uint8), "b.png")
    window.add_document(a)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])

    assert window.selected_documents == [a, b]
    window.compare_selection()
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.multi_compare_view.viewers[0].document is a
    assert window.multi_compare_view.viewers[1].document is b
    assert window.multi_compare_view.viewers[0].header.text() == "[1/2] a.png"
    assert window.multi_compare_view.viewers[1].header.text() == "[2/2] b.png"

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )
    table = window.comparison_analysis_panel.table
    assert table.rowCount() == 6
    assert table.columnCount() == 9
    assert table.horizontalHeaderItem(0).text() == "Id"
    assert table.horizontalHeaderItem(1).text() == "Ch"
    assert table.item(3, 0).text() == "2"
    assert table.item(3, 1).text() == "R"
    assert table.item(3, 4).text() == "20"
    assert table.item(3, 0).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert table.item(3, 1).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    summary = window.comparison_analysis_panel.image_summary
    assert summary.rowCount() == 2
    assert summary.item(1, 0).text() == "2"
    assert summary.item(1, 1).text().endswith("b.png")
    assert summary.item(1, 2).text() == "8-bit"
    assert summary.item(1, 3).text() == "64"
    assert window.comparison_analysis_panel.status.text() == ""
    assert window.comparison_analysis_panel.roi_label.text() == "x=0, y=0, width=8, height=8"
    histogram_plots = window.comparison_analysis_panel.plots[:2]
    assert all(not plot.isHidden() for plot in histogram_plots)
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(histogram_plots[0])
    )[:2] == (0, 0)
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(histogram_plots[1])
    )[:2] == (1, 0)
    for plot in histogram_plots:
        histogram_bars = plot.listDataItems()
        assert len(histogram_bars) == 3
        assert [bar.opts["pen"].color().name() for bar in histogram_bars] == [
            "#ff3b30",
            "#24b34b",
            "#2684ff",
        ]
        assert all(bar.opts["stepMode"] == "center" for bar in histogram_bars)
        assert all(bar.opts["fillLevel"] == 0.0 for bar in histogram_bars)
        assert all(bar.opts["fillBrush"] is not None for bar in histogram_bars)
    window.comparison_analysis_panel.channel_buttons["B"].setChecked(False)
    assert all(len(plot.listDataItems()) == 2 for plot in histogram_plots)

    window._shared_line_changed(LineSelection(1, 4, 6))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=3000,
    )
    profile_curves = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.PlotDataItem)
    ]
    assert len(profile_curves) == 6
    assert all(curve.opts["pen"].style() == Qt.PenStyle.SolidLine for curve in profile_curves)
    assert all(curve.opts.get("symbol") is None for curve in profile_curves)
    assert len(window.line_profile_panel.plot.listDataItems()) == 12
    profile_markers = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.ScatterPlotItem)
    ]
    assert len(profile_markers) == 6
    assert profile_markers[0].opts["brush"].color().name() == "#ff3b30"
    y_max = window.line_profile_panel.plot.getViewBox().viewRange()[1][1]
    scene_position = window.line_profile_panel.plot.getViewBox().mapViewToScene(QPointF(2, y_max))
    window.line_profile_panel._on_plot_mouse_moved(scene_position)
    assert window.line_profile_panel._hover_text is not None
    assert window.line_profile_panel._hover_text.isVisible()
    profile_hover_text = window.line_profile_panel._hover_text.toPlainText()
    assert "Distance 2 px" in profile_hover_text
    assert "a.png" not in profile_hover_text
    assert "b.png" not in profile_hover_text
    assert profile_hover_text.splitlines().count("R") == 2
    assert window.line_profile_panel._hover_text.anchor.y() == 0
    window.line_profile_panel.channel_buttons["R"].setChecked(False)
    assert (
        len(
            [
                item
                for item in window.line_profile_panel.plot.listDataItems()
                if isinstance(item, pg.PlotDataItem)
            ]
        )
        == 4
    )

    window._inspect_multi_pixel(a, 1, 2, (0, 0, 0))
    assert window.pixel_status.text().startswith("Position (   1,    2)")
    assert "1 (R   0, G   0, B   0)" in window.structured_status.pixel_value.text()
    assert "2 (R  20, G  20, B  20)" in window.structured_status.pixel_value.text()
    assert "Img" not in window.structured_status.pixel_value.text()
    assert "TYPE" not in window.structured_status.pixel_value.text()

    window.set_view_capacity(1)
    assert window.viewer.document is a
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    window.viewer.view_box.setRange(xRange=(1.0, 6.0), yRange=(1.0, 6.0), padding=0)
    original_range = window.viewer.view_box.viewRange()
    qtbot.keyClick(window.viewer, Qt.Key.Key_2)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    assert window.viewer.header.text() == "[2/2] b.png"
    assert np.allclose(window.viewer.view_box.viewRange(), original_range)
    assert window.pixel_status.text() == "Position (   -,    -)"

    window._inspect_pixel(1, 2, (20, 20, 20))
    assert window.pixel_status.text() == "Position (   1,    2)"
    assert window.structured_status.pixel_value.text() == "1 (R  20, G  20, B  20)"
    assert "TYPE" not in window.structured_status.pixel_value.text()

    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is a
    window.analysis_tabs.setCurrentWidget(window.difference_panel)
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.viewer
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )
    assert window._difference_document is not None
    assert np.all(window._difference_document.source == 20)
    assert window.analysis_tabs.currentWidget() is window.difference_panel
    assert window.difference_panel.metric_scope.text() == "Scope Full image · RGB combined"
    assert not hasattr(window.difference_panel, "plot")
    assert window._layout_mode == "Single View"
    window._navigate_single_view("difference")
    assert not window.viewer.header.navigation.isHidden()
    window._navigate_single_view(a.document_id)
    assert window.viewer.document is a
    window._navigate_single_view("difference")
    assert window.viewer.document is window._difference_document
    difference_range = window.viewer.view_box.viewRange()
    window.difference_panel.gain.setValue(3)
    assert window.viewer.document is window._difference_document
    assert np.allclose(window.viewer.view_box.viewRange(), difference_range)
    qtbot.keyClick(window.viewer, Qt.Key.Key_2)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    qtbot.keyClick(window.viewer, Qt.Key.Key_Right)  # type: ignore[attr-defined]
    assert window.viewer.document is window._difference_document
    qtbot.keyClick(window.viewer, Qt.Key.Key_Left)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    window.close()


def test_error_document_can_be_registered(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    error = ImageDocument.error_document("bad.png", "decode failed", Path("bad.png"))
    window.add_document(error)
    assert error.loading_state == "error"
    item = window.document_list.currentItem()
    assert item.text(0) == "bad.png"
    assert item.text(1) == "PNG"
    assert not item.icon(0).isNull()
    assert "Load failed" in item.toolTip(0)
    window.close()
